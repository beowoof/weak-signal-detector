from datetime import date
from pathlib import Path

from wsf.collect import CHRONOLOGY, OFFICIAL, PHYSICAL, VALIDATE, load_collection, run_collection
from wsf.notice import (
    CollectionPosture,
    Notice,
    NoticeState,
    NoticeTrigger,
    NoticeWorkflow,
    save_notice,
)
from wsf.scenario import create_scenario


def _trigger(**overrides) -> NoticeTrigger:
    payload = dict(
        scenario_id="desk-case",
        window_id="incident",
        collection_id="collection-1",
        measurement_id="measure-1",
        policy_id="coupling_k3_z15_p3",
        policy_params={"threshold_z": 1.5},
        created_at="2026-09-03T00:00:00Z",
        start=date(2022, 2, 10),
        end=date(2022, 2, 12),
        duration_days=3,
        days_before_window_end=11,
        contributing_domains=["information", "public_attention", "digital_infrastructure"],
        contributing_series=["attn.wiki_pageviews", "talk.gdelt_cameo", "net.ripe_prefixes"],
        observed={
            "daily_dates": ["2022-02-10", "2022-02-11", "2022-02-12"],
            "daily_series_z": [
                {"attn.wiki_pageviews": 0.5, "talk.gdelt_cameo": 1.6, "net.ripe_prefixes": 3.1},
                {"attn.wiki_pageviews": 2.1, "talk.gdelt_cameo": 2.2, "net.ripe_prefixes": 2.9},
                {"attn.wiki_pageviews": 4.6, "talk.gdelt_cameo": 1.8, "net.ripe_prefixes": 2.8},
            ],
        },
        derived={"max_energy": 10.0},
        heuristic={"policy_id": "coupling_k3_z15_p3", "kind": "quantitative_convergence"},
        unknowns=[],
        imaging_status_by_day={
            "2022-02-10": "normal",
            "2022-02-11": "normal",
            "2022-02-12": "normal",
        },
        recommended_posture=CollectionPosture.focused,
        recommended_posture_reason="chorus_with_physical_available",
    )
    payload.update(overrides)
    return NoticeTrigger.model_validate(payload)


def _write_notice(root: Path) -> Notice:
    create_scenario(root, "desk-case")
    notice = Notice(
        notice_id="notice-abc",
        trigger=_trigger(),
        workflow=NoticeWorkflow(),
    )
    save_notice(root, notice, overwrite_trigger=True)
    return notice


def _obs(series_id: str, day: str, value: float, *, available: str | None = None) -> str:
    available = available or f"{day}T23:59:59Z"
    return (
        f'{{"version_id":"{series_id}:{day}","series_id":"{series_id}","period_id":"incident",'
        f'"event_time":"{day}T00:00:00Z","available_at":"{available}",'
        f'"retrieved_at":"2026-09-02T00:00:00Z","value":{value},"quality":"ok","extra":"{{}}"}}'
    )


def test_validate_and_harvest_write_into_packet(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _write_notice(tmp_path)
    obs_dir = tmp_path / "scenarios" / "desk-case" / "corpus" / "collection-1" / "observations"
    obs_dir.mkdir(parents=True)
    (obs_dir / "gdelt_incident.jsonl").write_text(
        "\n".join(
            [
                _obs("talk.gdelt_cameo", "2022-01-20", 800),
                _obs("talk.gdelt_cameo", "2022-02-10", 1680),
                _obs("nav.spatial_warnings", "2022-02-01", 14),
                _obs("nav.spatial_warnings", "2022-02-10", 7),
                _obs("tempo.firms_thermal", "2022-02-10", 0),
                _obs("tempo.firms_thermal", "2022-02-12", 1),
                _obs(
                    "tempo.viirs_aoi",
                    "2022-02-10",
                    3.4,
                    available="2022-02-13T00:00:00Z",
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "wsf.collect._fetch_declared",
        lambda *args, **kwargs: ([], ["declared posture skipped in unit test"], None),
    )
    payload = run_collection(
        tmp_path,
        "desk-case",
        "notice-abc",
        kinds=[VALIDATE, CHRONOLOGY, PHYSICAL, OFFICIAL],
        replay=True,
        request_context=True,
    )
    assert payload["state"] == NoticeState.context_requested.value
    assert payload["selected_posture"] == "focused"
    kinds = {task["kind"]: task for task in payload["tasks"]}
    assert kinds[VALIDATE]["status"] == "complete"
    assert any("share" in item["text"] for item in kinds[VALIDATE]["items"])
    assert kinds[CHRONOLOGY]["status"] == "complete"
    assert kinds[CHRONOLOGY]["items"]
    assert kinds[CHRONOLOGY]["analyst_question"].startswith("Abnormal relative")
    assert kinds[PHYSICAL]["status"] == "complete"
    viirs = [item for item in kinds[PHYSICAL]["items"] if item["label"] == "VIIRS"]
    assert viirs
    assert viirs[0]["knowable"] is False
    assert kinds[OFFICIAL]["status"] == "complete"
    stored = load_collection(tmp_path, "desk-case", payload["packet_id"])
    assert len(stored["tasks"]) == 4


def test_request_context_does_not_jump_to_surge(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _write_notice(tmp_path)
    payload = run_collection(
        tmp_path,
        "desk-case",
        "notice-abc",
        kinds=[VALIDATE],
        replay=True,
        request_context=True,
    )
    assert payload["selected_posture"] == CollectionPosture.focused.value
