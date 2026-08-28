from __future__ import annotations

import csv
import io
import os
import re
import zipfile
from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path

from wsf.connectors.base import PullRequest
from wsf.connectors.daily import daily_count_result
from wsf.connectors.firms import _skipped
from wsf.time import date_range

ICEWS_NOTE = (
    "ICEWS_EVENTS_PATH should point at the Dataverse zip, an unpacked directory, "
    "or a single .tab/.csv. https://doi.org/10.7910/DVN/28075"
)
TABLE_SUFFIXES = {".tab", ".tsv", ".csv"}
EVENTS_YEAR = re.compile(r"(?:^|/)events\.(\d{4})\.", re.I)
WEEKLY_YEAR = re.compile(r"(?:^|/)((?:19|20)\d{2})\d{4}-icews-events", re.I)
ACTOR_ALIASES = {
    "RUS": {"RUS", "Russia", "Russian Federation"},
    "UKR": {"UKR", "Ukraine"},
    "USA": {"USA", "United States", "United States of America"},
    "DEU": {"DEU", "Germany", "Federal Republic of Germany"},
    "GRC": {"GRC", "Greece"},
}


class IcewsConnector:
    source = "icews"

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir

    def pull(self, request: PullRequest):
        days = date_range(request.start, request.end)
        retrieved_at = request.retrieved_at or datetime.now(UTC)
        path = _resolve_path(self.data_dir)
        if path is None or not path.exists():
            return _skipped(request, days, retrieved_at, ICEWS_NOTE)
        actor = str(request.queries.cameo_actor or "RUS")
        aliases = set(ACTOR_ALIASES.get(actor, {actor}))
        aliases.add(actor)
        roots = {str(code).zfill(2)[:2] for code in (request.queries.cameo_root_codes or [])}
        years = {day.year for day in days}
        counts: dict[date, float] = {day: 0.0 for day in days}
        n_rows = 0
        for row in iter_icews_rows(path, years):
            n_rows += 1
            source = str(row.get("Source Country") or row.get("source_country") or "")
            if source not in aliases and actor not in source:
                continue
            if roots:
                cameo = str(row.get("CAMEO Code") or row.get("cameo_code") or "")
                if cameo and icews_root(cameo) not in roots:
                    continue
            raw = str(row.get("Event Date") or row.get("event_date") or "")[:10]
            if len(raw) < 10:
                continue
            try:
                day = date.fromisoformat(raw.replace("/", "-"))
            except ValueError:
                continue
            if day in counts:
                counts[day] += 1
        request.log().line(
            f"icews {request.window_id} scanned_rows={n_rows} events={sum(counts.values())}"
        )
        return daily_count_result(
            request,
            days,
            counts,
            retrieved_at=retrieved_at,
            requests=[{"path": str(path), "scanned_rows": n_rows}],
            extra={"actor": actor},
            notes="ICEWS source-country daily talk counts from a local Dataverse dump.",
        )


def _resolve_path(data_dir: Path) -> Path | None:
    env_path = os.environ.get("ICEWS_EVENTS_PATH", "").strip()
    if env_path:
        return Path(env_path)
    for candidate in (
        data_dir / "events.csv",
        data_dir / "events.tab",
        data_dir,
    ):
        if candidate.exists():
            return candidate
    return None


def iter_icews_rows(path: Path, years: set[int]) -> Iterator[dict[str, str]]:
    if path.is_dir():
        for child in sorted(path.iterdir()):
            if child.is_dir() or child.suffix.lower() in {".zip", *TABLE_SUFFIXES}:
                yield from iter_icews_rows(child, years)
        return
    suffix = path.suffix.lower()
    if suffix == ".zip":
        with zipfile.ZipFile(path) as archive:
            yield from _rows_in_zip(archive, years)
        return
    if suffix in TABLE_SUFFIXES:
        if _skip_year(path.name, years):
            return
        with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
            yield from _dict_rows(handle, path.name)


def _rows_in_zip(archive: zipfile.ZipFile, years: set[int]) -> Iterator[dict[str, str]]:
    for info in archive.infolist():
        if info.is_dir():
            continue
        name = info.filename.replace("\\", "/")
        if _skip_year(name, years):
            continue
        lowered = name.lower()
        if lowered.endswith(".zip"):
            nested = zipfile.ZipFile(io.BytesIO(archive.read(info)))
            try:
                yield from _rows_in_zip(nested, years)
            finally:
                nested.close()
            continue
        if not any(lowered.endswith(suffix) for suffix in TABLE_SUFFIXES):
            continue
        with archive.open(info) as binary:
            text = io.TextIOWrapper(binary, encoding="utf-8", errors="replace", newline="")
            yield from _dict_rows(text, name)


def _dict_rows(handle: io.TextIOBase, name: str) -> Iterator[dict[str, str]]:
    delimiter = "," if name.lower().endswith(".csv") else "\t"
    reader = csv.DictReader(handle, delimiter=delimiter)
    for row in reader:
        yield {str(key).lstrip("\ufeff"): value or "" for key, value in row.items()}


def _skip_year(name: str, years: set[int]) -> bool:
    found = _years_in_name(name)
    return bool(found) and found.isdisjoint(years)


def _years_in_name(name: str) -> set[int]:
    found: set[int] = set()
    for match in EVENTS_YEAR.finditer(name):
        found.add(int(match.group(1)))
    for match in WEEKLY_YEAR.finditer(name):
        found.add(int(match.group(1)))
    return found


def icews_root(raw: str) -> str:
    digits = "".join(character for character in str(raw) if character.isdigit())
    if not digits:
        return ""
    padded = digits.zfill(3)
    return padded[:2]
