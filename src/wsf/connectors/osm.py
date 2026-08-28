from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import UTC, date, datetime, timedelta
from urllib.parse import urlencode

from wsf.connectors.base import PullRequest
from wsf.connectors.daily import daily_count_result
from wsf.connectors.firms import _skipped, _union_bbox
from wsf.connectors.http import HttpTransport, get_with_retry, redact_url
from wsf.time import date_range

OSM_CHANGESETS = "https://api.openstreetmap.org/api/0.6/changesets"


class OsmConnector:
    source = "osm"

    def __init__(self, transport: HttpTransport) -> None:
        self.transport = transport

    def pull(self, request: PullRequest):
        days = date_range(request.start, request.end)
        retrieved_at = request.retrieved_at or datetime.now(UTC)
        if not request.aois:
            return _skipped(request, days, retrieved_at, "OSM requires AOI bboxes")
        west, south, east, north = _union_bbox(request.aois)
        progress = request.log()
        counts: dict[date, float] = {day: 0.0 for day in days}
        requests: list[dict[str, object]] = []
        query = urlencode(
            {
                "bbox": f"{west},{south},{east},{north}",
                "time": (
                    f"{request.start.isoformat()},"
                    f"{(request.end + timedelta(days=1)).isoformat()}"
                ),
                "closed": "true",
            }
        )
        url = f"{OSM_CHANGESETS}?{query}"
        progress.status(f"osm {request.window_id} changesets")
        response = get_with_retry(self.transport, url, timeout=60, attempts=3, sleep=0.5)
        requests.append(
            {"url": redact_url(url), "status": response.status, "bytes": len(response.body)}
        )
        if response.status == 200:
            root = ET.fromstring(response.body)
            for node in root.findall("changeset"):
                closed = node.attrib.get("closed_at") or node.attrib.get("created_at") or ""
                if len(closed) < 10:
                    continue
                day = date.fromisoformat(closed[:10])
                if day in counts:
                    counts[day] += 1
        progress.line(f"osm {request.window_id} changesets={sum(counts.values())}")
        return daily_count_result(
            request,
            days,
            counts,
            retrieved_at=retrieved_at,
            requests=requests,
            notes="OSM closed changesets intersecting the union AOI; 0 is observed zero.",
        )
