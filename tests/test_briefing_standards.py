from copy import deepcopy

import pytest
from test_editorial_brief import completion

from wsf.briefing_standards import annotate_yardstick, packet_presentation
from wsf.editorial_brief import validate_and_render


def test_yardstick_longest_match_first_use_and_existing_ranges():
    seen = set()
    assert annotate_yardstick("Highly unlikely; unlikely; highly unlikely", seen) == (
        "Highly unlikely (approximately 10% to 20%); "
        "unlikely (approximately 25% to 35%); highly unlikely"
    )
    assert annotate_yardstick("Unlikely (approximately 25% to 35%)") == (
        "Unlikely (approximately 25% to 35%)"
    )
    assert annotate_yardstick("Likely then probable") == (
        "Likely (approximately 55% to 75%) then probable"
    )


def test_presentation_preserves_packet_facts_and_exposes_sources():
    packet = {
        "product": {
            "assessment": ["A change is unlikely. More details."],
            "hypotheses": [{"fit": "Realistic possibility"}],
            "collection": [{"title": "Check public reporting"}],
        },
        "collected_evidence": [{"source": "Source A"}, {"source": "Source A"}],
    }
    original = deepcopy(packet)
    presented = packet_presentation(packet)
    assert packet == original
    assert "25% to 35%" in presented["bluf"]
    assert "Source A" in presented["source_assessment"]
    assert "misinformation" in presented["source_assessment"]


def test_bluf_and_confidence_contract():
    parsed = completion()
    parsed["bluf"] = [{"text": "First. Second. Third.", "refs": ["A1"]}]
    with pytest.raises(ValueError, match="two sentences"):
        validate_and_render(parsed, {"A1": {}})
    parsed = completion()
    parsed["confidence"] = [{"text": "It is unclear.", "refs": ["A1"]}]
    with pytest.raises(ValueError, match="Confidence"):
        validate_and_render(parsed, {"A1": {}})
    rendered = validate_and_render(completion(), {"A1": {}})
    assert rendered.index("## BLUF") < rendered.index("## Analytical confidence")
    assert rendered.index("## Source assessment") < rendered.index("## Key judgements")
