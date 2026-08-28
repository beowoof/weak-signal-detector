from __future__ import annotations

import json
from datetime import UTC, date, datetime, time

from wsf.connectors.base import ConnectorResult, PullRequest, collection_item
from wsf.types import Observation


def daily_count_result(
    request: PullRequest,
    days: list[date],
    counts: dict[date, float],
    *,
    retrieved_at: datetime,
    requests: list[dict[str, object]],
    notes: str = "",
    weekend_missing: bool = False,
    absent_missing: bool = False,
    extra: dict[str, object] | None = None,
) -> ConnectorResult:
    observations: list[Observation] = []
    n_ok = n_missing = n_source_down = 0
    for day in days:
        if weekend_missing and day.weekday() >= 5:
            quality = "missing"
            value = None
            n_missing += 1
        elif day in counts:
            quality = "ok"
            value = float(counts[day])
            n_ok += 1
        elif weekend_missing or absent_missing:
            quality = "missing"
            value = None
            n_missing += 1
        else:
            quality = "ok"
            value = 0.0
            n_ok += 1
        payload_extra = {"event_day": day.isoformat(), **(extra or {})}
        observations.append(
            Observation(
                version_id=f"{request.source}:{request.window_id}:{day.isoformat()}",
                series_id=request.series_id,
                period_id=request.window_id,
                event_time=datetime(day.year, day.month, day.day, tzinfo=UTC),
                available_at=datetime.combine(day, time(23, 59, 59), tzinfo=UTC),
                retrieved_at=retrieved_at,
                value=value,
                quality=quality,  # type: ignore[arg-type]
                extra=json.dumps(payload_extra, sort_keys=True),
            )
        )
    n_expected = n_ok + n_missing + n_source_down
    coverage = n_ok / n_expected if n_expected else 0.0
    checksum_ready = True
    return ConnectorResult(
        item=collection_item(
            source=request.source,
            window_id=request.window_id,
            series_id=request.series_id,
            coverage=coverage,
            provenance_complete=checksum_ready,
            contains_post_cutoff_material=False,
            checksum="",
            n_expected=n_expected,
            n_ok=n_ok,
            n_missing=n_missing,
            n_source_down=n_source_down,
            observations_path=None,
            provenance_path=None,
            notes=notes,
        ),
        observations=observations,
        requests=requests,
    )


def failed_result(
    request: PullRequest, days: list[date], error: str, retrieved_at: datetime
) -> ConnectorResult:
    observations = [
        Observation(
            version_id=f"{request.source}:{request.window_id}:{day.isoformat()}:down",
            series_id=request.series_id,
            period_id=request.window_id,
            event_time=datetime(day.year, day.month, day.day, tzinfo=UTC),
            available_at=datetime.combine(day, time(23, 59, 59), tzinfo=UTC),
            retrieved_at=retrieved_at,
            value=None,
            quality="source_down",
            extra=json.dumps({"error": error}, sort_keys=True),
        )
        for day in days
    ]
    return ConnectorResult(
        item=collection_item(
            source=request.source,
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
            notes=error,
        ),
        observations=observations,
        requests=[{"error": error}],
    )
