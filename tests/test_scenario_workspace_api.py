import json

from fastapi.testclient import TestClient

from dashboard.server import create_app
from wsf.scenario import create_scenario


def workspace(tmp_path):
    directory = create_scenario(tmp_path, "example")
    client = TestClient(create_app(api_only=True, project_root=tmp_path))
    return directory, client


def test_scenarios_without_measurements_are_discoverable(tmp_path):
    _, client = workspace(tmp_path)
    assert client.get("/api/scenarios").json()["scenarios"][0]["scenario_id"] == "example"


def test_save_validates_preserves_extra_fields_and_rejects_stale_revision(tmp_path):
    directory, client = workspace(tmp_path)
    original = client.get("/api/scenario", params={"scenario": "example"}).json()
    status = (directory / "status.json").read_bytes()
    document = json.loads(original["text"])
    document["research_question"] = "A new question"
    document["future_extension"] = {"keep": True}
    body = {"scenario": "example", "revision": original["revision"], "text": json.dumps(document)}
    validated = client.post("/api/scenario/validate", json=body)
    assert validated.status_code == 200
    assert validated.json()["warnings"]  # A valid draft need not be collection-ready.
    assert (directory / "scenario.json").read_text() == original["text"]
    saved = client.post("/api/scenario/save", json=body)
    assert saved.status_code == 200
    assert json.loads(saved.json()["text"])["future_extension"] == {"keep": True}
    assert client.post("/api/scenario/save", json=body).status_code == 409
    assert (directory / "status.json").read_bytes() == status
    assert not list((directory / "corpus").iterdir())


def test_invalid_contracts_do_not_write(tmp_path):
    directory, client = workspace(tmp_path)
    original = (directory / "scenario.json").read_text()
    document = json.loads(original)
    document["incident"].update(start="2022-02-05", end="2022-02-01")
    for text in ['{"scenario_id":', '{"x":1,"x":2}', '{"x":NaN}', json.dumps(document)]:
        response = client.post("/api/scenario/save", json={"scenario": "example", "text": text})
        assert response.status_code == 422
        assert (directory / "scenario.json").read_text() == original
    document = json.loads(original)
    document["scenario_id"] = "different"
    assert (
        client.post(
            "/api/scenario/validate", json={"scenario": "example", "text": json.dumps(document)}
        ).status_code
        == 422
    )


def test_frozen_contract_is_read_only(tmp_path):
    directory, client = workspace(tmp_path)
    (directory / "freeze.json").write_text("{}")
    original = client.get("/api/scenario", params={"scenario": "example"}).json()
    assert original["frozen"]
    response = client.post(
        "/api/scenario/save",
        json={"scenario": "example", "text": original["text"], "revision": original["revision"]},
    )
    assert response.status_code == 409


def test_artifacts_inventory_preview_paging_and_download(tmp_path):
    directory, client = workspace(tmp_path)
    run = directory / "reviews" / "review-1"
    run.mkdir()
    gaps = {"critical_gaps": [], "warning_gaps": [{"source": "viirs", "reason": "cloud"}]}
    (run / "missing.json").write_text(json.dumps(gaps))
    (run / "rows.jsonl").write_text('{"value":0}\n{"value":null}\nnot json\n')
    args = {"scenario": "example", "path": "reviews/review-1/missing.json"}
    listing = client.get("/api/scenario/artifacts", params={"scenario": "example"}).json()
    assert any(item["name"] == "missing.json" for item in listing["artifacts"])
    assert client.get("/api/scenario/artifact", params=args).json()["data"] == gaps
    assert client.get("/api/scenario/artifact/download", params=args).json() == gaps
    args["path"] = "reviews/review-1/rows.jsonl"
    page = client.get("/api/scenario/artifact", params={**args, "limit": 2}).json()
    assert page["records"] == [{"value": 0}, {"value": None}]
    assert page["next_offset"] == 2
    final = client.get("/api/scenario/artifact", params={**args, "offset": 2}).json()
    assert final["records"][0]["parse_error"]
    assert final["next_offset"] is None


def test_preview_bounds_and_path_confinement(tmp_path):
    directory, client = workspace(tmp_path)
    outside = tmp_path / "private.json"
    outside.write_text('{"private":true}')
    (directory / "reviews" / "linked.json").symlink_to(outside)
    (directory / "reviews" / "large.json").write_text('"' + "a" * 1_000_001 + '"')
    for path in [
        "../private.json",
        "/etc/passwd",
        "reviews/../../private.json",
        "reviews/linked.json",
        "scenario.json",
    ]:
        assert client.get(
            "/api/scenario/artifact", params={"scenario": "example", "path": path}
        ).status_code in {400, 404}
    response = client.get(
        "/api/scenario/artifact", params={"scenario": "example", "path": "reviews/large.json"}
    )
    assert response.json()["truncated"]
    assert "data" not in response.json()
    assert client.get("/api/scenario", params={"scenario": "../outside"}).status_code == 400
    assert (
        client.get(
            "/api/scenario/artifact",
            params={"scenario": "example", "path": "status.json", "offset": -1},
        ).status_code
        == 422
    )


def test_scenario_symlink_is_not_editable(tmp_path):
    directory, client = workspace(tmp_path)
    original = (directory / "scenario.json").read_text()
    (directory / "scenario.json").unlink()
    target = tmp_path / "contract.json"
    target.write_text(original)
    (directory / "scenario.json").symlink_to(target)
    assert client.get("/api/scenario", params={"scenario": "example"}).status_code == 400
    assert target.read_text() == original
