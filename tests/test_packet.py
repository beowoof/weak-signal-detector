from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from wsf.notice import CollectionPosture, Notice, NoticeTrigger, NoticeWorkflow, save_notice
from wsf.packet import build_and_save, build_packet, resolve_clocks
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
        contributing_series=["attn.wiki_pageviews", "talk.gdelt_cameo", "talk.icews_cameo"],
        observed={
            "daily_dates": ["2022-02-10", "2022-02-11", "2022-02-12"],
            "daily_series_z": [
                {"attn.wiki_pageviews": 0.5, "talk.gdelt_cameo": 1.6, "talk.icews_cameo": 1.4},
                {"attn.wiki_pageviews": 2.1, "talk.gdelt_cameo": 2.2, "talk.icews_cameo": 0.6},
                {"attn.wiki_pageviews": 4.6, "talk.gdelt_cameo": 1.8, "talk.icews_cameo": -1.5},
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


def _write_notice(root: Path, trigger: NoticeTrigger | None = None) -> Notice:
    create_scenario(root, "desk-case")
    notice = Notice(
        notice_id="notice-abc",
        trigger=trigger or _trigger(),
        workflow=NoticeWorkflow(),
    )
    save_notice(root, notice, overwrite_trigger=True)
    return notice


def test_live_mode_refuses_stale_historical_notice() -> None:
    notice = Notice(notice_id="notice-abc", trigger=_trigger())
    with pytest.raises(ValueError, match="historical replay"):
        resolve_clocks(notice, replay=False, now=datetime(2026, 9, 3, tzinfo=UTC))


def test_replay_cutoff_is_episode_end_evening() -> None:
    notice = Notice(notice_id="notice-abc", trigger=_trigger())
    clocks = resolve_clocks(notice, replay=True, now=datetime(2026, 9, 3, tzinfo=UTC))
    assert clocks.mode == "replay"
    assert clocks.knowledge_rule == "available_at"
    assert clocks.knowledge_cutoff.date() == date(2022, 2, 12)
    assert clocks.knowledge_cutoff.hour == 23


def test_live_recent_notice_uses_now() -> None:
    trigger = _trigger(
        created_at="2026-09-03T12:00:00Z",
        start=date(2026, 9, 1),
        end=date(2026, 9, 3),
        observed={
            "daily_dates": ["2026-09-01", "2026-09-02", "2026-09-03"],
            "daily_series_z": [{"attn.wiki_pageviews": 1.0}],
        },
    )
    notice = Notice(notice_id="notice-live", trigger=trigger)
    now = datetime(2026, 9, 3, 15, 0, tzinfo=UTC)
    clocks = resolve_clocks(notice, replay=False, now=now)
    assert clocks.mode == "live"
    assert clocks.knowledge_cutoff == now
    assert clocks.knowledge_rule == "available_at_and_retrieved_at"


def test_replay_packet_writes_evidence_and_marks_notice(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _write_notice(tmp_path)
    packet, path = build_and_save(tmp_path, "desk-case", "notice-abc", replay=True)
    assert path.is_file()
    assert packet.clocks.mode == "replay"
    assert packet.collected_evidence
    assert {item.significance for item in packet.collected_evidence} == {"unassigned"}
    assert packet.counterevidence == []
    names = [item.hypothesis for item in packet.hypotheses]
    assert "routine_variation" in names
    assert "preparation_for_overt_action" in names
    assert any(
        dep["shared_information_substrate"] == "public_reporting" for dep in packet.dependencies
    )
    assert packet.layers["anomaly"] == "present"
    assert packet.layers["geopolitical_context"] in {"missing", "partial"}
    assert packet.brief
    assert any(section.id == "alert" for section in packet.brief)
    assert packet.information_environment["votes"] is False
    loaded = build_packet(tmp_path, "desk-case", "notice-abc", replay=True)
    assert loaded.packet_id == packet.packet_id
    from wsf.notice import load_notice

    notice = load_notice(tmp_path, "desk-case", "notice-abc")
    assert notice.workflow.packet_id == packet.packet_id
    assert notice.workflow.state.value == "in_packet"
    assert packet.product is not None
    assert packet.product.analytic_state == "watch"
    assert packet.product.confidence == "Low"
    assert "Watch" in packet.product.analytic_state_label
    assert "We assess it is almost certain" in packet.product.assessment[0]
    assert packet.product.does_not_support == []
    joined = " ".join(packet.product.assessment).lower()
    assert "realistic possibility" in joined
    assert "observable systems" not in joined
    assert "area of interest" not in joined
    brief_md = path.with_name("brief.md").read_text(encoding="utf-8")
    assert "## Assessment" in brief_md
    assert "## Competing explanations" in brief_md
    assert "# Evidence and provenance" in brief_md
    pdf_path = path.with_name("brief.pdf")
    assert pdf_path.is_file()
    from pypdf import PdfReader

    text = "\n".join(page.extract_text() or "" for page in PdfReader(str(pdf_path)).pages)
    assert "Assessment" in text
    assert "Watch" in text


def test_replay_excludes_observations_after_cutoff(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _write_notice(tmp_path)
    obs_dir = tmp_path / "scenarios" / "desk-case" / "corpus" / "collection-1" / "observations"
    obs_dir.mkdir(parents=True)
    (obs_dir / "wikipedia_incident.jsonl").write_text(
        "\n".join(
            [
                (
                    '{"version_id":"w:1","series_id":"attn.wiki_pageviews","period_id":"incident",'
                    '"event_time":"2022-02-10T00:00:00Z","available_at":"2022-02-11T00:00:00Z",'
                    '"retrieved_at":"2026-09-02T00:00:00Z","value":1.0,"quality":"ok","extra":"{}"}'
                ),
                (
                    '{"version_id":"w:2","series_id":"attn.wiki_pageviews","period_id":"incident",'
                    '"event_time":"2022-02-12T00:00:00Z","available_at":"2022-02-20T00:00:00Z",'
                    '"retrieved_at":"2026-09-02T00:00:00Z","value":9.0,"quality":"ok","extra":"{}"}'
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    packet = build_packet(tmp_path, "desk-case", "notice-abc", replay=True)
    assert packet.brief
    brief_text = " ".join(section.body for section in packet.brief)
    assert "9.0" not in brief_text
    wiki = [item for item in packet.collected_evidence if item.series_id == "attn.wiki_pageviews"]
    days = {item.evidence_time.date().isoformat() for item in wiki if item.evidence_time}
    assert "2022-02-10" in days
    assert "2022-02-12" not in days


def test_product_watch_for_preparatory_window(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _write_notice(tmp_path)
    packet = build_packet(tmp_path, "desk-case", "notice-abc", replay=True)
    assert packet.product.analytic_state == "watch"
    assert packet.product.change == "Broadening multi-domain anomaly"
    assert packet.product.hypotheses
    reversible = next(
        row for row in packet.product.hypotheses if row["hypothesis"] == "Reversible preparation"
    )
    assert reversible["fit"] == "Realistic possibility"
    assert "discriminate" in reversible
    artefact = next(
        row for row in packet.product.hypotheses if row["hypothesis"] == "Measurement artefact"
    )
    assert artefact["fit"] == "Unlikely"
    assert packet.product.collection
    assert packet.product.watchlist
    public = next(row for row in packet.product.watchlist if row["indicator"] == "Public reporting")
    assert "GDELT" in public["observation"] or "Wikipedia" in public["observation"]


def test_product_escalation_near_window_end(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _write_notice(tmp_path, _trigger(days_before_window_end=0))
    packet = build_packet(tmp_path, "desk-case", "notice-abc", replay=True)
    assert packet.product.analytic_state == "escalation"
    assert packet.product.analytic_state_label == "Escalation"
    overt = next(
        row
        for row in packet.product.hypotheses
        if row["hypothesis"] == "Preparation for overt action"
    )
    assert overt["fit"] == "Realistic possibility"
    routine = next(
        row for row in packet.product.hypotheses if row["hypothesis"] == "Routine variation"
    )
    assert routine["fit"] == "Unlikely"
    assert any(
        "likely that the abnormality has intensified" in para for para in packet.product.assessment
    )


def test_ukraine_preparatory_product_is_watch() -> None:
    root = Path(__file__).resolve().parents[1]
    notice_path = (
        root / "scenarios" / "ukraine2022" / "notices" / "notice-8f9869999a00" / "notice.json"
    )
    corpus = (
        root
        / "scenarios"
        / "ukraine2022"
        / "corpus"
        / "collection-20260902T172316Z-3a7030"
        / "observations"
    )
    if not notice_path.is_file() or not corpus.is_dir():
        pytest.skip("ukraine2022 pin collection is not on disk")
    packet = build_packet(root, "ukraine2022", "notice-8f9869999a00", replay=True)
    assert packet.product is not None
    assert packet.product.analytic_state == "watch"
    assert packet.product.headline.startswith("Ukraine:")
    assert packet.product.confidence == "Low"
    warnings = packet.product.availability_warnings
    assert any("VIIRS" in warning for warning in warnings)
    assert all("must not" not in warning.lower() for warning in warnings)
    observations = " ".join(row["observation"] for row in packet.product.watchlist)
    assert "3.72" in observations
    assert "RIPE prefixes" in observations
    assert (
        "FIRMS recorded one thermal detection within the monitored staging AOIs"
        in observations
    )
    assert "Yelnya" not in observations
    assert "declined from 14 to 7" in observations
    assert any("Physical posture" in row["title"] for row in packet.product.collection)
    official = next(row for row in packet.product.collection if row["title"] == "Official posture")
    assert "travel advice" in official["why"]
    assert "costly government action" in official["why"]
    joined = " ".join(packet.product.assessment)
    assert "We assess it is almost certain" in joined
    assert "Russia" in joined
    assert "Ukraine" in joined
    assert "Moscow" in joined
    assert "Yelnya" not in joined
    assert "Belgorod" not in joined
    assert packet.product.geographic_frame not in joined
    assert "realistic possibility" in joined.lower()
    assert "decision this supports is collection" in joined.lower()
    assert "must not" not in joined.lower()
    assert packet.product.keys
    assert "Russia" in packet.product.keys
    assert "Ukraine" in packet.product.keys
    assert "Ukrainian border" in packet.product.keys
    assert "Yelnya" in packet.product.keys
    assert "Belgorod" in packet.product.keys
    assert all("should not be counted" not in c.lower() for c in packet.product.caveats)


def test_ukraine_late_product_is_escalation() -> None:
    root = Path(__file__).resolve().parents[1]
    notice_path = (
        root / "scenarios" / "ukraine2022" / "notices" / "notice-184a38674e17" / "notice.json"
    )
    if not notice_path.is_file():
        pytest.skip("ukraine2022 late notice is not on disk")
    packet = build_packet(root, "ukraine2022", "notice-184a38674e17", replay=True)
    assert packet.product is not None
    assert packet.product.analytic_state == "escalation"
    observations = " ".join(row["observation"] for row in packet.product.watchlist)
    assert "within the monitored staging AOIs" in observations
    assert "Yelnya" not in observations
    joined = " ".join(packet.product.assessment)
    assert packet.product.geographic_frame not in joined
