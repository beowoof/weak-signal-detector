import json

import pytest
from test_draft import FakeChat

from wsf.editorial_brief import SECTIONS, assessment_inputs, synthesize, validate_and_render


def completion(ref="A1"):
    return {
        key: [
            {
                "text": (
                    "Confidence is Low because source support is incomplete."
                    if key == "confidence"
                    else "The explanation remains unresolved."
                ),
                "refs": [ref],
            }
        ]
        for key in SECTIONS
    }


def test_editorial_input_uses_retained_wording_and_preserves_audit(tmp_path, monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "fixture")
    chat = FakeChat(json.dumps(completion()))
    review = {
        "claims": [
            {"claim_id": "c1", "statement": "Original broader claim"},
            {"claim_id": "c2", "statement": "Rejected model claim"},
        ],
        "hypothesis_updates": [],
        "proposed_decision": "wait",
        "research": {
            "collection_outcomes": [
                {
                    "question": "Government actions",
                    "status": "no_admitted_documents",
                    "reason": "No usable pre-cutoff archive capture",
                }
            ]
        },
    }
    decisions = {
        "c1": {"status": "edited", "text": "Narrower retained claim"},
        "c2": {"status": "rejected", "reason": "Unsupported"},
    }
    result = synthesize(
        tmp_path, tmp_path, {"notes": "Explanation unresolved."}, review, decisions, transport=chat
    )
    inputs = next((tmp_path / "brief_runs").glob("*/input.json")).read_text()
    assert "Narrower retained claim" in inputs
    assert "No usable pre-cutoff archive capture" in inputs
    assert "Rejected model claim" not in inputs
    assert "Original broader claim" not in inputs
    assert result["model"] == "fixture"
    assert "## Key judgements" in result["body"]
    assert list((tmp_path / "brief_runs").glob("*/completion.json"))


def test_invalid_refs_and_incomplete_sections_fail():
    with pytest.raises(ValueError, match="unknown input references"):
        validate_and_render(completion("invented"), {"A1": {}})
    with pytest.raises(ValueError, match="all required"):
        validate_and_render({}, {"A1": {}})


def test_failed_model_output_is_retained(tmp_path, monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "fixture")
    with pytest.raises(ValueError, match="Brief synthesis failed"):
        synthesize(
            tmp_path,
            tmp_path,
            {"notes": "Assessment"},
            None,
            {},
            transport=FakeChat(json.dumps(completion("invented"))),
        )
    assert list((tmp_path / "brief_runs").glob("*/error.json"))
    assert list((tmp_path / "brief_runs").glob("*/completion.json"))


def test_semantic_inflation_deflated():
    c = completion("A1")
    c["key_judgements"][0]["text"] = (
        "The scale of force movement and extraordinary diplomatic precautions "
        "exceed thresholds for routine fluctuation or standard exercise activity, "
        "though exercise components remain plausible."
    )
    rendered = validate_and_render(c, {"A1": {}})
    assert (
        "are difficult to explain as routine fluctuation and weaken standard exercise activity "
        "as a complete explanation" in rendered
    )
    assert "exceed thresholds" not in rendered
    assert (
        c["key_judgements"][0]["text"]
        == "The scale of force movement and extraordinary diplomatic precautions "
        "are difficult to explain as routine fluctuation and weaken standard exercise activity "
        "as a complete explanation, "
        "though exercise components remain plausible."
    )


def test_input_distinguishes_initial_cue_from_later_assessment_and_review():
    notes = """Packet assessment

The explanation remains unresolved.

## Working assessment

Material preparation is supported with moderate confidence.

## What that showed
Reported movements from Yelnya towards Klintsy on 11 February suggest forward staging.

## Decision

Send up.

<!-- reviewed-material:start -->
## Reviewed findings

Recommended next action: collect_more

## Review limitations

Primary verification is incomplete.
<!-- reviewed-material:end -->"""
    inputs = assessment_inputs(notes)
    assert [p["kind"] for p in inputs.values()] == [
        "initial_packet_context",
        "analyst_assessment",
        "analyst_assessment",
        "analyst_assessment",
        "retained_review_material",
        "review_limitation",
    ]
    assert inputs["A3"]["section"] == "findings"
    assert "Yelnya towards Klintsy on 11 February" in inputs["A3"]["text"]
    assert inputs["A4"]["text"] == "Send up."
    assert inputs["A5"]["text"] == "Recommended next action: collect_more"
    assert "<!--" not in json.dumps(inputs)


def test_freeform_assessment_is_preserved_without_recognised_headings():
    notes = "A qualified judgement.\n\nA specific counterargument."
    inputs = assessment_inputs(notes)
    assert [p["text"] for p in inputs.values()] == notes.split("\n\n")
    assert all(p["section"] == "freeform" for p in inputs.values())


def test_substantive_analysis_precedes_source_methodology():
    rendered = validate_and_render(completion(), {"A1": {}})
    assert rendered.index("## Key judgements") < rendered.index("## Source assessment")
    assert rendered.index("## Outlook") < rendered.index("## Analytical confidence")
