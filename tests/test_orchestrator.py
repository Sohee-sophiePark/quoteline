import json

import pytest

from quoteline.bandit import LinUCB
from quoteline.config import settings
from quoteline.harness import Runner, Trace
from quoteline.llm.scripted import ScriptedClient
from quoteline.models import ARMS
from quoteline.orchestrator import approve, run
from quoteline.retriever import Retriever, key
from quoteline.state import RunState, load_state

Q = "How does speculative decoding speed up LLM inference?"
SUBQ = "How does speculative decoding work?"
PAPER = {
    "id": "2211.17192",
    "title": "Fast Inference from Transformers via Speculative Decoding",
    "authors": ["Yaniv Leviathan", "Matan Kalman"],
    "published": "2022-11-30",
    "abstract": "We introduce speculative decoding - an algorithm to sample from autoregressive "
    "models faster without any changes to the outputs.",
    "sources": ["arxiv"],
}
GOOD = {
    "takeaway": "Drafting with a small model speeds decoding without changing outputs "
    "{{p:2211.17192}}.",
    "paragraphs": ["A small model drafts tokens that the large model verifies {{p:2211.17192}}."],
    "papers": [
        {"paper_id": "2211.17192", "contribution_quote": "We introduce speculative decoding"}
    ],
}
BAD = {**GOOD, "paragraphs": ["This sentence has no citation."]}


@pytest.fixture
def retriever(tmp_path):
    path = tmp_path / "retrieval.jsonl"
    with path.open("w") as f:
        for arm in ARMS[:2]:  # untrained LinUCB picks the first two arms
            f.write(json.dumps({"key": key(arm, SUBQ), "papers": [PAPER]}) + "\n")
    return Retriever("replay", path)


def script(drafts, verdict=None, fail_on_writer=False):
    drafts = list(drafts)

    def respond(req):
        if req.purpose == "planner":
            return {"subquestions": [{"text": SUBQ}]}
        if req.purpose == "reader":
            assert "<untrusted" in req.user and "2211.17192" in req.user
            return {
                "claims": [
                    {
                        "paper_id": "2211.17192",
                        "quote": "sample from autoregressive models faster",
                        "claim": "It speeds up sampling.",
                    }
                ]
            }
        if req.purpose == "writer":
            if fail_on_writer:
                raise RuntimeError("quota")
            return drafts.pop(0)
        return verdict or {"faithfulness": 5, "coverage": 4, "issues": []}

    return ScriptedClient(respond)


async def go(state, client, retriever, runs):
    runner = Runner(settings(), client, Trace())
    return await run(state, settings(), runner, retriever, LinUCB(), runs)


async def test_happy_path_awaits_approval(tmp_path, retriever):
    client = script([GOOD])
    s = await go(RunState(run_id="r1", question=Q), client, retriever, tmp_path)
    assert s.status == "AWAITING_APPROVAL" and s.llm_calls == 4
    assert [c.purpose for c in client.calls] == ["planner", "reader", "writer", "evaluator"]
    assert s.choices[0].arms == ["arxiv:keyword", "arxiv:conceptual"]
    assert all(g.passed for g in s.gates[0])
    assert s.rendered.references[0].authors == "Yaniv Leviathan et al."
    assert load_state(tmp_path, "r1").status == "AWAITING_APPROVAL"
    path = approve(s, tmp_path)
    assert "arXiv:2211.17192" in path.read_text() and s.status == "APPROVED"


async def test_gate_failure_triggers_revision_without_evaluator(tmp_path, retriever):
    client = script([BAD, GOOD])
    s = await go(RunState(run_id="r2", question=Q), client, retriever, tmp_path)
    purposes = [c.purpose for c in client.calls]
    assert purposes == ["planner", "reader", "writer", "writer", "evaluator"]
    assert "G3 every sentence cited" in client.calls[3].user
    assert s.status == "AWAITING_APPROVAL" and len(s.drafts) == 2


async def test_low_verdict_ends_in_needs_review_after_max_revisions(tmp_path, retriever):
    low = {"faithfulness": 2, "coverage": 5, "issues": ["Overclaims speedup."]}
    client = script([GOOD, GOOD, GOOD], verdict=low)
    s = await go(RunState(run_id="r3", question=Q), client, retriever, tmp_path)
    assert s.status == "NEEDS_REVIEW" and len(s.drafts) == 3 and len(s.verdicts) == 3
    assert "Overclaims speedup." in client.calls[4].user


async def test_resume_skips_completed_steps(tmp_path, retriever):
    with pytest.raises(RuntimeError):
        await go(
            RunState(run_id="r4", question=Q), script([], fail_on_writer=True), retriever, tmp_path
        )
    saved = load_state(tmp_path, "r4")
    assert saved.completed_steps == ["plan", "retrieve", "read"] and saved.llm_calls == 2
    client = script([GOOD])
    s = await go(saved, client, retriever, tmp_path)
    assert [c.purpose for c in client.calls] == ["writer", "evaluator"]
    assert s.status == "AWAITING_APPROVAL" and s.llm_calls == 4
