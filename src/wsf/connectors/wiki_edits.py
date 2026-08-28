from __future__ import annotations

import json
from datetime import UTC, date, datetime
from urllib.parse import urlencode

from wsf.connectors.base import PullRequest
from wsf.connectors.daily import daily_count_result
from wsf.connectors.http import HttpTransport, get_with_retry, redact_url
from wsf.time import date_range

API = "https://en.wikipedia.org/w/api.php"


class WikiEditsConnector:
    source = "wiki_edits"

    def __init__(self, transport: HttpTransport) -> None:
        self.transport = transport

    def pull(self, request: PullRequest):
        titles: list[str] = list(request.queries.wiki_titles)
        days = date_range(request.start, request.end)
        retrieved_at = request.retrieved_at or datetime.now(UTC)
        progress = request.log()
        counts: dict[date, float] = {day: 0.0 for day in days}
        requests: list[dict[str, object]] = []
        start = f"{request.end.isoformat()}T23:59:59Z"
        end = f"{request.start.isoformat()}T00:00:00Z"
        for index, title in enumerate(titles, start=1):
            progress.status(f"wiki_edits {request.window_id} {index}/{len(titles)} {title}")
            continue_token = None
            while True:
                params = {
                    "action": "query",
                    "format": "json",
                    "prop": "revisions",
                    "titles": title,
                    "rvlimit": "500",
                    "rvprop": "timestamp",
                    "rvdir": "older",
                    "rvstart": start,
                    "rvend": end,
                }
                if continue_token:
                    params["rvcontinue"] = continue_token
                url = f"{API}?{urlencode(params)}"
                response = get_with_retry(self.transport, url, timeout=60, attempts=3, sleep=0.5)
                requests.append(
                    {
                        "url": redact_url(url),
                        "status": response.status,
                        "title": title,
                        "bytes": len(response.body),
                    }
                )
                if response.status != 200:
                    break
                payload = json.loads(response.body.decode("utf-8"))
                pages = (payload.get("query") or {}).get("pages") or {}
                for page in pages.values():
                    for revision in page.get("revisions") or []:
                        stamp = str(revision.get("timestamp", ""))[:10]
                        if not stamp:
                            continue
                        day = date.fromisoformat(stamp)
                        if day in counts:
                            counts[day] += 1
                continue_token = (payload.get("continue") or {}).get("rvcontinue")
                if not continue_token:
                    break
        progress.line(f"wiki_edits {request.window_id} edits={sum(counts.values())}")
        return daily_count_result(
            request,
            days,
            counts,
            retrieved_at=retrieved_at,
            requests=requests,
            notes="English Wikipedia revisions on frozen titles; 0 is observed zero.",
        )
