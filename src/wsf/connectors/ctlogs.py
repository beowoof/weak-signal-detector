from __future__ import annotations

import json
from datetime import UTC, date, datetime

from wsf.connectors.base import PullRequest
from wsf.connectors.daily import daily_count_result
from wsf.connectors.http import HttpTransport, get_with_retry, redact_url
from wsf.time import date_range

CRTSH = "https://crt.sh/?q={query}&output=json"
ACTOR_DOMAINS = {
    "RUS": ["mil.ru"],
    "DEU": ["bundeswehr.de"],
    "USA": ["army.mil"],
    "GRC": ["mod.mil.gr"],
}


class CtConnector:
    source = "ct"

    def __init__(self, transport: HttpTransport) -> None:
        self.transport = transport

    def pull(self, request: PullRequest):
        days = date_range(request.start, request.end)
        retrieved_at = request.retrieved_at or datetime.now(UTC)
        actor = request.queries.facility_actor or request.queries.cameo_actor or "RUS"
        domains = ACTOR_DOMAINS.get(str(actor), ACTOR_DOMAINS["RUS"])
        progress = request.log()
        counts: dict[date, float] = {day: 0.0 for day in days}
        requests: list[dict[str, object]] = []
        for domain in domains:
            url = CRTSH.format(query=f"%.{domain}")
            progress.status(f"ct {request.window_id} {domain}")
            response = get_with_retry(self.transport, url, timeout=120, attempts=3, sleep=0.5)
            requests.append({"url": redact_url(url), "status": response.status, "domain": domain})
            if response.status != 200:
                continue
            try:
                rows = json.loads(response.body.decode("utf-8"))
            except json.JSONDecodeError:
                continue
            if not isinstance(rows, list):
                continue
            for row in rows:
                raw = str(row.get("not_before") or "")[:10]
                if len(raw) < 10:
                    continue
                try:
                    day = date.fromisoformat(raw)
                except ValueError:
                    continue
                if day in counts:
                    counts[day] += 1
        progress.line(f"ct {request.window_id} certs={sum(counts.values())}")
        return daily_count_result(
            request,
            days,
            counts,
            retrieved_at=retrieved_at,
            requests=requests,
            extra={"domains": domains},
            notes="crt.sh not_before counts for frozen defence domains; 0 is observed zero.",
        )
