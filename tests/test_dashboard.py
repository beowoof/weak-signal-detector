import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dashboard.server import create_app, discover_results, load_result, result_index


def write_result(root: Path, scenario_id: str, measure_id: str) -> None:
    scenario_dir = root / scenario_id
    result_dir = scenario_dir / "measurement" / measure_id
    result_dir.mkdir(parents=True)
    (scenario_dir / "scenario.json").write_text(
        json.dumps(
            {
                "scenario_id": scenario_id,
                "purpose": "test",
                "incident": {"id": "incident", "start": "2020-01-01", "end": "2020-01-02"},
            }
        ),
        encoding="utf-8",
    )
    (result_dir / "summary.json").write_text(
        json.dumps(
            {
                "measure_id": measure_id,
                "n_feature_rows": 1,
                "protocol_id": "coincidence_test",
            }
        ),
        encoding="utf-8",
    )
    (result_dir / "features.jsonl").write_text(
        json.dumps(
            {
                "event_day": "2020-01-01",
                "series_id": "test.series",
                "window_id": "incident",
                "raw": 3.0,
                "z": 1.5,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (result_dir / "days.jsonl").write_text(
        json.dumps({"day": "2020-01-01", "window_id": "incident", "verdict": "quiet"}) + "\n",
        encoding="utf-8",
    )


def test_discover_index_and_load_result(tmp_path: Path) -> None:
    write_result(tmp_path, "scenario-a", "measure-002")
    write_result(tmp_path, "scenario-a", "measure-001")

    refs = discover_results(tmp_path)
    assert [item.key for item in refs] == [
        "scenario-a/measure-002",
        "scenario-a/measure-001",
    ]

    index = result_index(tmp_path)
    assert len(index["results"]) == 2
    assert index["results"][0]["measurement_mode"] == "legacy_unspecified"
    assert index["scenarios"]["scenario-a"]["purpose"] == "test"

    result = load_result("scenario-a/measure-002", tmp_path)
    assert result["summary"]["protocol_id"] == "coincidence_test"
    assert result["features"][0]["z"] == 1.5
    assert result["days"][0]["verdict"] == "quiet"
    assert "coupling" in result
    assert "notices" in result
    assert result["notices"] == []


def test_load_result_rejects_unknown_key(tmp_path: Path) -> None:
    with pytest.raises(KeyError):
        load_result("../../outside", tmp_path)


def test_api_results_and_result(tmp_path: Path) -> None:
    write_result(tmp_path, "scenario-a", "measure-002")
    write_result(tmp_path, "scenario-a", "measure-001")
    client = TestClient(create_app(api_only=True, scenarios_root=tmp_path))

    catalog = client.get("/api/results")
    assert catalog.status_code == 200
    body = catalog.json()
    assert [item["key"] for item in body["results"]] == [
        "scenario-a/measure-002",
        "scenario-a/measure-001",
    ]
    assert body["scenarios"]["scenario-a"]["purpose"] == "test"

    loaded = client.get("/api/result", params={"key": "scenario-a/measure-002"})
    assert loaded.status_code == 200
    payload = loaded.json()
    assert payload["summary"]["protocol_id"] == "coincidence_test"
    assert payload["features"][0]["z"] == 1.5
    assert payload["notices"] == []
    assert "coupling" in payload


def test_api_unknown_key_is_404(tmp_path: Path) -> None:
    client = TestClient(create_app(api_only=True, scenarios_root=tmp_path))
    response = client.get("/api/result", params={"key": "nope/nope"})
    assert response.status_code == 404
    assert response.json()["detail"] == "Unknown result set"


def test_api_only_does_not_serve_ui(tmp_path: Path) -> None:
    client = TestClient(create_app(api_only=True, scenarios_root=tmp_path))
    assert client.get("/").status_code == 404


def test_full_app_serves_index(tmp_path: Path) -> None:
    client = TestClient(create_app(api_only=False, scenarios_root=tmp_path))
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")


def test_api_cors_allows_vite_origin(tmp_path: Path) -> None:
    client = TestClient(create_app(api_only=True, scenarios_root=tmp_path))
    response = client.get("/api/results", headers={"Origin": "http://127.0.0.1:5173"})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "*"


def test_api_notices_index_and_get(tmp_path: Path) -> None:
    write_result(tmp_path, "scenario-a", "measure-002")
    notice_dir = tmp_path / "scenario-a" / "notices" / "notice-abc"
    notice_dir.mkdir(parents=True)
    (notice_dir / "notice.json").write_text(
        json.dumps(
            {
                "schema_id": "notice_v0",
                "notice_id": "notice-abc",
                "trigger": {
                    "scenario_id": "scenario-a",
                    "collection_id": "collection-1",
                    "measurement_id": "measure-002",
                    "window_id": "incident",
                    "policy_id": "coupling_k3_z15_p3",
                    "policy_params": {},
                    "created_at": "2026-09-03T00:00:00Z",
                    "start": "2022-02-10",
                    "end": "2022-02-12",
                    "duration_days": 3,
                    "days_before_window_end": 11,
                    "contributing_domains": ["information"],
                    "contributing_series": ["talk.gdelt_cameo"],
                    "observed": {},
                    "derived": {},
                    "heuristic": {},
                    "unknowns": [],
                    "imaging_status_by_day": {},
                    "recommended_posture": "focused",
                    "recommended_posture_reason": "chorus_with_physical_available",
                },
                "workflow": {"state": "new"},
            }
        ),
        encoding="utf-8",
    )
    client = TestClient(create_app(api_only=True, scenarios_root=tmp_path, project_root=tmp_path))
    listed = client.get("/api/notices")
    assert listed.status_code == 200
    body = listed.json()
    assert len(body["notices"]) == 1
    assert body["notices"][0]["notice_id"] == "notice-abc"
    assert body["notices"][0]["key"] == "scenario-a/measure-002"

    loaded = client.get("/api/notice", params={"scenario": "scenario-a", "notice_id": "notice-abc"})
    assert loaded.status_code == 200
    assert loaded.json()["trigger"]["window_id"] == "incident"

    missing = client.get("/api/notice", params={"scenario": "scenario-a", "notice_id": "nope"})
    assert missing.status_code == 404

    acted = client.post(
        "/api/notice/action",
        json={"scenario": "scenario-a", "notice_id": "notice-abc", "action": "ack"},
    )
    assert acted.status_code == 200
    assert acted.json()["workflow"]["state"] == "acked"

    missing_emit = client.post(
        "/api/notice/emit",
        json={"scenario": "missing-scenario", "measurement_id": "measure-002"},
    )
    assert missing_emit.status_code == 400

    missing_packet = client.post(
        "/api/packet/build",
        json={"scenario": "scenario-a", "notice_id": "nope", "replay": True},
    )
    assert missing_packet.status_code in {400, 404}


def test_api_health_without_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    client = TestClient(create_app(api_only=True, scenarios_root=tmp_path))
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["db"] == {"configured": False, "ok": True, "error": None}
    assert body["agent"] is None
