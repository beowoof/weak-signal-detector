"""Check source references mechanically; never certify entailment or decide for the analyst."""

from __future__ import annotations

from wsf.evidence_bundle import canonical


def review_assessment(parsed: dict, bundle: dict) -> dict:
    evidence = {item["id"]: item for item in bundle["items"]}
    findings, issues = [], []
    claims = parsed.get("claims") or []
    for index, claim in enumerate(claims):
        refs = claim.get("evidence_ids", [])
        quotes = claim.get("quotes", {})
        errors = []
        if not isinstance(claim.get("statement"), str) or not claim["statement"].strip():
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
