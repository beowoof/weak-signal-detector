"""packet_v0: cutoff-safe evidence assembly. Same compiler for live and replay."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from wsf.analysis.coupling import CAUSAL_DOMAINS
from wsf.notice import Notice, NoticeState, load_notice, save_notice
from wsf.protocol import load_yaml
from wsf.scenario import load_scenario, scenario_directory
from wsf.types import Observation

PACKET_SCHEMA = "packet_v0"
STALE_EMIT_DAYS = 14
DEFAULT_HYPOTHESES = [
    "routine_variation",
    "exercise_or_demonstration",
    "defensive_readiness",
    "reversible_mobilisation",
    "preparation_for_overt_action",
    "collection_or_measurement_artifact",
]

MEASUREMENT_FAMILY: dict[str, str] = {
    "talk.gdelt_cameo": "coder-events",
    "talk.icews_cameo": "coder-events",
    "attn.wiki_pageviews": "pageviews",
    "attn.wiki_edits": "pageviews",
    "dyad.moex_usdrub": "exchange_fixing",
    "dyad.fx": "exchange_fixing",
    "market.cbr_funding_spread": "central_bank_print",
    "official.gazette_cadence": "official-text",
    "official.gazette": "official-text",
}

SHARED_SUBSTRATE: dict[str, str] = {
    "talk.gdelt_cameo": "public_reporting",
    "talk.icews_cameo": "public_reporting",
    "attn.wiki_pageviews": "public_reporting",
    "attn.wiki_edits": "public_reporting",
    "dyad.moex_usdrub": "exchange_fixing",
    "dyad.fx": "exchange_fixing",
}


class PacketClocks(BaseModel):
    mode: Literal["live", "replay"]
    knowledge_cutoff: datetime
    built_at: datetime
    notice_emitted_at: datetime
    knowledge_rule: Literal["available_at", "available_at_and_retrieved_at"]


class EvidenceItem(BaseModel):
    item_id: str
    kind: Literal["observation", "coverage_hole", "environment_note"]
    series_id: str | None = None
    source: str | None = None
    evidence_time: datetime | None = None
    knowledge_time: datetime | None = None
    available_at: datetime | None = None
    retrieved_at: datetime | None = None
    geographic_scope: str | None = None
    relationship: str
    text: str
    significance: Literal["unassigned"] = "unassigned"
    originating_source_id: str | None = None
    syndication_cluster_id: str | None = None
    measurement_family: str | None = None
    shared_information_substrate: str | None = None


class HypothesisShell(BaseModel):
    hypothesis: str
    supporting_evidence: list[str] = Field(default_factory=list)
    contradicting_evidence: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    dependency_cautions: list[str] = Field(default_factory=list)
    assessment: str | None = None
    confidence: str | None = None


class CollectionLogEntry(BaseModel):
    action: str
    detail: str


class Packet(BaseModel):
    schema_id: Literal["packet_v0"] = PACKET_SCHEMA
    packet_id: str
    notice_id: str
    scenario_id: str
    clocks: PacketClocks
    measurement_snapshot: dict[str, Any]
    information_environment: dict[str, Any]
    collected_evidence: list[EvidenceItem]
    counterevidence: list[EvidenceItem] = Field(default_factory=list)
    unknowns: list[str]
    dependencies: list[dict[str, Any]]
    hypotheses: list[HypothesisShell]
    collection_log: list[CollectionLogEntry]


def packet_directory(project_root: Path, scenario_id: str, packet_id: str) -> Path:
    return scenario_directory(project_root, scenario_id) / "interpretation" / packet_id


def packet_path(project_root: Path, scenario_id: str, packet_id: str) -> Path:
    return packet_directory(project_root, scenario_id, packet_id) / "evidence.json"


def packet_id_for(notice_id: str, mode: str, cutoff: datetime) -> str:
    core = {"notice_id": notice_id, "mode": mode, "as_of": cutoff.date().isoformat()}
    digest = hashlib.sha256(json.dumps(core, sort_keys=True).encode()).hexdigest()[:12]
    return f"packet-{digest}"


def resolve_clocks(
    notice: Notice,
    *,
    replay: bool = False,
    as_of: datetime | None = None,
    now: datetime | None = None,
) -> PacketClocks:
    built_at = now or datetime.now(UTC)
    if built_at.tzinfo is None:
        built_at = built_at.replace(tzinfo=UTC)
    emitted = notice.trigger.created_at
    if emitted.tzinfo is None:
        emitted = emitted.replace(tzinfo=UTC)

    if as_of is not None:
        cutoff = as_of if as_of.tzinfo else as_of.replace(tzinfo=UTC)
        historical = replay or cutoff.date() < built_at.date()
        mode: Literal["live", "replay"] = "replay" if historical else "live"
    elif replay:
        cutoff = datetime.combine(notice.trigger.end, time(23, 59, 59), tzinfo=UTC)
        mode = "replay"
    else:
        cutoff = built_at
        mode = "live"
        emit_lag = (emitted.date() - notice.trigger.end).days
        if emit_lag > STALE_EMIT_DAYS:
            raise ValueError(
                f"notice {notice.notice_id} was emitted {emit_lag} days after the episode "
                f"ended ({notice.trigger.end}). That is a historical replay, not a live desk "
                "score. Pass --replay (cutoff = episode end) or --as-of TIMESTAMP."
            )

    rule: Literal["available_at", "available_at_and_retrieved_at"] = (
        "available_at" if mode == "replay" else "available_at_and_retrieved_at"
    )
    return PacketClocks(
        mode=mode,
        knowledge_cutoff=cutoff,
        built_at=built_at,
        notice_emitted_at=emitted,
        knowledge_rule=rule,
    )


def _knowable(available_at: datetime, retrieved_at: datetime, clocks: PacketClocks) -> bool:
    if available_at > clocks.knowledge_cutoff:
        return False
    if clocks.mode == "live" and retrieved_at > clocks.knowledge_cutoff:
        return False
    return True


def _as_dt(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _hypothesis_ids(project_root: Path) -> list[str]:
    path = project_root / "config" / "interpretation_protocol.yaml"
    if not path.is_file():
        return list(DEFAULT_HYPOTHESES)
    payload = load_yaml(path)
    return list(payload.get("hypotheses") or DEFAULT_HYPOTHESES)


def _load_window_observations(
    project_root: Path, notice: Notice
) -> tuple[list[Observation], list[CollectionLogEntry]]:
    log: list[CollectionLogEntry] = []
    collection_id = notice.trigger.collection_id
    root = (
        scenario_directory(project_root, notice.trigger.scenario_id)
        / "corpus"
        / collection_id
        / "observations"
    )
    if not root.is_dir():
        log.append(
            CollectionLogEntry(
                action="corpus_missing",
                detail=(
                    f"{collection_id} observations not on disk; "
                    "packet uses notice trigger facts only"
                ),
            )
        )
        return [], log
    rows: list[Observation] = []
    files = sorted(root.glob(f"*_{notice.trigger.window_id}.jsonl"))
    log.append(
        CollectionLogEntry(
            action="scan_corpus",
            detail=(
                f"{collection_id}: {len(files)} observation files "
                f"for window {notice.trigger.window_id}"
            ),
        )
    )
    for path in files:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rows.append(Observation.model_validate_json(line))
    return rows, log


def _scope(project_root: Path, scenario_id: str) -> str:
    scenario = load_scenario(project_root, scenario_id)
    counterparts = ",".join(scenario.actors.counterparts) or "?"
    return f"focal={scenario.actors.focal or '?'} counterparts={counterparts}"


def _observation_map(rows: list[Observation]) -> dict[tuple[str, date], Observation]:
    out: dict[tuple[str, date], Observation] = {}
    for row in rows:
        day = _as_dt(row.event_time).date()
        out[(row.series_id, day)] = row
    return out


def _evidence_from_notice(
    notice: Notice,
    clocks: PacketClocks,
    observations: list[Observation],
    scope: str,
) -> tuple[list[EvidenceItem], int]:
    items: list[EvidenceItem] = []
    excluded = 0
    by_key = _observation_map(observations)
    dates = [date.fromisoformat(day) for day in notice.trigger.observed.get("daily_dates") or []]
    series_days = notice.trigger.observed.get("daily_series_z") or []
    imaging = notice.trigger.imaging_status_by_day
    for day, z_map in zip(dates, series_days, strict=False):
        if not isinstance(z_map, dict):
            continue
        for series_id, z_value in sorted(z_map.items()):
            obs = by_key.get((series_id, day))
            if obs is not None:
                available = _as_dt(obs.available_at)
            else:
                available = datetime.combine(day, time(23, 59, 59), UTC)
            retrieved = _as_dt(obs.retrieved_at) if obs is not None else clocks.built_at
            if not _knowable(available, retrieved, clocks):
                excluded += 1
                continue
            quality = obs.quality if obs is not None else "unknown"
            raw = obs.value if obs is not None else None
            domain = CAUSAL_DOMAINS.get(series_id, "unmapped")
            kind: Literal["observation", "coverage_hole", "environment_note"] = (
                "coverage_hole" if quality in {"missing", "source_down"} else "observation"
            )
            text_parts = [f"z={z_value}"]
            if raw is not None:
                text_parts.append(f"raw={raw}")
            text_parts.append(f"quality={quality}")
            if series_id in imaging or day.isoformat() in imaging:
                text_parts.append(f"imaging={imaging.get(day.isoformat(), 'n/a')}")
            items.append(
                EvidenceItem(
                    item_id=f"obs:{series_id}:{day.isoformat()}",
                    kind=kind,
                    series_id=series_id,
                    source=series_id.split(".", 1)[0],
                    evidence_time=datetime.combine(day, time(0, 0), tzinfo=UTC),
                    knowledge_time=available,
                    available_at=available,
                    retrieved_at=retrieved,
                    geographic_scope=scope,
                    relationship=f"{domain}/{series_id}",
                    text="; ".join(text_parts),
                    measurement_family=MEASUREMENT_FAMILY.get(series_id),
                    shared_information_substrate=SHARED_SUBSTRATE.get(series_id),
                )
            )
    return items, excluded


def _dependencies(series: list[str]) -> list[dict[str, Any]]:
    by_substrate: dict[str, list[str]] = {}
    for series_id in series:
        substrate = SHARED_SUBSTRATE.get(series_id)
        if substrate:
            by_substrate.setdefault(substrate, []).append(series_id)
    deps = []
    for substrate, members in sorted(by_substrate.items()):
        if len(members) < 2:
            continue
        deps.append(
            {
                "shared_information_substrate": substrate,
                "series": members,
                "caution": (
                    "these series can move together because they read the same public environment"
                ),
            }
        )
    return deps


def _information_environment(notice: Notice, items: list[EvidenceItem]) -> dict[str, Any]:
    proxy_series = [
        series_id
        for series_id in notice.trigger.contributing_series
        if SHARED_SUBSTRATE.get(series_id) == "public_reporting"
    ]
    return {
        "snapshot_id": notice.trigger.information_environment_snapshot_id,
        "status": "proxies_only",
        "notes": [
            "No separate GKG/RIMA/official snapshot yet. Talk, ICEWS, and Wikipedia are "
            "already in the quantitative chorus; they describe the information environment "
            "but do not add extra independent votes in this packet.",
        ],
        "proxy_series": proxy_series,
        "n_public_reporting_items": sum(
            1 for item in items if item.shared_information_substrate == "public_reporting"
        ),
    }


def build_packet(
    project_root: Path,
    scenario_id: str,
    notice_id: str,
    *,
    replay: bool = False,
    as_of: datetime | None = None,
    now: datetime | None = None,
) -> Packet:
    notice = load_notice(project_root, scenario_id, notice_id)
    if notice.trigger.scenario_id != scenario_id:
        raise ValueError(f"notice {notice_id} belongs to {notice.trigger.scenario_id}")
    clocks = resolve_clocks(notice, replay=replay, as_of=as_of, now=now)
    observations, log = _load_window_observations(project_root, notice)
    scope = _scope(project_root, scenario_id)
    evidence, excluded = _evidence_from_notice(notice, clocks, observations, scope)
    log.append(
        CollectionLogEntry(
            action="cutoff",
            detail=(
                f"mode={clocks.mode} rule={clocks.knowledge_rule} "
                f"cutoff={clocks.knowledge_cutoff.isoformat()} "
                f"kept={len(evidence)} excluded_unknowable={excluded}"
            ),
        )
    )
    log.append(
        CollectionLogEntry(
            action="no_context_harvest",
            detail=(
                "posture-bounded collector is not in this slice; "
                "packet is notice + in-corpus observations"
            ),
        )
    )
    packet = Packet(
        packet_id=packet_id_for(notice.notice_id, clocks.mode, clocks.knowledge_cutoff),
        notice_id=notice.notice_id,
        scenario_id=scenario_id,
        clocks=clocks,
        measurement_snapshot={
            "collection_id": notice.trigger.collection_id,
            "measurement_id": notice.trigger.measurement_id,
            "window_id": notice.trigger.window_id,
            "start": notice.trigger.start.isoformat(),
            "end": notice.trigger.end.isoformat(),
            "contributing_domains": notice.trigger.contributing_domains,
            "contributing_series": notice.trigger.contributing_series,
            "observed": notice.trigger.observed,
            "derived": notice.trigger.derived,
            "heuristic": notice.trigger.heuristic,
            "unknowns": notice.trigger.unknowns,
            "imaging_status_by_day": notice.trigger.imaging_status_by_day,
            "recommended_posture": notice.trigger.recommended_posture.value,
            "recommended_posture_reason": notice.trigger.recommended_posture_reason,
        },
        information_environment=_information_environment(notice, evidence),
        collected_evidence=evidence,
        counterevidence=[],
        unknowns=list(notice.trigger.unknowns),
        dependencies=_dependencies(notice.trigger.contributing_series),
        hypotheses=[HypothesisShell(hypothesis=name) for name in _hypothesis_ids(project_root)],
        collection_log=log,
    )
    return packet


def save_packet(project_root: Path, packet: Packet, notice: Notice) -> Path:
    path = packet_path(project_root, packet.scenario_id, packet.packet_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(packet.model_dump_json(indent=2) + "\n", encoding="utf-8")
    notice.workflow.state = NoticeState.in_packet
    notice.workflow.packet_id = packet.packet_id
    notice.workflow.updated_at = packet.clocks.built_at
    save_notice(project_root, notice, overwrite_trigger=False)
    return path


def build_and_save(
    project_root: Path,
    scenario_id: str,
    notice_id: str,
    *,
    replay: bool = False,
    as_of: datetime | None = None,
) -> tuple[Packet, Path]:
    packet = build_packet(project_root, scenario_id, notice_id, replay=replay, as_of=as_of)
    notice = load_notice(project_root, scenario_id, notice_id)
    path = save_packet(project_root, packet, notice)
    return packet, path
