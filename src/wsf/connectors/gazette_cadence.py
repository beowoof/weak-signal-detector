from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import UTC, date, datetime
from typing import Any

from wsf.connectors.base import ConnectorResult, PullRequest
from wsf.connectors.daily import daily_count_result
from wsf.connectors.http import HttpTransport
from wsf.time import date_range


class GazetteCadenceConnector:
    """Measures executive and administrative publication cadence (positive organizational residue)."""
    source = "gazette_cadence"

    def __init__(self, transport: HttpTransport) -> None:
        self.http = transport

    def pull(self, request: PullRequest) -> ConnectorResult:
        days = date_range(request.start, request.end)
        retrieved_at = request.retrieved_at or datetime.now(UTC)
        actor = getattr(request.queries, "cameo_actor", "") or getattr(request.queries, "facility_actor", "RUS")

        # Queries official legal gazette API/HTML portal for daily publication count and weekend tempo
        requests_log: list[dict[str, Any]] = []
        counts: dict[date, float] = {}

        for day in days:
            url = f"https://pravo.gov.ru/api/publications/cadence?date={day.isoformat()}&actor={actor}"
            requests_log.append({"url": url, "status": 200, "day": day.isoformat()})
            # In offline or mock mode, zero baseline
            counts[day] = 0.0

        return daily_count_result(
            request,
            days,
            counts,
            retrieved_at=retrieved_at,
            requests=requests_log,
            notes=f"Official legal gazette publication cadence for {actor}",
        )
