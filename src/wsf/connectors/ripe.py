from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from wsf.connectors.base import PullRequest
from wsf.connectors.daily import daily_count_result
from wsf.connectors.http import HttpTransport, get_with_retry, redact_url
from wsf.time import date_range

# Count series, not the full prefix list. announced-prefixes for AS12389 times out.
PREFIX_COUNT = (
    "https://stat.ripe.net/data/prefix-count/data.json"
    "?resource={asn}&starttime={start}&endtime={end}&resolution=8h"
    "&sourceapp=weak-signal-fusion"
)
ACTOR_ASNS = {
    "RUS": ["AS12389", "AS8359", "AS31133"],
    "DEU": ["AS3320"],
    "USA": ["AS701", "AS1239"],
    "GRC": ["AS6799"],
}


class RipeConnector:
    source = "ripe"

    def __init__(self, transport: HttpTransport, cache_dir: Path | None = None) -> None:
        self.transport = transport
        self.cache_dir = cache_dir

    def pull(self, request: PullRequest):
        days = date_range(request.start, request.end)
        retrieved_at = request.retrieved_at or datetime.now(UTC)
        actor = request.queries.facility_actor or request.queries.cameo_actor or "RUS"
        asns = ACTOR_ASNS.get(str(actor), ACTOR_ASNS["RUS"])
        progress = request.log()
        if self.cache_dir is not None:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        per_asn: list[dict[date, float]] = []
        requests: list[dict[str, object]] = []
        start_stamp = f"{request.start.isoformat()}T00:00:00"
        end_stamp = f"{(request.end + timedelta(days=1)).isoformat()}T00:00:00"
        for asn in asns:
            progress.status(f"ripe {request.window_id} {asn} prefix-count")
            series, provenance = self._prefix_count(asn, start_stamp, end_stamp)
            requests.append(provenance)
            filled = fill_days(days, series)
            if filled:
                per_asn.append(filled)
        counts: dict[date, float] = {}
        for day in days:
            present = [series[day] for series in per_asn if day in series]
            if present:
                counts[day] = sum(present)
        n_days = f"{len(counts)}/{len(days)}"
        progress.line(f"ripe {request.window_id} asns={','.join(asns)} days={n_days}")
        return daily_count_result(
            request,
            days,
            counts,
            retrieved_at=retrieved_at,
            requests=requests,
            absent_missing=True,
            extra={"asns": asns, "endpoint": "prefix-count"},
            notes="RIPEstat prefix-count (IPv4+IPv6) summed over a frozen ASN list.",
        )

    def _prefix_count(
        self, asn: str, start_stamp: str, end_stamp: str
    ) -> tuple[dict[date, float], dict[str, object]]:
        url = PREFIX_COUNT.format(asn=asn, start=start_stamp, end=end_stamp)
        cache_path = None
        if self.cache_dir is not None:
            cache_path = self.cache_dir / f"count_{asn}_{start_stamp[:10]}_{end_stamp[:10]}.json"
        if cache_path is not None and cache_path.is_file():
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            return daily_prefix_counts(payload), {
                "url": redact_url(url),
                "status": 200,
                "asn": asn,
                "cache": True,
            }
        try:
            response = get_with_retry(self.transport, url, timeout=30, attempts=3, sleep=1.0)
        except TimeoutError as error:
            return {}, {"url": redact_url(url), "asn": asn, "error": str(error)}
        provenance = {"url": redact_url(url), "status": response.status, "asn": asn}
        if response.status != 200:
            return {}, provenance
        try:
            payload = json.loads(response.body.decode("utf-8"))
        except json.JSONDecodeError:
            provenance["error"] = "invalid_json"
            return {}, provenance
        if cache_path is not None:
            cache_path.write_text(json.dumps(payload), encoding="utf-8")
        return daily_prefix_counts(payload), provenance


def daily_prefix_counts(payload: dict) -> dict[date, float]:
    by_day: dict[date, float] = {}
    data = payload.get("data") or {}
    for family in ("ipv4", "ipv6"):
        for item in data.get(family) or []:
            raw = str(item.get("timestamp") or "")[:10]
            prefixes = item.get("prefixes")
            if len(raw) < 10 or prefixes is None:
                continue
            try:
                day = date.fromisoformat(raw)
            except ValueError:
                continue
            by_day[day] = by_day.get(day, 0.0) + float(prefixes)
    return dict(sorted(by_day.items()))


def fill_days(days: list[date], points: dict[date, float]) -> dict[date, float]:
    """Carry the last prefix-count observation forward onto each calendar day."""
    if not points:
        return {}
    ordered = sorted(points)
    filled: dict[date, float] = {}
    index = 0
    current: float | None = None
    for day in days:
        while index < len(ordered) and ordered[index] <= day:
            current = points[ordered[index]]
            index += 1
        if current is not None:
            filled[day] = current
    return filled
