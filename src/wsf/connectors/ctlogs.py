from __future__ import annotations

import json
from datetime import UTC, date, datetime

from wsf.connectors.base import PullRequest
from wsf.connectors.daily import daily_count_result, failed_result
from wsf.connectors.http import HttpTransport, get_with_retry, redact_url
from wsf.time import date_range

CRTSH = "https://crt.sh/?q={query}&output=json"
# mil.ru is often absent from public CT (national CAs). kremlin.ru / government.ru
# match the frozen official-host list and do appear in public logs.
ACTOR_DOMAINS = {
    "RUS": ["mil.ru", "kremlin.ru", "government.ru"],
    "DEU": ["bundeswehr.de", "bundesregierung.de"],
    "USA": ["army.mil", "defense.gov", "whitehouse.gov"],
    "GRC": ["mod.mil.gr", "government.gov.gr"],
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
        counts: dict[date, float] = {}
        requests: list[dict[str, object]] = []
        failures: list[str] = []
        successes = 0
        for domain in domains:
            domain_ok = False
            for query in (f"%.{domain}", domain):
                url = CRTSH.format(query=query)
                progress.status(f"ct {request.window_id} {query}")
                try:
                    response = get_with_retry(
                        self.transport, url, timeout=25, attempts=3, sleep=0.8
                    )
                except TimeoutError as error:
                    requests.append(
                        {"url": redact_url(url), "domain": domain, "error": str(error)}
                    )
                    failures.append(f"{query}: timeout")
                    continue
                requests.append(
                    {
                        "url": redact_url(url),
                        "status": response.status,
                        "domain": domain,
                        "bytes": len(response.body),
                    }
                )
                if response.status != 200:
                    failures.append(f"{query}: HTTP {response.status}")
                    continue
                try:
                    rows = json.loads(response.body.decode("utf-8"))
                except json.JSONDecodeError:
                    failures.append(f"{query}: invalid json")
                    continue
                if not isinstance(rows, list):
                    failures.append(f"{query}: non-list body")
                    continue
                successes += 1
                domain_ok = True
                for row in rows:
                    raw = str(row.get("not_before") or "")[:10]
                    if len(raw) < 10:
                        continue
                    try:
                        day = date.fromisoformat(raw)
                    except ValueError:
                        continue
                    if request.start <= day <= request.end:
                        counts[day] = counts.get(day, 0.0) + 1
                break
            if not domain_ok:
                failures.append(f"{domain}: no usable response")
        if successes == 0:
            progress.line(f"ct {request.window_id} source_down failures={failures[:4]}")
            result = failed_result(
                request,
                days,
                "crt.sh returned no usable response; recorded source_down, not zero. "
                + "; ".join(failures[:6]),
                retrieved_at,
            )
            result.requests = requests
            return result
        for day in days:
            counts.setdefault(day, 0.0)
        progress.line(
            f"ct {request.window_id} certs={sum(counts.values())} "
            f"queries_ok={successes} failures={len(failures)}"
        )
        return daily_count_result(
            request,
            days,
            counts,
            retrieved_at=retrieved_at,
            requests=requests,
            extra={"domains": domains},
            notes=(
                "crt.sh not_before counts for frozen official domains; "
                "0 is observed zero only after a 200 JSON response. "
                "HTTP 502/timeout is source_down."
            ),
        )
