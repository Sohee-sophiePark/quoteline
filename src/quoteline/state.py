"""RunState with atomic save/load; completed steps make a stopped run resumable."""

import datetime as dt
import os
from pathlib import Path

from pydantic import BaseModel, Field

from quoteline.harness import Event
from quoteline.models import Draft, GateResult, Paper, Plan, Reading, Verdict
from quoteline.render import Rendered


def _now() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="seconds")


class ArmChoice(BaseModel):
    subquestion: str
    arms: list[str]
    scores: dict[str, float]


class RunState(BaseModel):
    run_id: str
    question: str
    status: str = "CREATED"  # → AWAITING_APPROVAL | NEEDS_REVIEW | APPROVED | FAILED
    plan: Plan | None = None
    choices: list[ArmChoice] = []
    retrieval: dict[str, list[str]] = {}  # "arm|query" → paper IDs
    papers: dict[str, Paper] = {}
    reading: Reading | None = None
    drafts: list[Draft] = []
    gates: list[list[GateResult]] = []
    verdicts: list[Verdict] = []
    rendered: Rendered | None = None
    events: list[Event] = []
    completed_steps: list[str] = []
    llm_calls: int = 0
    error: str | None = None
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


def state_path(runs_dir: Path, run_id: str) -> Path:
    return runs_dir / run_id / "state.json"


def save_state(state: RunState, runs_dir: Path) -> Path:
    state.updated_at = _now()
    path = state_path(runs_dir, state.run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(state.model_dump_json(indent=1), encoding="utf-8")
    os.replace(tmp, path)
    return path


def load_state(runs_dir: Path, run_id: str) -> RunState:
    return RunState.model_validate_json(state_path(runs_dir, run_id).read_text(encoding="utf-8"))
