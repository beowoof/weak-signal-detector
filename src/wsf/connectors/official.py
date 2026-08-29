from __future__ import annotations

import json
from datetime import UTC, date, datetime

from wsf.connectors.base import PullRequest
from wsf.connectors.daily import daily_count_result
from wsf.connectors.http import HttpTransport, get_with_retry, redact_url
from wsf.time import date_range

CDX = "https://web.archive.org/cdx/search/cdx"
ACTOR_HOSTS = {
    "RUS": ["kremlin.ru", "mil.ru", "government.ru"],
    "DEU": ["bundesregierung.de", "bmvg.de"],
    "USA": ["whitehouse.gov", "defense.gov"],
    "GRC": ["government.gov.gr"],
}


class OfficialConnector:
    source = "official"

    def __init__(self, transport: HttpTransport) -> None:
        self.transport = transport

    def pull(self, request: PullRequest):
        days = date_range(request.start, request.end)
        retrieved_at = request.retrieved_at or datetime.now(UTC)
        actor = request.queries.facility_actor or request.queries.cameo_actor or "RUS"
        hosts = ACTOR_HOSTS.get(str(actor), ACTOR_HOSTS["RUS"])
        progress = request.log()
        counts: dict[date, float] = {day: 0.0 for day in days}
        requests: list[dict[str, object]] = []
        start = request.start.strftime("%Y%m%d")
        end = request.end.strftime("%Y%m%d")
        for host in hosts:
            url = (
                f"{CDX}?url={host}/*&from={start}&to={end}&output=json"
                "&fl=timestamp,original&filter=statuscode:200&collapse=digest"
            )
            progress.status(f"official {request.window_id} {host}")
            try:
                response = get_with_retry(
                    self.transport, url, timeout=180, attempts=4, sleep=2.0
                )
            except TimeoutError as error:
                requests.append(
                    {"url": redact_url(url), "host": host, "error": str(error)}
                )
                progress.line(f"official {request.window_id} {host} truncated/timeout")
                continue
            requests.append({"url": redact_url(url), "status": response.status, "host": host})
            if response.status != 200:
                continue
            try:
                rows = json.loads(response.body.decode("utf-8"))
            except json.JSONDecodeError:
                continue
            for row in rows[1:]:
                if not row:
                    continue
                stamp = str(row[0])
                if len(stamp) < 8:
                    continue
                day = date(int(stamp[0:4]), int(stamp[4:6]), int(stamp[6:8]))
                if day in counts:
                    counts[day] += 1
        progress.line(f"official {request.window_id} captures={sum(counts.values())}")
        return daily_count_result(
            request,
            days,
            counts,
            retrieved_at=retrieved_at,
            requests=requests,
            extra={"hosts": hosts},
            notes="Internet Archive CDX captures of frozen official hosts.",
        )
