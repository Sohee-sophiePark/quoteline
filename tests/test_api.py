from fastapi.testclient import TestClient

from quoteline import api
from quoteline.config import settings
from quoteline.render import Rendered
from quoteline.state import RunState, save_state


def test_get_and_approve_run(tmp_path, monkeypatch):
    s = settings().model_copy(update={"paths": {**settings().paths, "runs": str(tmp_path)}})
    monkeypatch.setattr(api, "settings", lambda: s)
    state = RunState(
        run_id="abc123",
        question="What is speculative decoding?",
        status="AWAITING_APPROVAL",
        rendered=Rendered(takeaway="T [1].", paragraphs=["P [1]."], references=[]),
    )
    save_state(state, tmp_path)
    client = TestClient(api.create_app())
    assert client.get("/api/runs/abc123").json()["status"] == "AWAITING_APPROVAL"
    assert client.get("/api/runs/..%2Fx").status_code == 404
    assert client.post("/api/runs/abc123/approve").json()["status"] == "APPROVED"
    assert (tmp_path / "library" / "abc123.md").exists()


def test_ask_validates_length():
    client = TestClient(api.create_app())
    assert client.post("/api/ask", json={"question": "short"}).status_code == 422
