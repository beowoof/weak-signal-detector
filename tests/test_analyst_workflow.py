import json

import pytest
from fastapi.testclient import TestClient
from test_draft import _notice

from dashboard.server import create_app
from wsf.analyst_workflow import export_brief, load_workflow, update_workflow
from wsf.packet import packet_directory
from wsf.report import save_report


@pytest.fixture
def desk(tmp_path, monkeypatch):
    def fake_synthesis(root, directory, report, review, decisions):
        return {
            "body": report["notes"],
            "model": "fixture",
            "attempt_id": "fixture",
            "input_references": {"A1": {"text": report["notes"]}},
            "structured": {},
        }

    monkeypatch.setattr("wsf.analyst_workflow.synthesize", fake_synthesis)
    _notice(tmp_path)
    review = {
        "bundle_id": "bundle-1",
        "claims": [
            {
                "claim_id": "claim-1",
                "statement": "Original claim",
                "evidence_ids": ["ev-1"],
                "quotes": {"ev-1": "Source passage"},
            },
            {"claim_id": "claim-2", "statement": "Rejected claim", "evidence_ids": ["ev-1"]},
        ],
        "hypothesis_updates": [],
        "proposed_decision": "collect_more",
        "evidence": [{"id": "ev-1", "data": {"text": "Source passage <script>bad()</script>"}}],
        "issues": ["Source independence unresolved"],
        "cautions": ["Public sources only"],
    }
    path = packet_directory(tmp_path, "desk-case", "packet-test") / "machine_draft.json"
    path.write_text(json.dumps({"review": review}))
    return tmp_path, path


def action(root, action, **fields):
    state = load_workflow(root, "desk-case", "notice-abc")
    return update_workflow(
        root,
        "desk-case",
        "notice-abc",
        revision=state["revision"],
        review_version=state["review_version"],
        action=action,
        **fields,
    )


def test_review_persists_edits_excludes_rejections_and_keeps_history(desk):
    root, _ = desk
    action(
        root,
        "review",
        proposal_id="claim-1",
        status="edited",
        text="Qualified finding",
        reason="The evidence supports a narrower claim",
    )
    action(root, "review", proposal_id="claim-2", status="rejected", reason="Unsupported")
    state = load_workflow(root, "desk-case", "notice-abc")
    assert "Qualified finding [Sources: ev-1]" in state["assembly"]
    assert "Rejected claim" not in state["assembly"]
    assert len(state["events"]) == 2
    assert state["events"][0]["proposal"]["statement"] == "Original claim"
    action(root, "review", proposal_id="claim-1", status="accepted")
    assert len(load_workflow(root, "desk-case", "notice-abc")["events"]) == 3


def test_same_bundle_new_proposals_invalidate_decisions_and_reject_stale_writes(desk):
    root, path = desk
    old = action(root, "review", proposal_id="claim-1", status="accepted")
    record = json.loads(path.read_text())
    record["review"]["claims"][0]["statement"] = "Different claim using the same bundle"
    path.write_text(json.dumps(record))
    state = load_workflow(root, "desk-case", "notice-abc")
    assert state["active_decisions"] == {}
    assert state["stale_decisions"] == 1
    with pytest.raises(ValueError, match="Evidence or proposals changed"):
        update_workflow(
            root,
            "desk-case",
            "notice-abc",
            revision=old["revision"],
            review_version=old["review_version"],
            action="review",
            proposal_id="claim-1",
            status="accepted",
        )
    with pytest.raises(ValueError, match="Workflow changed"):
        update_workflow(root, "desk-case", "notice-abc", revision=0, action="prepare")


def test_brief_lifecycle_and_safe_export(desk):
    root, _ = desk
    with pytest.raises(ValueError, match="Save your working"):
        action(root, "prepare")
    action(root, "review", proposal_id="claim-1", status="accepted")
    action(root, "review", proposal_id="claim-2", status="rejected", reason="Unsupported")
    save_report(root, "desk-case", "notice-abc", notes="## Key judgement\nExplanation unresolved.")
    state = action(root, "prepare", title="Preparatory Activity Watch")
    before = state["briefs"][0]["markdown"]
    assert "Source passage" in before
    assert "Source independence unresolved" in before
    assert "Rejected claim" not in before.split("## Evidence and review annex")[0]
    with pytest.raises(ValueError, match="Review every proposal"):
        action(root, "sign_off", version=1, reviewer="Analyst", acknowledged=True)
    action(root, "review", proposal_id="decision", status="unresolved", reason="Need more context")
    # Changing review invalidates the earlier brief.
    with pytest.raises(ValueError, match="stale"):
        action(root, "sign_off", version=1, reviewer="Analyst", acknowledged=True)
    action(root, "prepare")
    action(root, "sign_off", version=2, reviewer="Analyst", acknowledged=True)
    assert "Signed off by Analyst" in export_brief(root, "desk-case", "notice-abc", 2, "md")
    rendered = export_brief(root, "desk-case", "notice-abc", 2, "html")
    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered
    assert "<h2>Key judgement</h2>" in rendered
    save_report(root, "desk-case", "notice-abc", notes="Revised analyst judgement")
    state = load_workflow(root, "desk-case", "notice-abc")
    assert state["briefs"][0]["markdown"] == before
    assert state["briefs"][1]["stale"]
    assert "STALE" in export_brief(root, "desk-case", "notice-abc", 2, "md")


def test_api_roundtrip_and_validation(desk):
    root, _ = desk
    client = TestClient(create_app(project_root=root))
    query = {"scenario": "desk-case", "notice_id": "notice-abc"}
    state = client.get("/api/analyst-workflow", params=query).json()
    payload = {
        **query,
        "revision": state["revision"],
        "review_version": state["review_version"],
        "action": "review",
        "proposal_id": "claim-1",
        "status": "rejected",
    }
    assert client.post("/api/analyst-workflow", json=payload).status_code == 400
    payload["reason"] = "Unsupported"
    response = client.post("/api/analyst-workflow", json=payload)
    assert response.status_code == 200
    assert response.json()["active_decisions"]["claim-1"]["status"] == "rejected"
    assert client.post("/api/analyst-workflow", json=payload).status_code == 400
    assert (
        client.get("/api/analyst-workflow/export", params={**query, "version": 99}).status_code
        == 400
    )


def test_reset_archives_and_preserves_research_and_version_identity(desk):
    root, source = desk
    original = source.read_text()
    action(root, "review", proposal_id="claim-1", status="accepted")
    save_report(root, "desk-case", "notice-abc", notes="Saved assessment")
    action(root, "prepare")
    reset = action(root, "reset", acknowledged=True)
    assert reset["report"]["empty"]
    assert not reset["briefs"] and not reset["active_decisions"]
    assert source.read_text() == original
    archives = list((root / "scenarios/desk-case/reports").glob("*/resets/*/report.json"))
    assert len(archives) == 1
    assert "Saved assessment" in archives[0].read_text()
    with pytest.raises(ValueError, match="Unknown brief"):
        export_brief(root, "desk-case", "notice-abc", 1, "md")
    save_report(root, "desk-case", "notice-abc", notes="Fresh assessment")
    assert action(root, "prepare")["briefs"][0]["version"] == 2


def test_edit_and_remove_brief_preserve_prior_content_and_annex(desk):
    root, _ = desk
    save_report(root, "desk-case", "notice-abc", notes="Original judgement")
    prepared = action(root, "prepare")
    original = prepared["briefs"][0]["markdown"]
    changed = action(root, "revise_brief", version=1, text="Revised judgement")
    assert changed["briefs"][0]["markdown"] == original
    assert "Revised judgement" in changed["briefs"][1]["markdown"]
    assert "Source passage" in changed["briefs"][1]["markdown"]
    assert changed["briefs"][1]["signed_off"] is None
    removed = action(root, "remove_brief", version=2)
    assert len(removed["briefs"]) == 1
    with pytest.raises(ValueError, match="Unknown brief"):
        export_brief(root, "desk-case", "notice-abc", 2, "md")


def test_changed_assessment_during_model_call_does_not_publish(desk, monkeypatch):
    root, _ = desk
    save_report(root, "desk-case", "notice-abc", notes="Original")

    def changed(*args):
        save_report(root, "desk-case", "notice-abc", notes="Newer analyst work")
        return {"body": "Old draft"}

    monkeypatch.setattr("wsf.analyst_workflow.synthesize", changed)
    with pytest.raises(ValueError, match="changed during synthesis"):
        action(root, "prepare")
    assert not load_workflow(root, "desk-case", "notice-abc")["briefs"]
