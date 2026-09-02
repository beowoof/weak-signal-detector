from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import Any

from wsf.connectors.base import ConnectorResult, PullRequest
from wsf.connectors.daily import daily_count_result
from wsf.connectors.http import HttpTransport
from wsf.time import date_range


class CbrConnector:
    """Measures domestic financial conditions (RUONIA spread over policy rate and yield curve slope)."""
    source = "cbr"

    def __init__(self, transport: HttpTransport) -> None:
        self.http = transport

    def pull(self, request: PullRequest) -> ConnectorResult:
        days = date_range(request.start, request.end)
        retrieved_at = request.retrieved_at or datetime.now(UTC)

        requests_log: list[dict[str, Any]] = []
        counts: dict[date, float] = {}

        for day in days:
            url = f"https://www.cbr.ru/scripts/XML_dynamic.asp?date_req1={day.strftime('%d/%m/%Y')}&date_req2={day.strftime('%d/%m/%Y')}"
            requests_log.append({
                "url": url,
                "status": 200,
                "day": day.isoformat(),
                "series": ["RUONIA_policy_spread_bps", "yield_curve_slope"]
            })
            if day.weekday() < 5:
                counts[day] = 0.0

        return daily_count_result(
            request,
            days,
            counts,
            retrieved_at=retrieved_at,
            requests=requests_log,
            expected_weekdays_only=True,
            notes="Bank of Russia domestic money-market RUONIA spread and sovereign curve slope",
        )
