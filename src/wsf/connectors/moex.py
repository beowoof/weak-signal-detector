from __future__ import annotations

import json
from datetime import UTC, date, datetime
from urllib.parse import urlencode

from wsf.connectors.base import PullRequest
from wsf.connectors.daily import daily_count_result, failed_result
from wsf.connectors.http import HttpTransport, get_with_retry, redact_url
from wsf.time import date_range

MOEX_URL = (
    "https://iss.moex.com/iss/history/engines/currency/markets/selt/"
    "boards/CETS/securities/USD000UTSTOM.json"
)
MOEX_PAGE = 100


class MoexConnector:
    source = "moex"

    def __init__(self, transport: HttpTransport) -> None:
        self.transport = transport

    def pull(self, request: PullRequest):
        days = date_range(request.start, request.end)
        retrieved_at = request.retrieved_at or datetime.now(UTC)
        progress = request.log()
        progress.status(f"moex {request.window_id} USD000UTSTOM")
        counts: dict[date, float] = {}
        requests: list[dict[str, object]] = []
        start = 0
        while True:
            query = urlencode(
                {
                    "from": request.start.isoformat(),
                    "till": request.end.isoformat(),
                    "start": start,
                }
            )
            url = f"{MOEX_URL}?{query}"
            response = get_with_retry(self.transport, url, timeout=60, attempts=3, sleep=0.5)
            requests.append(
                {"url": redact_url(url), "status": response.status, "bytes": len(response.body)}
            )
            if response.status != 200:
                progress.line(f"moex {request.window_id} HTTP {response.status}")
                result = failed_result(
                    request, days, f"MOEX HTTP {response.status}", retrieved_at
                )
                result.requests = requests
                return result
            payload = json.loads(response.body.decode("utf-8"))
            table = payload.get("history") or {}
            columns = list(table.get("columns") or [])
            close_idx = columns.index("CLOSE") if "CLOSE" in columns else -1
            date_idx = columns.index("TRADEDATE") if "TRADEDATE" in columns else 1
            rows = list(table.get("data") or [])
            for row in rows:
                if close_idx < 0 or close_idx >= len(row) or row[close_idx] is None:
                    continue
                day = date.fromisoformat(str(row[date_idx])[:10])
                counts[day] = float(row[close_idx])
            if len(rows) < MOEX_PAGE:
                break
            start += len(rows)
        progress.line(f"moex {request.window_id} prints={len(counts)}")
        return daily_count_result(
            request,
            days,
            counts,
            retrieved_at=retrieved_at,
            requests=requests,
            expected_weekdays_only=True,
            notes=(
                "MOEX USD000UTSTOM close; weekends and exchange non-sessions are missing "
                "(cannot flag) and are not coverage failures."
            ),
        )
