"""Declared UK/US government posture. Contextual prior; does not vote."""

from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from urllib.parse import quote

from wsf.connectors.base import ConnectorResult, PullRequest, collection_item
from wsf.connectors.http import HttpTransport, get_with_retry, redact_url
from wsf.time import date_range
from wsf.types import Observation

GOVUK_CONTENT = "https://www.gov.uk/api/content/foreign-travel-advice"
STATE_ADVISORIES = "https://cadataapi.state.gov/api/TravelAdvisories"
WAYBACK_CDX = "https://web.archive.org/cdx/search/cdx"
STATE_PAGES: dict[str, str] = {
    "RUS": (
        "https://travel.state.gov/content/travel/en/traveladvisories/"
        "traveladvisories/russia-travel-advisory.html"
    ),
    "UKR": (
        "https://travel.state.gov/content/travel/en/traveladvisories/"
        "traveladvisories/ukraine-travel-advisory.html"
    ),
}
LEVEL_RE = re.compile(r"Level\s+([1-4])\s*:\s*([^<\n]{0,48})", re.I)

COUNTRY_SLUGS: dict[str, str] = {
    "RUS": "russia",
    "UKR": "ukraine",
    "DEU": "germany",
    "USA": "usa",
    "CHN": "china",
    "BLR": "belarus",
}

STATE_TITLE_PREFIX: dict[str, str] = {
    "RUS": "russia",
    "UKR": "ukraine",
    "DEU": "germany",
    "CHN": "china",
    "BLR": "belarus",
}

UK_LEVEL = {
    "avoid_all_travel_to_whole_country": 4,
    "avoid_all_but_essential_travel_to_whole_country": 3,
    "avoid_all_travel_to_parts": 3,
    "avoid_all_but_essential_travel_to_parts": 2,
}

DIPLOMATIC_MARKERS = (
    "embassy staff",
    "dependants",
    "dependents",
    "withdrawn from",
    "temporary relocation of british embassy",
    "relocation of british embassy",
)
LEAVE_MARKERS = (
    "leave now",
    "leave immediately",
    "leave while commercial",
    "british nationals should leave",
    "advises against all travel",
)
THREAT_MARKERS = (
    "military incursion",
    "military operations",
    "invasion",
    "build up of russian forces",
    "troop deployments",
    "widespread military activity",
)


def _parse_ts(value: str) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _country_in_note(note: str, slug: str, code: str) -> bool:
    lowered = note.lower()
    names = {slug.lower(), code.lower()}
    if slug == "ukraine":
        names.update({"ukraine", "kyiv", "kiev", "donetsk", "luhansk", "crimea"})
    if slug == "russia":
        names.update({"russia", "russian"})
    return any(name in lowered for name in names)


def _uk_travel_level(note: str) -> int | None:
    text = note.lower()
    if "against all but essential travel" in text:
        return 3
    if "against all travel" in text or "advises against all travel" in text:
        if "parts" in text or "donetsk" in text or "luhansk" in text or "crimea" in text:
            if "rest of" in text or "whole" in text:
                return 4 if "whole" in text else 3
            return 3
        return 4
    return None


def _flags(note: str) -> dict[str, bool]:
    text = note.lower()
    return {
        "diplomatic": any(marker in text for marker in DIPLOMATIC_MARKERS),
        "leave": any(marker in text for marker in LEAVE_MARKERS),
        "threat": any(marker in text for marker in THREAT_MARKERS),
    }


def _cutoff_ok(when: datetime, cutoff: datetime) -> bool:
    return when <= cutoff


class DeclaredPostureConnector:
    """FCDO travel-advice history + US State advisories. Votes=false contextual prior."""

    source = "declared_posture"

    def __init__(self, transport: HttpTransport) -> None:
        self.http = transport
        self.last_events: list[dict[str, Any]] = []

    def pull(self, request: PullRequest) -> ConnectorResult:
        days = date_range(request.start, request.end)
        retrieved_at = request.retrieved_at or datetime.now(UTC)
        cutoff = retrieved_at
        progress = request.log()
        codes = _country_codes(request)
        events: list[dict[str, Any]] = []
        requests_log: list[dict[str, Any]] = []
        self.last_events: list[dict[str, Any]] = []

        for code in codes:
            slug = COUNTRY_SLUGS.get(code)
            if not slug:
                continue
            url = f"{GOVUK_CONTENT}/{slug}"
            progress.status(f"declared_posture fcdo {slug}")
            events.extend(self._govuk_events(url, code, slug, cutoff, requests_log))

        progress.status("declared_posture us_state")
        events.extend(self._state_events(codes, cutoff, requests_log))
        events.sort(key=lambda item: item["at"])
        self.last_events = events
        observations = _daily_observations(request, days, events, retrieved_at, cutoff)
        n_ok = sum(1 for row in observations if row.quality == "ok")
        return ConnectorResult(
            item=collection_item(
                source=self.source,
                window_id=request.window_id,
                series_id=request.series_id,
                coverage=n_ok / len(observations) if observations else 0.0,
                provenance_complete=True,
                contains_post_cutoff_material=False,
                checksum="",
                n_expected=len(days) * 4,
                n_ok=n_ok,
                n_missing=len(observations) - n_ok,
                n_source_down=0,
                observations_path=None,
                provenance_path=None,
                notes=(
                    "Declared UK/US posture. Not a detector input. "
                    "GOV.UK change_history is cutoff-filtered. US State uses the live "
                    "API when contemporaneous, otherwise the last Wayback snapshot "
                    "at or before cutoff."
                ),
            ),
            observations=observations,
            requests=requests_log,
        )

    def _govuk_events(
        self,
        url: str,
        code: str,
        slug: str,
        cutoff: datetime,
        requests_log: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        try:
            response = get_with_retry(self.http, url, timeout=30, attempts=3, sleep=0.5)
        except TimeoutError as error:
            requests_log.append({"url": redact_url(url), "error": str(error)})
            return []
        requests_log.append({"url": redact_url(url), "status": response.status})
        if response.status != 200:
            return []
        try:
            payload = json.loads(response.body.decode("utf-8"))
        except json.JSONDecodeError:
            return []
        events = []
        for row in payload.get("details", {}).get("change_history") or []:
            when = _parse_ts(str(row.get("public_timestamp") or ""))
            note = str(row.get("note") or "").strip()
            if when is None or not note or not _cutoff_ok(when, cutoff):
                continue
            if not _country_in_note(note, slug, code):
                continue
            flags = _flags(note)
            level = _uk_travel_level(note)
            events.append(
                {
                    "at": when,
                    "country": code,
                    "government": "UK/FCDO",
                    "category": "travel_risk" if level else "official_threat_language",
                    "severity": level,
                    "action": (
                        "leave_advice"
                        if flags["leave"]
                        else "diplomatic_drawdown"
                        if flags["diplomatic"]
                        else "travel_update"
                    ),
                    "text": note,
                    "costly": flags["diplomatic"] or flags["leave"],
                    "flags": flags,
                    "issuer": "UK/FCDO",
                }
            )
        return events

    def _state_events(
        self,
        codes: list[str],
        cutoff: datetime,
        requests_log: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        try:
            response = get_with_retry(
                self.http, STATE_ADVISORIES, timeout=30, attempts=3, sleep=0.5
            )
        except TimeoutError as error:
            requests_log.append({"url": redact_url(STATE_ADVISORIES), "error": str(error)})
            return []
        requests_log.append({"url": redact_url(STATE_ADVISORIES), "status": response.status})
        if response.status != 200:
            return []
        try:
            rows = json.loads(response.body.decode("utf-8"))
        except json.JSONDecodeError:
            return []
        events = []
        wanted = {STATE_TITLE_PREFIX[code]: code for code in codes if code in STATE_TITLE_PREFIX}
        for row in rows:
            title = str(row.get("Title") or "")
            prefix = title.split("-", 1)[0].strip().lower()
            code = wanted.get(prefix)
            if not code:
                continue
            updated = _parse_ts(str(row.get("Updated") or row.get("Published") or ""))
            if updated is None or not _cutoff_ok(updated, cutoff):
                continue
            match = re.search(r"Level\s+([1-4])", title, re.I)
            if not match:
                continue
            level = int(match.group(1))
            events.append(_us_event(code, updated, level, title))
        have = {event["country"] for event in events}
        for code in codes:
            if code in have or code not in STATE_PAGES:
                continue
            events.extend(self._wayback_level(code, cutoff, requests_log))
        return events

    def _wayback_level(
        self,
        code: str,
        cutoff: datetime,
        requests_log: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        page = STATE_PAGES[code]
        start = (cutoff.date() - timedelta(days=90)).strftime("%Y%m%d")
        until = cutoff.strftime("%Y%m%d%H%M%S")
        cdx = (
            f"{WAYBACK_CDX}?url={quote(page, safe='')}&from={start}&to={until}"
            "&output=json&fl=timestamp,original,statuscode&filter=statuscode:200"
            "&collapse=digest"
        )
        try:
            response = get_with_retry(self.http, cdx, timeout=25, attempts=2, sleep=0.5)
        except TimeoutError as error:
            requests_log.append({"url": redact_url(cdx), "error": str(error)})
            return []
        requests_log.append({"url": redact_url(cdx), "status": response.status})
        if response.status != 200:
            return []
        try:
            rows = json.loads(response.body.decode("utf-8"))
        except json.JSONDecodeError:
            return []
        chosen = None
        for row in rows[1:]:
            if not row:
                continue
            stamp = str(row[0])
            when = _cdx_timestamp(stamp)
            if when is None or when > cutoff:
                continue
            chosen = (stamp, when, str(row[1]) if len(row) > 1 else page)
        if chosen is None:
            return []
        stamp, when, original = chosen
        snapshot = f"https://web.archive.org/web/{stamp}id_/{original}"
        try:
            page_resp = get_with_retry(self.http, snapshot, timeout=25, attempts=2, sleep=0.5)
        except TimeoutError as error:
            requests_log.append({"url": redact_url(snapshot), "error": str(error)})
            return []
        requests_log.append({"url": redact_url(snapshot), "status": page_resp.status})
        if page_resp.status != 200:
            return []
        html = page_resp.body.decode("utf-8", errors="replace")
        match = LEVEL_RE.search(html)
        if not match:
            return []
        level = int(match.group(1))
        label = match.group(2).strip()
        title = f"{STATE_TITLE_PREFIX[code].title()} - Level {level}: {label}"
        return [_us_event(code, when, level, title)]


def _cdx_timestamp(stamp: str) -> datetime | None:
    if len(stamp) < 8:
        return None
    try:
        return datetime(
            int(stamp[0:4]),
            int(stamp[4:6]),
            int(stamp[6:8]),
            int(stamp[8:10] or 0),
            int(stamp[10:12] or 0),
            int(stamp[12:14] or 0),
            tzinfo=UTC,
        )
    except ValueError:
        return None


def _us_event(code: str, when: datetime, level: int, text: str) -> dict[str, Any]:
    return {
        "at": when,
        "country": code,
        "government": "US/State",
        "category": "travel_risk",
        "severity": level,
        "action": "travel_advisory",
        "text": text,
        "costly": level >= 4,
        "flags": {"diplomatic": False, "leave": level >= 4, "threat": False},
        "issuer": "US/State",
    }


def _country_codes(request: PullRequest) -> list[str]:
    focal = str(
        getattr(request.queries, "facility_actor", None)
        or getattr(request.queries, "cameo_actor", "")
        or ""
    )
    codes = [focal.upper()] if focal else []
    counterparts = getattr(request.queries, "wiki_titles", None) or []
    for title in counterparts:
        lowered = str(title).lower()
        if lowered == "ukraine" and "UKR" not in codes:
            codes.append("UKR")
        if lowered == "russia" and "RUS" not in codes:
            codes.append("RUS")
    if "RUS" in codes and "UKR" not in codes:
        codes.append("UKR")
    return codes or ["RUS", "UKR"]


def reconstruct_events(
    history_by_slug: dict[str, list[dict[str, Any]]],
    cutoff: datetime,
) -> list[dict[str, Any]]:
    """Test helper: build events from already-fetched GOV.UK change_history rows."""
    events = []
    reverse = {slug: code for code, slug in COUNTRY_SLUGS.items()}
    for slug, rows in history_by_slug.items():
        code = reverse.get(slug, slug.upper()[:3])
        for row in rows:
            when = _parse_ts(str(row.get("public_timestamp") or ""))
            note = str(row.get("note") or "").strip()
            if when is None or not note or not _cutoff_ok(when, cutoff):
                continue
            flags = _flags(note)
            events.append(
                {
                    "at": when,
                    "country": code,
                    "government": "UK/FCDO",
                    "category": "travel_risk",
                    "severity": _uk_travel_level(note),
                    "action": (
                        "leave_advice"
                        if flags["leave"]
                        else "diplomatic_drawdown"
                        if flags["diplomatic"]
                        else "travel_update"
                    ),
                    "text": note,
                    "costly": flags["diplomatic"] or flags["leave"],
                    "flags": flags,
                    "issuer": "UK/FCDO",
                }
            )
    events.sort(key=lambda item: item["at"])
    return events


def state_at_cutoff(events: list[dict[str, Any]], cutoff: datetime) -> dict[str, Any]:
    travel: dict[str, int] = {}
    diplomatic = False
    leave = False
    threat = False
    costly: list[dict[str, Any]] = []
    for event in events:
        if event["at"] > cutoff:
            continue
        flags = event.get("flags") or {}
        country = event.get("country") or "?"
        if event.get("severity"):
            travel[country] = max(travel.get(country, 1), int(event["severity"]))
        diplomatic = diplomatic or bool(flags.get("diplomatic"))
        leave = leave or bool(flags.get("leave"))
        threat = threat or bool(flags.get("threat"))
        if event.get("costly"):
            costly.append(event)
    return {
        "travel_risk": travel,
        "diplomatic_drawdown": diplomatic,
        "leave_advice": leave,
        "threat_language": threat,
        "costly_events": costly,
    }


def _daily_observations(
    request: PullRequest,
    days: list[date],
    events: list[dict[str, Any]],
    retrieved_at: datetime,
    cutoff: datetime,
) -> list[Observation]:
    travel: dict[str, int] = {}
    diplomatic = 0.0
    threat = 0.0
    action = 0.0
    observations: list[Observation] = []
    event_i = 0
    for day in days:
        day_end = datetime.combine(day, time(23, 59, 59), tzinfo=UTC)
        bound = min(day_end, cutoff)
        while event_i < len(events) and events[event_i]["at"] <= bound:
            event = events[event_i]
            flags = event.get("flags") or {}
            if event.get("severity"):
                country = event.get("country") or "?"
                travel[country] = max(travel.get(country, 1), int(event["severity"]))
            if flags.get("diplomatic"):
                diplomatic = 1.0
            if flags.get("threat"):
                threat = 1.0
            if flags.get("leave") or flags.get("diplomatic"):
                action = 1.0
            event_i += 1
        knowable = bound <= cutoff
        extra = {
            "event_day": day.isoformat(),
            "travel_by_country": travel.copy(),
            "votes": False,
        }
        values = {
            "posture.travel_risk": float(max(travel.values()) if travel else 0),
            "posture.diplomatic_posture": diplomatic,
            "posture.official_threat_language": threat,
            "posture.government_action": action,
        }
        for series_id, value in values.items():
            quality = "ok" if knowable and (travel or diplomatic or threat or action) else "missing"
            if not knowable:
                quality = "missing"
                value_out = None
            else:
                value_out = value if quality == "ok" else None
            observations.append(
                Observation(
                    version_id=f"{request.source}:{series_id}:{day.isoformat()}",
                    series_id=series_id,
                    period_id=request.window_id,
                    event_time=datetime(day.year, day.month, day.day, tzinfo=UTC),
                    available_at=bound,
                    retrieved_at=retrieved_at,
                    value=value_out,
                    quality=quality,  # type: ignore[arg-type]
                    extra=json.dumps(extra, sort_keys=True),
                )
            )
    return observations
