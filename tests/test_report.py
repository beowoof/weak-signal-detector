from datetime import date
from pathlib import Path

from wsf.notice import CollectionPosture, Notice, NoticeTrigger, NoticeWorkflow, save_notice
from wsf.packet import build_and_save
from wsf.report import load_report, save_report
from wsf.scenario import create_scenario


def _write_notice(root: Path) -> Notice:
    create_scenario(root, "desk-case")
    notice = Notice(
        notice_id="notice-abc",
        trigger=NoticeTrigger.model_validate(
            {
                "scenario_id": "desk-case",
                "window_id": "incident",
                "collection_id": "collection-1",
                "measurement_id": "measure-1",
                "policy_id": "coupling_k3_z15_p3",
                "policy_params": {"threshold_z": 1.5},
                "created_at": "2026-09-03T00:00:00Z",
                "start": date(2022, 2, 10),
                "end": date(2022, 2, 12),
                "duration_days": 3,
                "days_before_window_end": 11,
                "contributing_domains": ["information"],
                "contributing_series": ["talk.gdelt_cameo"],
                "observed": {"daily_dates": ["2022-02-10"]},
                "derived": {},
                "heuristic": {},
                "unknowns": [],
                "imaging_status_by_day": {},
                "recommended_posture": CollectionPosture.focused,
                "recommended_posture_reason": "chorus_with_physical_available",
            }
        ),
        workflow=NoticeWorkflow(),
    )
    save_notice(root, notice, overwrite_trigger=True)
    return notice


def test_report_template_is_empty_and_save_roundtrips(tmp_path: Path) -> None:
    _write_notice(tmp_path)
    build_and_save(tmp_path, "desk-case", "notice-abc", replay=True)
    blank = load_report(tmp_path, "desk-case", "notice-abc")
    assert blank["empty"] is True
    assert "## Working assessment" in blank["notes"]
    assert "[What do you make of this cue?" in blank["notes"]
    assert "Decision" in blank["notes"]
    saved = save_report(
        tmp_path,
        "desk-case",
        "notice-abc",
        notes="Abnormal activity is real; explanation unresolved.\n\nCollect physical posture.",
    )
    assert saved["empty"] is False
    assert saved["notes"].startswith("Abnormal activity is real")
    path = tmp_path / "scenarios" / "desk-case" / "reports" / saved["report_id"] / "report.md"
    text = path.read_text(encoding="utf-8")
    assert "Abnormal activity is real" in text
    assert "Collect physical posture" in text
    reloaded = load_report(tmp_path, "desk-case", "notice-abc")
    assert "Collect physical posture" in reloaded["notes"]
