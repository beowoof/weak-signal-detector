"""Packet-scoped collection tasks. Harvest files into the packet; do not vote."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal

from pydantic import BaseModel, Field

from wsf.connectors.base import PullRequest
from wsf.connectors.copernicus_catalogue import search_catalogue
from wsf.connectors.declared_posture import DeclaredPostureConnector, state_at_cutoff
from wsf.connectors.http import HttpTransport, UrllibTransport
from wsf.connectors.tavily import harvest_searches
from wsf.notice import (
    CollectionPosture,
    Notice,
    NoticeAction,
    NoticeState,
    apply_action,
    load_notice,
    save_notice,
)
from wsf.packet import (
    CollectionLogEntry,
    Packet,
    _as_dt,
    _fmt_num,
    _hypothesis_table,
    _knowable,
    _load_window_observations,
    _obs_on_days,
    _parse_extra,
    _theatre_frame,
    build_and_save,
    packet_directory,
    packet_path,
)
from wsf.scenario import load_scenario
from wsf.types import Observation

TASK_SCHEMA = "collection_task_v0"
LOOKBACK_DAYS = 30
VALIDATE = "validate"
CHRONOLOGY = "chronology"
PHYSICAL = "refresh_physical"
OFFICIAL = "official_pack"
SEARCH = "open_source_search"
HARVEST_KINDS = (CHRONOLOGY, PHYSICAL, OFFICIAL)
ALL_KINDS = (VALIDATE, *HARVEST_KINDS, SEARCH)

SERIES_CHRONICLE = (
    "market.cbr_funding_spread",
    "dyad.moex_usdrub",
    "net.ripe_prefixes",
    "talk.gdelt_cameo",
    "attn.wiki_pageviews",
    "tempo.firms_thermal",
    "nav.spatial_warnings",
)


class CollectionTask(BaseModel):
    schema_id: Literal["collection_task_v0"] = TASK_SCHEMA
    task_id: str
    kind: str
    title: str
    status: Literal["complete", "blocked"]
    posture: str
    knowledge_cutoff: datetime
    ran_at: datetime
    summary: str
    items: list[dict[str, Any]] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    analyst_question: str | None = None
    plan: dict[str, Any] | None = None


def collection_directory(project_root: Path, scenario_id: str, packet_id: str) -> Path:
    return packet_directory(project_root, scenario_id, packet_id) / "collection"


def _task_path(root: Path, kind: str) -> Path:
    return root / f"{kind}.json"


def load_collection(project_root: Path, scenario_id: str, packet_id: str) -> dict[str, Any]:
    directory = collection_directory(project_root, scenario_id, packet_id)
    tasks: list[dict[str, Any]] = []
    if directory.is_dir():
        for kind in ALL_KINDS:
            path = _task_path(directory, kind)
            if path.is_file():
                tasks.append(
                    CollectionTask.model_validate_json(path.read_text()).model_dump(mode="json")
                )
    return {"packet_id": packet_id, "tasks": tasks}


def _day_of(row: Observation) -> date:
    return _as_dt(row.event_time).date()


def _frame(project_root: Path, scenario_id: str) -> dict[str, Any]:
    try:
        return _theatre_frame(project_root, scenario_id)
    except (OSError, ValueError, FileNotFoundError):
        return {}


def _window(
    notice: Notice,
    clocks,
    *,
    start: date | None = None,
    extra_notes: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "evidence_start": (start or notice.trigger.start).isoformat(),
        "evidence_end": notice.trigger.end.isoformat(),
        "knowledge_cutoff": clocks.knowledge_cutoff.isoformat(),
        "admissible": (
            "Use only material with available_at at or before the knowledge cutoff. "
            "Replay uses available_at; live also requires retrieved_at."
        ),
        "notes": list(extra_notes or []),
    }


def _discriminators(packet: Packet, family: str) -> list[dict[str, str]]:
    rows = (
        list(packet.product.hypotheses)
        if packet.product and packet.product.hypotheses
        else _hypothesis_table("watch")
    )
    physical = {
        "Exercise / demonstration",
        "Defensive readiness",
        "Reversible preparation",
        "Preparation for overt action",
        "Measurement artefact",
    }
    official = {
        "Exercise / demonstration",
        "Defensive readiness",
        "Reversible preparation",
        "Preparation for overt action",
    }
    wanted = physical if family == "physical" else official
    out = [
        {"hypothesis": row["hypothesis"], "look_for": row["discriminate"]}
        for row in rows
        if row.get("hypothesis") in wanted
    ]
    if family == "official":
        out.append(
            {
                "hypothesis": "Declared prior",
                "look_for": (
                    "Whether the quantitative cue is consistent with, ahead of, or "
                    "divergent from contemporaneous UK/US public posture."
                ),
            }
        )
    return out


def _series_status(items: list[dict[str, Any]], series_id: str) -> str:
    rows = [item for item in items if item.get("series_id") == series_id]
    if not rows:
        return "not_in_collection"
    if any(item.get("knowable") and item.get("quality") == "ok" for item in rows):
        return "knowable"
    if any(item.get("knowable") is False for item in rows):
        return "awaiting_cutoff"
    if any(item.get("quality") in {"missing", "source_down"} for item in rows):
        return "missing"
    return "present"


PHYSICAL_SOURCES = (
    {
        "id": "tempo.firms_thermal",
        "name": "FIRMS (NOAA-20 thermal)",
        "role": "corpus",
        "answers": (
            "Thermal detections inside the monitored staging AOIs as a combined set. "
            "Name an AOI only when the observation attributes it."
        ),
        "query": (
            "Sum detections per day inside each AOI bbox. Do not read a combined "
            "count as one detection in every listed place."
        ),
    },
    {
        "id": "tempo.viirs_aoi",
        "name": "VIIRS night-time lights",
        "role": "corpus",
        "answers": "Brightness and concentration at named AOIs.",
        "query": (
            "Episode nights at each staging AOI. Reconstructed 3-day latency: a night "
            "is inadmissible until available_at."
        ),
    },
    {
        "id": "tempo.s1_backscatter",
        "name": "Sentinel-1 SAR backscatter",
        "role": "corpus",
        "answers": "All-weather change at named AOIs when optical is delayed or cloudy.",
        "query": "Ascending IW VV on AOI bboxes for episode days knowable at cutoff.",
    },
    {
        "id": "copernicus_catalogue",
        "name": "Copernicus catalogue (S1 GRD / S2 L1C)",
        "role": "desk",
        "answers": (
            "Whether public Sentinel-1 GRD or Sentinel-2 L1C granules exist over named "
            "AOIs on admissible dates. Pointers only; scenes are not downloaded."
        ),
        "query": (
            "CDSE OData per AOI bbox. Sensing in the episode; knowable if reconstructed "
            "availability is at or before cutoff. Does not vote."
        ),
    },
    {
        "id": "osm_infrastructure",
        "name": "OpenStreetMap infrastructure",
        "role": "open",
        "answers": "Railheads, roads, airfields and staging-area layout at named AOIs.",
        "query": "Static map layers. Always knowable at cutoff.",
    },
)

OFFICIAL_SOURCES = (
    {
        "id": "posture.travel_risk",
        "name": "UK FCDO travel advice",
        "role": "desk",
        "answers": "UK-declared geographic risk, leave-now, and travel-advice escalations.",
        "query": "FCDO change_history for theatre countries; notes dated at or before cutoff.",
    },
    {
        "id": "us_state_advisories",
        "name": "US State travel advisories",
        "role": "desk",
        "answers": (
            "US-declared travel risk. Live API only when contemporaneous; otherwise "
            "the last Wayback snapshot at or before cutoff."
        ),
        "query": "State CA API or Wayback CDX last snapshot at or before cutoff.",
    },
    {
        "id": "nav.spatial_warnings",
        "name": "NAVAREA maritime warnings",
        "role": "corpus",
        "answers": "Public maritime restrictions. Not diplomatic posture.",
        "query": "Knowable NAVAREA counts, episode plus 30-day lookback.",
    },
    {
        "id": "air.notam_restrictions",
        "name": "NOTAM / airspace restrictions",
        "role": "open",
        "answers": "Airspace closures and other costly formal measures.",
        "query": "NOTAM text for the theatre, dates at or before cutoff. Not in this corpus.",
    },
    {
        "id": "official_statements",
        "name": "Official statements and formal measures",
        "role": "open",
        "answers": (
            "Signalling versus costly government action: statements, warnings, "
            "defence announcements, diplomatic drawdowns, sanctions."
        ),
        "query": (
            "Contemporaneous Russian, Ukrainian, UK, US and allied issuers. Identify "
            "changes in declared threat assessment or costly action. Desk does not "
            "scrape news."
        ),
    },
)


def _physical_sources(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for source in PHYSICAL_SOURCES:
        row = dict(source)
        if source["id"] == "copernicus_catalogue":
            hits = [item for item in items if item.get("kind") == "catalogue_granule"]
            if any(item.get("knowable") for item in hits):
                row["status"] = "knowable"
            elif hits:
                row["status"] = "awaiting_cutoff"
            else:
                row["status"] = "not_in_collection"
        elif source["role"] == "open":
            row["status"] = "analyst"
        else:
            row["status"] = _series_status(items, source["id"])
        rows.append(row)
    return rows


def _official_sources(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    declared = any(item.get("kind") == "declared_posture" for item in items)
    for source in OFFICIAL_SOURCES:
        row = dict(source)
        if source["role"] == "open":
            row["status"] = "analyst"
        elif source["id"] in {"posture.travel_risk", "us_state_advisories"}:
            row["status"] = "knowable" if declared else "not_in_collection"
        elif source["id"] == "nav.spatial_warnings":
            row["status"] = (
                "knowable"
                if any(item.get("series_id") == "nav.spatial_warnings" for item in items)
                else "not_in_collection"
            )
        else:
            row["status"] = "not_in_collection"
        rows.append(row)
    return rows


def _official_issuers(frame: dict[str, Any]) -> list[str]:
    names: list[str] = []
    adjective = frame.get("adjective") or ""
    focal = frame.get("focal_name") or ""
    if adjective:
        names.append(f"{adjective} government")
    elif focal:
        names.append(focal)
    counterparts = frame.get("counterpart_adjectives") or frame.get("counterpart_names") or []
    for name in counterparts:
        names.append(f"{name} government")
    for extra in ("United Kingdom", "United States", "relevant allies"):
        if extra not in names:
            names.append(extra)
    return names


def _knowable_in(
    observations: list[Observation],
    clocks,
    series_id: str,
    start: date,
    end: date,
) -> list[Observation]:
    rows = []
    for item in _obs_on_days(observations, series_id, start, end):
        if _knowable(_as_dt(item.available_at), _as_dt(item.retrieved_at), clocks):
            rows.append(item)
    return rows


def _validate(packet: Packet, notice: Notice, clocks, now: datetime) -> CollectionTask:
    items: list[dict[str, Any]] = []
    deps = packet.dependencies or []
    if deps:
        for dep in deps:
            members = ", ".join(dep.get("series") or [])
            items.append(
                {
                    "id": "substrate",
                    "status": "warn",
                    "text": (f"{members} share {dep.get('shared_information_substrate')}."),
                }
            )
    else:
        items.append(
            {
                "id": "substrate",
                "status": "ok",
                "text": "No shared-substrate cluster among contributing series.",
            }
        )
    domains = notice.trigger.contributing_domains
    items.append(
        {
            "id": "chorus",
            "status": "ok" if len(domains) >= 3 else "warn",
            "text": (
                f"{len(domains)} contributing domains: "
                + ", ".join(d.replace("_", " ") for d in domains)
            ),
        }
    )
    holes = [
        item
        for item in packet.collected_evidence
        if item.kind == "coverage_hole" or "quality=missing" in (item.text or "")
    ]
    items.append(
        {
            "id": "holes",
            "status": "warn" if holes else "ok",
            "text": (
                f"{len(holes)} coverage holes among knowable series-days."
                if holes
                else "No coverage holes among knowable series-days."
            ),
        }
    )
    viirs = [
        warning
        for warning in (packet.product.availability_warnings if packet.product else [])
        if "VIIRS" in warning
    ]
    items.append(
        {
            "id": "viirs_latency",
            "status": "warn" if viirs else "ok",
            "text": viirs[0] if viirs else "No VIIRS availability warning on this packet.",
        }
    )
    imaging = notice.trigger.imaging_status_by_day or {}
    items.append(
        {
            "id": "imaging",
            "status": "ok",
            "text": "Imaging by day: "
            + (", ".join(f"{day}={status}" for day, status in sorted(imaging.items())) or "none"),
        }
    )
    return CollectionTask(
        task_id=f"{packet.packet_id}:validate",
        kind=VALIDATE,
        title="Validate the cue",
        status="complete",
        posture=CollectionPosture.focused.value,
        knowledge_cutoff=clocks.knowledge_cutoff,
        ran_at=now,
        summary=(
            "Checklist from the packet: substrate, chorus breadth, holes, latency. No new harvest."
        ),
        items=items,
        notes=[
            "Confirm the multi-domain effect is not duplicated reporting "
            "or one common exogenous event."
        ],
        analyst_question=(
            "Is the chorus real, or is it one information environment counted twice?"
        ),
    )


def _chronology(
    packet: Packet, notice: Notice, observations: list[Observation], clocks, now: datetime
) -> CollectionTask:
    start = notice.trigger.start
    lookback_start = start - timedelta(days=LOOKBACK_DAYS)
    lookback_end = start - timedelta(days=1)
    days: list[dict[str, Any]] = []
    cursor = lookback_start
    while cursor <= lookback_end:
        row: dict[str, Any] = {"day": cursor.isoformat(), "series": []}
        for series_id in SERIES_CHRONICLE:
            match = next(
                (item for item in _knowable_in(observations, clocks, series_id, cursor, cursor)),
                None,
            )
            if match is None:
                continue
            extra = _parse_extra(match)
            note_bits = []
            if extra.get("root_codes"):
                note_bits.append("codes=" + ",".join(str(c) for c in extra["root_codes"]))
            if extra.get("asns"):
                note_bits.append("asn=" + ",".join(str(a) for a in extra["asns"]))
            row["series"].append(
                {
                    "series_id": series_id,
                    "value": match.value,
                    "quality": match.quality,
                    "note": "; ".join(note_bits) or None,
                }
            )
        if row["series"]:
            days.append(row)
        cursor += timedelta(days=1)

    highlights = []
    ripe = _knowable_in(
        observations, clocks, "net.ripe_prefixes", lookback_start, notice.trigger.end
    )
    ripe_vals = [
        (_day_of(item), item.value)
        for item in ripe
        if item.quality == "ok" and item.value is not None
    ]
    for prev, last in zip(ripe_vals, ripe_vals[1:], strict=False):
        if prev[1] and last[1] and last[1] < prev[1] * 0.5:
            highlights.append(
                f"RIPE prefixes {_fmt_num(prev[1])} ({prev[0].isoformat()}) → "
                f"{_fmt_num(last[1])} ({last[0].isoformat()})."
            )
            break
    cbr = _knowable_in(
        observations, clocks, "market.cbr_funding_spread", lookback_start, notice.trigger.end
    )
    cbr_ok = [item for item in cbr if item.quality == "ok" and item.value is not None]
    if cbr_ok:
        peak = max(cbr_ok, key=lambda item: abs(item.value or 0))
        highlights.append(
            f"CBR funding spread peaked at {_fmt_num(peak.value)} on "
            f"{_day_of(peak).isoformat()} in the lookback-plus-episode window."
        )

    notes = [
        "Assembled from in-corpus observations knowable at cutoff. Not a live search.",
        *highlights,
    ]
    status: Literal["complete", "blocked"] = "complete" if days else "blocked"
    return CollectionTask(
        task_id=f"{packet.packet_id}:chronology",
        kind=CHRONOLOGY,
        title="Crisis baseline (30 days)",
        status=status,
        posture=CollectionPosture.focused.value,
        knowledge_cutoff=clocks.knowledge_cutoff,
        ran_at=now,
        summary=(
            f"{len(days)} days with knowable observations "
            f"{lookback_start.isoformat()} → {lookback_end.isoformat()}."
            if days
            else "No knowable lookback observations in this collection."
        ),
        items=days,
        notes=notes,
        analyst_question="Abnormal relative to what was already happening?",
    )


def _physical(
    packet: Packet,
    notice: Notice,
    observations: list[Observation],
    clocks,
    now: datetime,
    project_root: Path,
) -> CollectionTask:
    start, end = notice.trigger.start, notice.trigger.end
    items: list[dict[str, Any]] = []
    for series_id, label in (
        ("tempo.firms_thermal", "FIRMS"),
        ("tempo.viirs_aoi", "VIIRS"),
        ("tempo.s1_backscatter", "SAR"),
    ):
        for row in _obs_on_days(observations, series_id, start, end):
            knowable = _knowable(_as_dt(row.available_at), _as_dt(row.retrieved_at), clocks)
            extra = _parse_extra(row)
            items.append(
                {
                    "series_id": series_id,
                    "label": label,
                    "day": _day_of(row).isoformat(),
                    "value": row.value if knowable else None,
                    "quality": row.quality if knowable else "not_yet_available",
                    "knowable": knowable,
                    "available_at": _as_dt(row.available_at).isoformat(),
                    "aoi_means": extra.get("aoi_means") if knowable else None,
                    "contributing_aois": extra.get("contributing_aois") if knowable else None,
                    "coverage_details": extra.get("coverage_details") if knowable else None,
                    "availability_reason": (
                        "Not available under "
                        f"{extra.get('availability_regime', 'recorded availability')} "
                        f"until {_as_dt(row.available_at).isoformat()}"
                        if not knowable
                        else None
                    ),
                    "orbit": extra.get("orbit_direction"),
                }
            )
    viirs_waiting = [item for item in items if item["label"] == "VIIRS" and not item["knowable"]]
    notes = []
    if viirs_waiting:
        notes.append(
            f"VIIRS: {len(viirs_waiting)} episode night(s) awaiting availability at cutoff."
        )
    sar_missing = [
        item
        for item in items
        if item["label"] == "SAR" and item["quality"] in {"missing", "not_yet_available"}
    ]
    if sar_missing:
        notes.append("SAR/backscatter is missing or not knowable on one or more episode days.")
    frame = _frame(project_root, notice.trigger.scenario_id)
    granules, catalogue_notes = search_catalogue(
        UrllibTransport(),
        list(frame.get("aois") or []),
        start=start,
        end=end,
        cutoff=clocks.knowledge_cutoff,
    )
    items.extend(granules)
    notes.extend(catalogue_notes)
    if granules:
        _attach_catalogue(packet, granules)
        packet.collection_log.append(
            CollectionLogEntry(
                action="physical_catalogue",
                detail=(
                    f"listed={len(granules)} knowable="
                    f"{sum(1 for row in granules if row.get('knowable'))}"
                ),
            )
        )
    status: Literal["complete", "blocked"] = "complete" if items else "blocked"
    window_notes = list(notes)
    question = (
        "Is there independent physical evidence of concentration, dispersal or movement "
        "in the named staging AOIs?"
    )
    plan = {
        "question": question,
        "aois": list(frame.get("aois") or []),
        "window": _window(notice, clocks, extra_notes=window_notes),
        "sources": _physical_sources(items),
        "discriminators": _discriminators(packet, "physical"),
    }
    return CollectionTask(
        task_id=f"{packet.packet_id}:refresh_physical",
        kind=PHYSICAL,
        title="Refresh physical",
        status=status,
        posture=CollectionPosture.focused.value,
        knowledge_cutoff=clocks.knowledge_cutoff,
        ran_at=now,
        summary=(
            f"{len(items)} physical series-days in the episode; "
            f"{sum(1 for item in items if item['knowable'])} knowable at cutoff."
            if items
            else "No FIRMS, VIIRS or SAR observations in this collection."
        ),
        items=items,
        notes=notes,
        analyst_question=question,
        plan=plan,
    )


def _declared_codes(project_root: Path, scenario_id: str) -> list[str]:
    try:
        scenario = load_scenario(project_root, scenario_id)
    except (OSError, ValueError, FileNotFoundError):
        return ["RUS", "UKR"]
    codes = []
    if scenario.actors.focal:
        codes.append(scenario.actors.focal.upper())
    for code in scenario.actors.counterparts:
        if code and code.upper() not in codes:
            codes.append(code.upper())
    if "RUS" in codes and "UKR" not in codes:
        codes.append("UKR")
    return codes or ["RUS", "UKR"]


def _fetch_declared(
    project_root: Path,
    notice: Notice,
    clocks,
    start: date,
    end: date,
) -> tuple[list[dict[str, Any]], list[str], dict[str, Any] | None]:
    codes = _declared_codes(project_root, notice.trigger.scenario_id)
    titles = []
    if "UKR" in codes:
        titles.append("Ukraine")
    if "RUS" in codes:
        titles.append("Russia")
    request = PullRequest(
        source="declared_posture",
        series_id="posture.travel_risk",
        scenario_id=notice.trigger.scenario_id,
        window_id=notice.trigger.window_id,
        start=start,
        end=end,
        queries=SimpleNamespace(
            facility_actor=codes[0] if codes else "RUS",
            cameo_actor=codes[0] if codes else "RUS",
            wiki_titles=titles,
        ),
        retrieved_at=clocks.knowledge_cutoff,
    )
    try:
        connector = DeclaredPostureConnector(UrllibTransport())
        result = connector.pull(request)
    except (OSError, TimeoutError, ValueError) as error:
        return [], [f"Declared posture harvest failed: {error}"], None
    events = [
        {
            "kind": "declared_posture",
            "country": event.get("country"),
            "government": event.get("government"),
            "date": event["at"].date().isoformat(),
            "at": event["at"].isoformat(),
            "category": event.get("category"),
            "severity": event.get("severity"),
            "action": event.get("action"),
            "text": event.get("text"),
            "costly": bool(event.get("costly")),
        }
        for event in getattr(connector, "last_events", [])
        if start <= event["at"].date() <= end
    ]
    snapshot = state_at_cutoff(getattr(connector, "last_events", []), clocks.knowledge_cutoff)
    notes = [
        "Declared UK/US posture is the public prior.",
        "Weight: embassy drawdown, leave-now, travel-advice escalation over rhetoric.",
    ]
    if not events:
        notes.append("No dated FCDO/State posture events knowable at this cutoff.")
    us_used = any(item.get("government") == "US/State" for item in events)
    if not us_used:
        notes.append(
            "US State contemporaneous advisory was not reconstructed "
            "(live API after cutoff and no Wayback snapshot at or before cutoff)."
        )
    travel = snapshot.get("travel_risk") or {}
    if travel:
        bits = [f"{code} level {level}" for code, level in sorted(travel.items())]
        notes.append("Travel risk in effect at cutoff: " + ", ".join(bits) + ".")
    if snapshot.get("diplomatic_drawdown"):
        notes.append("Diplomatic drawdown is in effect at cutoff (embassy/dependants).")
    if snapshot.get("leave_advice"):
        notes.append("Leave-now / against-all-travel advice is in effect at cutoff.")
    if result.item.get("n_ok") == 0 and not events:
        notes.append("Declared-posture connector returned no knowable events.")
    return events, notes, snapshot


def _attach_catalogue(packet: Packet, granules: list[dict[str, Any]]) -> None:
    knowable = [row for row in granules if row.get("knowable")]
    n_sar = sum(1 for row in knowable if row.get("collection") == "SENTINEL-1")
    n_opt = sum(1 for row in knowable if row.get("collection") == "SENTINEL-2")
    geo = packet.geopolitical_context or {}
    items = [item for item in (geo.get("items") or []) if item.get("kind") != "physical_catalogue"]
    items.append(
        {
            "kind": "physical_catalogue",
            "votes": False,
            "summary": (
                f"{len(knowable)} Copernicus granules over named AOIs knowable at cutoff "
                f"({n_sar} SAR, {n_opt} optical). Pointers only; do not vote."
            ),
            "n_knowable": len(knowable),
            "n_listed": len(granules),
            "granules": knowable[:40],
        }
    )
    notes = list(geo.get("notes") or [])
    notes.append(
        "Physical catalogue is a coverage pointer. Presence of a granule is not "
        "equipment detection or confirmation of mobilisation."
    )
    geo["items"] = items
    geo["notes"] = notes
    geo["status"] = "partial"
    geo["votes"] = False
    packet.geopolitical_context = geo


def _attach_posture(packet: Packet, snapshot: dict[str, Any], events: list[dict[str, Any]]) -> None:
    geo = packet.geopolitical_context or {}
    items = [item for item in (geo.get("items") or []) if item.get("kind") != "declared_posture"]
    items.append(
        {
            "kind": "declared_posture",
            "votes": False,
            "summary": "UK/US publicly declared geographic risk and diplomatic posture at cutoff.",
            "travel_risk": snapshot.get("travel_risk") or {},
            "diplomatic_drawdown": snapshot.get("diplomatic_drawdown"),
            "leave_advice": snapshot.get("leave_advice"),
            "threat_language": snapshot.get("threat_language"),
            "n_costly_events": len(snapshot.get("costly_events") or []),
            "events": events[-12:],
        }
    )
    notes = [
        note
        for note in (geo.get("notes") or [])
        if "No RIMA, gazette, or official-statement" not in note
        and "collector is not wired" not in note
    ]
    notes.append(
        "Declared posture is the UK/US public prior. Compare the quantitative cue to it: "
        "consistent with, ahead of, or divergent from that prior."
    )
    geo["items"] = items
    geo["notes"] = notes
    geo["status"] = "partial"
    geo["votes"] = False
    packet.geopolitical_context = geo
    env = packet.information_environment or {}
    dimensions = list(env.get("dimensions") or [])
    for dim in dimensions:
        if dim.get("id") == "official_posture":
            dim["status"] = "present"
            dim["summary"] = (
                "UK FCDO travel-advice history (cutoff-filtered) plus US State advisories "
                "when contemporaneous. Does not vote."
            )
    env["dimensions"] = dimensions
    packet.information_environment = env


def _official(
    packet: Packet,
    notice: Notice,
    observations: list[Observation],
    clocks,
    now: datetime,
    project_root: Path,
) -> CollectionTask:
    start = notice.trigger.start - timedelta(days=LOOKBACK_DAYS)
    end = notice.trigger.end
    nav = _knowable_in(observations, clocks, "nav.spatial_warnings", start, end)
    items: list[dict[str, Any]] = [
        {
            "series_id": "nav.spatial_warnings",
            "day": _day_of(row).isoformat(),
            "value": row.value,
            "quality": row.quality,
        }
        for row in nav
    ]
    missing = []
    if not _obs_on_days(observations, "official.gazette", start, end) and not _obs_on_days(
        observations, "official.gazette_cadence", start, end
    ):
        missing.append("gazette / official statements")
    if not _obs_on_days(observations, "air.notam_restrictions", start, end):
        missing.append("NOTAM")
    notes = [
        "NAVAREA counts are public maritime warnings, not diplomatic posture.",
        "No RIMA or defence-ministry statement harvest is attached to this collection.",
    ]
    if missing:
        notes.append("Missing in this collection: " + ", ".join(missing) + ".")
    if nav:
        first, last = nav[0].value, nav[-1].value
        notes.append(
            f"NAVAREA warnings {_fmt_num(first)} ({_day_of(nav[0]).isoformat()}) → "
            f"{_fmt_num(last)} ({_day_of(nav[-1]).isoformat()})."
        )
    declared_events, declared_notes, snapshot = _fetch_declared(
        project_root, notice, clocks, start, end
    )
    items.extend(declared_events)
    notes.extend(declared_notes)
    if snapshot is not None:
        _attach_posture(packet, snapshot, declared_events)
    status: Literal["complete", "blocked"] = "complete" if items or declared_events else "blocked"
    n_declared = len(declared_events)
    summary = (
        f"{len(nav)} knowable NAVAREA days; {n_declared} dated UK/US posture events "
        "knowable at cutoff."
        if items or declared_events
        else "No official-posture observations knowable at cutoff."
    )
    question = (
        "Is the quantitative cue consistent with, ahead of, or divergent from "
        "the contemporaneous UK/US declared prior?"
    )
    frame = _frame(project_root, notice.trigger.scenario_id)
    plan = {
        "question": question,
        "issuers": _official_issuers(frame),
        "aois": list(frame.get("aois") or []),
        "window": _window(
            notice,
            clocks,
            start=start,
            extra_notes=["Lookback is 30 days through episode end, cutoff-filtered."],
        ),
        "sources": _official_sources(items),
        "discriminators": _discriminators(packet, "official"),
    }
    return CollectionTask(
        task_id=f"{packet.packet_id}:official_pack",
        kind=OFFICIAL,
        title="Official pack",
        status=status,
        posture=CollectionPosture.focused.value,
        knowledge_cutoff=clocks.knowledge_cutoff,
        ran_at=now,
        summary=summary,
        items=items,
        notes=notes,
        analyst_question=question,
        plan=plan,
    )


def _attach_search(packet: Packet, harvested: dict[str, Any]) -> None:
    hits = harvested.get("hits") or []
    geo = packet.geopolitical_context or {}
    items = [item for item in (geo.get("items") or []) if item.get("kind") != "open_source_search"]
    items.append(
        {
            "kind": "open_source_search",
            "votes": False,
            "summary": (
                f"{len(hits)} Tavily hits published on or before cutoff. Search does not vote."
            ),
            "n_hits": len(hits),
            "dropped_n": harvested.get("dropped_n") or 0,
            "queries": harvested.get("queries") or [],
        }
    )
    notes = list(geo.get("notes") or [])
    if harvested.get("reason"):
        notes.append(str(harvested["reason"]))
    packet.geopolitical_context = {
        **geo,
        "items": items,
        "notes": notes,
        "status": geo.get("status") or "partial",
    }


def _search(
    packet: Packet,
    notice: Notice,
    clocks,
    now: datetime,
    project_root: Path,
    transport: HttpTransport | None = None,
) -> CollectionTask:
    start = notice.trigger.start - timedelta(days=LOOKBACK_DAYS)
    harvested = harvest_searches(
        notice,
        project_root,
        start=start,
        cutoff=clocks.knowledge_cutoff,
        transport=transport,
    )
    items = list(harvested.get("hits") or [])
    notes = [
        "Tavily news search is dated to the packet cutoff. Hits do not vote.",
        "Undated results and anything published after cutoff are dropped.",
    ]
    if harvested.get("reason"):
        notes.append(str(harvested["reason"]))
    notes.append(
        f"{len(items)} kept, {harvested.get('dropped_n') or 0} dropped, "
        f"{len(harvested.get('queries') or [])} queries."
    )
    unverified = sum(1 for item in items if item.get("date_unverified"))
    if unverified:
        notes.append(
            f"{unverified} official-domain hits have no publish date; treat as unverified."
        )
    if items:
        _attach_search(packet, harvested)
    status: Literal["complete", "blocked"] = (
        "blocked" if harvested.get("status") == "blocked" else "complete"
    )
    question = (
        "Do contemporaneous public reports corroborate, contradict, or leave "
        "unresolved the quantitative cue?"
    )
    frame = _frame(project_root, notice.trigger.scenario_id)
    plan = {
        "question": question,
        "window": _window(notice, clocks, start=start),
        "queries": harvested.get("queries") or [],
        "aois": list(frame.get("aois") or []),
        "discriminators": _discriminators(packet, "search"),
    }
    return CollectionTask(
        task_id=f"{packet.packet_id}:open_source_search",
        kind=SEARCH,
        title="Open-source search",
        status=status,
        posture=CollectionPosture.focused.value,
        knowledge_cutoff=clocks.knowledge_cutoff,
        ran_at=now,
        summary=(
            harvested.get("reason")
            or f"{len(items)} dated search leads; document versions require verification."
        ),
        items=items,
        notes=notes,
        analyst_question=question,
        plan=plan,
    )


def _run_kind(
    kind: str,
    packet: Packet,
    notice: Notice,
    observations: list[Observation],
    clocks,
    now: datetime,
    project_root: Path,
    transport: HttpTransport | None = None,
) -> CollectionTask:
    if kind == VALIDATE:
        return _validate(packet, notice, clocks, now)
    if kind == CHRONOLOGY:
        return _chronology(packet, notice, observations, clocks, now)
    if kind == PHYSICAL:
        return _physical(packet, notice, observations, clocks, now, project_root)
    if kind == OFFICIAL:
        return _official(packet, notice, observations, clocks, now, project_root)
    if kind == SEARCH:
        return _search(packet, notice, clocks, now, project_root, transport)
    raise ValueError(f"unknown collection task {kind}")


def run_collection(
    project_root: Path,
    scenario_id: str,
    notice_id: str,
    *,
    kinds: list[str] | None = None,
    replay: bool = False,
    request_context: bool = False,
    transport: HttpTransport | None = None,
) -> dict[str, Any]:
    notice = load_notice(project_root, scenario_id, notice_id)
    if not notice.workflow.packet_id:
        packet, _path = build_and_save(project_root, scenario_id, notice_id, replay=replay)
        notice = load_notice(project_root, scenario_id, notice_id)
    else:
        payload = packet_path(project_root, scenario_id, notice.workflow.packet_id)
        packet = Packet.model_validate_json(payload.read_text(encoding="utf-8"))
    if request_context and notice.workflow.state is not NoticeState.context_requested:
        apply_action(notice, NoticeAction.request_context)
        save_notice(project_root, notice, overwrite_trigger=False)
        notice = load_notice(project_root, scenario_id, notice_id)
    clocks = packet.clocks
    observations, _log = _load_window_observations(project_root, notice)
    wanted = list(kinds or HARVEST_KINDS)
    for kind in wanted:
        if kind not in ALL_KINDS:
            raise ValueError(f"unknown collection task {kind}")
    now = datetime.now(UTC)
    directory = collection_directory(project_root, scenario_id, packet.packet_id)
    directory.mkdir(parents=True, exist_ok=True)
    tasks: list[CollectionTask] = []
    for kind in wanted:
        task = _run_kind(kind, packet, notice, observations, clocks, now, project_root, transport)
        _task_path(directory, kind).write_text(
            task.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        tasks.append(task)
    packet_path(project_root, scenario_id, packet.packet_id).write_text(
        packet.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    index_path = directory / "index.json"
    existing: dict[str, dict[str, str]] = {}
    if index_path.is_file():
        try:
            previous = json.loads(index_path.read_text(encoding="utf-8"))
            for row in previous.get("tasks") or []:
                if row.get("kind"):
                    existing[row["kind"]] = row
        except (OSError, json.JSONDecodeError, TypeError):
            existing = {}
    for task in tasks:
        existing[task.kind] = {
            "kind": task.kind,
            "status": task.status,
            "title": task.title,
        }
    index = {
        "packet_id": packet.packet_id,
        "notice_id": notice.notice_id,
        "updated_at": now.isoformat(),
        "tasks": [existing[kind] for kind in ALL_KINDS if kind in existing],
    }
    (directory / "index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    return {
        "scenario": scenario_id,
        "notice_id": notice.notice_id,
        "packet_id": packet.packet_id,
        "state": notice.workflow.state.value,
        "selected_posture": (
            notice.workflow.selected_posture.value if notice.workflow.selected_posture else None
        ),
        "tasks": [task.model_dump(mode="json") for task in tasks],
    }
