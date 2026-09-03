"""Copernicus catalogue pointers over named AOIs. Cutoff-safe; does not vote."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from urllib.parse import quote

from wsf.connectors.http import HttpTransport, get_with_retry

CATALOGUE = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
PRODUCT_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products({id})"

# CDSE now stores reprocessed PublicationDate for Sentinel-2. When publication
# is far after sensing, reconstruct operational availability like VIIRS latency.
REPROCESS_AFTER_DAYS = 14
LATENCY_DAYS = {
    "SENTINEL-1": 1,
    "SENTINEL-2": 1,
}

SEARCHES = (
    ("SENTINEL-1", "GRDH"),
    ("SENTINEL-2", "MSIL1C"),
)


def _polygon(bbox: list[float]) -> str:
    west, south, east, north = (float(value) for value in bbox)
    return (
        f"POLYGON(({west} {south},{east} {south},{east} {north},"
        f"{west} {north},{west} {south}))"
    )


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _content_start(row: dict[str, Any]) -> datetime | None:
    content = row.get("ContentDate") or {}
    if isinstance(content, dict):
        return _parse_dt(content.get("Start"))
    return _parse_dt(content)


def _available_at(collection: str, sensing: datetime, published: datetime | None) -> datetime:
    latency = LATENCY_DAYS.get(collection, 1)
    reconstructed = datetime.combine(
        (sensing.astimezone(UTC) + timedelta(days=latency)).date(),
        time(23, 59, 59),
        tzinfo=UTC,
    )
    if published is None:
        return reconstructed
    gap = published - sensing
    if gap.days >= REPROCESS_AFTER_DAYS:
        return reconstructed
    return published


def _dedupe_key(aoi_id: str, collection: str, name: str, sensing: datetime) -> str:
    parts = name.split("_")
    tile = next((part for part in parts if part.startswith("T") and len(part) == 6), "")
    stamp = sensing.strftime("%Y%m%dT%H%M")
    return f"{aoi_id}:{collection}:{tile or name[:20]}:{stamp}"


def _filter(collection: str, token: str, bbox: list[float], start: date, end: date) -> str:
    poly = _polygon(bbox)
    end_exclusive = (end + timedelta(days=1)).isoformat()
    return (
        f"Collection/Name eq '{collection}' and contains(Name,'{token}') and "
        f"OData.CSC.Intersects(area=geography'SRID=4326;{poly}') and "
        f"ContentDate/Start ge {start.isoformat()}T00:00:00.000Z and "
        f"ContentDate/Start lt {end_exclusive}T00:00:00.000Z"
    )


def search_catalogue(
    transport: HttpTransport,
    aois: list[dict[str, Any]],
    *,
    start: date,
    end: date,
    cutoff: datetime,
    sleep: float = 0.15,
) -> tuple[list[dict[str, Any]], list[str]]:
    """List S1 GRD and S2 L1C granules over AOIs. Does not download scenes."""
    granules: list[dict[str, Any]] = []
    notes: list[str] = []
    seen: set[str] = set()
    failures = 0
    for aoi in aois:
        bbox = list(aoi.get("bbox") or [])
        if len(bbox) != 4:
            continue
        aoi_id = str(aoi.get("id") or "")
        aoi_name = str(aoi.get("name") or aoi_id)
        for collection, token in SEARCHES:
            filt = _filter(collection, token, bbox, start, end)
            url = (
                f"{CATALOGUE}?$filter={quote(filt)}"
                "&$select=Id,Name,ContentDate,PublicationDate,OriginDate"
                "&$top=12"
            )
            try:
                response = get_with_retry(
                    transport, url, timeout=60, attempts=3, sleep=sleep
                )
            except (OSError, TimeoutError) as error:
                failures += 1
                notes.append(f"{collection} catalogue search failed for {aoi_name}: {error}")
                continue
            if response.status != 200:
                failures += 1
                notes.append(
                    f"{collection} catalogue search for {aoi_name} returned "
                    f"HTTP {response.status}."
                )
                continue
            try:
                payload = response.body.decode("utf-8")
                rows = (json.loads(payload).get("value")) or []
            except (UnicodeDecodeError, ValueError) as error:
                failures += 1
                notes.append(f"{collection} catalogue parse failed for {aoi_name}: {error}")
                continue
            for row in rows:
                name = str(row.get("Name") or "")
                if token not in name or "COG" in name or "RAW" in name:
                    continue
                sensing = _content_start(row)
                if sensing is None:
                    continue
                published = _parse_dt(row.get("PublicationDate"))
                available = _available_at(collection, sensing, published)
                knowable = available <= cutoff
                key = _dedupe_key(aoi_id, collection, name, sensing)
                if key in seen:
                    continue
                seen.add(key)
                product_id = str(row.get("Id") or "")
                granules.append(
                    {
                        "kind": "catalogue_granule",
                        "votes": False,
                        "collection": collection,
                        "product_type": token,
                        "name": name,
                        "aoi_id": aoi_id,
                        "aoi_name": aoi_name,
                        "sensing_date": sensing.date().isoformat(),
                        "sensing_at": sensing.isoformat(),
                        "published_at": published.isoformat() if published else None,
                        "available_at": available.isoformat(),
                        "knowable": knowable,
                        "reconstructed": bool(
                            published is None
                            or (published - sensing).days >= REPROCESS_AFTER_DAYS
                        ),
                        "url": PRODUCT_URL.format(id=product_id) if product_id else CATALOGUE,
                    }
                )
    knowable = [row for row in granules if row["knowable"]]
    notes.append(
        "Copernicus catalogue pointers only. Scenes are not downloaded and do not vote. "
        "Sentinel-2 PublicationDate on CDSE is often a later reprocess; knowable rows "
        "use reconstructed 1-day L1C / GRD availability when publication is stale."
    )
    if failures:
        notes.append(f"{failures} catalogue request(s) failed.")
    notes.append(
        f"{len(knowable)} granules knowable at cutoff of {len(granules)} listed "
        f"over {len(aois)} AOIs ({start.isoformat()}–{end.isoformat()})."
    )
    return granules, notes
