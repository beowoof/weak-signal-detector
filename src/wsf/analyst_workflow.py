"""Durable analyst decisions and versioned briefs with bounded editorial synthesis."""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import shutil
import uuid
from datetime import UTC, datetime
from threading import RLock

from wsf.editorial_brief import synthesize
from wsf.notice import load_notice
from wsf.packet import packet_directory
from wsf.report import load_report, report_directory, report_id_for, save_report

_LOCK = RLock()
_PREPARING = set()
_PROGRESS = {}


def _brief_progress(root, scenario, notice_id, stage, completed):
    key = (str(root), scenario, notice_id)
    with _LOCK:
        now = datetime.now(UTC).isoformat()
        _PROGRESS[key] = {
            "started_at": _PROGRESS.get(key, {}).get("started_at", now),
            "updated_at": now,
            "stage": stage,
            "completed": completed,
            "total": 4,
        }


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def current_review(root, scenario, notice_id):
    notice = load_notice(root, scenario, notice_id)
    if not notice.workflow.packet_id:
        return None
    path = packet_directory(root, scenario, notice.workflow.packet_id) / "machine_draft.json"
    return json.loads(path.read_text()).get("review") if path.exists() else None


def _path(root, scenario, notice_id):
    notice = load_notice(root, scenario, notice_id)
    return (
        report_directory(root, scenario, notice.workflow.report_id or report_id_for(notice_id))
        / "workflow.json"
    )


def _read(root, scenario, notice_id):
    path = _path(root, scenario, notice_id)
    return (
        json.loads(path.read_text())
        if path.exists()
        else {
            "revision": 0,
            "decisions": {},
            "events": [],
            "briefs": [],
        }
    )


def proposals(review):
    if not review:
        return {}
    result = {c["claim_id"]: c for c in review.get("claims", [])}
    result.update(
        {f"hypothesis:{h['hypothesis']}": h for h in review.get("hypothesis_updates", [])}
    )
    result["decision"] = {"statement": review.get("proposed_decision", "unresolved")}
    return result


def _active(state, review):
    version = digest(review)
    return {k: v for k, v in state["decisions"].items() if v["review_version"] == version}


def _material(review, decisions):
    lines = ["## Reviewed findings"]
    for key, proposal in proposals(review).items():
        decision = decisions.get(key, {})
        if decision.get("status") not in {"accepted", "edited"}:
            continue
        statement = (
            decision.get("text") or proposal.get("statement") or proposal.get("rationale", "")
        )
        if key.startswith("hypothesis:"):
            statement = (
                f"{proposal['hypothesis']}: {proposal.get('change', 'unresolved')}. {statement}"
            )
        elif key == "decision":
            statement = f"Recommended next action: {statement}"
        refs = proposal.get("evidence_ids", []) or (
            proposal.get("supporting_evidence", []) + proposal.get("contradicting_evidence", [])
        )
        lines.append(f"- {statement}" + (f" [Sources: {', '.join(refs)}]" if refs else ""))
    lines += ["", "## Review limitations"]
    for key in proposals(review):
        decision = decisions.get(key, {})
        if decision.get("status") not in {"accepted", "edited"}:
            lines.append(
                f"- {key}: {decision.get('status', 'not reviewed')}. {decision.get('reason', '')}"
            )
    for issue in (review or {}).get("issues", []) + (review or {}).get("cautions", []):
        lines.append(f"- {issue}")
    lines += [
        "",
        "## Analyst judgement and implications",
        "",
        "## Alternative explanations and uncertainty",
        "",
        "## Next questions and collection priorities",
        "",
    ]
    return "\n".join(lines)


def load_workflow(root, scenario, notice_id):
    with _LOCK:
        state = _read(root, scenario, notice_id)
        review = current_review(root, scenario, notice_id)
        report = load_report(root, scenario, notice_id)
        active = _active(state, review)
        fingerprint = digest({"notes": report["notes"], "review": review, "decisions": active})
        briefs = [
            {**b, "stale": b["fingerprint"] != fingerprint}
            for b in state["briefs"]
            if not b.get("removed")
        ]
        return {
            **state,
            "briefs": briefs,
            "review_version": digest(review),
            "review": review,
            "active_decisions": active,
            "stale_decisions": len(state["decisions"]) - len(active),
            "assembly": _material(review, active),
            "fingerprint": fingerprint,
            "report": report,
            "preparing": (str(root), scenario, notice_id) in _PREPARING,
            "brief_progress": _PROGRESS.get((str(root), scenario, notice_id)),
        }


def _natural_sort_key(key: str):
    parts = re.split(r"(\d+)", key)
    return [int(p) if p.isdigit() else p.lower() for p in parts]


def _format_dt(val: str | None) -> str:
    if not val or not isinstance(val, str):
        return str(val or "")
    m = re.match(
        r"^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?$",
        val.strip(),
    )
    if m:
        return f"{m.group(1)} {m.group(2)} UTC"
    return val


def _clean_quote(quote: str) -> str:
    if not quote:
        return ""
    q = quote.strip()
    m = re.match(r'^"([^"]+)":\s*(.*)$', q)
    if m:
        key = m.group(1)
        val = m.group(2).strip()
        if val.startswith('"') and val.endswith('"') and len(val) >= 2:
            val = val[1:-1].strip()
        q = f"{key}: {val}"
    if (q.startswith('"') and q.endswith('"')) or (q.startswith("'") and q.endswith("'")):
        q = q[1:-1].strip()
    return q


def _clean_analyst_text(text: str) -> list[str]:
    if not text:
        return []
    cleaned = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL).strip()
    if not cleaned:
        return []
    raw_lines = [l.strip() for l in cleaned.splitlines() if l.strip()]
    if not raw_lines:
        return []
    template_headers = {
        "## analyst judgement and implications",
        "## alternative explanations and uncertainty",
        "## next questions and collection priorities",
        "## reviewed findings",
        "## review limitations",
    }
    if len(raw_lines) == 1 and raw_lines[0].lower() in template_headers:
        return []
    lines = []
    for line in raw_lines:
        if line.startswith("#"):
            h = line.lstrip("#").strip()
            lines.append(h if h.endswith(":") else f"{h}:")
        elif line.startswith(("- ", "* ", "• ")):
            lines.append(line[2:].strip())
        else:
            lines.append(line)
    return lines


def _render_input_references(input_references: dict) -> str:
    if not input_references:
        return "No input references recorded.\n"

    a_keys = [k for k in input_references if k.startswith("A") and k[1:].isdigit()]
    p_keys = [k for k in input_references if k.startswith("P") and k[1:].isdigit()]
    s_keys = [k for k in input_references if k.startswith("S") and k[1:].isdigit()]
    r_keys = [k for k in input_references if k.startswith("R") and k[1:].isdigit()]
    other_keys = [
        k
        for k in input_references
        if k not in a_keys and k not in p_keys and k not in s_keys and k not in r_keys
    ]

    a_keys.sort(key=_natural_sort_key)
    p_keys.sort(key=_natural_sort_key)
    s_keys.sort(key=_natural_sort_key)
    r_keys.sort(key=_natural_sort_key)
    other_keys.sort(key=_natural_sort_key)

    lines = []

    if a_keys:
        lines.append("### Analyst working assessment")
        for k in a_keys:
            val = input_references[k]
            text = val.get("text", "") if isinstance(val, dict) else str(val)
            parsed_lines = _clean_analyst_text(text)
            if not parsed_lines:
                continue
            lines.append(f"- **{k}**: {parsed_lines[0]}")
            for sub in parsed_lines[1:]:
                lines.append(f"  - {sub}")
        lines.append("")

    if p_keys:
        lines.append("### Reviewed proposals & findings")
        for k in p_keys:
            val = input_references[k]
            if isinstance(val, dict):
                prop_id = val.get("proposal_id", "")
                text = val.get("text", "").strip()
                sources = val.get("evidence_ids", []) or val.get("supporting_evidence", [])
                src_str = f" [Sources: {', '.join(sources)}]" if sources else ""
                reason = val.get("analyst_reason", "").strip()
                reason_str = f" — Analyst note: {reason}" if reason else ""
                prefix = f" (*{prop_id}*)" if prop_id else ""
                lines.append(f"- **{k}**{prefix}: {text}{src_str}{reason_str}")
            else:
                lines.append(f"- **{k}**: {val}")
        lines.append("")

    if s_keys:
        lines.append("### Source provenance")
        for k in s_keys:
            val = input_references[k]
            if isinstance(val, dict):
                ev_id = val.get("evidence_id", "")
                orig = val.get("originator", "")
                verif = val.get("verification", "unverified")
                avail = val.get("available_at", "")
                url = val.get("archive_url") or val.get("url")
                details = [f"Verification: {verif}"]
                if avail:
                    details.append(f"Available: {_format_dt(avail)}")
                if url:
                    details.append(f"URL: {url}")
                prefix = f" (*{ev_id}*)" if ev_id else ""
                lines.append(f"- **{k}**{prefix}: `{orig}` ({' | '.join(details)})")
            else:
                lines.append(f"- **{k}**: {val}")
        lines.append("")

    if r_keys:
        lines.append("### Review limitations & cautions")
        for k in r_keys:
            val = input_references[k]
            text = val.get("text") if isinstance(val, dict) else val
            if isinstance(text, dict):
                pid = text.get("proposal_id", "")
                status = text.get("status", "rejected")
                reason = text.get("reason", "").strip()
                lines.append(f"- **{k}** (*{pid} {status}*): {reason}")
            else:
                lines.append(f"- **{k}**: {str(text).strip()}")
        lines.append("")

    if other_keys:
        lines.append("### Additional references")
        for k in other_keys:
            val = input_references[k]
            if isinstance(val, dict) and "text" in val:
                lines.append(f"- **{k}**: {val['text']}")
            else:
                lines.append(f"- **{k}**: {val}")
        lines.append("")

    return "\n".join(lines).strip()


def _render_source_data(data: dict) -> list[str]:
    if not data or not isinstance(data, dict):
        return []
    lines = []
    kind = data.get("kind")
    if kind == "declared_posture":
        date = _format_dt(data.get("date", ""))
        gov = data.get("government", "")
        country = data.get("country", "")
        action = data.get("action", "")
        costly = data.get("costly")
        severity = data.get("severity")
        meta = f"{date} · {gov} ({country}) — Action: {action}"
        extra = []
        if costly is not None:
            extra.append(f"costly: {str(costly).lower()}")
        if severity is not None:
            extra.append(f"severity: {severity}")
        if extra:
            meta += f" ({', '.join(extra)})"
        lines.append(f"- **Posture event**: {meta}")
        if data.get("text"):
            lines.append(f'- **Statement**: "{_clean_quote(data["text"])}"')
        if data.get("category"):
            lines.append(f"- **Category**: {data['category']}")
    elif kind == "catalogue_granule":
        name = data.get("name", "")
        collection = data.get("collection", "")
        prod_type = data.get("product_type", "")
        aoi = f"{data.get('aoi_name', '')} ({data.get('aoi_id', '')})".strip()
        sensing = _format_dt(data.get("sensing_at") or data.get("sensing_date", ""))
        lines.append(f"- **Granule**: `{name}`")
        if collection or prod_type or aoi:
            lines.append(f"- **Platform & Sensor**: {collection} ({prod_type}) · AOI: {aoi}")
        if sensing:
            lines.append(f"- **Sensing time**: {sensing}")
    elif kind in {"observation", "coverage_hole"}:
        series_id = data.get("series_id", "")
        sub = data.get("shared_information_substrate") or data.get("relationship", "")
        sub_str = f" ({sub})" if sub else ""
        lines.append(f"- **Series**: `{series_id}`{sub_str}")
        if data.get("text"):
            lines.append(f"- **Reading**: {data['text']}")
        if data.get("geographic_scope"):
            lines.append(f"- **Scope**: {data['geographic_scope']}")
    elif "series" in data and isinstance(data["series"], list):
        day = _format_dt(data.get("day", ""))
        lines.append(f"- **Chronology record**: {day}")
        for s in data["series"]:
            sid = s.get("series_id", "")
            val = s.get("value")
            val_str = (
                f"{val:.2f}"
                if isinstance(val, float)
                else ("—" if val is None else str(val))
            )
            qual = s.get("quality", "ok")
            note = f" (note: {s['note']})" if s.get("note") else ""
            lines.append(f"  - `{sid}`: {val_str} [quality: {qual}]{note}")
    elif data.get("label") or (data.get("series_id") and "value" in data):
        label = data.get("label") or data.get("series_id", "")
        day = _format_dt(data.get("day", ""))
        val = data.get("value")
        val_str = (
            f"{val:.2f}"
            if isinstance(val, float)
            else ("—" if val is None else str(val))
        )
        qual = data.get("quality", "ok")
        orbit = f" · Orbit: {data['orbit']}" if data.get("orbit") else ""
        lines.append(f"- **Observation**: {label} ({day}) — Value: {val_str} [quality: {qual}]{orbit}")
    else:
        skip_keys = {"url", "archive_url"}
        for k, v in data.items():
            if k in skip_keys or v is None or v == "" or v == []:
                continue
            label = k.replace("_", " ").capitalize()
            if isinstance(v, (str, int, float, bool)):
                lines.append(
                    f"- **{label}**: {_format_dt(str(v)) if any(t in k for t in ('time', 'date', 'at')) else v}"
                )
            elif isinstance(v, list) and all(isinstance(x, str) for x in v):
                lines.append(f"- **{label}**: {', '.join(v)}")
            else:
                lines.append(f"- **{label}**: {json.dumps(v, ensure_ascii=False)}")
    return lines


def _render_gaps_and_cautions(review: dict) -> list[str]:
    lines = [
        "### Gaps, counterevidence and provenance cautions",
        "",
        "#### Analytical issues & validation checks",
    ]
    issues = (review or {}).get("issues", [])
    if issues:
        for issue in issues:
            lines.append(f"- {issue}")
    else:
        lines.append("- None identified.")
    lines.append("")

    cautions = (review or {}).get("cautions", [])
    lines.append("#### Provenance cautions & context limits")
    if cautions:
        for caution in cautions:
            lines.append(f"- {caution}")
    else:
        lines.append("- None identified.")
    lines.append("")

    excluded = (review or {}).get("excluded", [])
    lines.append("#### Excluded evidence")
    if excluded:
        for item in excluded:
            eid = item.get("id", "unknown")
            kind = item.get("kind", "")
            reason = item.get("reason", "unspecified")
            ref = item.get("source_ref", "")
            ref_str = f" (ref: `{ref}`)" if ref else ""
            lines.append(f"- **`{eid}`** (*{kind}*): Excluded — {reason}{ref_str}")
    else:
        lines.append("- None excluded.")
    lines.append("")

    omitted = (review or {}).get("omitted", [])
    lines.append("#### Omitted evidence (character / budget limits)")
    if omitted:
        for item in omitted:
            eid = item.get("id", "unknown")
            kind = item.get("kind", "")
            reason = item.get("reason", "unspecified")
            ref = item.get("source_ref", "")
            ref_str = f" (ref: `{ref}`)" if ref else ""
            lines.append(f"- **`{eid}`** (*{kind}*): Omitted — {reason}{ref_str}")
    else:
        lines.append("- None omitted.")
    lines.append("")

    research = (review or {}).get("research", {})
    if research:
        lines.append("#### Research execution & source retrieval trail")
        usage = research.get("usage", {})
        if usage:
            u_parts = []
            if "search_requests" in usage:
                u_parts.append(f"{usage['search_requests']} search requests")
            if "document_attempts" in usage:
                u_parts.append(f"{usage['document_attempts']} document attempts")
            if "elapsed_s" in usage:
                u_parts.append(f"{usage['elapsed_s']}s elapsed")
            u_str = f"Usage: {', '.join(u_parts)}" if u_parts else "Usage: completed"
            if research.get("limit_reached"):
                u_str += f". Limit reached: `{research['limit_reached']}`"
            lines.append(f"- {u_str}")
        requests = research.get("requests", {})
        if requests:
            for req_id, details in requests.items():
                status = details.get("status", "")
                if "result_count" in details:
                    lines.append(f"  - `{req_id}`: {status} ({details['result_count']} results)")
                elif "reason" in details:
                    lines.append(f"  - `{req_id}`: {status} — {details['reason']}")
                else:
                    lines.append(f"  - `{req_id}`: {status}")
        lines.append("")

    hyp_updates = (review or {}).get("hypothesis_updates", [])
    if hyp_updates:
        lines.append("#### Competing hypothesis updates")
        for h in hyp_updates:
            hyp = h.get("hypothesis", "")
            change = h.get("change", "unresolved")
            conf = h.get("confidence")
            conf_str = f" (Confidence: {conf})" if conf else ""
            lines.append(f"- **{hyp}**: **{change}**{conf_str}")
            if h.get("rationale"):
                lines.append(f"  - *Rationale*: {h['rationale']}")
            if h.get("supporting_evidence"):
                lines.append(f"  - *Supporting evidence*: {', '.join(h['supporting_evidence'])}")
            if h.get("contradicting_evidence"):
                lines.append(f"  - *Contradicting evidence*: {', '.join(h['contradicting_evidence'])}")
            if h.get("unknowns"):
                lines.append(f"  - *Unknowns*: {'; '.join(h['unknowns'])}")
            if h.get("discriminators"):
                lines.append(f"  - *Discriminators*: {'; '.join(h['discriminators'])}")
        lines.append("")

    return lines


def _annex(review, decisions):
    lines = [
        "## Evidence and review annex",
        "",
        "Public-source assessment. Reference matching does not certify "
        "factual truth or entailment.",
        "",
    ]
    for key, proposal in proposals(review).items():
        decision = decisions.get(key, {})
        lines += [
            f"### {key} — {decision.get('status', 'not reviewed')}",
            str(proposal.get("statement") or proposal.get("rationale", "")),
            f"Analyst rationale: {decision.get('reason') or 'Not supplied'}",
            "",
        ]
        if proposal.get("quotes"):
            for ev_id, quote in proposal["quotes"].items():
                lines.append(f'- **Cited quote ({ev_id})**: "{_clean_quote(quote)}"')
            lines.append("")
        if key.startswith("hypothesis:"):
            meta = []
            if proposal.get("confidence"):
                meta.append(f"- **Confidence**: {proposal['confidence']}")
            if proposal.get("supporting_evidence"):
                meta.append(f"- **Supporting evidence**: {', '.join(proposal['supporting_evidence'])}")
            if proposal.get("contradicting_evidence"):
                meta.append(f"- **Contradicting evidence**: {', '.join(proposal['contradicting_evidence'])}")
            if proposal.get("unknowns"):
                meta.append(f"- **Unknowns**: {'; '.join(proposal['unknowns'])}")
            if proposal.get("discriminators"):
                meta.append(f"- **Discriminators**: {'; '.join(proposal['discriminators'])}")
            if meta:
                lines.extend(meta)
                lines.append("")
    for item in (review or {}).get("evidence", []):
        data = item.get("data", {})
        lines += [
            f"### Source {item['id']}",
            str(item.get("source_ref", "")),
            f"Available: {_format_dt(item.get('available_at', 'Unknown'))} | "
            f"Retrieved: {_format_dt(item.get('retrieved_at', 'Unknown'))}",
            f"Verification: {item.get('verification', 'Unknown')}",
        ]
        url = data.get("archive_url") or data.get("url")
        if url:
            lines.append(str(url))
        rendered_data = _render_source_data(data)
        if rendered_data:
            lines.extend(rendered_data)
        lines.append("")
    lines.extend(_render_gaps_and_cautions(review))
    return "\n".join(lines)


def update_workflow(root, scenario, notice_id, *, revision, action, review_version="", **fields):
    key = (str(root), scenario, notice_id)
    if action == "prepare":
        with _LOCK:
            if key in _PREPARING:
                raise ValueError("Brief synthesis is already running for this notice")
            _PREPARING.add(key)
            _PROGRESS.pop(key, None)
            _brief_progress(root, scenario, notice_id, "Preparing assessment and sources", 0)
    try:
        result = _update_workflow(
            root,
            scenario,
            notice_id,
            revision=revision,
            action=action,
            review_version=review_version,
            **fields,
        )
    except Exception:
        if action == "prepare":
            _brief_progress(root, scenario, notice_id, "Failed — existing briefs retained", 0)
        raise
    finally:
        if action == "prepare":
            with _LOCK:
                _PREPARING.discard(key)
    if action == "prepare":
        _brief_progress(root, scenario, notice_id, "Complete — ready for review", 4)
        result["preparing"] = False
        result["brief_progress"] = _PROGRESS[key]
    return result


def _update_workflow(root, scenario, notice_id, *, revision, action, review_version="", **fields):
    # Never hold the workflow lock across a potentially slow model call.
    editorial = None
    if action == "prepare":
        with _LOCK:
            initial = load_workflow(root, scenario, notice_id)
            if initial["revision"] != revision:
                raise ValueError("Workflow changed. Reload before applying this action.")
            report = initial["report"]
            if report["empty"] or not report["notes"].strip():
                raise ValueError("Save your working assessment before preparing a brief")
        editorial = synthesize(
            root,
            _path(root, scenario, notice_id).parent,
            report,
            initial["review"],
            initial["active_decisions"],
            progress=lambda stage, completed: _brief_progress(
                root, scenario, notice_id, stage, completed
            ),
        )
        _brief_progress(root, scenario, notice_id, "Saving the brief and evidence annex", 3)
    with _LOCK:
        view = load_workflow(root, scenario, notice_id)
        if revision != view["revision"]:
            raise ValueError("Workflow changed. Reload before applying this action.")
        if editorial and view["fingerprint"] != initial["fingerprint"]:
            raise ValueError(
                "Assessment changed during synthesis; prepare again from current notes"
            )
        state = _read(root, scenario, notice_id)
        now = datetime.now(UTC).isoformat()
        event = {"at": now, "action": action}
        if action == "review":
            if review_version != view["review_version"]:
                raise ValueError("Evidence or proposals changed. Review the current version first.")
            key, status = fields.get("proposal_id"), fields.get("status")
            if key not in proposals(view["review"]) or status not in {
                "accepted",
                "rejected",
                "edited",
                "unresolved",
            }:
                raise ValueError("Unknown proposal or review status")
            reason, text = fields.get("reason", "").strip(), fields.get("text", "").strip()
            if status in {"rejected", "edited", "unresolved"} and not reason:
                raise ValueError("Record a reason for this decision")
            if status == "edited" and not text:
                raise ValueError("Edited proposals need replacement text")
            decision = {
                "status": status,
                "text": text if status == "edited" else "",
                "reason": reason,
                "at": now,
                "review_version": review_version,
            }
            state["decisions"][key] = decision
            event.update(
                proposal_id=key, decision=decision, proposal=proposals(view["review"])[key]
            )
        elif action == "prepare":
            report = load_report(root, scenario, notice_id)
            if report["empty"] or not report["notes"].strip():
                raise ValueError("Save your working assessment before preparing a brief")
            title = fields.get("title", "").strip() or "Public-source intelligence assessment"
            number = state.get("next_version", len(state["briefs"]) + 1)
            state["next_version"] = number + 1
            context = report.get("context", {})
            markdown = (
                f"# {title}\n\nVersion {number} | Prepared {_format_dt(now)}\n"
                f"Scenario: {scenario} | Notice: {notice_id}\n"
                f"Information cutoff: {_format_dt(context.get('cutoff') or 'Not recorded')}\n\n"
                f"{editorial['body']}\n\n"
                + "## Editorial input references\n\n"
                + _render_input_references(editorial["input_references"])
                + "\n\n"
                + _annex(view["review"], view["active_decisions"])
            )
            state["briefs"].append(
                {
                    "version": number,
                    "created_at": now,
                    "title": title,
                    "fingerprint": view["fingerprint"],
                    "markdown": markdown,
                    "review_version": view["review_version"],
                    "signed_off": None,
                    "editorial": editorial,
                    "body": editorial["body"],
                    "annex": markdown.split("## Editorial input references", 1)[1],
                }
            )
            event["version"] = number
        elif action == "revise_brief":
            source = next(
                (
                    b
                    for b in state["briefs"]
                    if b["version"] == fields.get("version") and not b.get("removed")
                ),
                None,
            )
            if not source or source["fingerprint"] != view["fingerprint"]:
                raise ValueError("Brief is missing or stale; prepare a current version first")
            body = fields.get("text", "").strip()
            if not body:
                raise ValueError("Brief text cannot be empty")
            number = state.get("next_version", len(state["briefs"]) + 1)
            state["next_version"] = number + 1
            title = fields.get("title", "").strip() or source["title"]
            annex = source.get("annex", "")
            cutoff = view["report"].get("context", {}).get("cutoff") or "Not recorded"
            state["briefs"].append(
                {
                    **source,
                    "version": number,
                    "created_at": now,
                    "title": title,
                    "body": body,
                    "signed_off": None,
                    "parent_version": source["version"],
                    "markdown": f"# {title}\n\nVersion {number} | Edited {_format_dt(now)}\n"
                    f"Scenario: {scenario} | Notice: {notice_id}\n"
                    f"Information cutoff: {_format_dt(cutoff)}\n\n"
                    f"{body}\n\n" + "## Editorial input references" + annex,
                }
            )
            event["version"] = number
        elif action == "remove_brief":
            brief = next(
                (
                    b
                    for b in state["briefs"]
                    if b["version"] == fields.get("version") and not b.get("removed")
                ),
                None,
            )
            if not brief:
                raise ValueError("Unknown brief version")
            brief["removed"] = now
            event["version"] = brief["version"]
        elif action == "reset":
            if not fields.get("acknowledged"):
                raise ValueError("Confirm reset of this assessment, decisions and briefs")
            directory = _path(root, scenario, notice_id).parent
            archive = directory / "resets" / uuid.uuid4().hex
            archive.mkdir(parents=True)
            for filename in ("report.json", "report.md", "workflow.json"):
                source = directory / filename
                if source.exists():
                    shutil.copy2(source, archive / filename)
            save_report(
                root,
                scenario,
                notice_id,
                sections={
                    k: ""
                    for k in (
                        "assessment",
                        "hypotheses",
                        "collected",
                        "findings",
                        "decision",
                        "change",
                    )
                },
                notes="",
            )
            state.setdefault("next_version", len(state["briefs"]) + 1)
            state["decisions"], state["briefs"] = {}, []
            event["archive"] = archive.name
        elif action == "sign_off":
            version = fields.get("version")
            brief = next(
                (b for b in state["briefs"] if b["version"] == version and not b.get("removed")),
                None,
            )
            if not brief or brief["fingerprint"] != view["fingerprint"]:
                raise ValueError(
                    "This brief is stale. Prepare a new version from the saved assessment"
                )
            missing = set(proposals(view["review"])) - set(view["active_decisions"])
            if missing:
                raise ValueError("Review every proposal or explicitly mark it unresolved first")
            reviewer = fields.get("reviewer", "").strip()
            if not reviewer or not fields.get("acknowledged"):
                raise ValueError(
                    "Name the reviewer and confirm sources, caveats and assessment were checked"
                )
            if brief["signed_off"]:
                raise ValueError("This version is already signed off")
            brief["signed_off"] = {"reviewer": reviewer, "at": now}
            event.update(version=version, reviewer=reviewer)
        else:
            raise ValueError("Unknown workflow action")
        state["events"].append(event)
        state["revision"] += 1
        path = _path(root, scenario, notice_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n")
        os.replace(temporary, path)
        return load_workflow(root, scenario, notice_id)


def export_brief(root, scenario, notice_id, version, format):
    view = load_workflow(root, scenario, notice_id)
    brief = next(
        (b for b in view["briefs"] if b["version"] == version and not b.get("removed")), None
    )
    if not brief:
        raise ValueError("Unknown brief version")
    approval = brief["signed_off"]
    status = (
        "STALE — assessment or review has changed"
        if brief["stale"]
        else (
            f"Signed off by {approval['reviewer']} at {_format_dt(approval['at'])}"
            if approval
            else "DRAFT — awaiting sign-off"
        )
    )
    markdown = brief["markdown"]
    markdown = re.sub(
        r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?(?!\s*UTC)",
        r"\1 \2 UTC",
        markdown,
    )
    text = f"Status: {status}\nNot distributed.\n\n{markdown}"
    if format == "html":
        def _format_inline(safe: str) -> str:
            safe = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", safe)
            safe = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<em>\1</em>", safe)
            safe = re.sub(r"`([^`]+?)`", r"<code>\1</code>", safe)
            return safe

        rendered = []
        for line in text.splitlines():
            if line.startswith("# "):
                content = _format_inline(html.escape(line[2:]))
                rendered.append(f"<h1>{content}</h1>")
            elif line.startswith("## "):
                content = _format_inline(html.escape(line[3:]))
                rendered.append(f"<h2>{content}</h2>")
            elif line.startswith("### "):
                content = _format_inline(html.escape(line[4:]))
                rendered.append(f"<h3>{content}</h3>")
            elif line.startswith("#### "):
                content = _format_inline(html.escape(line[5:]))
                rendered.append(f"<h4>{content}</h4>")
            elif line.startswith("  - "):
                content = _format_inline(html.escape(line[4:]))
                rendered.append(f"<p class='finding finding-sub'>• {content}</p>")
            elif line.startswith("- "):
                content = _format_inline(html.escape(line[2:]))
                rendered.append(f"<p class='finding'>• {content}</p>")
            elif line:
                content = _format_inline(html.escape(line))
                rendered.append(f"<p>{content}</p>")
        return (
            "<!doctype html><html lang='en'><meta charset='utf-8'>"
            "<title>Intelligence assessment</title>"
            "<style>body{max-width:85ch;margin:3rem auto;padding:0 1.5rem;"
            "font:16px/1.6 system-ui;color:#182b39}p{overflow-wrap:anywhere}"
            "h1,h2,h3,h4{line-height:1.25;break-after:avoid}"
            ".finding{padding-left:1rem;margin:0.25rem 0}"
            ".finding-sub{padding-left:2.5rem;margin:0.2rem 0}"
            "code{font-family:monospace;font-size:0.9em;background:#f0f2f5;padding:0.1em 0.3em;border-radius:3px}"
            "@media print{body{margin:0;max-width:none}h2{margin-top:2rem}}</style><body>"
            + "\n".join(rendered)
            + "</body></html>"
        )
    if format != "md":
        raise ValueError("Unsupported export format")
    return text


def clean_notes(notes):
    return (
        notes.replace("<!-- reviewed-material:start -->", "")
        .replace("<!-- reviewed-material:end -->", "")
        .strip()
    )
