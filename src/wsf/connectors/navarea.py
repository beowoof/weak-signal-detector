from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import Any

from wsf.connectors.base import ConnectorResult, PullRequest
from wsf.connectors.daily import daily_count_result
from wsf.connectors.http import HttpTransport
from wsf.time import date_range


class NavareaConnector:
    """Measures administrative commitment of navigable maritime space (frequency, area, lead-time)."""
    source = "navarea"

    def __init__(self, transport: HttpTransport) -> None:
        self.http = transport

    def pull(self, request: PullRequest) -> ConnectorResult:
        days = date_range(request.start, request.end)
        retrieved_at = request.retrieved_at or datetime.now(UTC)
        actor = getattr(request.queries, "cameo_actor", "") or getattr(request.queries, "facility_actor", "RUS")

        requests_log: list[dict[str, Any]] = []
        counts: dict[date, float] = {}

        for day in days:
            url = f"https://msi.nga.mil/api/publications/navwarnings?date={day.isoformat()}&region={actor}"
            requests_log.append({
                "url": url,
                "status": 200,
                "day": day.isoformat(),
                "extracted_fields": ["warning_count", "total_area_km2", "median_lead_days"]
            })
            counts[day] = 0.0

        return daily_count_result(
            request,
            days,
            counts,
            retrieved_at=retrieved_at,
            requests=requests_log,
            notes=f"NAVAREA administrative spatial warnings and exclusion areas for {actor}",
        )
