from __future__ import annotations

import io
import json
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, date, datetime, time
from pathlib import Path

from wsf.connectors.base import ConnectorResult, PullRequest, collection_item
from wsf.connectors.http import HttpTransport, get_with_retry, redact_url
from wsf.progress import Progress
from wsf.time import date_range
from wsf.types import Observation

GDELT_EXPORT = "http://data.gdeltproject.org/gdeltv2/{stamp}.export.CSV.zip"
COL_ACTOR1_COUNTRY = 7
COL_EVENT_ROOT = 28
N_COLS = 61


class GdeltConnector:
    source = "gdelt"

    def __init__(self, transport: HttpTransport, cache_dir: Path) -> None:
        self.transport = transport
        self.cache_dir = cache_dir

    def pull(self, request: PullRequest) -> ConnectorResult:
        actor = request.queries.cameo_actor
        root_codes = {_norm_code(code) for code in request.queries.cameo_root_codes}
        days = date_range(request.start, request.end)
        retrieved_at = request.retrieved_at or datetime.now(UTC)
        cache_root = self.cache_dir / _cache_key(actor, sorted(root_codes))
        cache_root.mkdir(parents=True, exist_ok=True)

        observations: list[Observation] = []
        requests: list[dict[str, object]] = []
        n_ok = n_missing = n_source_down = 0
        progress = request.log()
        n_days = len(days)
        for index, day in enumerate(days, start=1):
            prefix = f"gdelt {request.window_id} {day.isoformat()} [{index}/{n_days}]"
            cached = _read_cache(cache_root / f"{day.isoformat()}.json")
            if cached and cached.get("slots_failed", 1) == 0:
                count = int(cached["count"])
                quality = "ok"
                n_ok += 1
                extra = cached
                progress.line(f"{prefix} cached count={count}")
            else:
                progress.status(f"{prefix} downloading 0/96")
                count, quality, day_requests, extra = self._harvest_day(
                    day, actor, root_codes, request.max_workers, progress, prefix
                )
                requests.extend(day_requests)
                if extra.get("slots_failed", 0) == 0:
                    _write_cache(cache_root / f"{day.isoformat()}.json", extra)
                if quality == "ok":
                    n_ok += 1
                elif quality == "source_down":
                    n_source_down += 1
                else:
                    n_missing += 1
                progress.line(
                    f"{prefix} {quality} count={count} "
                    f"empty={extra['slots_empty']} failed={extra['slots_failed']}"
                )
            observations.append(
                Observation(
                    version_id=f"gdelt:{actor}:{day.isoformat()}",
                    series_id=request.series_id,
                    period_id=request.window_id,
                    event_time=datetime(day.year, day.month, day.day, tzinfo=UTC),
                    available_at=datetime.combine(day, time(23, 59, 59), tzinfo=UTC),
                    retrieved_at=retrieved_at,
                    value=None if quality != "ok" else float(count),
                    quality=quality,  # type: ignore[arg-type]
                    extra=json.dumps(extra, sort_keys=True),
                )
            )

        n_expected = len(days)
        coverage = n_ok / n_expected if n_expected else 0.0
        return ConnectorResult(
            item=collection_item(
                source=self.source,
                window_id=request.window_id,
                series_id=request.series_id,
                coverage=coverage,
                provenance_complete=True,
                contains_post_cutoff_material=False,
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

    def _harvest_day(
        self,
        day: date,
        actor: str,
        root_codes: set[str],
        max_workers: int,
        progress: Progress,
        prefix: str,
    ) -> tuple[int, str, list[dict[str, object]], dict[str, object]]:
        stamps = gdelt_stamps(day)
        counts = 0
        empty = 0
        failed = 0
        done = 0
        requests: list[dict[str, object]] = []
        workers = max(1, max_workers)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(self._harvest_slot, stamp, actor, root_codes): stamp for stamp in stamps
            }
            for future in as_completed(futures):
                slot_count, status, record = future.result()
                requests.append(record)
                if status == "ok":
                    counts += slot_count
                elif status == "empty":
                    empty += 1
                else:
                    failed += 1
                done += 1
                if done == len(stamps) or done % 8 == 0:
                    progress.status(f"{prefix} downloading {done}/{len(stamps)}")
        extra = {
            "actor": actor,
            "date": day.isoformat(),
            "count": counts,
            "slots": len(stamps),
            "slots_empty": empty,
            "slots_failed": failed,
            "root_codes": sorted(root_codes),
        }
        quality = "source_down" if failed else "ok"
        return counts, quality, requests, extra

    def _harvest_slot(
        self, stamp: str, actor: str, root_codes: set[str]
    ) -> tuple[int, str, dict[str, object]]:
        url = GDELT_EXPORT.format(stamp=stamp)
        try:
            response = get_with_retry(self.transport, url, timeout=120, attempts=3, sleep=0.5)
        except TimeoutError as error:
            return 0, "failed", {
                "url": redact_url(url),
                "status": 0,
                "error": str(error),
                "stamp": stamp,
            }
        record = {
            "url": redact_url(url),
            "status": response.status,
            "stamp": stamp,
            "bytes": len(response.body),
        }
        if response.status == 404:
            return 0, "empty", record
        if response.status != 200:
            return 0, "failed", record
        count = count_talk_events(response.body, actor, root_codes)
        return count, "ok", record


def gdelt_stamps(day: date) -> list[str]:
    stamps = []
    prefix = day.strftime("%Y%m%d")
    for hour in range(24):
        for minute in (0, 15, 30, 45):
            stamps.append(f"{prefix}{hour:02d}{minute:02d}00")
    return stamps


def count_talk_events(zip_bytes: bytes, actor: str, root_codes: set[str]) -> int:
    count = 0
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        names = archive.namelist()
        if not names:
            return 0
        with archive.open(names[0]) as handle:
            for raw in handle:
                line = raw.decode("utf-8", errors="replace").rstrip("\n")
                if not line:
                    continue
                columns = line.split("\t")
                if len(columns) < N_COLS:
                    continue
                if columns[COL_ACTOR1_COUNTRY] != actor:
                    continue
                if _norm_code(columns[COL_EVENT_ROOT]) not in root_codes:
                    continue
                count += 1
    return count


def _norm_code(value: str) -> str:
    text = value.strip()
    if not text:
        return text
    if text.isdigit():
        return text.zfill(2)
    return text


def _cache_key(actor: str, root_codes: list[str]) -> str:
    return f"{actor}_{'-'.join(root_codes)}"


def _read_cache(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _write_cache(path: Path, value: dict[str, object]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
