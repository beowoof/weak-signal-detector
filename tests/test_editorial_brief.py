import json

import pytest
from test_draft import FakeChat

from wsf.editorial_brief import SECTIONS, synthesize, validate_and_render


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
        "are difficult to explain as routine fluctuation and weaken standard exercise activity as a complete explanation"
        in rendered
    )
    assert "exceed thresholds" not in rendered
    assert (
        c["key_judgements"][0]["text"]
        == "The scale of force movement and extraordinary diplomatic precautions "
        "are difficult to explain as routine fluctuation and weaken standard exercise activity as a complete explanation, "
        "though exercise components remain plausible."
    )
