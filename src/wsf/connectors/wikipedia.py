from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from urllib.parse import quote

from wsf.connectors.base import ConnectorResult, PullRequest, collection_item
from wsf.connectors.http import HttpTransport, get_with_retry, redact_url
from wsf.time import date_range
from wsf.types import Observation

WIKI_URL = (
    "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
    "en.wikipedia/all-access/user/{title}/daily/{start}/{end}"
)


class WikipediaConnector:
    source = "wikipedia"

    def __init__(self, transport: HttpTransport) -> None:
        self.transport = transport

    def pull(self, request: PullRequest) -> ConnectorResult:
        titles: list[str] = list(request.queries.wiki_titles)
        days = date_range(request.start, request.end)
        retrieved_at = request.retrieved_at or datetime.now(UTC)
        per_title: dict[str, dict[date, int | None]] = {}
        requests: list[dict[str, object]] = []
        title_status: dict[str, str] = {}

        progress = request.log()
        n_titles = len(titles)
        for index, title in enumerate(titles, start=1):
            progress.status(
                f"wikipedia {request.window_id} title {index}/{n_titles} {title}"
            )
            encoded = quote(title.replace(" ", "_"), safe="")
            url = WIKI_URL.format(
                title=encoded,
                start=request.start.strftime("%Y%m%d"),
                end=request.end.strftime("%Y%m%d"),
            )
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
                title_status[title] = "source_down"
                per_title[title] = {day: None for day in days}
                continue
            payload = json.loads(response.body.decode("utf-8"))
            counts: dict[date, int | None] = {day: None for day in days}
            for item in payload.get("items") or []:
                stamp = str(item.get("timestamp", ""))[:8]
                day = date.fromisoformat(f"{stamp[0:4]}-{stamp[4:6]}-{stamp[6:8]}")
                if day in counts:
                    counts[day] = int(item["views"])
            per_title[title] = counts
            title_status[title] = "ok"

        observations: list[Observation] = []
        n_ok = n_missing = n_source_down = 0
        for day in days:
            extra = {
                "titles": {
                    title: {"views": per_title[title][day], "status": title_status[title]}
                    for title in titles
                }
            }
            failed = any(title_status[title] != "ok" for title in titles)
            incomplete = any(per_title[title][day] is None for title in titles)
            if failed or incomplete:
                quality = "missing"
                value = None
                n_missing += 1
            else:
                quality = "ok"
                value = float(sum(per_title[title][day] or 0 for title in titles))
                n_ok += 1
            event_time = datetime(day.year, day.month, day.day, tzinfo=UTC)
            available_at = datetime(day.year, day.month, day.day, tzinfo=UTC) + timedelta(days=1)
            observations.append(
                Observation(
                    version_id=f"wiki:{request.window_id}:{day.isoformat()}",
                    series_id=request.series_id,
                    period_id=request.window_id,
                    event_time=event_time,
                    available_at=available_at,
                    retrieved_at=retrieved_at,
                    value=value,
                    quality=quality,  # type: ignore[arg-type]
                    extra=json.dumps(extra, sort_keys=True),
                )
            )

        n_expected = len(days)
        coverage = n_ok / n_expected if n_expected else 0.0
        progress.line(
            f"wikipedia {request.window_id} coverage={coverage:.3f} "
            f"ok={n_ok} missing={n_missing}"
        )
        post_cutoff = any(item.event_time.date() > request.end for item in observations)
        provenance_complete = all(
            item.version_id and item.available_at and item.retrieved_at for item in observations
        )
        return ConnectorResult(
            item=collection_item(
                source=self.source,
                window_id=request.window_id,
                series_id=request.series_id,
                coverage=coverage,
                provenance_complete=provenance_complete,
                contains_post_cutoff_material=post_cutoff,
                checksum="",
                n_expected=n_expected,
                n_ok=n_ok,
                n_missing=n_missing,
                n_source_down=n_source_down,
                observations_path=None,
                provenance_path=None,
            ),
            observations=observations,
            requests=requests,
        )
