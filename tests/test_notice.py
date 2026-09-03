from datetime import date
from pathlib import Path

import pytest

from wsf.notice import (
    CollectionPosture,
    Notice,
    NoticeAction,
    NoticeState,
    NoticeTrigger,
    NoticeWorkflow,
    apply_action,
    list_notices,
    notice_id_for,
    save_notice,
)
from wsf.scenario import create_scenario


def _trigger(**overrides) -> NoticeTrigger:
    payload = dict(
        scenario_id="fixture",
        window_id="incident",
        collection_id="collection-1",
        measurement_id="measure-1",
        policy_id="coupling_k3_z15_p3",
        policy_params={"threshold_z": 1.5, "min_domains": 3, "persistence_days": 3},
        created_at="2026-09-03T00:00:00Z",
        start=date(2022, 2, 10),
        end=date(2022, 2, 12),
        duration_days=3,
        days_before_window_end=11,
        contributing_domains=["information", "market", "public_attention"],
        contributing_series=["attn.wiki_pageviews", "talk.gdelt_cameo"],
        observed={},
        derived={"max_energy": 10.0},
        heuristic={"policy_id": "coupling_k3_z15_p3"},
        unknowns=[],
        imaging_status_by_day={"2022-02-10": "normal"},
        recommended_posture=CollectionPosture.focused,
        recommended_posture_reason="chorus_with_physical_available",
    )
    payload.update(overrides)
    return NoticeTrigger.model_validate(payload)


def test_notice_id_is_stable_for_the_same_trigger() -> None:
    first = notice_id_for(_trigger())
    later = _trigger(created_at="2026-09-04T00:00:00Z", derived={"max_energy": 99.0})
    second = notice_id_for(later)
    assert first == second
    assert first.startswith("notice-")


def test_save_notice_does_not_rewrite_trigger(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    create_scenario(tmp_path, "desk-case")
    original = Notice(
        notice_id="notice-abc",
        trigger=_trigger(scenario_id="desk-case"),
        workflow=NoticeWorkflow(),
    )
    save_notice(tmp_path, original, overwrite_trigger=True)
    mutated = Notice(
        notice_id="notice-abc",
        trigger=_trigger(scenario_id="desk-case", derived={"max_energy": 1.0}),
        workflow=NoticeWorkflow(state=NoticeState.acked, closure_rationale=None),
    )
    save_notice(tmp_path, mutated, overwrite_trigger=False)
    loaded = list_notices(tmp_path, "desk-case")[0]
    assert loaded.trigger.derived["max_energy"] == 10.0
    assert loaded.workflow.state is NoticeState.acked


def test_operator_actions_are_a_state_machine() -> None:
    notice = Notice(notice_id="notice-abc", trigger=_trigger(), workflow=NoticeWorkflow())
    apply_action(notice, NoticeAction.ack)
    assert notice.workflow.state is NoticeState.acked
    apply_action(notice, NoticeAction.request_context)
    assert notice.workflow.state is NoticeState.context_requested
    assert notice.workflow.selected_posture is CollectionPosture.focused
    apply_action(notice, NoticeAction.reexamine)
    assert notice.workflow.state is NoticeState.watching
    apply_action(notice, NoticeAction.reject, note="cloud gap misread as chorus")
    assert notice.workflow.state is NoticeState.rejected
    assert notice.workflow.events[-1].action is NoticeAction.reject
    with pytest.raises(ValueError, match="rejected"):
        apply_action(notice, NoticeAction.ack)


def test_ignore_is_terminal() -> None:
    notice = Notice(notice_id="notice-abc", trigger=_trigger(), workflow=NoticeWorkflow())
    apply_action(notice, "ignore")
    assert notice.workflow.state is NoticeState.dismissed
    with pytest.raises(ValueError):
        apply_action(notice, "reexamine")
