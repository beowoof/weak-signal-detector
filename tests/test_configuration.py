from pathlib import Path

from pydantic import TypeAdapter

from wsf.protocol import load_yaml
from wsf.register import validate_configuration
from wsf.types import CausalDomain, IndicatorSpec

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_rus_physical_aois_are_staging_corridors() -> None:
    facilities = load_yaml(PROJECT_ROOT / "config" / "facilities.yaml")
    rus = facilities["actors"]["RUS"]["aois"]
    ids = {item["id"] for item in rus}
    assert "RUS-capital" not in ids
    assert "RUS-mod" not in ids
    assert len(rus) >= 6
    assert facilities["generation"]["max_aois_per_focal"] >= len(rus)
    assert {item["kind"] for item in rus} <= {"staging", "frontier_railhead"}


def test_frozen_configuration_contracts_are_valid() -> None:
    result = validate_configuration(PROJECT_ROOT / "config")
    assert result["indicator_count"] == 27
    assert result["period_count"] == 5
    assert len(result["config_hashes"]) == 9


def test_v1_basket_spans_independent_causal_domains() -> None:
    indicators = TypeAdapter(list[IndicatorSpec]).validate_python(
        load_yaml(PROJECT_ROOT / "config" / "indicator_register.yaml")
    )
    basket = [item for item in indicators if item.in_basket]
    domains = {item.causal_domain for item in basket}
    assert CausalDomain.physical_activity in domains
    assert CausalDomain.information in domains
    assert CausalDomain.public_attention in domains
    assert CausalDomain.digital_infrastructure in domains
    assert CausalDomain.market in domains
    demoted = {item.id: item for item in indicators}
    assert demoted["attn.osm_changesets"].in_basket is False
    assert demoted["attn.wiki_edits"].in_basket is False
    assert demoted["info.brent"].in_basket is False
    assert demoted["official.gazette"].in_basket is False
    assert demoted["official.ct_certs"].in_basket is False
    assert demoted["official.ct_certs"].causal_domain is CausalDomain.digital_infrastructure
    assert demoted["official.gazette"].collector == "Internet Archive"
    assert demoted["attn.osm_changesets"].causal_domain is CausalDomain.public_attention
    assert demoted["mobility.opensky"].status.value == "uninstantiated"
    assert demoted["tempo.s1_backscatter"].in_basket is True
    icews = demoted["talk.icews_cameo"]
    gdelt = demoted["talk.gdelt_cameo"]
    assert icews.causal_domain is gdelt.causal_domain is CausalDomain.information
