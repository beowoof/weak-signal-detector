"""Check source references mechanically; never certify entailment or decide for the analyst."""

from __future__ import annotations

import re

from wsf.evidence_bundle import canonical

SERIES_PATTERNS = {
    "attn.wiki_pageviews": [
        r"\bwiki\b",
        r"\bwikipedia\b",
        r"\bpageviews?\b",
        r"\battn\.wiki_pageviews\b",
    ],
    "market.cbr_funding_spread": [
        r"\bcbr\b",
        r"\bfunding\s+spread\b",
        r"\bmarket\.cbr_funding_spread\b",
    ],
    "net.ripe_prefixes": [r"\bripe\b", r"\bprefix(?:es)?\b", r"\bnet\.ripe_prefixes\b"],
    "talk.gdelt_cameo": [r"\bgdelt\b", r"\btalk\.gdelt_cameo\b"],
    "talk.icews_cameo": [r"\bicews\b", r"\btalk\.icews_cameo\b"],
    "tempo.firms_thermal": [r"\bfirms\b", r"\bthermal\b", r"\btempo\.firms_thermal\b"],
    "tempo.s1_backscatter": [
        r"\bsar\b",
        r"\bbackscatter\b",
        r"\bs1_backscatter\b",
        r"\btempo\.s1_backscatter\b",
    ],
    "tempo.viirs_aoi": [r"\bviirs\b", r"\bntl\b", r"\btempo\.viirs_aoi\b"],
    "dyad.moex_usdrub": [
        r"\busd/rub\b",
        r"\bmoex\b",
        r"\bexchange\s+fixing\b",
        r"\bdyad\.moex_usdrub\b",
    ],
    "nav.spatial_warnings": [
        r"\bspatial\s+warnings?\b",
        r"\bnavarea\b",
        r"\bnotam\b",
        r"\bnav\.spatial_warnings\b",
    ],
}


def _evidence_dates(row: dict) -> set[str]:
    dates = set()
    data = row.get("data", {})
    if isinstance(data, dict):
        for field in ("evidence_time", "day", "date", "sensing_date"):
            val = data.get(field)
            if val is not None:
                m = re.search(r"(\d{4}-\d{2}-\d{2})", str(val))
                if m:
                    dates.add(m.group(1))
        item_id = data.get("item_id")
        if item_id is not None:
            m = re.search(r"(\d{4}-\d{2}-\d{2})", str(item_id))
            if m:
                dates.add(m.group(1))
        if dates:
            return dates
        for field in ("at", "sensing_at", "published_at"):
            val = data.get(field)
            if val is not None:
                m = re.search(r"(\d{4}-\d{2}-\d{2})", str(val))
                if m:
                    dates.add(m.group(1))
        if dates:
            return dates
    for field in ("source_ref", "available_at"):
        val = row.get(field)
        if val is not None:
            m = re.search(r"(\d{4}-\d{2}-\d{2})", str(val))
            if m:
                dates.add(m.group(1))
    return dates


def _number_in_evidence(val: float, data: dict, quote: str | None) -> bool:
    for field in ("value", "raw"):
        v = data.get(field)
        if isinstance(v, (int, float)) and abs(float(v) - val) <= 0.05:
            return True
    all_text = f"{quote or ''} {data.get('text', '')}"
    nums = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", all_text)]
    return any(abs(n - val) <= 0.05 for n in nums)


def _check_claim_evidence_invariants(statement: str, row: dict, quote: str | None) -> list[str]:
    errors = []
    data = row.get("data", {})
    if not isinstance(data, dict):
        data = {}

    claim_dates = set(re.findall(r"\b\d{4}-\d{2}-\d{2}\b", statement))
    if claim_dates:
        ev_dates = _evidence_dates(row)
        if ev_dates and not (claim_dates & ev_dates):
            errors.append("claim_evidence_date_mismatch")

    series_id = data.get("series_id")
    if isinstance(series_id, str) and series_id in SERIES_PATTERNS:
        mentioned_series = {
            sid
            for sid, patterns in SERIES_PATTERNS.items()
            if any(re.search(pat, statement, re.IGNORECASE) for pat in patterns)
        }
        if mentioned_series and series_id not in mentioned_series:
            errors.append("claim_evidence_series_mismatch")

    z_claim_match = re.search(
        r"\b(?:z[- ]?score|z)\s*(?:was|reached|of|is|=)?\s*(-?\d+(?:\.\d+)?)\b",
        statement,
        re.IGNORECASE,
    )
    if z_claim_match:
        z_claim = float(z_claim_match.group(1))
        ev_text = data.get("text") or canonical(data)
        z_ev_match = re.search(r"\bz\s*=\s*(-?\d+(?:\.\d+)?)", ev_text)
        if not z_ev_match and isinstance(quote, str):
            z_ev_match = re.search(r"\bz\s*=\s*(-?\d+(?:\.\d+)?)", quote)

        if z_ev_match:
            z_ev = float(z_ev_match.group(1))
            if abs(z_claim - z_ev) > 0.05:
                errors.append("claim_evidence_value_mismatch")
        elif "z" in data and isinstance(data["z"], (int, float)):
            if abs(z_claim - float(data["z"])) > 0.05:
                errors.append("claim_evidence_value_mismatch")
        else:
            if not _number_in_evidence(z_claim, data, quote):
                errors.append("claim_evidence_value_mismatch")

    val_claim_match = re.search(
        r"\bvalue\s*(?:was|showed a value of|is|of|:)?\s*(-?\d+(?:\.\d+)?)\b",
        statement,
        re.IGNORECASE,
    )
    if val_claim_match and not z_claim_match:
        val_claim = float(val_claim_match.group(1))
        if not _number_in_evidence(val_claim, data, quote):
            errors.append("claim_evidence_value_mismatch")

    return errors


def review_assessment(parsed: dict, bundle: dict) -> dict:
    evidence = {item["id"]: item for item in bundle["items"]}
    findings, issues = [], []
    claims = parsed.get("claims") or []
    for index, claim in enumerate(claims):
        refs = claim.get("evidence_ids", [])
        quotes = claim.get("quotes", {})
        errors = []
        statement = claim.get("statement")
        if not isinstance(statement, str) or not statement.strip():
            errors.append("missing_claim_statement")
        if not isinstance(refs, list) or not refs or not all(isinstance(r, str) for r in refs):
            errors.append("missing_or_invalid_evidence_ids")
            refs = []
        if not isinstance(quotes, dict):
            quotes = {}
        for ref in refs:
            if ref not in evidence:
                errors.append(f"unknown_or_excluded_evidence:{ref}")
                continue
            row = evidence[ref]
            raw_text = row["data"].get("text")
            text = raw_text if isinstance(raw_text, str) else canonical(row["data"])
            quote = quotes.get(ref)
            if not isinstance(quote, str) or not quote.strip() or quote not in text:
                errors.append(f"quote_not_in_evidence:{ref}")
            if isinstance(statement, str) and statement.strip():
                for inv_err in _check_claim_evidence_invariants(statement, row, quote):
                    errors.append(f"{inv_err}:{ref}")
        findings.append(
            {
                **claim,
                "claim_id": f"claim-{index + 1}",
                "reference_check": "needs_review" if errors else "references_match",
                "issues": errors,
            }
        )
        issues.extend(errors)
    if not claims:
        issues.append("No claim-level grounding supplied; prose requires manual verification")
    updates = parsed.get("hypothesis_updates") or []
    expected = bundle["hypotheses"]
    by_name = {}
    for update in updates:
        name = update.get("hypothesis")
        if name not in expected or name in by_name:
            issues.append("Unknown or duplicate hypothesis update")
            continue
        errors = []
        all_refs = []
        for key in ("supporting_evidence", "contradicting_evidence"):
            refs = update.get(key, [])
            if not isinstance(refs, list) or not all(isinstance(r, str) for r in refs):
                errors.append(f"Invalid {key}")
                continue
            all_refs.extend(refs)
            if any(ref not in evidence for ref in refs):
                errors.append(f"Unknown/excluded reference in {key}")
        change = update.get("change")
        if not isinstance(change, str) or change not in {
            "raised",
            "lowered",
            "unchanged",
            "unresolved",
        }:
            errors.append("Missing/invalid direction of change")
        if isinstance(change, str) and change in {"raised", "lowered"} and not all_refs:
            errors.append("Changed hypothesis has no evidence references")
        if not update.get("rationale"):
            errors.append("Missing rationale")
        by_name[name] = {**update, "issues": errors}
        issues.extend(errors)
    for name in expected:
        if name not in by_name:
            issues.append(f"Hypothesis not assessed: {name}")
            by_name[name] = {
                "hypothesis": name,
                "change": "unresolved",
                "rationale": "Model omitted this hypothesis; analyst review required",
                "issues": ["not_assessed"],
            }
    decision = parsed.get("decision", "")
    if decision not in {"wait", "collect_more", "send_up", "close"}:
        issues.append("No valid proposed collection decision")
    supplied_citations = parsed.get("citations") or []
    permitted_urls = {row["data"].get("url") for row in evidence.values()} - {None, ""}
    citations = []
    for citation in supplied_citations:
        ok = isinstance(citation.get("url"), str) and citation["url"] in permitted_urls
        citations.append(
            {**citation, "reference_check": "url_in_bundle" if ok else "unverified_url"}
        )
        if not ok:
            issues.append("Citation URL is not in admitted evidence")
    return {
        "schema_id": "assessment_review_v1",
        "bundle_id": bundle["bundle_id"],
        "status": "needs_review" if issues else "references_checked",
        "notice": "Reference/quotation checks are not factual verification or proof of entailment.",
        "initial_cue": bundle["initial_cue"],
        "claims": findings,
        "hypothesis_updates": list(by_name.values()),
        "proposed_decision": decision or "unresolved",
        "issues": issues,
        "citations": citations,
        "evidence": bundle["items"],
        "excluded": bundle["excluded"],
        "omitted": bundle["omitted"],
        "cautions": bundle["cautions"],
    }
