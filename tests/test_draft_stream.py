import io
import json
import threading

import pytest
from fastapi.testclient import TestClient

from dashboard import server
from dashboard.draft_stream import draft_events
from wsf.progress import DraftProgress


def test_stages_and_heartbeats_arrive_before_generation_finishes():
    release = threading.Event()

    def run(*, progress):
        progress("Ollama generating", 2)
        assert release.wait(5)
        return {"notes": "finished"}

    stream = draft_events(run, heartbeat=0.01)
    try:
        start = json.loads(next(stream))
        stage = json.loads(next(stream))
        pulse = json.loads(next(stream))
        assert start["job_id"] == stage["job_id"] == pulse["job_id"]
        assert stage["stage"] == pulse["stage"] == "Ollama generating"
        assert stage["completed"] == 2
    finally:
        release.set()
    result = json.loads(next(stream))
    assert result["type"] == "result"
    assert result["result"] == {"notes": "finished"}
    assert list(stream) == []


@pytest.mark.parametrize(
    "error,status",
    [(ValueError("bad model"), 400), (KeyError("notice"), 404), (RuntimeError("private"), 500)],
)
def test_stream_errors_are_terminal(error, status):
    def run(*, progress):
        raise error

    events = [json.loads(line) for line in draft_events(run)]
    assert events[-1]["type"] == "error"
    assert events[-1]["status"] == status
    assert "private" not in events[-1]["detail"]


def test_existing_json_endpoint_is_unchanged(tmp_path, monkeypatch):
    def run(*args, **kwargs):
        assert "progress" not in kwargs
        return {"notes": "existing UI contract"}

    monkeypatch.setattr(server, "run_desk_draft", run)
    client = TestClient(server.create_app(api_only=True, project_root=tmp_path))
    response = client.post("/api/packet/draft", json={"scenario": "case", "notice_id": "notice"})
    assert response.status_code == 200
    assert response.json() == {"notes": "existing UI contract"}


def test_user_research_limits_reach_worker_and_invalid_limits_fail(tmp_path, monkeypatch):
    def run(*args, **kwargs):
        assert kwargs["research_limits"].documents == 24
        assert kwargs["research_limits"].seconds == 300
        return {"notes": "done"}

    monkeypatch.setattr(server, "run_desk_draft", run)
    client = TestClient(server.create_app(api_only=True, project_root=tmp_path))
    body = {
        "scenario": "case",
        "notice_id": "notice",
        "research_limits": {"queries": 6, "documents": 24, "seconds": 300},
    }
    assert client.post("/api/packet/draft", json=body).status_code == 200
    body["research_limits"]["seconds"] = 3600
    assert client.post("/api/packet/draft", json=body).status_code == 422


def test_non_terminal_progress_is_readable_and_throttled():
    output = io.StringIO()
    progress = DraftProgress(stream=output)
    for elapsed in (0, 2, 30):
        progress.update(
            {
                "job_id": "Job-test",
                "stage": "Ollama generating",
                "completed": 2,
                "elapsed_s": elapsed,
            }
        )
    progress.close()
    lines = output.getvalue().splitlines()
    assert len(lines) == 2
    assert "2/5 stages" in lines[0]
    assert "%" not in output.getvalue()
    assert "\033" not in output.getvalue()
