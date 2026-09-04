"""Bounded machine draft of the analyst working assessment.

Does not open notices, does not vote, does not overwrite a saved human report
unless apply=True and that report is still empty.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import textwrap
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, ValidationError

from wsf.collect import SEARCH, load_collection, run_collection
from wsf.connectors.http import HttpTransport, UrllibTransport, post_with_retry
from wsf.connectors.tavily import forbidden_terms
from wsf.env import load_project_env
from wsf.notice import load_notice
from wsf.packet import Packet, packet_directory, packet_path
from wsf.report import SECTIONS, load_report, save_report

DRAFT_SCHEMA = "desk_draft_v0"


@dataclass(frozen=True)
class OllamaConfig:
    base_url: str
    model: str
    timeout: float = 900
    max_tokens: int = 4096
    num_ctx: int = 32768

    @property
    def options(self) -> dict[str, Any]:
        return {
            "temperature": 0,
            "seed": 42,
            "num_predict": self.max_tokens,
            "num_ctx": self.num_ctx,
        }


class DraftOutput(BaseModel):
    notes: str = ""
    sections: dict[str, str] = Field(default_factory=dict)
    citations: list[dict[str, Any]] = Field(default_factory=list)
    ancr: str | None = None
    leakage_self_check: str = ""


def _section_markdown(value: Any, *, depth: int = 0) -> str:
    """Render model-authored section structure without inventing assessment text."""
    if depth > 8:
        raise ValueError("section nesting exceeds 8 levels")
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        items = []
        for item in value:
            rendered = _section_markdown(item, depth=depth + 1).strip()
            if rendered:
                items.append("- " + textwrap.indent(rendered, "  ").lstrip())
        return "\n".join(items)
    if isinstance(value, dict):
        fields = []
        for key, item in value.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError("section object keys must be non-empty strings")
            # Named scalar measurements are meaningful; bare scalar sections are not.
            if isinstance(item, (bool, int, float)):
                rendered = json.dumps(item, allow_nan=False)
            elif item is None:
                rendered = "null"
            else:
                rendered = _section_markdown(item, depth=depth + 1).strip()
            if rendered:
                label = key.replace("_", " ")
                separator = "\n\n" if isinstance(item, (list, dict)) else " "
                fields.append(f"**{label}:**{separator}{rendered}")
        return "\n\n".join(fields)
    raise ValueError("section content must be text, a list of text/objects, or an object")


def _normalise_sections(payload: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    sections = payload.get("sections")
    if not isinstance(sections, dict):
        return payload, []  # Let the strict schema reject an invalid sections container.
    converted = []
    normalised = {}
    for key, value in sections.items():
        normalised[key] = _section_markdown(value)
        if not isinstance(value, str):
            converted.append(key)
    return {**payload, "sections": normalised}, converted


_LEAKAGE_EXTRA = (
    "full-scale invasion",
    "invaded ukraine on 24",
    "24 february 2022 invasion",
    "february 24 invasion",
)


def ollama_config(project_root: Path) -> OllamaConfig:
    load_project_env(project_root)
    base = (os.environ.get("OLLAMA_BASE_URL") or "http://localhost:11434").strip().rstrip("/")
    model = (os.environ.get("OLLAMA_MODEL") or "").strip()
    if not model:
        raise ValueError("OLLAMA_MODEL is not set; configure it in .env for desk drafting")
    parts = urlsplit(base)
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.query or parts.fragment:
        raise ValueError("OLLAMA_BASE_URL must be an HTTP(S) server base URL")
    if parts.username or parts.password:
        raise ValueError("OLLAMA_BASE_URL must not contain embedded credentials")
    if parts.path not in {"", "/"}:
        raise ValueError("OLLAMA_BASE_URL must be the server root, without /api or /v1")
    try:
        timeout = float(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "900"))
        tokens = int(os.environ.get("OLLAMA_MAX_OUTPUT_TOKENS", "4096"))
        context = int(os.environ.get("OLLAMA_NUM_CTX", "32768"))
        if not math.isfinite(timeout) or timeout <= 0 or tokens <= 0 or context <= tokens:
            raise ValueError
    except ValueError as exc:
        raise ValueError(
            "Ollama limits must be positive numbers and OLLAMA_NUM_CTX must exceed "
            "OLLAMA_MAX_OUTPUT_TOKENS"
        ) from exc
    return OllamaConfig(base, model, timeout, tokens, context)


def _extract_json(text: str) -> dict[str, Any]:
    blob = text.strip()
    if blob.startswith("```"):
        blob = re.sub(r"^```(?:json)?\s*", "", blob)
        blob = re.sub(r"\s*```$", "", blob)
    try:
        value = json.loads(blob)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", blob, flags=re.DOTALL)
    if not match:
        raise ValueError("model did not return JSON")
    value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise ValueError("model JSON was not an object")
    return value


def _leakage_hits(text: str, forbidden: list[str]) -> list[str]:
    lowered = text.lower()
    found: list[str] = []
    for term in [*forbidden, *_LEAKAGE_EXTRA]:
        if term and term.lower() in lowered and term not in found:
            found.append(term)
    return found


def _system_prompt(cutoff: str, forbidden: list[str]) -> str:
    banned = ", ".join(forbidden) if forbidden else "(none listed)"
    return (
        "You are a collection-cueing desk officer. You write a working assessment "
        "an analyst will edit. You do not determine intent. You do not open notices. "
        "You do not change scores.\n"
        f"Knowledge cutoff is {cutoff}. Events after that instant are unknown. "
        "Do not mention later outcomes. Do not use pretrained knowledge of what "
        "happened after the cutoff.\n"
        "Cite only the packet and the supplied search hits. If a fact is not there, "
        "say it is unknown. Significance of individual evidence items stays unassigned.\n"
        "Use PHIA Probability Yardstick language and AnCR (Low/Moderate/High). "
        "At Watch, keep causal explanations at realistic possibility unless the "
        "packet already ranked them. Every hypothesis in the packet must appear.\n"
        f"Forbidden outcome language: {banned}.\n"
        "Return JSON only with keys: notes (markdown for the working assessment), "
        "sections (object with assessment, hypotheses, collected, findings, "
        "decision, change), citations (list of {title,url,published}), "
        "ancr, leakage_self_check (string). "
        "notes and every value in sections must be Markdown strings, not arrays or objects. "
        'For example: "sections": {"hypotheses": "- Routine activity: unresolved", '
        '"collected": "- Source and observation", "findings": "- Finding and limitation"}. '
        "Use an empty string for an empty section."
    )


def _user_payload(packet: Packet, collection: dict[str, Any]) -> str:
    product = packet.product
    search_hits: list[dict[str, Any]] = []
    official_notes: list[str] = []
    for task in collection.get("tasks") or []:
        if task.get("kind") == SEARCH:
            search_hits.extend(task.get("items") or [])
        if task.get("kind") == "official_pack":
            official_notes.extend(task.get("notes") or [])
    body = {
        "cutoff": packet.clocks.knowledge_cutoff.isoformat(),
        "mode": packet.clocks.mode,
        "headline": product.headline if product else None,
        "analytic_state": product.analytic_state_label if product else None,
        "confidence": product.confidence if product else None,
        "assessment": list(product.assessment or []) if product else [],
        "watchlist": list(product.watchlist or []) if product else [],
        "hypotheses": list(product.hypotheses or []) if product else [],
        "collection_requirements": list(product.collection or []) if product else [],
        "availability_warnings": list(product.availability_warnings or []) if product else [],
        "search_hits": search_hits[:24],
        "official_pack_notes": official_notes[:12],
        "instruction": (
            "Write the working assessment as of cutoff. Recommend a collection "
            "decision (wait / collect more / send up / close), not a threat grade."
        ),
    }
    return json.dumps(body, indent=2, default=str)


def complete_chat(
    *,
    config: OllamaConfig,
    system: str,
    user: str,
    transport: HttpTransport | None = None,
    progress: Callable[[str, int], None] | None = None,
) -> dict[str, Any]:
    payload = {
        "model": config.model,
        "stream": False,
        "think": False,
        "format": "json",
        "options": config.options,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    headers = {
        "Content-Type": "application/json",
    }
    client = transport or UrllibTransport()

    def request():
        try:
            return post_with_retry(
                client,
                config.base_url + "/api/chat",
                headers=headers,
                data=json.dumps(payload).encode(),
                timeout=config.timeout,
                # Do not silently run a second costly generation after an uncertain timeout.
                attempts=1,
            )
        except (TimeoutError, OSError) as exc:
            raise ValueError(
                f"Ollama request failed for {config.model} at {config.base_url}. "
                "Check that the server is running and reachable; from Docker, localhost "
                "means the container (use a host-reachable OLLAMA_BASE_URL). "
                "For slow local generation, increase OLLAMA_TIMEOUT_SECONDS."
            ) from exc

    response = request()
    output_mode = "native_json"
    # An explicit capability rejection is safe to resubmit; an uncertain timeout is not.
    if response.status == 501:
        try:
            rejected = json.loads(response.body)
        except (ValueError, UnicodeError):
            rejected = None
        if (
            isinstance(rejected, dict)
            and rejected.get("error") == "structured output is unavailable"
        ):
            payload.pop("format")
            output_mode = "prompt_json"
            if progress:
                progress("Ollama generating (prompt JSON; native structured output unavailable)", 2)
            response = request()
    if response.status >= 400:
        raise ValueError(
            f"Ollama HTTP {response.status} for model {config.model}: "
            f"{response.body[:300].decode('utf-8', errors='replace')}"
        )
    try:
        body = json.loads(response.body.decode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise ValueError("Ollama returned an invalid JSON response") from exc
    if not isinstance(body, dict):
        raise ValueError("Ollama response must be an object")
    if body.get("error"):
        raise ValueError(f"Ollama error: {str(body['error'])[:300]}")
    if body.get("done") is not True or body.get("done_reason") in {"length", "max_tokens"}:
        raise ValueError(
            "Ollama returned an incomplete or token-limited draft; existing drafts "
            "were kept. Increase OLLAMA_MAX_OUTPUT_TOKENS if needed."
        )
    message = body.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Ollama returned empty content")
    body["output_mode"] = output_mode
    return body


def _compose_notes(parsed: dict[str, Any], packet: Packet) -> str:
    notes = str(parsed.get("notes") or "").strip()
    if notes:
        return notes + "\n"
    product = packet.product
    lines = [
        f"# {product.headline if product else 'Working assessment'}",
        "",
        "Machine draft. Edit before saving. The desk has not selected a hypothesis.",
        "",
    ]
    sections = parsed.get("sections") or {}
    for item in SECTIONS:
        body = str(sections.get(item["id"]) or "").strip()
        lines.extend([f"## {item['title']}", "", body or f"[{item['prompt']}]", ""])
    return "\n".join(lines).rstrip() + "\n"


def run_desk_draft(
    project_root: Path,
    scenario_id: str,
    notice_id: str,
    *,
    replay: bool = False,
    search: bool = True,
    apply: bool = False,
    search_transport: HttpTransport | None = None,
    chat_transport: HttpTransport | None = None,
    progress: Callable[[str, int], None] | None = None,
) -> dict[str, Any]:
    def report(stage: str, completed: int) -> None:
        if progress:
            progress(stage, completed)

    report("Preparing packet and configuration", 0)
    # Configuration errors must not first spend search credits or mutate collection.
    config = ollama_config(project_root)
    notice = load_notice(project_root, scenario_id, notice_id)
    if search:
        report("Searching cutoff-dated open sources", 1)
        run_collection(
            project_root,
            scenario_id,
            notice_id,
            kinds=[SEARCH],
            replay=replay,
            transport=search_transport,
        )
        notice = load_notice(project_root, scenario_id, notice_id)
    if not notice.workflow.packet_id:
        raise ValueError("notice has no packet; build the brief first")
    packet_id = notice.workflow.packet_id
    packet = Packet.model_validate_json(
        packet_path(project_root, scenario_id, packet_id).read_text(encoding="utf-8")
    )
    collection = load_collection(project_root, scenario_id, packet_id)
    forbidden = forbidden_terms(project_root, scenario_id)
    cutoff = packet.clocks.knowledge_cutoff.isoformat()
    system = _system_prompt(cutoff, forbidden)
    user = _user_payload(packet, collection)
    report("Ollama loading / generating (completion time unknown)", 2)
    completion = complete_chat(
        config=config,
        system=system,
        user=user,
        transport=chat_transport,
        progress=progress,
    )
    report("Validating assessment structure and cutoff language", 3)
    raw = completion["message"]["content"]
    try:
        normalised, converted_sections = _normalise_sections(_extract_json(raw))
        parsed = DraftOutput.model_validate(normalised).model_dump()
    except (ValueError, ValidationError) as exc:
        raise ValueError(f"Ollama draft did not match the assessment structure: {exc}") from exc
    if not parsed["notes"].strip() and not any(
        parsed["sections"].get(section["id"], "").strip() for section in SECTIONS
    ):
        raise ValueError("Ollama draft contained no assessment text; existing drafts were kept")
    notes = _compose_notes(parsed, packet)
    # Sections are saved even when a standalone notes body takes display precedence.
    leakage = _leakage_hits("\n".join([notes, *parsed["sections"].values()]), forbidden)
    created = datetime.now(UTC)
    record = {
        "schema_id": DRAFT_SCHEMA,
        "notice_id": notice_id,
        "packet_id": packet_id,
        "scenario_id": scenario_id,
        "created_at": created.isoformat(),
        "provider": "ollama",
        "model": config.model,
        "base_url": config.base_url,
        "generation_options": config.options,
        "output_mode": completion["output_mode"],
        "prompt_sha256": hashlib.sha256((system + "\n" + user).encode()).hexdigest(),
        "raw_response": raw,
        "normalisation": {
            "method": "section_markdown_v1",
            "converted_sections": converted_sections,
        },
        "generation": {
            key: completion[key]
            for key in (
                "model",
                "done_reason",
                "total_duration",
                "load_duration",
                "prompt_eval_count",
                "prompt_eval_duration",
                "eval_count",
                "eval_duration",
            )
            if key in completion
        },
        "knowledge_cutoff": cutoff,
        "mode": packet.clocks.mode,
        "notes": notes,
        "sections": parsed.get("sections") or {},
        "citations": parsed.get("citations") or [],
        "ancr": parsed.get("ancr"),
        "leakage": leakage,
        "votes": False,
    }
    directory = packet_directory(project_root, scenario_id, packet_id)
    report("Saving draft artefacts", 4)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "machine_draft.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8"
    )
    (directory / "machine_draft.md").write_text(notes, encoding="utf-8")
    applied = False
    if apply and not leakage:
        existing = load_report(project_root, scenario_id, notice_id)
        if existing.get("empty"):
            save_report(project_root, scenario_id, notice_id, notes=notes)
            applied = True
    report("Complete — leakage flagged; review required" if leakage else "Complete", 5)
    return {
        "scenario": scenario_id,
        "provider": "ollama",
        "model": config.model,
        "notice_id": notice_id,
        "packet_id": packet_id,
        "path": str(directory / "machine_draft.json"),
        "markdown": str(directory / "machine_draft.md"),
        "leakage": leakage,
        "applied": applied,
        "n_citations": len(record["citations"]),
        "notes": notes,
        "votes": False,
    }
