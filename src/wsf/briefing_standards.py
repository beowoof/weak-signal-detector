"""Presentation standards for assessed language; never modify detector facts."""

from __future__ import annotations

import copy
import re

YARDSTICK_SOURCE = (
    "https://www.gov.uk/government/publications/explaining-uncertainty-in-uk-intelligence-assessment/"
    "explaining-uncertainty-in-uk-intelligence-assessment"
)
RANGES = {
    "remote chance": ">0% to approximately 5%",
    "highly unlikely": "approximately 10% to 20%",
    "unlikely": "approximately 25% to 35%",
    "realistic possibility": "approximately 40% to less than 50%",
    "likely or probable": "approximately 55% to 75%",
    "highly likely": "approximately 80% to 90%",
    "almost certain": "approximately 95% to less than 100%",
    "likely": "approximately 55% to 75%",
    "probable": "approximately 55% to 75%",
}
PATTERN = re.compile(r"\b(" + "|".join(sorted(RANGES, key=len, reverse=True)) + r")\b", re.I)


def annotate_yardstick(text, seen=None):
    seen = seen if seen is not None else set()

    def replace(match):
        term = match.group().lower()
        family = "likely or probable" if term in {"likely", "probable"} else term
        if family in seen:
            return match.group()
        seen.add(family)
        # Preserve an existing numeric expansion instead of adding a second one.
        if re.match(r"\s*\([^)]*%[^)]*\)", text[match.end() :]):
            return match.group()
        return f"{match.group()} ({RANGES[term]})"

    return PATTERN.sub(replace, text)


def packet_presentation(packet):
    product = copy.deepcopy(packet.get("product"))
    if not product:
        return None
    assessment = product.get("assessment", [])
    lead = re.split(r"(?<=[.!?])\s+", assessment[0])[0] if assessment else ""
    product["bluf"] = lead + (
        " Targeted public-source collection is needed to distinguish the competing explanations."
        if product.get("collection")
        else ""
    )
    labels = {
        "attn.wiki_pageviews": "Wikipedia pageviews (public attention)",
        "dyad.moex_usdrub": "MOEX USD/RUB series",
        "market.cbr_funding_spread": "Central Bank of Russia funding series",
        "nav.spatial_warnings": "NAVAREA warning series",
        "net.ripe_prefixes": "RIPEstat network-prefix series",
        "talk.gdelt_cameo": "GDELT-coded public reporting",
        "talk.icews_cameo": "ICEWS-coded public reporting",
        "tempo.firms_thermal": "FIRMS thermal-detection series",
        "tempo.s1_backscatter": "Sentinel-1 backscatter series",
        "tempo.viirs_ntl": "VIIRS night-light series",
    }
    sources = sorted(
        {
            labels.get(item.get("series_id"), item.get("series_id") or item.get("source"))
            for item in packet.get("collected_evidence", [])
            if item.get("series_id") or item.get("source")
        }
    )
    product["confidence_rationale"] = re.sub(
        r"^Analytical confidence is (?:low|moderate|high)\.\s*",
        "",
        product.get("confidence_rationale", ""),
        flags=re.I,
    )
    product["source_assessment"] = (
        "Source base: "
        + (", ".join(sources) if sources else "source provenance not recorded")
        + ". Public-source provenance is not independent verification. "
        "Originator reliability, corroboration and misinformation have not been fully assessed; "
        "repeated reporting must not be counted as independent confirmation."
    )
    seen = set()
    product["bluf"] = annotate_yardstick(product["bluf"], seen)
    product["assessment"] = [annotate_yardstick(p, seen) for p in assessment]
    for row in product.get("hypotheses", []):
        row["fit"] = annotate_yardstick(row["fit"], seen)
    return product
