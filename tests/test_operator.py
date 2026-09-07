import json
import time

from fastapi.testclient import TestClient
from test_workflow import _complete_scenario

from dashboard.server import create_app


def test_plan_and_rehearsal_outputs_without_network(tmp_path):
    _complete_scenario(tmp_path)
    client = TestClient(create_app(api_only=True, project_root=tmp_path))
    body = {"scenario": "ukraine2022", "mock": True}
    preview = client.post("/api/operator/plan", json=body)
    assert preview.status_code == 200
    plan = preview.json()
    assert plan["mode"] == "Synthetic rehearsal"
    assert not list((tmp_path / "scenarios/ukraine2022/corpus").iterdir())
    response = client.post("/api/operator/run", json={**body, "revision": plan["revision"]})
    assert response.status_code == 200
    job_id = response.json()["id"]
    for _ in range(200):
        job = client.get(f"/api/operator/job/{job_id}").json()
        if job["state"] != "running":
            break
        time.sleep(0.01)
    assert job["state"] == "stopped_mock"
    assert job["result"]["stages"] == ["validate", "collect", "review"]
    assert job["result"]["review"]["review_id"]
    assert "measure" not in job["result"]


def test_stale_plan_cannot_execute_and_invalid_options_rejected(tmp_path):
    directory = _complete_scenario(tmp_path)
    client = TestClient(create_app(api_only=True, project_root=tmp_path))
    body = {"scenario": "ukraine2022", "through": "validate"}
    plan = client.post("/api/operator/plan", json=body).json()
    path = directory / "status.json"
    status = json.loads(path.read_text())
    status["active_collection_id"] = "changed"
    path.write_text(json.dumps(status))
    assert (
        client.post("/api/operator/run", json={**body, "revision": plan["revision"]}).status_code
        == 409
    )
    for changes in [
        {"start": "emit"},
        {"only": ["invalid"]},
        {"focus": "../secret"},
        {"source_workers": 100},
    ]:
        assert client.post("/api/operator/plan", json={**body, **changes}).status_code in (400, 422)
    assert client.post("/api/operator/create", json={"scenario": "../bad"}).status_code == 422
    assert client.post("/api/operator/create", json={"scenario": "new-case"}).status_code == 200
    assert client.post("/api/operator/create", json={"scenario": "new-case"}).status_code == 422


def test_receipts_survive_new_api_and_uncertain_jobs_do_not_retry(tmp_path):
    from dashboard.job_history import JobHistory

    history = JobHistory(tmp_path)
    job = history.start("build watch packet", {"scenario": "example"})
    history.call("emit notices", {"scenario": "example"}, lambda: {"n_notices": 0})
    client = TestClient(create_app(api_only=True, project_root=tmp_path))
    receipts = client.get("/api/operator/jobs").json()["jobs"]
    assert len(receipts) == 2
    assert {r["state"] for r in receipts} == {"completed", "unknown"}
    assert client.get(f"/api/operator/job/{job['id']}").json()["state"] == "unknown"
    assert client.get("/api/operator/job/not-a-job").status_code == 400


def test_failed_receipt_does_not_reuse_success_and_late_poll_cannot_regress(tmp_path):
    import pytest

    from dashboard.job_history import JobHistory

    history = JobHistory(tmp_path)
    with pytest.raises(ValueError):
        history.call(
            "emit notices",
            {"scenario": "example"},
            lambda: (_ for _ in ()).throw(ValueError("fixture failure")),
        )
    failed = history.list()[0]
    assert failed["state"] == "failed"
    assert "result" not in failed
    history.save({**failed, "state": "running"})
    assert history.read(failed["id"])["state"] == "failed"
