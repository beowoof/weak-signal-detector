"""packet_v0: cutoff-safe evidence assembly. Same compiler for live and replay."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from wsf.analysis.coupling import CAUSAL_DOMAINS
from wsf.notice import Notice, NoticeState, list_notices, load_notice, save_notice
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

SERIES_LABELS: dict[str, str] = {
    "market.cbr_funding_spread": "Russian financial conditions",
    "net.ripe_prefixes": "Digital infrastructure",
    "talk.gdelt_cameo": "Public reporting (GDELT)",
    "talk.icews_cameo": "Public reporting (ICEWS)",
    "attn.wiki_pageviews": "Public attention (Wikipedia)",
    "tempo.firms_thermal": "Physical activity (FIRMS)",
    "tempo.viirs_aoi": "Physical activity (VIIRS)",
    "tempo.s1_backscatter": "Physical activity (SAR)",
    "nav.spatial_warnings": "Maritime warnings",
    "dyad.moex_usdrub": "USD/RUB (MOEX)",
}

THEATRE_NAMES: dict[str, str] = {
    "UKR": "Ukraine",
    "RUS": "Russia",
    "DEU": "Germany",
    "USA": "United States",
    "CHN": "China",
}

ACTOR_ADJECTIVES: dict[str, str] = {
    "RUS": "Russian",
    "UKR": "Ukrainian",
    "DEU": "German",
    "USA": "US",
    "CHN": "Chinese",
}

CAPITALS: dict[str, str] = {
    "RUS": "Moscow",
    "UKR": "Kyiv",
    "DEU": "Berlin",
    "USA": "Washington",
    "CHN": "Beijing",
}

AOI_KIND_PHRASE: dict[str, str] = {
    "staging": "staging areas",
    "frontier_railhead": "frontier railheads",
    "capital": "the capital",
    "civil_airport": "civil airports",
    "mod_hq": "defence headquarters",
}

PRODUCT_NAME = "Preparatory Activity Watch"

DOMAIN_PHRASE: dict[str, str] = {
    "domestic_financial_conditions": "financial conditions",
    "market": "financial conditions",
    "digital_infrastructure": "digital infrastructure",
    "information": "public reporting",
    "public_attention": "public reporting",
    "physical_activity": "physical activity",
    "spatial_restriction": "maritime warnings",
}

PUBLIC_SERIES = (
    "talk.gdelt_cameo",
    "talk.icews_cameo",
    "attn.wiki_pageviews",
    "attn.wiki_edits",
)


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


class BriefSection(BaseModel):
    id: str
    title: str
    body: str


class ProductBrief(BaseModel):
    bluf: str = ""
    source_assessment: str = ""
    headline: str
    period: str
    available_by: str
    analytic_state: str
    analytic_state_label: str
    change: str
    confidence: str
    confidence_rationale: str = ""
    assessment: list[str]
    watchlist: list[dict[str, str]]
    supports: list[str]
    does_not_support: list[str]
    caveats: list[str]
    hypotheses: list[dict[str, str]]
    collection: list[dict[str, str]]
    availability_warnings: list[str]
    analyst_note: str
    keys: list[str] = Field(default_factory=list)
    geographic_frame: str = ""


class Packet(BaseModel):
    schema_id: Literal["packet_v0"] = PACKET_SCHEMA
    packet_id: str
    notice_id: str
    scenario_id: str
    clocks: PacketClocks
    layers: dict[str, str]
    brief: list[BriefSection] = Field(default_factory=list)
    product: ProductBrief | None = None
    measurement_snapshot: dict[str, Any]
    information_environment: dict[str, Any]
    geopolitical_context: dict[str, Any]
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


def _parse_extra(observation: Observation) -> dict[str, Any]:
    raw = observation.extra
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _obs_on_days(
    observations: list[Observation], series_id: str, start: date, end: date
) -> list[Observation]:
    rows = []
    for item in observations:
        if item.series_id != series_id:
            continue
        day = _as_dt(item.event_time).date()
        if start <= day <= end:
            rows.append(item)
    return sorted(rows, key=lambda item: _as_dt(item.event_time))


def _dimension(
    dim_id: str,
    *,
    status: str,
    summary: str,
    series_id: str | None = None,
    values: Any = None,
) -> dict[str, Any]:
    return {
        "id": dim_id,
        "status": status,
        "votes": False,
        "series_id": series_id,
        "summary": summary,
        "values": values,
    }


def _knowable_obs(
    observations: list[Observation], clocks: PacketClocks, series_id: str, start: date, end: date
) -> list[Observation]:
    rows = []
    for item in _obs_on_days(observations, series_id, start, end):
        if _knowable(_as_dt(item.available_at), _as_dt(item.retrieved_at), clocks):
            rows.append(item)
    return rows


def _fmt_num(value: float | None) -> str:
    if value is None or not isinstance(value, int | float):
        return "—"
    if abs(value) >= 100:
        return f"{value:,.0f}"
    return f"{value:.2f}"


def _fmt_count(value: float | None) -> str:
    if value is None or not isinstance(value, int | float):
        return "—"
    if abs(value - round(value)) < 1e-6:
        return str(int(round(value)))
    return _fmt_num(value)


def _fmt_period(start: date, end: date) -> str:
    if start.year == end.year and start.month == end.month:
        return f"{start.day}–{end.day} {end.strftime('%B %Y')}"
    if start.year == end.year:
        return f"{start.day} {start.strftime('%B')} – {end.day} {end.strftime('%B %Y')}"
    return f"{start.isoformat()} – {end.isoformat()}"


def _fmt_cutoff(when: datetime) -> str:
    return f"{when.strftime('%H:%MZ')}, {when.day} {when.strftime('%B')}"


def _fmt_short_day(day: date | str) -> str:
    if isinstance(day, str):
        day = date.fromisoformat(day[:10])
    return f"{day.day} {day.strftime('%b')}"


def _information_environment(
    notice: Notice,
    items: list[EvidenceItem],
    observations: list[Observation],
    clocks: PacketClocks,
) -> dict[str, Any]:
    start, end = notice.trigger.start, notice.trigger.end
    gdelt = _knowable_obs(observations, clocks, "talk.gdelt_cameo", start, end)
    wiki = _knowable_obs(observations, clocks, "attn.wiki_pageviews", start, end)
    dimensions = [
        _dimension(
            "reporting_volume",
            status="proxy" if gdelt else "missing",
            series_id="talk.gdelt_cameo",
            summary=(
                "GDELT CAMEO event counts for the actor over the episode. This is a volume "
                "proxy from a series that already votes in the notice; it is not a GKG tone set."
                if gdelt
                else "No GDELT observations in-corpus for this episode."
            ),
            values=(
                [
                    {
                        "day": _as_dt(row.event_time).date().isoformat(),
                        "count": row.value,
                        "quality": row.quality,
                    }
                    for row in gdelt
                ]
                if gdelt
                else None
            ),
        ),
        _dimension(
            "geographic_focus",
            status="proxy" if wiki else "missing",
            series_id="attn.wiki_pageviews",
            summary=(
                "Wikipedia title mix (Ukraine / Russia / Russian Armed Forces) as a focus "
                "proxy. Pageviews already vote in the notice; this split only shows where "
                "attention sat."
                if wiki
                else "No Wikipedia observations in-corpus for this episode."
            ),
            values=(
                [
                    {
                        "day": _as_dt(row.event_time).date().isoformat(),
                        "total": row.value,
                        "titles": (_parse_extra(row).get("titles") or {}),
                    }
                    for row in wiki
                ]
                if wiki
                else None
            ),
        ),
        _dimension(
            "tone",
            status="missing",
            summary="Tone/intensity needs GKG, Media Cloud, or RIMA. Not in this harvest.",
        ),
        _dimension(
            "source_diversity",
            status="missing",
            summary="Originating-outlet diversity is not in the CAMEO count series.",
        ),
        _dimension(
            "official_posture",
            status="missing",
            summary=(
                "Declared UK/US posture (travel advice, diplomatic drawdown, leave-now, "
                "threat language) is not in this corpus. Official pack harvests it "
                "cutoff-safe from FCDO change_history."
            ),
        ),
        _dimension(
            "narrative_concentration",
            status="missing",
            summary="Competing-explanation mix is not measured yet.",
        ),
    ]
    statuses = {item["status"] for item in dimensions}
    if "proxy" in statuses:
        env_status = "partial"
    elif statuses == {"missing"}:
        env_status = "missing"
    else:
        env_status = "present"
    return {
        "snapshot_id": notice.trigger.information_environment_snapshot_id,
        "status": env_status,
        "votes": False,
        "notes": [
            "Environment dimensions never add a vote to the notice that opened this packet.",
            "present = dedicated snapshot; proxy = chorus series reused as description; "
            "missing = not harvested.",
        ],
        "n_public_reporting_items": sum(
            1 for item in items if item.shared_information_substrate == "public_reporting"
        ),
        "dimensions": dimensions,
    }


def _geopolitical_context(
    notice: Notice, observations: list[Observation], clocks: PacketClocks
) -> dict[str, Any]:
    requested = notice.workflow.state.value == "context_requested"
    nav = _knowable_obs(
        observations, clocks, "nav.spatial_warnings", notice.trigger.start, notice.trigger.end
    )
    items = []
    if nav:
        items.append(
            {
                "kind": "official_maritime",
                "series_id": "nav.spatial_warnings",
                "votes": False,
                "summary": "NGA NAVAREA warning counts for RUS areas (knowable at cutoff).",
                "values": [
                    {
                        "day": _as_dt(row.event_time).date().isoformat(),
                        "count": row.value,
                        "quality": row.quality,
                    }
                    for row in nav
                ],
            }
        )
    posture_series = (
        "posture.travel_risk",
        "posture.diplomatic_posture",
        "posture.government_action",
        "posture.official_threat_language",
    )
    posture_rows = []
    for series_id in posture_series:
        posture_rows.extend(
            _knowable_obs(observations, clocks, series_id, notice.trigger.start, notice.trigger.end)
        )
    if posture_rows:
        latest = {}
        for row in posture_rows:
            latest[row.series_id] = row.value
        items.append(
            {
                "kind": "declared_posture",
                "votes": False,
                "summary": "UK/US declared geographic-risk prior.",
                "values": {
                    series_id: latest.get(series_id)
                    for series_id in posture_series
                    if series_id in latest
                },
            }
        )
    notes = [
        "NAVAREA counts are public maritime warnings, not diplomatic posture.",
    ]
    if not posture_rows:
        notes.append(
            "No declared UK/US posture series in this corpus. Run Official pack to harvest "
            "FCDO travel-advice history (cutoff-filtered)."
        )
    if requested:
        notes.append("Operator requested more information.")
    return {
        "status": "partial" if items else "missing",
        "votes": False,
        "requested": requested,
        "items": items,
        "notes": notes,
    }


def _z_path(notice: Notice, series_id: str) -> list[float]:
    dates = notice.trigger.observed.get("daily_dates") or []
    series_days = notice.trigger.observed.get("daily_series_z") or []
    out: list[float] = []
    for _day, z_map in zip(dates, series_days, strict=False):
        if isinstance(z_map, dict) and isinstance(z_map.get(series_id), int | float):
            out.append(float(z_map[series_id]))
    return out


def _sigma_span(values: list[float]) -> str:
    if not values:
        return "near baseline"
    lo, hi = min(values), max(values)
    if abs(hi - lo) < 0.15:
        return f"{hi:.2f}σ"
    return f"{lo:.2f}–{hi:.2f}σ"


def _implication(series_id: str, z_values: list[float]) -> str:
    peak = max((abs(v) for v in z_values), default=0)
    if series_id == "market.cbr_funding_spread" and peak >= 2.5:
        return (
            "Strongest abnormality in the window; unusually large move in "
            "domestic funding conditions."
        )
    if series_id == "net.ripe_prefixes" and peak >= 2.5:
        return "Persistent rather than transient infrastructure anomaly."
    if series_id in {"talk.gdelt_cameo", "attn.wiki_pageviews", "talk.icews_cameo"}:
        return (
            "Confirms a heightened information environment; partly dependent "
            "on the same public reporting."
        )
    if series_id == "tempo.firms_thermal" and peak < 2:
        return "Weak physical indicator."
    if series_id == "nav.spatial_warnings" and z_values and z_values[-1] < z_values[0]:
        return "Does not reinforce the broader anomaly."
    if peak >= 2.5:
        return "Large deviation from the recent baseline."
    if peak >= 1.5:
        return "Elevated relative to the recent baseline."
    return "Near baseline."


def _prior_notice_in_window(project_root: Path, notice: Notice) -> bool:
    """True when an earlier notice already exists in the same scoring window."""
    try:
        others = list_notices(project_root, notice.trigger.scenario_id)
    except FileNotFoundError:
        return False
    return any(
        other.notice_id != notice.notice_id
        and other.trigger.window_id == notice.trigger.window_id
        and other.trigger.end < notice.trigger.start
        for other in others
    )


def _analytic_state(
    notice: Notice,
    *,
    prior_in_window: bool = False,
) -> tuple[str, str, str]:
    duration = notice.trigger.duration_days
    n_dom = len(notice.trigger.contributing_domains)
    # Escalation is a subsequent cue in the same window, not "near the
    # research window's end date". Window geometry is a design choice.
    # First notices stay at Watch: physical corroboration raises AnCR,
    # it does not promote the desk to preparatory_pattern on its own.
    if prior_in_window and n_dom >= 3:
        return (
            "escalation",
            "Escalation",
            "Rapid increase in anomaly energy and domain breadth",
        )
    if duration >= 3 and n_dom >= 3:
        return ("watch", "Watch", "Broadening multi-domain anomaly")
    if n_dom >= 2:
        return ("anomaly", "Anomaly", "Co-movement detected")
    return ("quiet", "Quiet", "No multi-domain abnormality")


def _theatre_name(project_root: Path, scenario_id: str) -> str:
    scenario = load_scenario(project_root, scenario_id)
    for code in [*scenario.actors.counterparts, scenario.actors.focal]:
        if code and code in THEATRE_NAMES:
            return THEATRE_NAMES[code]
    return scenario_id


def _actor_adjective(project_root: Path, scenario_id: str) -> str:
    scenario = load_scenario(project_root, scenario_id)
    return ACTOR_ADJECTIVES.get(scenario.actors.focal or "", "")


def _place_name(aoi_id: str) -> str:
    tail = aoi_id.split("-", 1)[-1]
    return tail.replace("_", " ").title()


def _join_plain(parts: list[str]) -> str:
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def _theatre_frame(project_root: Path, scenario_id: str) -> dict[str, Any]:
    scenario = load_scenario(project_root, scenario_id)
    focal = scenario.actors.focal or ""
    counterparts = [code for code in (scenario.actors.counterparts or []) if code]
    aois: list[dict[str, Any]] = []
    path = project_root / "config" / "facilities.yaml"
    if path.is_file() and focal:
        data = load_yaml(path)
        entry = (data or {}).get("actors", {}).get(focal) or {}
        aois = list(entry.get("aois") or [])
    places = [_place_name(str(item.get("id"))) for item in aois if item.get("id")]
    kinds: list[str] = []
    for item in aois:
        phrase = AOI_KIND_PHRASE.get(str(item.get("kind") or ""), "")
        if phrase and phrase not in kinds:
            kinds.append(phrase)
    focal_name = THEATRE_NAMES.get(focal, focal)
    counterpart_names = [THEATRE_NAMES.get(code, code) for code in counterparts]
    adjective = ACTOR_ADJECTIVES.get(focal, "")
    capital = CAPITALS.get(focal, "")
    keys: list[str] = []
    for name in [focal_name, *counterpart_names]:
        if name and name not in keys:
            keys.append(name)
    if capital and capital not in keys:
        keys.append(capital)
    if counterparts:
        other_adj = ACTOR_ADJECTIVES.get(counterparts[0], counterpart_names[0])
        border = f"{other_adj} border"
        if border not in keys:
            keys.append(border)
    for place in places:
        if place not in keys:
            keys.append(place)
    if kinds and counterpart_names and places:
        other_adj = ACTOR_ADJECTIVES.get(counterparts[0], counterpart_names[0])
        geographic_frame = (
            f"{adjective or focal_name} {_join_plain(kinds)} on the "
            f"{other_adj} border approaches: {_join_plain(places)}."
        )
    elif places:
        geographic_frame = f"Physical AOIs: {_join_plain(places)}."
    else:
        geographic_frame = ""
    aoi_rows = [
        {
            "id": str(item.get("id")),
            "name": _place_name(str(item.get("id"))),
            "kind": str(item.get("kind") or ""),
            "bbox": list(item.get("bbox") or []),
        }
        for item in aois
        if item.get("id")
    ]
    return {
        "focal": focal,
        "focal_name": focal_name,
        "adjective": adjective,
        "counterpart_names": counterpart_names,
        "counterpart_adjectives": [
            ACTOR_ADJECTIVES.get(code, name)
            for code, name in zip(counterparts, counterpart_names, strict=False)
        ],
        "capital": capital,
        "places": places,
        "aois": aoi_rows,
        "kinds": kinds,
        "keys": keys,
        "geographic_frame": geographic_frame,
    }


def _knowable_ok(
    observations: list[Observation], clocks: PacketClocks, series_id: str, start: date, end: date
) -> list[Observation]:
    return [
        row
        for row in _knowable_obs(observations, clocks, series_id, start, end)
        if row.quality == "ok"
    ]


def _z_by_day(notice: Notice, series_id: str) -> dict[date, float]:
    out: dict[date, float] = {}
    dates = notice.trigger.observed.get("daily_dates") or []
    series_days = notice.trigger.observed.get("daily_series_z") or []
    for day_s, z_map in zip(dates, series_days, strict=False):
        if isinstance(z_map, dict) and isinstance(z_map.get(series_id), int | float):
            out[date.fromisoformat(day_s)] = float(z_map[series_id])
    return out


def _ok_z_pairs(
    notice: Notice,
    observations: list[Observation],
    clocks: PacketClocks,
    series_id: str,
) -> list[tuple[date, float]]:
    zmap = _z_by_day(notice, series_id)
    ok_days = {
        _as_dt(row.event_time).date()
        for row in _knowable_ok(
            observations, clocks, series_id, notice.trigger.start, notice.trigger.end
        )
    }
    if ok_days:
        return [(day, zmap[day]) for day in sorted(ok_days) if day in zmap]
    return sorted(zmap.items())


def _join_clause(parts: list[str]) -> str:
    if not parts:
        return "Several domains"
    if len(parts) == 1:
        return parts[0][:1].upper() + parts[0][1:]
    body = ", ".join(parts[:-1]) + " and " + parts[-1]
    return body[:1].upper() + body[1:]


def _domain_clause(notice: Notice) -> str:
    rank = {
        "domestic_financial_conditions": 0,
        "market": 0,
        "digital_infrastructure": 1,
        "information": 2,
        "public_attention": 2,
        "physical_activity": 3,
        "spatial_restriction": 4,
    }
    ordered = sorted(
        notice.trigger.contributing_domains,
        key=lambda name: rank.get(name, 50),
    )
    seen: list[str] = []
    for name in ordered:
        phrase = DOMAIN_PHRASE.get(name, name.replace("_", " "))
        if phrase not in seen:
            seen.append(phrase)
    return _join_clause(seen)


def _cbr_observation(notice: Notice, observations: list[Observation], clocks: PacketClocks) -> str:
    pairs = _ok_z_pairs(notice, observations, clocks, "market.cbr_funding_spread")
    if not pairs:
        return "CBR funding conditions were not knowable at cutoff."
    peak_day, peak_z = max(pairs, key=lambda item: item[1])
    prior = [item for item in pairs if item[0] < peak_day]
    text = f"CBR funding spread reached {peak_z:.2f}σ on {_fmt_short_day(peak_day)}"
    if prior:
        prev_day, prev_z = prior[-1]
        text += f" after {prev_z:.2f}σ on {_fmt_short_day(prev_day)}"
    return text


def _moex_observation(notice: Notice, observations: list[Observation], clocks: PacketClocks) -> str:
    pairs = _ok_z_pairs(notice, observations, clocks, "dyad.moex_usdrub")
    if not pairs:
        pairs = _ok_z_pairs(notice, observations, clocks, "dyad.fx")
        series_id = "dyad.fx"
    else:
        series_id = "dyad.moex_usdrub"
    if not pairs:
        return "Exchange-rate conditions were not knowable at cutoff."
    peak_day, peak_z = max(pairs, key=lambda item: abs(item[1]))
    rows = _knowable_ok(observations, clocks, series_id, notice.trigger.start, notice.trigger.end)
    last = next((row.value for row in reversed(rows) if row.value is not None), None)
    text = f"USD/RUB reached {peak_z:.2f}σ on {_fmt_short_day(peak_day)}"
    if last is not None:
        text += f" (last print {_fmt_num(last)})"
    return text


def _ripe_observation(notice: Notice, observations: list[Observation], clocks: PacketClocks) -> str:
    pairs = _ok_z_pairs(notice, observations, clocks, "net.ripe_prefixes")
    if not pairs:
        return "RIPE prefix counts were not knowable at cutoff."
    n = len(pairs)
    duration = "three days" if n == 3 else f"{n} days"
    span = _sigma_span([z for _, z in pairs])
    return f"RIPE prefixes remained {span} above baseline for {duration}"


def _public_observation(
    notice: Notice, observations: list[Observation], clocks: PacketClocks
) -> str:
    start, end = notice.trigger.start, notice.trigger.end
    parts: list[str] = []
    gdelt_z = [z for _, z in _ok_z_pairs(notice, observations, clocks, "talk.gdelt_cameo")]
    if gdelt_z:
        if max(abs(z) for z in gdelt_z) >= 1.5:
            parts.append("GDELT reporting remained elevated")
        else:
            parts.append("GDELT reporting was near baseline")
    wiki = _knowable_ok(observations, clocks, "attn.wiki_pageviews", start, end)
    if len(wiki) >= 2:
        first, last = wiki[0].value, wiki[-1].value
        if last is not None and first is not None and last > first:
            parts.append(
                f"Wikipedia attention rose from {_fmt_num(first)} to {_fmt_num(last)} views"
            )
        elif last is not None and first is not None:
            parts.append(f"Wikipedia attention {_fmt_num(first)} → {_fmt_num(last)} views")
    elif wiki:
        parts.append(f"Wikipedia attention {_fmt_num(wiki[0].value)} views")
    elif _ok_z_pairs(notice, observations, clocks, "attn.wiki_pageviews"):
        parts.append("Wikipedia attention was elevated relative to baseline")
    return "; ".join(parts) if parts else "Public reporting was not knowable at cutoff."


def _firms_observation(
    notice: Notice, observations: list[Observation], clocks: PacketClocks
) -> str:
    rows = _knowable_ok(
        observations, clocks, "tempo.firms_thermal", notice.trigger.start, notice.trigger.end
    )
    hits = [row for row in rows if (row.value or 0) > 0]
    if not rows:
        z_pairs = _ok_z_pairs(notice, observations, clocks, "tempo.firms_thermal")
        if not z_pairs:
            return "FIRMS thermal detections were not knowable at cutoff."
        peak = max(abs(z) for _, z in z_pairs)
        return f"FIRMS thermal detections peaked at {peak:.2f}σ relative to baseline."
    if not hits:
        return "FIRMS recorded no thermal detections within the monitored staging AOIs."
    total = int(round(sum(row.value or 0 for row in hits)))
    days = ", ".join(_fmt_short_day(_as_dt(row.event_time).date()) for row in hits)
    noun = "detection" if total == 1 else "detections"
    count = "one" if total == 1 else str(total)
    return f"FIRMS recorded {count} thermal {noun} within the monitored staging AOIs on {days}."


def _navarea_observation(
    notice: Notice, observations: list[Observation], clocks: PacketClocks
) -> str:
    rows = _knowable_ok(
        observations, clocks, "nav.spatial_warnings", notice.trigger.start, notice.trigger.end
    )
    values = [row.value for row in rows if row.value is not None]
    if len(values) >= 2:
        first, last = values[0], values[-1]
        if last < first:
            return f"NAVAREA warnings declined from {_fmt_count(first)} to {_fmt_count(last)}"
        if last > first:
            return f"NAVAREA warnings rose from {_fmt_count(first)} to {_fmt_count(last)}"
        return f"NAVAREA warnings remained at {_fmt_count(last)}"
    if values:
        return f"NAVAREA warnings {_fmt_count(values[0])}"
    return "NAVAREA warnings were not knowable at cutoff."


def _watchlist(
    notice: Notice,
    observations: list[Observation],
    clocks: PacketClocks,
    actor_adjective: str = "",
) -> list[dict[str, str]]:
    contributing = set(notice.trigger.contributing_series)
    rows: list[dict[str, str]] = []
    financial_label = (
        f"{actor_adjective} financial conditions" if actor_adjective else "Financial conditions"
    )

    def add(indicator: str, observation: str, series_id: str, z_values: list[float]) -> None:
        rows.append(
            {
                "indicator": indicator,
                "observation": observation,
                "implication": _implication(series_id, z_values),
            }
        )

    if "market.cbr_funding_spread" in contributing:
        add(
            financial_label,
            _cbr_observation(notice, observations, clocks),
            "market.cbr_funding_spread",
            [z for _, z in _ok_z_pairs(notice, observations, clocks, "market.cbr_funding_spread")],
        )
    elif "dyad.moex_usdrub" in contributing or "dyad.fx" in contributing:
        series_id = "dyad.moex_usdrub" if "dyad.moex_usdrub" in contributing else "dyad.fx"
        add(
            financial_label,
            _moex_observation(notice, observations, clocks),
            series_id,
            [z for _, z in _ok_z_pairs(notice, observations, clocks, series_id)],
        )
    if "net.ripe_prefixes" in contributing:
        add(
            "Digital infrastructure",
            _ripe_observation(notice, observations, clocks),
            "net.ripe_prefixes",
            [z for _, z in _ok_z_pairs(notice, observations, clocks, "net.ripe_prefixes")],
        )
    if contributing & set(PUBLIC_SERIES):
        public_z = [
            z
            for series_id in PUBLIC_SERIES
            for _, z in _ok_z_pairs(notice, observations, clocks, series_id)
        ]
        add(
            "Public reporting",
            _public_observation(notice, observations, clocks),
            "talk.gdelt_cameo",
            public_z,
        )
    if "tempo.firms_thermal" in contributing or _knowable_ok(
        observations, clocks, "tempo.firms_thermal", notice.trigger.start, notice.trigger.end
    ):
        add(
            "Physical activity",
            _firms_observation(notice, observations, clocks),
            "tempo.firms_thermal",
            [z for _, z in _ok_z_pairs(notice, observations, clocks, "tempo.firms_thermal")],
        )
    nav_rows = _knowable_ok(
        observations, clocks, "nav.spatial_warnings", notice.trigger.start, notice.trigger.end
    )
    if nav_rows or "nav.spatial_warnings" in contributing:
        add(
            "Maritime warnings",
            _navarea_observation(notice, observations, clocks),
            "nav.spatial_warnings",
            [z for _, z in _ok_z_pairs(notice, observations, clocks, "nav.spatial_warnings")],
        )
    return rows


def _hypothesis_table(state: str) -> list[dict[str, str]]:
    """Likelihoods are PHIA Probability Yardstick terms, not a selected hypothesis."""
    realistic = "Realistic possibility"
    unlikely = "Unlikely"
    highly_unlikely = "Highly unlikely"
    probable = "Likely/probable"
    routine, exercise, defensive, reversible, overt, artefact = (
        realistic,
        realistic,
        realistic,
        realistic,
        realistic,
        unlikely,
    )
    if state == "preparatory_pattern":
        routine, reversible, artefact = unlikely, probable, highly_unlikely
    elif state == "escalation":
        routine, exercise, artefact = unlikely, unlikely, highly_unlikely
    return [
        {
            "hypothesis": "Routine variation",
            "fit": routine,
            "discriminate": "Anomalies decay without additional domains activating.",
        },
        {
            "hypothesis": "Exercise / demonstration",
            "fit": exercise,
            "discriminate": "Physical activity consistent with announced exercise patterns.",
        },
        {
            "hypothesis": "Defensive readiness",
            "fit": defensive,
            "discriminate": "Persistent posture indicators without further domain broadening.",
        },
        {
            "hypothesis": "Reversible preparation",
            "fit": reversible,
            "discriminate": "Additional independent logistical, financial or spatial indicators.",
        },
        {
            "hypothesis": "Preparation for overt action",
            "fit": overt,
            "discriminate": (
                "Sustained multi-domain increase plus corroborating physical or "
                "official-posture evidence."
            ),
        },
        {
            "hypothesis": "Measurement artefact",
            "fit": artefact,
            "discriminate": "Anomalies disappear after source or baseline validation.",
        },
    ]


def _named_elevation(notice: Notice, frame: dict[str, Any]) -> str:
    adj = frame.get("adjective") or ""
    focal_name = frame.get("focal_name") or ""
    others = frame.get("counterpart_names") or []
    capital = frame.get("capital") or ""
    domains = set(notice.trigger.contributing_domains)
    series = set(notice.trigger.contributing_series)
    bits: list[str] = []
    if "domestic_financial_conditions" in domains or "market.cbr_funding_spread" in series:
        bit = f"{adj} financial conditions".strip() or "Financial conditions"
        if capital:
            bit += f" (CBR, {capital})"
        bits.append(bit)
    elif "market" in domains or "dyad.moex_usdrub" in series or "dyad.fx" in series:
        bits.append(f"{adj} financial conditions".strip() or "financial conditions")
    if "digital_infrastructure" in domains or "net.ripe_prefixes" in series:
        bits.append(f"{adj} RIPEstat prefixes".strip() or "RIPEstat prefixes")
    if "information" in domains or "public_attention" in domains:
        if focal_name and others:
            bits.append(f"public reporting on {focal_name} and {others[0]}")
        else:
            bits.append("public reporting")
    if "physical_activity" in domains or "tempo.firms_thermal" in series:
        bits.append("physical activity")
    nav_z = notice.trigger.observed.get("daily_series_z") or []
    nav_values = [
        float(day["nav.spatial_warnings"])
        for day in nav_z
        if isinstance(day, dict) and isinstance(day.get("nav.spatial_warnings"), int | float)
    ]
    nav_persisted = bool(nav_values) and nav_values[-1] >= 1.5
    if "spatial_restriction" in domains and nav_persisted:
        bits.append("maritime warnings")
    if not bits:
        return (
            f"{_domain_clause(notice)} are simultaneously elevated relative to their "
            "recent baselines."
        )
    return (
        f"{_join_clause(bits)} are simultaneously elevated relative to their recent "
        "baselines. The signal is co-movement across those channels."
    )


def _assessment_paragraphs(state: str, notice: Notice, frame: dict[str, Any]) -> list[str]:
    adj = frame.get("adjective") or ""
    others = frame.get("counterpart_names") or []
    if adj and others:
        lead = (
            "We assess it is almost certain that abnormal activity is present "
            f"across several {adj} observables with bearing on {others[0]}."
        )
    elif adj:
        lead = (
            "We assess it is almost certain that abnormal activity is present "
            f"across several {adj} observables."
        )
    else:
        lead = (
            "We assess it is almost certain that abnormal activity is present "
            "across several domains."
        )
    paras = [lead, _named_elevation(notice, frame)]
    geo = frame.get("geographic_frame") or ""
    if state == "escalation":
        paras += [
            (
                "We assess it is likely that the abnormality has intensified: "
                "anomaly energy and domain breadth have increased."
            ),
            (
                "It is a realistic possibility that this reflects heightened readiness "
                "or reversible preparation. It is unlikely to be routine variation."
            ),
            (
                "The decision this supports is urgent collection of dated public "
                "reports of logistics, exercises and government actions on those AOIs."
                if geo
                else (
                    "The decision this supports is urgent collection of dated public "
                    "reports of logistics, exercises and government actions."
                )
            ),
        ]
    elif state == "preparatory_pattern":
        paras += [
            "We assess it is likely that the abnormality is sustained rather than transient.",
            (
                "It is probable that this reflects reversible preparation. Preparation "
                "for overt action remains a realistic possibility."
            ),
            (
                "The decision this supports is collection of dated public "
                "reports of logistics, exercises and government actions, which would bear "
                "on these likelihoods."
            ),
        ]
    else:
        collect = (
            "The decision this supports is collection of dated public "
            "reports of logistics, exercises and government actions on those AOIs."
            if geo
            else (
                "The decision this supports is collection of dated public reports of "
                "logistics, exercises and government actions."
            )
        )
        paras += [
            (
                "It is a realistic possibility that this reflects reversible preparation, "
                "defensive readiness, routine variation or exercise activity. Present "
                "reporting does not discriminate among those explanations."
            ),
            collect,
        ]
    return paras


def _ancr() -> tuple[str, str]:
    # This compiler has measured series, not a reviewed causal assessment. A VIIRS
    # observation or a large FIRMS z-score cannot confer confidence in an explanation.
    return "Low", (
        "Confidence in the explanation is low: the pattern identifies a change worth "
        "investigating, but the packet has not established which activity accounts for it. "
        "The assessment should turn on whether the timing, persistence and content of "
        "publicly available evidence favour preparation over a response to crisis news."
    )


def _compile_product(
    notice: Notice,
    clocks: PacketClocks,
    observations: list[Observation],
    environment: dict[str, Any],
    _context: dict[str, Any],
    theatre: str,
    actor_adjective: str = "",
    frame: dict[str, Any] | None = None,
    *,
    prior_in_window: bool = False,
) -> ProductBrief:
    start, end = notice.trigger.start, notice.trigger.end
    viirs_all = _obs_on_days(observations, "tempo.viirs_aoi", start, end)
    viirs_knowable = _knowable_obs(observations, clocks, "tempo.viirs_aoi", start, end)
    sar_last_missing = any(
        row.quality == "missing" and _as_dt(row.event_time).date() == end
        for row in _obs_on_days(observations, "tempo.s1_backscatter", start, end)
    )
    state, state_label, change = _analytic_state(
        notice,
        prior_in_window=prior_in_window,
    )
    frame = frame or {}
    watchlist = _watchlist(notice, observations, clocks, actor_adjective)
    places = frame.get("places") or []
    official_missing = all(
        dim.get("status") == "missing"
        for dim in environment.get("dimensions") or []
        if dim.get("id") == "official_posture"
    )
    confidence, confidence_rationale = _ancr()

    availability = []
    if viirs_all and not viirs_knowable:
        latency = 3
        sample = viirs_all[0] if viirs_all else None
        if sample:
            latency = int(_parse_extra(sample).get("assumed_latency_days") or 3)
        availability.append(
            f"VIIRS NTL {start.isoformat()}–{end.isoformat()}: not yet available "
            f"({latency}-day reconstructed latency)."
        )

    collection: list[dict[str, str]] = []
    if not viirs_knowable:
        sar_note = (
            " SAR/backscatter coverage for the last episode day is also unavailable."
            if sar_last_missing
            else ""
        )
        collection.append(
            {
                "rank": "1",
                "title": "Public evidence of preparation",
                "why": (
                    "Look for dated public reports of transport, logistics, exercise schedules "
                    "and changes in local restrictions around "
                    f"{_join_plain(places) or 'the declared AOIs'}. Compare their timing with "
                    "the signal and trace repeated reports to their original source. "
                    "These can inform an assessment of preparation without direct observation "
                    "of deployments. "
                    f"VIIRS NTL is unavailable at this cutoff.{sar_note}"
                ),
            }
        )
    if official_missing:
        collection.append(
            {
                "rank": str(len(collection) + 1),
                "title": "Published government actions",
                "why": (
                    "Use FCDO travel-advice change histories, public embassy notices, defence "
                    "ministry releases and published NOTAM/NAVAREA restrictions available by "
                    "the cutoff. Look for dated changes in advice, staffing, exercises or "
                    "access that help distinguish precaution, signalling and preparation. "
                    "Check the collection record before requesting material already gathered."
                ),
            }
        )
    cbr_last_missing = any(
        row.quality == "missing" and _as_dt(row.event_time).date() == end
        for row in _knowable_obs(observations, clocks, "market.cbr_funding_spread", start, end)
    )
    moex_last_missing = any(
        row.quality == "missing" and _as_dt(row.event_time).date() == end
        for row in _obs_on_days(observations, "dyad.moex_usdrub", start, end)
    )
    if cbr_last_missing or moex_last_missing:
        collection.append(
            {
                "rank": str(len(collection) + 1),
                "title": "Financial persistence",
                "why": (
                    "Determine whether the abnormal CBR funding conditions persist or intensify. "
                    "USD/RUB data for the last episode day are not yet available."
                ),
            }
        )
    collection.append(
        {
            "rank": str(len(collection) + 1),
            "title": "Information-environment composition",
            "why": (
                "Inspect the underlying reports: which events explain the increase, when "
                "did they occur, and how many distinct originating sources describe them? "
                "Compare news timing with the other signals to test a common news response."
            ),
        }
    )
    assessment = _assessment_paragraphs(state, notice, frame)
    return ProductBrief(
        headline=f"{theatre}: {PRODUCT_NAME}",
        period=_fmt_period(start, end),
        available_by=_fmt_cutoff(clocks.knowledge_cutoff),
        analytic_state=state,
        analytic_state_label=state_label,
        change=change,
        confidence=confidence,
        confidence_rationale=confidence_rationale,
        assessment=assessment,
        watchlist=watchlist,
        supports=[assessment[0]],
        does_not_support=[],
        caveats=[
            "News-event counts and Wikipedia attention can rise in response to the same "
            "story. Their agreement alone does not supply separate evidence of preparation."
        ]
        if any(
            series in notice.trigger.contributing_series
            for series in ("talk.gdelt_cameo", "talk.icews_cameo", "attn.wiki_pageviews")
        )
        else [],
        keys=list(frame.get("keys") or []),
        geographic_frame=str(frame.get("geographic_frame") or ""),
        hypotheses=_hypothesis_table(state),
        collection=collection,
        availability_warnings=availability,
        analyst_note=confidence_rationale,
    )


def _compile_brief(
    notice: Notice,
    clocks: PacketClocks,
    observations: list[Observation],
    environment: dict[str, Any],
    context: dict[str, Any],
    dependencies: list[dict[str, Any]],
    excluded: int,
    hypotheses: list[HypothesisShell],
) -> list[BriefSection]:
    trigger = notice.trigger
    start, end = trigger.start, trigger.end
    domains = ", ".join(d.replace("_", " ") for d in trigger.contributing_domains) or "none"
    cutoff = clocks.knowledge_cutoff.isoformat()
    sections = [
        BriefSection(
            id="alert",
            title="Alert",
            body=(
                f"Notice {notice.notice_id} opened by "
                f"{trigger.heuristic.get('policy_id') or trigger.policy_id} "
                f"for {start.isoformat()} → {end.isoformat()} "
                f"({trigger.duration_days} days; {trigger.days_before_window_end} days before "
                f"window end). Contributing domains: {domains}. "
                f"Recommended posture: {trigger.recommended_posture.value} "
                f"({trigger.recommended_posture_reason.replace('_', ' ')}). "
                f"Knowledge cutoff: {cutoff} ({clocks.mode}; {clocks.knowledge_rule})."
            ),
        )
    ]
    moved = []
    for series_id in trigger.contributing_series:
        rows = _knowable_obs(observations, clocks, series_id, start, end)
        if not rows:
            moved.append(
                f"{series_id}: in the notice chorus but no observation was knowable at cutoff."
            )
            continue
        bits = []
        for row in rows:
            day = _as_dt(row.event_time).date().isoformat()
            bits.append(f"{day} {row.quality} raw={_fmt_num(row.value)}")
        moved.append(f"{series_id}: " + "; ".join(bits))
    sections.append(
        BriefSection(
            id="what_moved",
            title="What moved (knowable at cutoff)",
            body=(
                "\n".join(moved) if moved else "No contributing-series observations were knowable."
            ),
        )
    )

    quiet_bits = []
    firms = _knowable_obs(observations, clocks, "tempo.firms_thermal", start, end)
    if firms:
        quiet_bits.append(
            "FIRMS thermal: "
            + ", ".join(
                f"{_as_dt(r.event_time).date().isoformat()}={_fmt_num(r.value)}" for r in firms
            )
            + " detections inside staging AOIs."
        )
    viirs = _obs_on_days(observations, "tempo.viirs_aoi", start, end)
    viirs_unk = [
        r for r in viirs if not _knowable(_as_dt(r.available_at), _as_dt(r.retrieved_at), clocks)
    ]
    if viirs_unk:
        latency = _parse_extra(viirs_unk[0]).get("assumed_latency_days", 3)
        quiet_bits.append(
            "VIIRS NTL for these nights exists in the measurement but was not yet available "
            f"at cutoff ({latency}-day reconstructed latency)."
        )
    wiki_late = [
        r
        for r in _obs_on_days(observations, "attn.wiki_pageviews", start, end)
        if not _knowable(_as_dt(r.available_at), _as_dt(r.retrieved_at), clocks)
    ]
    if wiki_late:
        days = ", ".join(_as_dt(r.event_time).date().isoformat() for r in wiki_late)
        quiet_bits.append(
            f"Wikipedia pageviews for {days} were not yet available at cutoff "
            "(next-day Wikimedia lag)."
        )
    sections.append(
        BriefSection(
            id="quiet_or_unavailable",
            title="What was quiet, local, or not yet knowable",
            body=" ".join(quiet_bits) if quiet_bits else "No additional quiet/unavailable notes.",
        )
    )

    env_lines = []
    for dim in environment.get("dimensions") or []:
        env_lines.append(f"{dim['id'].replace('_', ' ')} [{dim['status']}]: {dim['summary']}")
        values = dim.get("values") or []
        if dim["id"] == "geographic_focus":
            for row in values:
                titles = row.get("titles") or {}
                parts = [
                    f"{name}={_fmt_num((info or {}).get('views'))}"
                    for name, info in sorted(titles.items())
                    if isinstance(info, dict)
                ]
                if parts:
                    env_lines.append(f"  {row['day']}: " + ", ".join(parts))
        if dim["id"] == "reporting_volume":
            for row in values:
                env_lines.append(f"  {row['day']}: count={_fmt_num(row.get('count'))}")
    env_lines.append("These dimensions describe the environment. They do not add a vote.")
    icews = _knowable_obs(observations, clocks, "talk.icews_cameo", start, end)
    gdelt = _knowable_obs(observations, clocks, "talk.gdelt_cameo", start, end)
    if icews and gdelt:
        env_lines.append(
            "ICEWS vs GDELT (same public_reporting substrate): ICEWS "
            + ", ".join(
                f"{_as_dt(r.event_time).date().isoformat()}={_fmt_num(r.value)}" for r in icews
            )
            + "; GDELT "
            + ", ".join(
                f"{_as_dt(r.event_time).date().isoformat()}={_fmt_num(r.value)}" for r in gdelt
            )
            + ". Divergence is not independent corroboration."
        )
    sections.append(
        BriefSection(
            id="environment",
            title="Information environment",
            body="\n".join(env_lines),
        )
    )

    geo_lines = list(context.get("notes") or [])
    for item in context.get("items") or []:
        geo_lines.append(item.get("summary") or "")
        for row in item.get("values") or []:
            geo_lines.append(f"  {row['day']}: count={_fmt_num(row.get('count'))}")
    sections.append(
        BriefSection(
            id="geopolitics",
            title="Geopolitical / official context",
            body="\n".join(line for line in geo_lines if line),
        )
    )

    dep_lines = [
        f"{dep['shared_information_substrate']}: {', '.join(dep['series'])}. {dep['caution']}"
        for dep in dependencies
    ]
    sections.append(
        BriefSection(
            id="dependencies",
            title="Dependencies",
            body=" ".join(dep_lines) if dep_lines else "No shared-substrate cautions recorded.",
        )
    )
    hole_lines = [
        f"{row.series_id} {_as_dt(row.event_time).date().isoformat()} quality={row.quality}"
        for row in observations
        if row.quality in {"missing", "source_down"}
        and start <= _as_dt(row.event_time).date() <= end
        and _knowable(_as_dt(row.available_at), _as_dt(row.retrieved_at), clocks)
    ]
    if excluded:
        hole_lines.append(f"{excluded} series-days excluded as not knowable at cutoff.")
    sections.append(
        BriefSection(
            id="unknowns",
            title="Unknowns and holes",
            body="\n".join(hole_lines) if hole_lines else "No coverage holes among knowable days.",
        )
    )
    hypo = ", ".join(item.hypothesis for item in hypotheses)
    sections.append(
        BriefSection(
            id="hypotheses",
            title="Hypotheses (unassessed)",
            body=(
                f"{hypo}. Fit is coarse and evidence-bound. The table is a collection "
                "plan: what would discriminate each explanation."
            ),
        )
    )
    sections.append(
        BriefSection(
            id="cannot_support",
            title="Methodological limits",
            body=(
                "GDELT, ICEWS and Wikipedia share a public-reporting substrate. "
                "VIIRS at this cutoff is inside reconstructed latency. "
                "Unharvested official text is absent."
            ),
        )
    )
    return sections


def _layer_status(environment: dict[str, Any], context: dict[str, Any]) -> dict[str, str]:
    return {
        "anomaly": "present",
        "notice": "present",
        "information_environment": environment["status"],
        "geopolitical_context": context["status"],
        "assessment": "empty",
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
    environment = _information_environment(notice, evidence, observations, clocks)
    context = _geopolitical_context(notice, observations, clocks)
    log.append(
        CollectionLogEntry(
            action="environment",
            detail=(
                f"information_environment={environment['status']} "
                f"geopolitical_context={context['status']}"
            ),
        )
    )
    packet = Packet(
        packet_id=packet_id_for(notice.notice_id, clocks.mode, clocks.knowledge_cutoff),
        notice_id=notice.notice_id,
        scenario_id=scenario_id,
        clocks=clocks,
        layers=_layer_status(environment, context),
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
        information_environment=environment,
        geopolitical_context=context,
        collected_evidence=evidence,
        counterevidence=[],
        unknowns=list(notice.trigger.unknowns),
        dependencies=_dependencies(notice.trigger.contributing_series),
        hypotheses=[HypothesisShell(hypothesis=name) for name in _hypothesis_ids(project_root)],
        collection_log=log,
    )
    packet.brief = _compile_brief(
        notice,
        clocks,
        observations,
        environment,
        context,
        packet.dependencies,
        excluded,
        packet.hypotheses,
    )
    frame = _theatre_frame(project_root, scenario_id)
    packet.product = _compile_product(
        notice,
        clocks,
        observations,
        environment,
        context,
        _theatre_name(project_root, scenario_id),
        _actor_adjective(project_root, scenario_id),
        frame,
        prior_in_window=_prior_notice_in_window(project_root, notice),
    )
    return packet


def save_packet(project_root: Path, packet: Packet, notice: Notice) -> Path:
    path = packet_path(project_root, packet.scenario_id, packet.packet_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(packet.model_dump_json(indent=2) + "\n", encoding="utf-8")
    brief_path = path.with_name("brief.md")
    lines: list[str] = []
    if packet.product:
        from wsf.briefing_standards import packet_presentation

        p = ProductBrief.model_validate(packet_presentation(packet.model_dump()))
        lines.extend(
            [
                f"# {p.headline}",
                "",
                f"{p.period} | Information available by {p.available_by}",
                "",
                f"**Analytic state:** {p.analytic_state_label}  ",
                f"**Analytical confidence (AnCR):** {p.confidence}  ",
                f"**Change:** {p.change}",
                "",
                "## BLUF",
                "",
                p.bluf,
                "",
                p.confidence_rationale,
                "",
                "## Source assessment",
                "",
                p.source_assessment,
                "",
            ]
        )
        if p.keys:
            lines.extend([f"**Keys:** {'; '.join(p.keys)}", ""])
        lines.extend(
            [
                f"_Notice {packet.notice_id} · cutoff "
                f"`{packet.clocks.knowledge_cutoff.isoformat()}` "
                f"({packet.clocks.mode})._",
                "",
                "## Assessment",
                "",
            ]
        )
        for para in p.assessment:
            lines.extend([para, ""])
        for warning in p.availability_warnings:
            lines.extend([f"> {warning}", ""])
        lines += ["## Why this is on the watchlist", ""]
        for row in p.watchlist:
            lines.append(f"- **{row['indicator']}.** {row['observation']} — {row['implication']}")
        lines += [
            "",
            "The important feature is co-movement across otherwise distinct domains, "
            "rather than any single decisive indicator.",
            "",
        ]
        for caveat in p.caveats:
            lines.extend([caveat, ""])
        lines += [
            "## Competing explanations",
            "",
            "Likelihoods use the PHIA Probability Yardstick.",
            "",
        ]
        for row in p.hypotheses:
            lines.append(
                f"- **{row['hypothesis']}** — {row['fit']}. "
                f"What would discriminate: {row['discriminate']}"
            )
        lines += ["", "## Collection requirements", ""]
        for row in p.collection:
            lines.append(f"{row['rank']}. **{row['title']}.** {row['why']}")
        lines += [
            "",
            "## Analyst note",
            "",
            p.analyst_note,
            "",
            "---",
            "",
            "# Evidence and provenance",
            "",
        ]
    else:
        lines.extend(
            [
                f"# Brief: {packet.notice_id}",
                "",
                f"Cutoff `{packet.clocks.knowledge_cutoff.isoformat()}` ({packet.clocks.mode}).",
                "",
            ]
        )
    for section in packet.brief:
        lines.extend([f"## {section.title}", "", section.body, ""])
    brief_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    from wsf.brief_pdf import write_brief_pdf

    write_brief_pdf(packet, path.with_name("brief.pdf"))
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
