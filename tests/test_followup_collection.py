import json
import time

from fastapi.testclient import TestClient
from test_draft import _notice

from dashboard.server import create_app
from wsf.packet import Packet, packet_directory, packet_path
from wsf.research import ResearchLimits, research_plan


def test_followup_is_pinned_bounded_and_never_applied_to_assessment(tmp_path, monkeypatch):
    _notice(tmp_path)
    path = packet_directory(tmp_path, "desk-case", "packet-test") / "machine_draft.json"
    path.write_text(
        json.dumps(
            {
                "review": {
                    "claims": [],
                    "hypothesis_updates": [
                        {"hypothesis": "routine", "discriminators": ["Was the exercise announced?"]}
                    ],
                }
            }
        )
    )
    received = {}

    def run(root, scenario, notice, **kwargs):
        received.update(kwargs)
        return {"review": {"claims": []}, "notes": "Fixture only"}

    monkeypatch.setattr("dashboard.followup_collection.run_desk_draft", run)
    client = TestClient(create_app(api_only=True, project_root=tmp_path))
    opts = client.get(
        "/api/followup/options", params={"scenario": "desk-case", "notice_id": "notice-abc"}
    ).json()
    body = {
        "scenario": "desk-case",
        "notice_id": "notice-abc",
        "review_version": opts["review_version"],
        "question_id": opts["questions"][0]["id"],
    }
    assert (
        client.post("/api/followup/run", json={**body, "review_version": "old"}).status_code == 409
    )
    assert not received
    assert client.post("/api/followup/run", json={**body, "queries": 100}).status_code == 422
    response = client.post("/api/followup/run", json=body)
    assert response.status_code == 200
    for _ in range(100):
        job = client.get("/api/operator/job/" + response.json()["id"]).json()
        if job["state"] != "running":
            break
        time.sleep(0.01)
    assert job["state"] == "completed"
    assert received["apply"] is False
    assert received["followup"]["question"] == "Was the exercise announced?"
    assert received["followup"]["packet_id"] == "packet-test"
    packet = Packet.model_validate_json(
        packet_path(tmp_path, "desk-case", "packet-test").read_text()
    )
    plan = research_plan(packet, ResearchLimits(), received["followup"])
    assert len(plan) == 1
    assert "Was the exercise announced?" in plan[0]["query"]
    assert "counterevidence" in plan[0]["fallback_query"]
    assert job["inputs"]["requirement"]["review_version"] == opts["review_version"]
