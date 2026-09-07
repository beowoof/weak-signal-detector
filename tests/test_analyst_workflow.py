import json

import pytest
from fastapi.testclient import TestClient
from test_draft import _notice

from dashboard.server import create_app
from wsf.analyst_workflow import (
    _render_gaps_and_cautions,
    _render_input_references,
    _render_source_data,
    _strip_input_refs,
    export_assessment,
    export_brief,
    load_workflow,
    update_workflow,
)
from wsf.packet import packet_directory
from wsf.report import save_report

# Distinct from the saved working assessment so export/preview tests can tell them apart.
EDITORIAL_FIXTURE = """## BLUF

- Condensed leadership takeaway from the saved assessment. [A1]

## Analytical confidence

- Moderate. Fixture rating from the supplied assessment. [A1]

## Source assessment

- Public sources as supplied in the assessment. [A1]

## Key judgements

- Condensed judgement for senior readers. [A1]

## Why it matters

- Leadership implication without new collection. [A1]

## Alternatives and uncertainty

- Alternative explanation remains open. [A1]

## Outlook and indicators to watch

- Watch for the specified discriminator. [A1]
"""


@pytest.fixture
def desk(tmp_path, monkeypatch):
    def fake_synthesis(root, directory, report, review, decisions, **kwargs):
        return {
            "body": EDITORIAL_FIXTURE,
            "model": "fixture",
            "attempt_id": "fixture",
            "input_references": {
                "A1": {"kind": "analyst_assessment", "text": report["notes"]}
            },
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
    product = export_brief(root, "desk-case", "notice-abc", 2, "md")
    assert "Signed off by Analyst" in product
    assert "Condensed leadership takeaway" in product
    assert "[A1]" not in product
    assert "Analyst working assessment" not in product
    assert "Key judgement\nExplanation unresolved" not in product
    rendered = export_brief(root, "desk-case", "notice-abc", 2, "html")
    assert "<script>" not in rendered
    assert "<h2>Key judgements</h2>" in rendered
    assert "<h2>BLUF</h2>" in rendered
    annex_html = export_brief(root, "desk-case", "notice-abc", 2, "html", annex=True)
    assert "&lt;script&gt;" in annex_html
    assert "<h3>Analyst working assessment</h3>" in annex_html
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
    assert "Revised judgement" in export_brief(root, "desk-case", "notice-abc", 2, "md")
    assert "Source passage" not in export_brief(root, "desk-case", "notice-abc", 2, "md")
    assert "Source passage" in export_brief(root, "desk-case", "notice-abc", 2, "md", annex=True)
    assert changed["briefs"][1]["signed_off"] is None
    removed = action(root, "remove_brief", version=2)
    assert len(removed["briefs"]) == 1
    with pytest.raises(ValueError, match="Unknown brief"):
        export_brief(root, "desk-case", "notice-abc", 2, "md")


def test_changed_assessment_during_model_call_does_not_publish(desk, monkeypatch):
    root, _ = desk
    save_report(root, "desk-case", "notice-abc", notes="Original")

    def changed(*args, **kwargs):
        save_report(root, "desk-case", "notice-abc", notes="Newer analyst work")
        return {"body": "Old draft"}

    monkeypatch.setattr("wsf.analyst_workflow.synthesize", changed)
    with pytest.raises(ValueError, match="changed during synthesis"):
        action(root, "prepare")
    assert not load_workflow(root, "desk-case", "notice-abc")["briefs"]


def test_generation_progress_is_visible_while_model_runs(desk, monkeypatch):
    root, _ = desk
    save_report(root, "desk-case", "notice-abc", notes="Assessment")

    def fake(*args, progress):
        progress("Model drafting", 1)
        during = load_workflow(root, "desk-case", "notice-abc")
        assert during["preparing"]
        assert during["brief_progress"]["completed"] == 1
        assert during["brief_progress"]["started_at"]
        progress("Checking references", 2)
        return {"body": "Brief", "input_references": {}}

    monkeypatch.setattr("wsf.analyst_workflow.synthesize", fake)
    result = action(root, "prepare")
    assert not result["preparing"]
    assert result["brief_progress"]["completed"] == 4


def test_render_input_references_organization_and_natural_sort():
    inputs = {
        "A10": {"kind": "analyst_assessment", "text": "Tenth paragraph"},
        "A2": {"kind": "analyst_assessment", "text": "Second paragraph"},
        "A1": {"kind": "analyst_assessment", "text": "First paragraph"},
        "P1": {
            "proposal_id": "claim-1",
            "text": "First claim text",
            "evidence_ids": ["ev-1"],
            "analyst_reason": "Good source",
        },
        "S1": {
            "kind": "source_provenance",
            "evidence_id": "ev-1",
            "originator": "test_ref",
            "verification": "verified",
            "available_at": "2022-02-10T00:00:00Z",
            "url": "https://example.com",
        },
        "R1": {
            "kind": "review_limitation",
            "text": {"proposal_id": "claim-99", "status": "rejected", "reason": "No evidence"},
        },
        "R2": {"kind": "review_limitation", "text": "Collector provenance caution"},
    }
    rendered = _render_input_references(inputs)
    assert "### Analyst working assessment" in rendered
    assert "### Reviewed proposals & findings" in rendered
    assert "### Source provenance" in rendered
    assert "### Review limitations & cautions" in rendered
    idx_a1 = rendered.index("**A1**")
    idx_a2 = rendered.index("**A2**")
    idx_a10 = rendered.index("**A10**")
    assert idx_a1 < idx_a2 < idx_a10
    assert "- **P1** (*claim-1*): First claim text [Sources: ev-1] — Analyst note: Good source" in rendered
    assert (
        "- **S1** (*ev-1*): `test_ref` (Verification: verified | Available: 2022-02-10 00:00:00 UTC | URL: https://example.com)"
        in rendered
    )
    assert "- **R1** (*claim-99 rejected*): No evidence" in rendered
    assert "- **R2**: Collector provenance caution" in rendered
    assert "{" not in rendered and "}" not in rendered


def test_render_input_references_cleans_comments_and_template_placeholders():
    inputs = {
        "A1": {"text": "<!-- reviewed-material:start -->\n## Reviewed findings\n- Finding 1\n- Finding 2"},
        "A2": {"text": "## Review limitations\n- Limitation 1"},
        "A3": {"text": "## Analyst judgement and implications"},
        "A4": {"text": "<!-- reviewed-material:end -->"},
        "A5": {"text": "Substantive judgement paragraph."},
    }
    rendered = _render_input_references(inputs)
    assert "<!-- reviewed-material" not in rendered
    assert not any(line.startswith("## ") for line in rendered.splitlines())
    assert "**A1**: Reviewed findings:" in rendered
    assert "  - Finding 1" in rendered
    assert "  - Finding 2" in rendered
    assert "**A2**: Review limitations:" in rendered
    assert "  - Limitation 1" in rendered
    assert "**A3**" not in rendered  # Empty template placeholder omitted
    assert "**A4**" not in rendered  # Comment-only placeholder omitted
    assert "**A5**: Substantive judgement paragraph." in rendered


def test_render_source_data_formats_all_kinds():
    posture = {
        "kind": "declared_posture",
        "date": "2022-02-11",
        "government": "UK/FCDO",
        "country": "UKR",
        "action": "leave_advice",
        "costly": True,
        "severity": 4,
        "text": "Leave Ukraine now.",
        "category": "travel_risk",
    }
    p_text = "\n".join(_render_source_data(posture))
    assert "2022-02-11 · UK/FCDO (UKR) — Action: leave_advice" in p_text
    assert "costly: true, severity: 4" in p_text
    assert '"Leave Ukraine now."' in p_text

    granule = {
        "kind": "catalogue_granule",
        "name": "S1A_TEST.SAFE",
        "collection": "SENTINEL-1",
        "product_type": "GRDH",
        "aoi_name": "Yelnya",
        "aoi_id": "RUS-yelnya",
        "sensing_at": "2022-02-11T04:00:00Z",
    }
    g_text = "\n".join(_render_source_data(granule))
    assert "`S1A_TEST.SAFE`" in g_text
    assert "SENTINEL-1 (GRDH) · AOI: Yelnya (RUS-yelnya)" in g_text
    assert "**Sensing time**: 2022-02-11 04:00:00 UTC" in g_text

    obs = {
        "kind": "observation",
        "series_id": "market.cbr_funding_spread",
        "text": "z=2.54; raw=21.0; quality=ok",
        "shared_information_substrate": "central_bank",
    }
    o_text = "\n".join(_render_source_data(obs))
    assert "`market.cbr_funding_spread` (central_bank)" in o_text
    assert "z=2.54; raw=21.0; quality=ok" in o_text

    chronology = {
        "day": "2022-01-11",
        "series": [
            {"series_id": "series.a", "value": 10.5, "quality": "ok", "note": None},
            {"series_id": "series.b", "value": 20.0, "quality": "missing", "note": "gap"},
        ],
    }
    c_text = "\n".join(_render_source_data(chronology))
    assert "**Chronology record**: 2022-01-11" in c_text
    assert "`series.a`: 10.50 [quality: ok]" in c_text
    assert "`series.b`: 20.00 [quality: missing] (note: gap)" in c_text

    missing_obs = {
        "label": "SAR",
        "day": "2022-02-12",
        "value": None,
        "quality": "missing",
        "orbit": "DESCENDING",
    }
    m_text = "\n".join(_render_source_data(missing_obs))
    assert "Value: — [quality: missing]" in m_text
    assert "None" not in m_text


def test_render_gaps_and_cautions_sections():
    review = {
        "issues": ["Issue one", "Issue two"],
        "cautions": ["Caution one"],
        "excluded": [
            {"id": "ev-ex-1", "kind": "physical", "reason": "unavailable", "source_ref": "ref/1"}
        ],
        "omitted": [
            {"id": "ev-om-1", "kind": "chronology", "reason": "budget_limit", "source_ref": "ref/2"}
        ],
        "research": {
            "usage": {"search_requests": 3, "document_attempts": 2, "elapsed_s": 12.3},
            "limit_reached": "requests",
            "requests": {"q-1": {"status": "complete", "result_count": 5}},
        },
        "hypothesis_updates": [
            {
                "hypothesis": "routine_variation",
                "change": "lowered",
                "confidence": "Low",
                "rationale": "Elevated indicators exceed baseline",
                "contradicting_evidence": ["ev-1", "ev-2"],
                "unknowns": ["Baseline uncertain"],
                "discriminators": ["Physical imagery"],
            }
        ],
    }
    lines = _render_gaps_and_cautions(review)
    text = "\n".join(lines)
    assert "#### Analytical issues & validation checks" in text
    assert "- Issue one" in text
    assert "#### Provenance cautions & context limits" in text
    assert "- Caution one" in text
    assert "#### Excluded evidence" in text
    assert "**`ev-ex-1`** (*physical*): Excluded — unavailable (ref: `ref/1`)" in text
    assert "#### Omitted evidence (character / budget limits)" in text
    assert "**`ev-om-1`** (*chronology*): Omitted — budget_limit (ref: `ref/2`)" in text
    assert "#### Research execution & source retrieval trail" in text
    assert "3 search requests, 2 document attempts, 12.3s elapsed" in text
    assert "`q-1`: complete (5 results)" in text
    assert "#### Competing hypothesis updates" in text
    assert "**routine_variation**: **lowered** (Confidence: Low)" in text
    assert "Elevated indicators exceed baseline" in text
    assert "ev-1, ev-2" in text
    assert "{" not in text and "}" not in text


def test_export_brief_html_formatting_and_no_raw_json(desk):
    import re
    root, _ = desk
    action(root, "review", proposal_id="claim-1", status="accepted")
    action(root, "review", proposal_id="claim-2", status="rejected", reason="Unsupported")
    action(root, "review", proposal_id="decision", status="accepted")
    save_report(root, "desk-case", "notice-abc", notes="Analyst assessment paragraph.")
    action(root, "prepare", title="Human Assessment")
    action(root, "sign_off", version=1, reviewer="Reviewer", acknowledged=True)
    html_out = export_brief(root, "desk-case", "notice-abc", 1, "html")
    assert "WSD Intelligence Desk" in html_out
    assert "<h1>Human Assessment</h1>" in html_out
    assert "<h2>BLUF</h2>" in html_out
    assert "<h2>Key judgements</h2>" in html_out
    assert "Condensed leadership takeaway" in html_out
    assert "[A1]" not in html_out
    assert "Analyst working assessment" not in html_out
    assert "claim-1" not in html_out
    assert "Analyst assessment paragraph" not in html_out
    assert "<p class='finding'>•" in html_out
    assert "<p>{</p>" not in html_out
    assert "<p>}</p>" not in html_out
    assert '"kind":' not in html_out
    assert '"proposal_id":' not in html_out
    assert "Signed off by Reviewer at " in html_out
    annex_html = export_brief(root, "desk-case", "notice-abc", 1, "html", annex=True)
    assert "<h3>Analyst working assessment</h3>" in annex_html
    assert "<h3>claim-1 — accepted</h3>" in annex_html
    assert "<h4>Analytical issues &amp; validation checks</h4>" in annex_html
    # Assert no raw microsecond ISO timestamps in exported HTML
    assert re.search(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}\.\d+", html_out) is None
    # Assert clean UTC datetimes
    assert re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} UTC", html_out) is not None


def test_export_brief_pdf_generation_and_api(desk):
    import io
    from pypdf import PdfReader
    root, _ = desk
    action(root, "review", proposal_id="claim-1", status="accepted")
    action(root, "review", proposal_id="claim-2", status="rejected", reason="Unsupported")
    action(root, "review", proposal_id="decision", status="accepted")
    save_report(root, "desk-case", "notice-abc", notes="Analyst assessment paragraph.")
    action(root, "prepare", title="Human Assessment")
    client = TestClient(create_app(project_root=root))
    query = {"scenario": "desk-case", "notice_id": "notice-abc", "version": 1, "format": "pdf"}
    draft = client.get("/api/analyst-workflow/export", params=query)
    assert draft.headers["content-disposition"] == 'attachment; filename="draft-brief-v1.pdf"'
    draft_text = "\n".join(
        p.extract_text() or "" for p in PdfReader(io.BytesIO(draft.content)).pages
    )
    assert "DRAFT" in draft_text
    assert "Signed off by Reviewer" not in draft_text
    action(root, "sign_off", version=1, reviewer="Reviewer", acknowledged=True)

    pdf_bytes = export_brief(root, "desk-case", "notice-abc", 1, "pdf")
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")

    reader = PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) >= 1
    extracted = "\n".join(p.extract_text() or "" for p in reader.pages)
    assert "Human Assessment" in extracted
    assert "Signed off by Reviewer" in extracted
    assert "Condensed leadership takeaway" in extracted
    assert "INTELLIGENCE BRIEF" in extracted
    assert "WSD INTELLIGENCE DESK" in extracted
    assert "awaiting sign-off" not in extracted
    assert "[A1]" not in extracted
    assert "Analyst assessment paragraph" not in extracted

    res = client.get("/api/analyst-workflow/export", params=query)
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.headers["content-disposition"] == 'attachment; filename="brief-v1.pdf"'
    assert res.content.startswith(b"%PDF")
    annex = client.get("/api/analyst-workflow/export", params={**query, "annex": True})
    assert annex.status_code == 200
    assert annex.headers["content-disposition"] == 'attachment; filename="brief-annex-v1.pdf"'


def test_strip_input_refs_leaves_prose_and_other_brackets():
    assert _strip_input_refs("- Takeaway [A3, A20]") == "- Takeaway"
    assert _strip_input_refs("Detail [A5, P1, R3].") == "Detail."
    assert _strip_input_refs("[quality: ok]") == "[quality: ok]"
    assert _strip_input_refs("No codes") == "No codes"


def test_export_assessment_is_working_notes_not_the_brief(desk):
    root, _ = desk
    with pytest.raises(ValueError, match="Save your working"):
        export_assessment(root, "desk-case", "notice-abc", "md")
    action(root, "review", proposal_id="claim-1", status="accepted")
    save_report(
        root, "desk-case", "notice-abc", notes="## Key judgement\nColleague-facing assessment."
    )
    action(root, "prepare", title="Leadership brief")
    md = export_assessment(root, "desk-case", "notice-abc", "md")
    assert "Colleague-facing assessment." in md
    assert "Working assessment" in md
    assert "Condensed leadership takeaway" not in md
    assert "Source passage" in md
    html_out = export_assessment(root, "desk-case", "notice-abc", "html")
    assert "Colleague-facing assessment." in html_out
    pdf_bytes = export_assessment(root, "desk-case", "notice-abc", "pdf")
    assert pdf_bytes.startswith(b"%PDF")
    client = TestClient(create_app(project_root=root))
    res = client.get(
        "/api/analyst-workflow/export-assessment",
        params={"scenario": "desk-case", "notice_id": "notice-abc", "format": "pdf"},
    )
    assert res.status_code == 200
    assert res.headers["content-disposition"] == 'attachment; filename="working-assessment.pdf"'
