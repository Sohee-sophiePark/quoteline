"""Local live-mode API (127.0.0.1 only): ask a question, read a run, approve a run."""

import uuid

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from quoteline.cli import research
from quoteline.config import settings
from quoteline.orchestrator import approve
from quoteline.state import RunState, load_state, state_path


class Ask(BaseModel):
    question: str = Field(min_length=8, max_length=300)


def create_app() -> FastAPI:
    app = FastAPI(title="quoteline (local)")
    s = settings()

    @app.post("/api/ask")
    async def ask(body: Ask) -> RunState:
        state = RunState(run_id=uuid.uuid4().hex[:8], question=body.question)
        try:
            return await research(state, s)
        except Exception as e:  # surfaced to the dev console; state.json keeps completed steps
            msg = f"{type(e).__name__}: {e} (resume with run id {state.run_id})"
            raise HTTPException(502, msg) from e

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str) -> RunState:
        if not run_id.isalnum() or not state_path(s.path("runs"), run_id).exists():
            raise HTTPException(404, "unknown run")
        return load_state(s.path("runs"), run_id)

    @app.post("/api/runs/{run_id}/approve")
    def approve_run(run_id: str) -> RunState:
        state = get_run(run_id)
        approve(state, s.path("runs"))
        return state

    return app
