from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime
from typing import Any

from wsf.connectors.base import ConnectorResult, PullRequest
from wsf.connectors.daily import daily_count_result
from wsf.connectors.http import HttpTransport, get_with_retry, redact_url
from wsf.time import date_range

NGA_MSI_WARN_URL = "https://msi.nga.mil/api/publications/broadcast-warn"
MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

ACTOR_NAVAREAS: dict[str, list[str]] = {
    "RUS": ["A", "C"],  # HYDROLANT (Atlantic/Black Sea/Baltic) and HYDROARC (Arctic)
    "USA": ["4", "12"],  # NAVAREA IV and XII
    "DEU": ["A"],
    "CHN": ["P"],  # HYDROPAC
    "GRC": ["A"],
}


def _parse_issue_date(issue_date_str: str) -> date | None:
    if not issue_date_str:
        return None
    m = re.search(r"(\d{2})\d{4}Z\s+([A-Z]{3})\s+(\d{2,4})", issue_date_str.upper())
    if m:
        day = int(m.group(1))
        mon_str = m.group(2)
        yr_str = m.group(3)
        yr = int(yr_str)
        if yr < 100:
            yr += 2000
        mon = MONTHS.get(mon_str)
        if mon and 1 <= day <= 31:
            try:
                return date(yr, mon, day)
            except ValueError:
                return None
    try:
        return date.fromisoformat(issue_date_str[:10])
    except (ValueError, TypeError):
        return None


class NavareaConnector:
    """Measures administrative commitment of navigable maritime space via NGA Worldwide Navigational Warnings."""
    source = "navarea"

    def __init__(self, transport: HttpTransport) -> None:
        self.http = transport

    def pull(self, request: PullRequest) -> ConnectorResult:
        days = date_range(request.start, request.end)
        retrieved_at = request.retrieved_at or datetime.now(UTC)
        progress = request.log()

        actor = getattr(request.queries, "cameo_actor", "") or getattr(request.queries, "facility_actor", "RUS")
        nav_areas = ACTOR_NAVAREAS.get(str(actor), ["A"])
        years = sorted({request.start.year, request.end.year})

        requests_log: list[dict[str, Any]] = []
        nav_counts: dict[date, float] = {day: 0.0 for day in days}
        source_down_days: set[date] = set()
        successful_years: set[int] = set()
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
        }

        for nav_area in nav_areas:
            for yr in years:
                url = f"{NGA_MSI_WARN_URL}?status=all&navArea={nav_area}&msgYear={yr}&output=json"
                progress.status(f"navarea {request.window_id} area={nav_area} year={yr}")
                try:
                    resp = get_with_retry(
                        self.http,
                        url,
                        headers=headers,
                        timeout=30,
                        attempts=3,
                        sleep=1.0,
                    )
                except (TimeoutError, Exception) as err:
                    requests_log.append({"url": redact_url(url), "error": str(err)})
                    continue

                requests_log.append({"url": redact_url(url), "status": resp.status, "bytes": len(resp.body)})
                if resp.status != 200 or not resp.body:
                    continue

                try:
                    data = json.loads(resp.body.decode("utf-8"))
                    warns = data.get("broadcast-warn", []) if isinstance(data, dict) else data
                    successful_years.add(yr)
                    for item in warns:
                        raw_date = item.get("issueDate") or item.get("msgDate")
                        d_val = _parse_issue_date(str(raw_date))
                        if d_val and d_val in nav_counts:
                            nav_counts[d_val] += 1.0
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue

        for yr in years:
            if yr not in successful_years:
                for d in days:
                    if d.year == yr:
                        source_down_days.add(d)

        counts = nav_counts

        non_zero = sum(1 for v in counts.values() if v > 0)
        progress.line(
            f"navarea {request.window_id} days={len(days)} non_zero_days={non_zero} "
            f"total_warnings={sum(counts.values()):.0f} down_days={len(source_down_days)}"
        )

        return daily_count_result(
            request,
            days,
            counts,
            retrieved_at=retrieved_at,
            requests=requests_log,
            source_down_days=source_down_days,
            notes=f"NGA NAVAREA maritime broadcast navigation warnings for {actor} areas {','.join(nav_areas)}",
        )
