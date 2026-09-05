"""Durable analyst decisions and versioned briefs with bounded editorial synthesis."""

from __future__ import annotations

import hashlib
import html
import json
import os
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
            lines.append(json.dumps(proposal["quotes"], ensure_ascii=False, indent=2))
    for item in (review or {}).get("evidence", []):
        data = item.get("data", {})
        lines += [
            f"### Source {item['id']}",
            str(item.get("source_ref", "")),
            f"Available: {item.get('available_at', 'Unknown')} | "
            f"Retrieved: {item.get('retrieved_at', 'Unknown')}",
            f"Verification: {item.get('verification', 'Unknown')}",
            str(data.get("archive_url") or data.get("url") or ""),
            json.dumps(data, ensure_ascii=False, indent=2),
            "",
        ]
    lines += [
        "### Gaps, counterevidence and provenance cautions",
        json.dumps(
            {
                k: (review or {}).get(k)
                for k in (
                    "issues",
                    "cautions",
                    "excluded",
                    "omitted",
                    "research",
                    "hypothesis_updates",
                )
            },
            ensure_ascii=False,
            indent=2,
        ),
    ]
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
                f"# {title}\n\nVersion {number} | Prepared {now}\n"
                f"Scenario: {scenario} | Notice: {notice_id}\n"
                f"Information cutoff: {context.get('cutoff') or 'Not recorded'}\n\n"
                f"{editorial['body']}\n\n"
                + "## Editorial input references\n\n"
                + json.dumps(editorial["input_references"], ensure_ascii=False, indent=2)
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
                    "markdown": f"# {title}\n\nVersion {number} | Edited {now}\n"
                    f"Scenario: {scenario} | Notice: {notice_id}\n"
                    f"Information cutoff: {cutoff}\n\n"
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
            f"Signed off by {approval['reviewer']} at {approval['at']}"
            if approval
            else "DRAFT — awaiting sign-off"
        )
    )
    text = f"Status: {status}\nNot distributed.\n\n{brief['markdown']}"
    if format == "html":
        rendered = []
        for line in text.splitlines():
            safe = html.escape(line)
            if line.startswith("# "):
                rendered.append(f"<h1>{safe[2:]}</h1>")
            elif line.startswith("## "):
                rendered.append(f"<h2>{safe[3:]}</h2>")
            elif line.startswith("### "):
                rendered.append(f"<h3>{safe[4:]}</h3>")
            elif line.startswith("- "):
                rendered.append(f"<p class='finding'>• {safe[2:]}</p>")
            elif line:
                rendered.append(f"<p>{safe}</p>")
        return (
            "<!doctype html><html lang='en'><meta charset='utf-8'>"
            "<title>Intelligence assessment</title>"
            "<style>body{max-width:85ch;margin:3rem auto;padding:0 1.5rem;"
            "font:16px/1.6 system-ui;color:#182b39}p{overflow-wrap:anywhere}"
            "h1,h2,h3{line-height:1.25;break-after:avoid}.finding{padding-left:1rem}"
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
