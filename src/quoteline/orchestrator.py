"""Research flow: plan → arms → retrieve → read → write ⇄ gates/evaluator → render → approval."""

from pathlib import Path

from quoteline.bandit import LinUCB, features
from quoteline.config import Settings
from quoteline.gates import check, injection_flags, wrap
from quoteline.harness import Runner, prompt
from quoteline.models import ARMS, Draft, Plan, Reading, Verdict
from quoteline.render import markdown, render
from quoteline.retriever import Retriever, key
from quoteline.sources.query import arxiv_ids
from quoteline.state import ArmChoice, RunState, save_state


def abstracts_block(state: RunState, ids: list[str]) -> str:
    return "\n".join(
        wrap("abstract", state.papers[i].abstract, id=i) for i in ids if i in state.papers
    )


async def run(
    state: RunState,
    settings: Settings,
    runner: Runner,
    retriever: Retriever,
    policy: LinUCB,
    runs_dir: Path,
) -> RunState:
    """Execute every step not yet in `state.completed_steps`, saving after each one."""
    trace = runner.trace
    trace.events = state.events
    runner.calls = state.llm_calls
    r = settings.research

    def done(step: str) -> None:
        state.completed_steps.append(step)
        state.llm_calls = runner.calls
        trace.emit("step_done", "system", {"step": step})
        state.events = trace.events
        save_state(state, runs_dir)

    if "plan" not in state.completed_steps:
        trace.emit(
            "injection_check", "system", {"flags": injection_flags({"question": state.question})}
        )
        state.plan = await runner.call(
            "planner",
            prompt(settings, "planner", max_subquestions=r.max_subquestions),
            wrap("question", state.question),
            Plan,
        )
        state.plan.subquestions = state.plan.subquestions[: r.max_subquestions]
        done("plan")

    if "retrieve" not in state.completed_steps:
        pairs = []
        for sq in state.plan.subquestions:
            x = features(sq.text)
            scores = policy.scores(x)
            arms = [ARMS[i] for i in policy.select(x, r.arms_per_subquestion)]
            state.choices.append(
                ArmChoice(
                    subquestion=sq.text,
                    arms=[a.name for a in arms],
                    scores={ARMS[i].name: round(float(s), 4) for i, s in enumerate(scores)},
                )
            )
            pairs += [(a, sq.text) for a in arms]
        trace.emit("arms_chosen", "policy", {"choices": [c.model_dump() for c in state.choices]})
        results = await retriever.retrieve(pairs)
        for a, t in pairs:
            papers = results[key(a, t)]
            state.retrieval[key(a, t)] = [p.id for p in papers]
            state.papers.update({p.id: p for p in papers})
        if ids := arxiv_ids(state.question):
            found = await retriever.lookup(ids)
            state.retrieval["lookup|" + ",".join(ids)] = [p.id for p in found]
            state.papers = {**{p.id: p for p in found}, **state.papers}
            trace.emit("lookup", "retrievers", {"ids": ids, "found": [p.id for p in found]})
        trace.emit("retrieved", "retrievers", {"pairs": len(pairs), "papers": len(state.papers)})
        done("retrieve")

    if "read" not in state.completed_steps:
        subqs = "\n".join(f"- {sq.text}" for sq in state.plan.subquestions)
        state.reading = await runner.call(
            "reader",
            prompt(settings, "reader"),
            f"Sub-questions:\n{subqs}\n\nAbstracts:\n{abstracts_block(state, list(state.papers))}",
            Reading,
        )
        done("read")

    while not state.rendered:
        n = len(state.drafts)
        feedback = revision_feedback(state)
        evidence = "\n".join(
            wrap("claim", f"{c.claim}\nquote: {c.quote}", paper_id=c.paper_id)
            for c in state.reading.claims
        )
        cited = list(dict.fromkeys(c.paper_id for c in state.reading.claims))
        user = (
            f"{wrap('question', state.question)}\n\nEvidence:\n{evidence}\n\n"
            f"Abstracts of cited papers:\n{abstracts_block(state, cited)}{feedback}"
        )
        draft = await runner.call("writer", prompt(settings, "writer"), user, Draft)
        state.drafts.append(draft)
        gates = check(draft, state.papers, state.question)
        state.gates.append(gates)
        trace.emit("gates", "system", {"round": n, "results": [g.model_dump() for g in gates]})
        last = n >= settings.loop.max_revisions
        if all(g.passed for g in gates):
            rendered = render(draft, state.papers)
            verdict = await runner.call(
                "evaluator",
                prompt(settings, "evaluator"),
                f"{wrap('question', state.question)}\n\n"
                f"{wrap('answer', markdown(state.question, rendered))}\n\n"
                f"Cited abstracts:\n{abstracts_block(state, [x.id for x in rendered.references])}",
                Verdict,
            )
            state.verdicts.append(verdict)
            trace.emit("verdict", "evaluator", {"round": n, **verdict.model_dump()})
            passed = min(verdict.faithfulness, verdict.coverage) >= settings.loop.pass_min_score
            if passed or last:
                state.rendered = rendered
                state.status = "AWAITING_APPROVAL" if passed else "NEEDS_REVIEW"
        elif last:
            state.rendered = render(draft, state.papers)
            state.status = "NEEDS_REVIEW"
        done(f"write_{n}")
    return state


def revision_feedback(state: RunState) -> str:
    if not state.drafts:
        return ""
    failed = [f"{g.gate}: {g.details}" for g in state.gates[-1] if not g.passed]
    issues = failed or (state.verdicts[-1].issues if state.verdicts else [])
    return "\n\nRevise your previous answer. Fix these problems:\n" + "\n".join(
        f"- {i}" for i in issues
    )


def approve(state: RunState, runs_dir: Path) -> Path:
    """Human approval: the only action — saves the rendered report to the local library."""
    assert state.rendered and state.status in ("AWAITING_APPROVAL", "NEEDS_REVIEW")
    path = runs_dir / "library" / f"{state.run_id}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown(state.question, state.rendered), encoding="utf-8")
    state.status = "APPROVED"
    save_state(state, runs_dir)
    return path
