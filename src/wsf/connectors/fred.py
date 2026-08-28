from __future__ import annotations

import json
import os
from datetime import UTC, date, datetime, time
from urllib.parse import urlencode

from wsf.connectors.base import ConnectorResult, PullRequest, collection_item
from wsf.connectors.http import HttpTransport, get_with_retry, redact_url
from wsf.time import date_range
from wsf.types import Observation

FRED_URL = "https://api.stlouisfed.org/fred/series/observations"


class FredConnector:
    source = "alfred"

    def __init__(self, transport: HttpTransport) -> None:
        self.transport = transport

    def pull(self, request: PullRequest) -> ConnectorResult:
        series_id = request.queries.fred_series
        days = date_range(request.start, request.end)
        retrieved_at = request.retrieved_at or datetime.now(UTC)
        progress = request.log()
        if not series_id:
            progress.line(f"alfred {request.window_id} skipped (no daily series)")
            return _null_series_result(request, days, retrieved_at)

        api_key = os.environ.get("FRED_API_KEY", "")
        if not api_key:
            raise ValueError("FRED_API_KEY is required for live ALFRED collection")
        query = urlencode(
            {
                "series_id": series_id,
                "api_key": api_key,
                "file_type": "json",
                "observation_start": request.start.isoformat(),
                "observation_end": request.end.isoformat(),
                "realtime_start": request.start.isoformat(),
                "realtime_end": request.end.isoformat(),
            }
        )
        url = f"{FRED_URL}?{query}"
        progress.status(f"alfred {request.window_id} {series_id}")
        response = get_with_retry(self.transport, url, timeout=60, attempts=3, sleep=0.5)
        requests = [
            {
                "url": redact_url(url),
                "status": response.status,
                "series_id": series_id,
                "bytes": len(response.body),
            }
        ]
        if response.status == 404:
            progress.line(f"alfred {request.window_id} unknown series {series_id}")
            result = _null_series_result(request, days, retrieved_at)
            result.requests = requests
            result.item["notes"] = (
                f"Unknown ALFRED series {series_id}; treated as missing, not substituted."
            )
            return result
        if response.status != 200:
            observations = [
                Observation(
                    version_id=f"alfred:{series_id}:{day.isoformat()}:down",
                    series_id=request.series_id,
                    period_id=request.window_id,
                    event_time=datetime(day.year, day.month, day.day, tzinfo=UTC),
                    available_at=datetime.combine(day, time(23, 59, 59), tzinfo=UTC),
                    retrieved_at=retrieved_at,
                    value=None,
                    quality="source_down",
                    extra=json.dumps({"http_status": response.status}, sort_keys=True),
                )
                for day in days
            ]
            return ConnectorResult(
                item=collection_item(
                    source=self.source,
                    window_id=request.window_id,
                    series_id=request.series_id,
                    coverage=0.0,
                    provenance_complete=True,
                    contains_post_cutoff_material=False,
                    checksum="",
                    n_expected=len(days),
                    n_ok=0,
                    n_missing=0,
                    n_source_down=len(days),
                    observations_path=None,
                    provenance_path=None,
                    notes=f"ALFRED HTTP {response.status}",
                ),
                observations=observations,
                requests=requests,
            )

        payload = json.loads(response.body.decode("utf-8"))
        by_day: dict[date, list[dict[str, str]]] = {day: [] for day in days}
        for row in payload.get("observations") or []:
            day = date.fromisoformat(row["date"])
            if day in by_day:
                by_day[day].append(row)

        observations = []
        n_ok = n_missing = n_source_down = 0
        weekday_expected = 0
        weekday_ok = 0
        for day in days:
            is_weekday = day.weekday() < 5
            if is_weekday:
                weekday_expected += 1
            vintages = by_day[day]
            if not vintages:
                quality = "missing"
                value = None
                version = f"alfred:{series_id}:{day.isoformat()}:missing"
                extra = {"series_id": series_id, "vintages": []}
                n_missing += 1
            else:
                latest = max(vintages, key=lambda item: item["realtime_start"])
                raw = latest.get("value", ".")
                if raw in {".", "", None}:
                    quality = "missing"
                    value = None
                    n_missing += 1
                else:
                    quality = "ok"
                    value = float(raw)
                    n_ok += 1
                    if is_weekday:
                        weekday_ok += 1
                version = f"alfred:{series_id}:{day.isoformat()}:{latest['realtime_start']}"
                extra = {
                    "series_id": series_id,
                    "realtime_start": latest["realtime_start"],
                    "vintages": vintages,
                }
            available = (
                date.fromisoformat(extra["realtime_start"])
                if extra.get("realtime_start")
                else day
            )
            observations.append(
                Observation(
                    version_id=version,
                    series_id=request.series_id,
                    period_id=request.window_id,
                    event_time=datetime(day.year, day.month, day.day, tzinfo=UTC),
                    available_at=datetime.combine(available, time(0, 0), tzinfo=UTC),
                    retrieved_at=retrieved_at,
                    value=value,
                    quality=quality,  # type: ignore[arg-type]
                    extra=json.dumps(extra, sort_keys=True),
                )
            )

        coverage = weekday_ok / weekday_expected if weekday_expected else 1.0
        progress.line(f"alfred {request.window_id} {series_id} coverage={coverage:.3f}")
        return ConnectorResult(
            item=collection_item(
                source=self.source,
                window_id=request.window_id,
                series_id=request.series_id,
                coverage=coverage,
                provenance_complete=True,
                contains_post_cutoff_material=any(
                    item.event_time.date() > request.end for item in observations
                ),
                checksum="",
                n_expected=weekday_expected,
                n_ok=weekday_ok,
                n_missing=n_missing,
                n_source_down=n_source_down,
                observations_path=None,
                provenance_path=None,
            ),
            observations=observations,
            requests=requests,
        )


def _null_series_result(
    request: PullRequest, days: list[date], retrieved_at: datetime
) -> ConnectorResult:
    observations = [
        Observation(
            version_id=f"alfred:null:{day.isoformat()}",
            series_id=request.series_id,
            period_id=request.window_id,
            event_time=datetime(day.year, day.month, day.day, tzinfo=UTC),
            available_at=datetime.combine(day, time(23, 59, 59), tzinfo=UTC),
            retrieved_at=retrieved_at,
            value=None,
            quality="missing",
            extra=json.dumps({"reason": "no_daily_h10_ruble"}, sort_keys=True),
        )
        for day in days
    ]
    return ConnectorResult(
        item=collection_item(
            source="alfred",
            window_id=request.window_id,
            series_id=request.series_id,
            coverage=1.0,
            provenance_complete=True,
            contains_post_cutoff_material=False,
            checksum="",
            n_expected=len(days),
            n_ok=0,
            n_missing=len(days),
            n_source_down=0,
            observations_path=None,
            provenance_path=None,
            not_applicable=True,
            notes="No daily H.10 ruble series; dyad.fx is reported missing by design.",
        ),
        observations=observations,
        requests=[],
    )
