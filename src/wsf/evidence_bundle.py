"""Versioned, model-addressable evidence. Never rewrites packets or detector facts."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, time
from pathlib import Path
from typing import Any

from wsf.packet import Packet


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str, allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value)
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if len(text) == 10:
            parsed = datetime.combine(parsed.date(), time(23, 59, 59))
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    except ValueError:
        return None


def document_rejection(item: dict, cutoff: datetime, mode: str) -> str | None:
    """Search snippets and publication labels alone do not establish a content version."""
    text = item.get("text")
    if not isinstance(text, str) or not text.strip():
        return "search_lead_only_no_document"
    if item.get("content_sha256") != hashlib.sha256(text.encode()).hexdigest():
        return "document_hash_missing_or_mismatched"
    retrieved = timestamp(item.get("retrieved_at"))
    available = timestamp(item.get("version_at"))
    if retrieved is None or available is None:
        return "content_version_unverified"
    if available > cutoff:
        return "content_version_after_cutoff"
    if mode == "live" and retrieved > cutoff:
        return "retrieved_after_cutoff"
    method = item.get("version_basis")
    if method == "archive_capture":
        from urllib.parse import urlsplit

        parts = urlsplit(str(item.get("archive_url", "")))
        stamp = available.strftime("%Y%m%d%H%M%S")
        if parts.scheme != "https" or parts.netloc != "web.archive.org":
            return "invalid_archive_provenance"
        if (
            item.get("archive_url")
            != f"https://web.archive.org/web/{stamp}id_/{item.get('url', '')}"
        ):
            return "archive_version_mismatch"
    elif method != "contemporaneous_retrieval" or retrieved != available:
        return "content_version_unverified"
    return None


def build_bundle(
    packet: Packet, collection: dict, *, documents: list[dict] | None = None, max_chars: int = 60000
) -> dict:
    if max_chars < 1000:
        raise ValueError("Evidence input budget must be at least 1000 characters")
    cutoff = timestamp(packet.clocks.knowledge_cutoff)
    mode = packet.clocks.mode
    assert cutoff is not None
    items, excluded, omitted = [], [], []
    used = 0

    def add(
        kind: str,
        data: dict,
        source: str,
        *,
        available: Any = None,
        retrieved: Any = None,
        reason: str | None = None,
        verification: str = "collector_record",
    ):
        ident = "ev-" + digest({"kind": kind, "source": source, "data": data})[:16]
        when = timestamp(available)
        if not reason and (when is None or when > cutoff):
            reason = "availability_unknown" if when is None else "not_available_at_cutoff"
        if not reason and mode == "live":
            seen = timestamp(retrieved)
            if seen is None or seen > cutoff:
                reason = "not_retrieved_at_cutoff"
        reference = {"id": ident, "kind": kind, "source_ref": source}
        if reason:
            excluded.append({**reference, "reason": reason})
            return
        item = {
            **reference,
            "data": data,
            "available_at": str(available),
            "retrieved_at": str(retrieved) if retrieved else None,
            "verification": verification,
            "significance": "unassigned",
        }
        if kind == "document":
            item["dependency_group"] = data.get("content_sha256")
        elif data.get("shared_information_substrate"):
            item["dependency_group"] = data["shared_information_substrate"]
        items.append(item)

    for row in packet.collected_evidence:
        if row.kind not in {"observation", "coverage_hole"}:
            excluded.append(
                {"id": row.item_id, "kind": row.kind, "reason": "derived_context_not_readmitted"}
            )
            continue
        add(
            row.kind,
            row.model_dump(mode="json"),
            f"evidence.json#{row.item_id}",
            available=row.available_at,
            retrieved=row.retrieved_at,
            verification="detector_observation" if row.kind == "observation" else "coverage_gap",
        )

    for task in collection.get("tasks", []):
        kind = task.get("kind")
        task_cutoff = timestamp(task.get("knowledge_cutoff"))
        cached_later = task_cutoff is None or task_cutoff > cutoff
        for index, row in enumerate(task.get("items", [])):
            source = f"collection/{kind}.json#/items/{index}"
            if kind == "open_source_search":
                add("search_lead", row, source, reason="search_lead_requires_versioned_document")
            elif kind == "official_pack" and row.get("kind") == "declared_posture":
                add(
                    "official_event",
                    row,
                    source,
                    available=row.get("at"),
                    retrieved=task.get("ran_at"),
                    reason="task_cutoff_unverified" if cached_later else None,
                    verification="collector_dated_event_not_independently_verified",
                )
            elif kind == "refresh_physical":
                catalogue = row.get("kind") == "catalogue_granule"
                add(
                    "catalogue_pointer" if catalogue else "physical_observation",
                    row,
                    source,
                    available=row.get("available_at"),
                    retrieved=task.get("ran_at"),
                    reason="collector_marks_unavailable" if not row.get("knowable") else None,
                    verification=(
                        "reconstructed_catalogue_availability_not_imagery"
                        if catalogue and row.get("reconstructed")
                        else "catalogue_pointer_not_imagery"
                        if catalogue
                        else "collector_record"
                    ),
                )
            elif kind == "chronology" or (kind == "official_pack" and row.get("series_id")):
                add(
                    "chronology" if kind == "chronology" else "administrative_observation",
                    row,
                    source,
                    available=row.get("day"),
                    retrieved=task.get("ran_at"),
                    reason="task_cutoff_unverified" if cached_later else None,
                    verification="collector_cutoff_filtered_series",
                )
    for row in documents or []:
        add(
            "document",
            row,
            "research/documents/" + digest(row),
            available=row.get("version_at"),
            retrieved=row.get("retrieved_at"),
            reason=document_rejection(row, cutoff, mode),
            verification="versioned_document_not_fact_verification",
        )
    product = packet.product
    # Prefer the cue and new discriminating evidence over repetitive lookback rows.
    priority = {
        "observation": 0,
        "coverage_hole": 0,
        "official_event": 1,
        "physical_observation": 2,
        "document": 3,
        "catalogue_pointer": 4,
        "chronology": 5,
        "administrative_observation": 6,
    }
    candidates, items = items, []
    for item in sorted(candidates, key=lambda row: priority.get(row["kind"], 9)):
        size = len(canonical(item))
        if used + size > max_chars:
            omitted.append(
                {k: item[k] for k in ("id", "kind", "source_ref")}
                | {"reason": "input_character_budget"}
            )
        else:
            items.append(item)
            used += size
    bundle = {
        "schema_id": "desk_evidence_v1",
        "packet_id": packet.packet_id,
        "cutoff": cutoff.isoformat(),
        "mode": mode,
        "source_hashes": {
            "packet": digest(packet.model_dump(mode="json")),
            "collection": digest(collection),
            "documents": digest(documents or []),
        },
        "initial_cue": packet.measurement_snapshot,
        "headline": product.headline if product else packet.scenario_id,
        "hypotheses": [h.hypothesis for h in packet.hypotheses]
        or ([h["hypothesis"] for h in product.hypotheses] if product else []),
        "requirements": product.collection if product else [],
        "dependencies": packet.dependencies,
        "items": items,
        "excluded": excluded,
        "omitted": omitted,
        "budget": {
            "max_item_chars": max_chars,
            "used_item_chars": used,
            "selection": "cue_then_official_physical_documents_catalogue_chronology_admin",
        },
        "cautions": [
            "Initial prose summaries and geopolitical context are not evidence inputs.",
            "Official events retain collector provenance; primary verification may be missing.",
            "Catalogue pointers do not establish scene content or observed deployment.",
            "Document versions establish availability, not factual truth or source independence.",
        ],
    }
    bundle["bundle_id"] = "bundle-" + digest(bundle)[:20]
    return bundle


def save_bundle(directory: Path, bundle: dict) -> Path:
    path = directory / "evidence_bundles" / (bundle["bundle_id"] + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    content = canonical(bundle) + "\n"
    if path.exists():
        if path.read_text() != content:
            raise ValueError("Existing evidence bundle differs; refusing overwrite")
    else:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(content)
    return path


def model_input(bundle: dict, *, max_chars: int = 32000) -> dict:
    """Build a bounded model view while retaining the complete bundle as the audit source."""
    if max_chars < 8000:
        raise ValueError("Model input budget must be at least 8000 characters")

    def compact(item: dict) -> dict:
        data = item["data"]
        kind = item["kind"]
        keep = {
            "observation": (
                "series_id",
                "evidence_time",
                "geographic_scope",
                "measurement_family",
                "text",
            ),
            "coverage_hole": (
                "series_id",
                "evidence_time",
                "geographic_scope",
                "measurement_family",
                "text",
            ),
            "catalogue_pointer": (
                "aoi_id",
                "aoi_name",
                "collection",
                "sensing_at",
                "available_at",
                "url",
            ),
        }.get(kind)
        if keep:
            data = {key: data[key] for key in keep if key in data}
        return {
            key: value
            for key, value in {
                "id": item["id"],
                "kind": kind,
                "source_ref": item["source_ref"],
                "available_at": item["available_at"],
                "verification": item["verification"],
                "dependency_group": item.get("dependency_group"),
                "data": data,
            }.items()
            if value is not None
        }

    by_kind: dict[str, list[dict]] = {}
    for item in bundle["items"]:
        by_kind.setdefault(item["kind"], []).append(compact(item))
    order = (
        "observation",
        "coverage_hole",
        "official_event",
        "physical_observation",
        "document",
        "catalogue_pointer",
        "chronology",
        "administrative_observation",
    )
    base = {
        "schema_id": "desk_model_input_v1",
        "bundle_id": bundle["bundle_id"],
        "cutoff": bundle["cutoff"],
        "mode": bundle["mode"],
        "headline": bundle["headline"],
        "initial_cue": bundle["initial_cue"],
        "hypotheses": bundle["hypotheses"],
        "requirements": bundle["requirements"],
        "dependencies": bundle["dependencies"],
        "cautions": bundle["cautions"],
        "evidence": [],
        "admission_summary": {
            "full_bundle_items": len(bundle["items"]),
            "full_bundle_excluded": len(bundle["excluded"]),
            "full_bundle_omitted": len(bundle["omitted"]),
        },
    }
    # Round-robin avoids allowing a long numeric series to crowd out other evidence classes.
    selected: list[dict] = []
    index = 0
    rows_to_consider = max((len(rows) for rows in by_kind.values()), default=0)
    while index < rows_to_consider:
        for kind in order:
            rows = by_kind.get(kind, [])
            if index >= len(rows):
                continue
            candidate = rows[index]
            trial = {**base, "evidence": [*selected, candidate]}
            if len(canonical(trial)) <= max_chars:
                selected.append(candidate)
        index += 1
    base["evidence"] = selected
    base["admission_summary"]["model_items"] = len(selected)
    base["admission_summary"]["not_selected_for_model"] = len(bundle["items"]) - len(selected)
    base["model_input_id"] = "input-" + digest(base)[:20]
    while selected and len(canonical(base)) > max_chars:
        selected.pop()
        base["evidence"] = selected
        base["admission_summary"]["model_items"] = len(selected)
        base["admission_summary"]["not_selected_for_model"] = len(bundle["items"]) - len(selected)
        del base["model_input_id"]
        base["model_input_id"] = "input-" + digest(base)[:20]
    if len(canonical(base)) > max_chars:
        raise ValueError("Model input metadata exceeds its character budget")
    return base
