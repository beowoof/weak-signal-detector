"""Analyst working assessment. Human-owned; the desk does not draft it."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from wsf.notice import Notice, load_notice, save_notice
from wsf.packet import Packet, packet_path
from wsf.scenario import scenario_directory

REPORT_SCHEMA = "report_v0"

SECTIONS: tuple[dict[str, str], ...] = (
    {
        "id": "assessment",
        "title": "Working assessment",
        "prompt": (
            "What do you make of this cue? State what you think is happening, how sure "
            "you are (AnCR), and what you are not claiming. A Watch product is a "
            "collection cue, not a finished assessment. Abnormal activity can be almost "
            "certain while the explanation remains unresolved."
        ),
    },
    {
        "id": "hypotheses",
        "title": "Hypotheses still open",
        "prompt": (
            "Note any explanation you would now downweight or raise, and on what "
            "evidence. You do not have to pick a winner. At Watch the desk holds the "
            "causal explanations at realistic possibility and does not rank preparation "
            "for overt action above exercise, readiness or reversible preparation."
        ),
    },
    {
        "id": "collected",
        "title": "What I collected",
        "prompt": (
            "What you actually looked at: sources, AOIs, dates. Include searches that "
            "returned nothing. Physical posture and official posture are first."
        ),
    },
    {
        "id": "findings",
        "title": "What that showed",
        "prompt": (
            "Findings from that collection. Separate observing the anomaly from "
            "explaining it. Null results belong here."
        ),
    },
    {
        "id": "decision",
        "title": "Decision",
        "prompt": (
            "Wait / collect more (say what) / send up / close as not significant. "
            "This is an effort decision, not a threat grade."
        ),
    },
    {
        "id": "change",
        "title": "What would change this",
        "prompt": (
            "Outstanding discriminators. What observation, if it arrived before the "
            "next cutoff, would move you."
        ),
    },
)

SECTION_IDS = tuple(item["id"] for item in SECTIONS)


class AnalystReport(BaseModel):
    schema_id: Literal["report_v0"] = REPORT_SCHEMA
    report_id: str
    notice_id: str
    packet_id: str | None = None
    scenario_id: str
    updated_at: datetime | None = None
    notes: str = ""
    sections: dict[str, str] = Field(default_factory=dict)


def report_id_for(notice_id: str) -> str:
    digest = hashlib.sha256(notice_id.encode()).hexdigest()[:12]
    return f"report-{digest}"


def report_directory(project_root: Path, scenario_id: str, report_id: str) -> Path:
    return scenario_directory(project_root, scenario_id) / "reports" / report_id


def report_path(project_root: Path, scenario_id: str, report_id: str) -> Path:
    return report_directory(project_root, scenario_id, report_id) / "report.json"


def _empty_sections() -> dict[str, str]:
    return {item["id"]: "" for item in SECTIONS}


def _load_packet(project_root: Path, notice: Notice) -> Packet | None:
    packet_id = notice.workflow.packet_id
    if not packet_id:
        return None
    path = packet_path(project_root, notice.trigger.scenario_id, packet_id)
    if not path.is_file():
        return None
    return Packet.model_validate_json(path.read_text(encoding="utf-8"))


def _context(notice: Notice, packet: Packet | None) -> dict[str, Any]:
    product = packet.product if packet else None
    start = notice.trigger.start.isoformat()
    end = notice.trigger.end.isoformat()
    return {
        "headline": product.headline if product else notice.notice_id,
        "period": product.period if product else f"{start} → {end}",
        "analytic_state": product.analytic_state_label if product else None,
        "confidence": product.confidence if product else None,
        "assessment": list(product.assessment or []) if product else [],
        "keys": list(product.keys or []) if product else [],
        "hypotheses": list(product.hypotheses or []) if product else [],
        "collection": list(product.collection or []) if product else [],
        "cutoff": (
            packet.clocks.knowledge_cutoff.isoformat()
            if packet is not None
            else None
        ),
        "mode": packet.clocks.mode if packet is not None else None,
        "prompts": [
            {"id": item["id"], "title": item["title"], "prompt": item["prompt"]}
            for item in SECTIONS
        ],
    }


def _template(report: AnalystReport, context: dict[str, Any]) -> str:
    lines = [
        f"# {context.get('headline') or report.notice_id}",
        "",
        f"{context.get('period') or ''} | "
        f"{context.get('analytic_state') or '—'} | "
        f"AnCR {context.get('confidence') or '—'}",
        "",
    ]
    if context.get("cutoff"):
        lines.extend(
            [f"Cutoff {context['cutoff']} ({context.get('mode') or ''}).", ""]
        )
    lines.extend(
        [
            "The desk has not selected a hypothesis. Edit this template. "
            "Skip anything you do not need.",
            "",
        ]
    )
    if context.get("keys"):
        lines.extend(["Keys: " + "; ".join(context["keys"]), ""])
    if context.get("assessment"):
        lines.extend(["Packet assessment", ""])
        for para in context["assessment"]:
            lines.append(f"- {para}")
        lines.append("")
    if context.get("hypotheses"):
        lines.extend(["Competing explanations (from the packet)", ""])
        for row in context["hypotheses"]:
            lines.append(
                f"- {row.get('hypothesis')} — {row.get('fit')}. "
                f"What would discriminate: {row.get('discriminate')}"
            )
        lines.append("")
    if context.get("collection"):
        lines.extend(["Collection requirements (from the packet)", ""])
        for row in context["collection"]:
            lines.append(f"{row.get('rank')}. {row.get('title')}. {row.get('why')}")
        lines.append("")
    by_id = {item["id"]: item for item in SECTIONS}
    for section_id in SECTION_IDS:
        meta = by_id[section_id]
        body = (report.sections.get(section_id) or "").strip()
        lines.extend([f"## {meta['title']}", ""])
        if body:
            lines.extend([body, ""])
        else:
            lines.extend([f"[{meta['prompt']}]", "", ""])
    return "\n".join(lines).rstrip() + "\n"


def _working_notes(report: AnalystReport, context: dict[str, Any]) -> tuple[str, bool]:
    saved = (report.notes or "").strip()
    if saved:
        return saved + "\n", False
    if any((report.sections.get(key) or "").strip() for key in SECTION_IDS):
        return _template(report, context), False
    return _template(report, context), True


def _payload(report: AnalystReport, context: dict[str, Any]) -> dict[str, Any]:
    notes, empty = _working_notes(report, context)
    data = report.model_dump(mode="json")
    data["context"] = context
    data["notes"] = notes
    data["markdown"] = notes
    data["empty"] = empty
    return data


def load_report(
    project_root: Path, scenario_id: str, notice_id: str
) -> dict[str, Any]:
    notice = load_notice(project_root, scenario_id, notice_id)
    packet = _load_packet(project_root, notice)
    report_id = notice.workflow.report_id or report_id_for(notice.notice_id)
    path = report_path(project_root, scenario_id, report_id)
    if path.is_file():
        report = AnalystReport.model_validate_json(path.read_text(encoding="utf-8"))
    else:
        report = AnalystReport(
            report_id=report_id,
            notice_id=notice.notice_id,
            packet_id=notice.workflow.packet_id,
            scenario_id=scenario_id,
            sections=_empty_sections(),
        )
    sections = _empty_sections()
    sections.update({key: report.sections.get(key) or "" for key in SECTION_IDS})
    report.sections = sections
    return _payload(report, _context(notice, packet))


def save_report(
    project_root: Path,
    scenario_id: str,
    notice_id: str,
    sections: dict[str, str] | None = None,
    *,
    notes: str | None = None,
) -> dict[str, Any]:
    notice = load_notice(project_root, scenario_id, notice_id)
    packet = _load_packet(project_root, notice)
    report_id = notice.workflow.report_id or report_id_for(notice.notice_id)
    path = report_path(project_root, scenario_id, report_id)
    if path.is_file():
        report = AnalystReport.model_validate_json(path.read_text(encoding="utf-8"))
    else:
        report = AnalystReport(
            report_id=report_id,
            notice_id=notice.notice_id,
            packet_id=notice.workflow.packet_id,
            scenario_id=scenario_id,
            sections=_empty_sections(),
        )
    merged = _empty_sections()
    merged.update({key: report.sections.get(key) or "" for key in SECTION_IDS})
    for key, value in (sections or {}).items():
        if key in SECTION_IDS:
            merged[key] = value
    report.sections = merged
    context = _context(notice, packet)
    if notes is not None:
        report.notes = notes
    elif sections:
        report.notes = _template(report, context)
    report.packet_id = notice.workflow.packet_id
    report.updated_at = datetime.now(UTC)
    directory = path.parent
    directory.mkdir(parents=True, exist_ok=True)
    path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    working, _empty = _working_notes(report, context)
    path.with_name("report.md").write_text(working, encoding="utf-8")
    if notice.workflow.report_id != report_id:
        notice.workflow.report_id = report_id
        notice.workflow.updated_at = report.updated_at
        save_notice(project_root, notice, overwrite_trigger=False)
    return _payload(report, context)
