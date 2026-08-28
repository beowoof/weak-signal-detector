from __future__ import annotations

import json
from datetime import UTC, date, datetime

from wsf.connectors.base import PullRequest
from wsf.connectors.daily import daily_count_result
from wsf.connectors.http import HttpTransport, get_with_retry, redact_url
from wsf.time import date_range

RIPE_PREFIXES = "https://stat.ripe.net/data/announced-prefixes/data.json?resource={asn}&starttime={stamp}"
ACTOR_ASNS = {
    "RUS": ["AS12389", "AS8359", "AS31133"],
    "DEU": ["AS3320"],
    "USA": ["AS701", "AS1239"],
    "GRC": ["AS6799"],
}


class RipeConnector:
    source = "ripe"

    def __init__(self, transport: HttpTransport) -> None:
        self.transport = transport

    def pull(self, request: PullRequest):
        days = date_range(request.start, request.end)
        retrieved_at = request.retrieved_at or datetime.now(UTC)
        actor = request.queries.facility_actor or request.queries.cameo_actor or "RUS"
        asns = ACTOR_ASNS.get(str(actor), ACTOR_ASNS["RUS"])
        progress = request.log()
        counts: dict[date, float] = {day: 0.0 for day in days}
        requests: list[dict[str, object]] = []
        for index, day in enumerate(days, start=1):
            progress.status(f"ripe {request.window_id} {day.isoformat()} [{index}/{len(days)}]")
            total = 0.0
            stamp = f"{day.isoformat()}T12:00:00"
            for asn in asns:
                url = RIPE_PREFIXES.format(asn=asn, stamp=stamp)
                response = get_with_retry(self.transport, url, timeout=60, attempts=3, sleep=0.5)
                requests.append({"url": redact_url(url), "status": response.status, "asn": asn})
                if response.status != 200:
                    continue
                payload = json.loads(response.body.decode("utf-8"))
                prefixes = ((payload.get("data") or {}).get("prefixes") or [])
                total += float(len(prefixes))
            counts[day] = total
        progress.line(f"ripe {request.window_id} asns={','.join(asns)}")
        return daily_count_result(
            request,
            days,
            counts,
            retrieved_at=retrieved_at,
            requests=requests,
            extra={"asns": asns},
            notes="RIPEstat announced-prefix count summed over a frozen ASN list.",
        )
