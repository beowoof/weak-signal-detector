from __future__ import annotations

import csv
import io
import os
from datetime import UTC, date, datetime, timedelta

from wsf.connectors.base import ConnectorResult, PullRequest
from wsf.connectors.daily import daily_count_result
from wsf.connectors.http import HttpTransport, get_with_retry, redact_url
from wsf.time import date_range

FIRMS_AREA = (
    "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/{sensor}/"
    "{west},{south},{east},{north}/{span}/{day}"
)
# Suomi-NPP FIRMS delivery ceases 1 Nov 2026. NOAA-20 VIIRS standard processing
# covers 1 Apr 2018–present, so it is the frozen instrument for 2022+ windows.
# NOAA-21 only starts 17 Jan 2024 and must not be mixed into the same series.
DEFAULT_SENSOR = "VIIRS_NOAA20_SP"
ALLOWED_SENSORS = frozenset(
    {
        "VIIRS_NOAA20_SP",
        "VIIRS_NOAA20_NRT",
        "VIIRS_NOAA21_NRT",
        "VIIRS_SNPP_SP",
        "VIIRS_SNPP_NRT",
        "MODIS_SP",
        "MODIS_NRT",
    }
)


class FirmsConnector:
    source = "firms"

    def __init__(self, transport: HttpTransport) -> None:
        self.transport = transport

    def pull(self, request: PullRequest) -> ConnectorResult:
        days = date_range(request.start, request.end)
        retrieved_at = request.retrieved_at or datetime.now(UTC)
        key = os.environ.get("FIRMS_MAP_KEY", "")
        if not key:
            return _skipped(
                request,
                days,
                retrieved_at,
                "FIRMS_MAP_KEY missing; free at firms.modaps.eosdis.nasa.gov/api/",
            )
        if not request.aois:
            return _skipped(request, days, retrieved_at, "FIRMS requires AOI bboxes")
        sensor = os.environ.get("FIRMS_SENSOR", DEFAULT_SENSOR).strip() or DEFAULT_SENSOR
        if sensor not in ALLOWED_SENSORS:
            return _skipped(
                request,
                days,
                retrieved_at,
                f"FIRMS_SENSOR {sensor!r} is not one of {sorted(ALLOWED_SENSORS)}",
            )
        west, south, east, north = _union_bbox(request.aois)
        progress = request.log()
        counts: dict[date, float] = {}
        requests: list[dict[str, object]] = []
        # Area API: 1 MAP_KEY transaction per call. NASA currently accepts day range 1–5.
        max_span = 5
        cursor = request.start
        down_days: set[date] = set()
        while cursor <= request.end:
            chunk_end = min(cursor + timedelta(days=max_span - 1), request.end)
            span = (chunk_end - cursor).days + 1
            url = FIRMS_AREA.format(
                key=key,
                sensor=sensor,
                west=west,
                south=south,
                east=east,
                north=north,
                span=span,
                day=chunk_end.isoformat(),
            )
            progress.status(f"firms {request.window_id} {cursor}..{chunk_end}")
            response = get_with_retry(self.transport, url, timeout=60, attempts=3, sleep=0.5)
            requests.append(
                {
                    "url": redact_url(url).replace(key, "REDACTED") if key else redact_url(url),
                    "status": response.status,
                    "bytes": len(response.body),
                }
            )
            text = response.body.decode("utf-8", errors="replace")
            chunk_days = date_range(cursor, chunk_end)
            if response.status != 200 or text.lower().startswith("invalid"):
                down_days.update(chunk_days)
            else:
                for day in chunk_days:
                    counts.setdefault(day, 0.0)
                reader = csv.DictReader(io.StringIO(text))
                for row in reader:
                    raw = row.get("acq_date") or row.get("ACQ_DATE")
                    if not raw:
                        continue
                    day = date.fromisoformat(raw[:10])
                    if day in counts:
                        counts[day] += 1
            cursor = chunk_end + timedelta(days=1)
        progress.line(
            f"firms {request.window_id} detections={sum(counts.values())} "
            f"down_days={len(down_days)}"
        )
        return daily_count_result(
            request,
            days,
            counts,
            retrieved_at=retrieved_at,
            requests=requests,
            source_down_days=down_days,
            extra={"sensor": sensor},
            notes=(
                f"{sensor} thermal detections in the union AOI; 0 is observed zero; "
                "HTTP/invalid responses are source_down, not zero. "
                "NOAA-20 is the frozen FIRMS instrument (SNPP delivery ends 2026-11-01)."
            ),
        )


def _union_bbox(aois: list[dict]) -> tuple[float, float, float, float]:
    west = min(float(item["bbox"][0]) for item in aois)
    south = min(float(item["bbox"][1]) for item in aois)
    east = max(float(item["bbox"][2]) for item in aois)
    north = max(float(item["bbox"][3]) for item in aois)
    return west, south, east, north


def _skipped(
    request: PullRequest, days: list[date], retrieved_at: datetime, notes: str
) -> ConnectorResult:
    result = daily_count_result(
        request, days, {}, retrieved_at=retrieved_at, requests=[], notes=notes, weekend_missing=True
    )
    result.item["not_applicable"] = True
    result.item["coverage"] = 1.0
    return result
