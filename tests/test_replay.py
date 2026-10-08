from test_orchestrator import GOOD, Q, retriever, script  # noqa: F401  (fixture reuse)

from quoteline.bandit import LinUCB
from quoteline.config import settings
from quoteline.harness import Runner, Trace
from quoteline.llm.cassette import CassetteClient
from quoteline.orchestrator import run
from quoteline.state import RunState


async def test_recorded_run_replays_identically(tmp_path, retriever):  # noqa: F811
    cassette = tmp_path / "runs.jsonl"
    rec = CassetteClient(cassette, "record", script([GOOD]))
    first = await run(
        RunState(run_id="a", question=Q),
        settings(),
        Runner(settings(), rec, Trace()),
        retriever,
        LinUCB(),
        tmp_path / "runs1",
    )
    replay = CassetteClient(cassette, "replay")
    second = await run(
        RunState(run_id="a", question=Q),
        settings(),
        Runner(settings(), replay, Trace()),
        retriever,
        LinUCB(),
        tmp_path / "runs2",
    )
    assert first.rendered == second.rendered and second.status == "AWAITING_APPROVAL"
    assert {e.payload.get("source") for e in second.events if e.kind == "llm_call"} == {"cassette"}
