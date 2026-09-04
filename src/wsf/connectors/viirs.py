from __future__ import annotations

import json
import math
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

from wsf.connectors.base import ConnectorResult, PullRequest, collection_item
from wsf.time import date_range
from wsf.types import Observation

PIXELS = 2400
TILE_DEGREES = 10.0
NTL_FILL = -999.9
QUALITY_VALID = {0, 1}
CLOUD_CLEAR = {0, 1}
CLOUD_DETECTION_SHIFT = 6
GRANULE_TILE = re.compile(r"h(\d{2})v(\d{2})")
CMR_VERSION = "2"
DOWNLOAD_TIMEOUT_S = 300
STALL_S = 60


class TileArrays:
    def __init__(
        self,
        ntl: list[list[float]],
        quality: list[list[int]],
        cloud: list[list[int]],
        lat: list[list[float]],
        lon: list[list[float]],
        production_timestamp: str | None = None,
        tile_id: str = "",
    ) -> None:
        self.ntl = ntl
        self.quality = quality
        self.cloud = cloud
        self.lat = lat
        self.lon = lon
        self.production_timestamp = production_timestamp
        self.tile_id = tile_id


class ViirsBackend(Protocol):
    def read_tile(
        self, day: date, tile_id: str, bbox: list[float], cache_dir: Path
    ) -> TileArrays | None:
        """Return arrays for one tile/day, or None if no granule was found."""


def viirs_extra_available() -> bool:
    try:
        import earthaccess  # noqa: F401
        import h5py  # noqa: F401
        import numpy  # noqa: F401
    except ImportError:
        return False
    return True


class ViirsConnector:
    source = "viirs"

    def __init__(self, cache_dir: Path, backend: ViirsBackend | None = None) -> None:
        self.cache_dir = cache_dir
        self.backend = backend

    def pull(self, request: PullRequest) -> ConnectorResult:
        if not request.aois:
            raise ValueError("live VIIRS collection requires at least one AOI bbox")
        progress = request.log()
        backend = self.backend or EarthaccessViirsBackend()
        if hasattr(backend, "progress"):
            backend.progress = progress
        days = date_range(request.start, request.end)
        retrieved_at = request.retrieved_at or datetime.now(UTC)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        observations: list[Observation] = []
        requests: list[dict[str, object]] = []
        n_ok = n_missing = n_source_down = 0
        n_days = len(days)
        for index, day in enumerate(days, start=1):
            aoi_means: dict[str, float | None] = {}
            contributing: list[str] = []
            production: list[str] = []
            day_failed = False
            for aoi in request.aois:
                bbox = [float(value) for value in aoi["bbox"]]
                tile_ids = sorted(tile_ids_for_bbox(bbox))
                values: list[float] = []
                for h, v in tile_ids:
                    tile_id = f"h{h:02d}v{v:02d}"
                    aoi_id = str(aoi["id"])
                    progress.status(
                        f"viirs {request.window_id} {day.isoformat()} "
                        f"[{index}/{n_days}] {aoi_id} {tile_id}",
                        source="viirs",
                        window=request.window_id,
                        day=day.isoformat(),
                        day_index=index,
                        day_count=n_days,
                        aoi=aoi_id,
                        tile=tile_id,
                        step="tile",
                        bytes=0,
                        total_bytes=None,
                        stalled=False,
                    )
                    stop = threading.Event()
                    watcher = threading.Thread(
                        target=_watch_partials,
                        args=(progress, self.cache_dir, stop),
                        daemon=True,
                    )
                    watcher.start()
                    try:
                        arrays = backend.read_tile(day, tile_id, bbox, self.cache_dir)
                    except Exception as error:  # noqa: BLE001
                        day_failed = True
                        requests.append(
                            {
                                "day": day.isoformat(),
                                "aoi": aoi["id"],
                                "tile": tile_id,
                                "error": str(error),
                            }
                        )
                        continue
                    finally:
                        stop.set()
                    requests.append(
                        {
                            "day": day.isoformat(),
                            "aoi": aoi["id"],
                            "tile": tile_id,
                            "found": arrays is not None,
                            "cmr_version": CMR_VERSION,
                            "grid": "geographic_15arcsec",
                        }
                    )
                    if arrays is None:
                        continue
                    mean = zonal_mean(arrays, bbox)
                    if mean is not None:
                        values.append(mean)
                    if arrays.production_timestamp:
                        production.append(arrays.production_timestamp)
                aoi_means[aoi["id"]] = sum(values) / len(values) if values else None
                if aoi_means[aoi["id"]] is not None:
                    contributing.append(aoi["id"])

            extra = {
                "aoi_means": aoi_means,
                "contributing_aois": contributing,
                "production_timestamps": production,
                "availability_regime": "reconstructed_assumed_latency",
                "assumed_latency_days": 3,
                "grid": "geographic_15arcsec",
            }
            if day_failed:
                quality = "source_down"
                value = None
                n_source_down += 1
            elif len(contributing) < 2:
                quality = "missing"
                value = None
                n_missing += 1
            else:
                quality = "ok"
                value = sum(aoi_means[aoi_id] or 0.0 for aoi_id in contributing) / len(
                    contributing
                )
                n_ok += 1
            progress.line(
                f"viirs {request.window_id} {day.isoformat()} [{index}/{n_days}] "
                f"{quality} aois={len(contributing)}"
            )
            event_time = datetime(day.year, day.month, day.day, tzinfo=UTC)
            observations.append(
                Observation(
                    version_id=f"viirs:{request.window_id}:{day.isoformat()}",
                    series_id=request.series_id,
                    period_id=request.window_id,
                    event_time=event_time,
                    available_at=event_time + timedelta(days=3),
                    retrieved_at=retrieved_at,
                    value=value,
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
                notes=(
                    "VIIRS Collection 2 is retrospectively reconstructed "
                    "under a 3-day assumed latency."
                ),
            ),
            observations=observations,
            requests=requests,
        )


class EarthaccessViirsBackend:
    progress: Any = None

    def read_tile(
        self, day: date, tile_id: str, bbox: list[float], cache_dir: Path
    ) -> TileArrays | None:
        if not viirs_extra_available():
            raise RuntimeError("live VIIRS requires `uv sync --extra viirs`")
        if not os.environ.get("EARTHDATA_TOKEN"):
            raise RuntimeError("EARTHDATA_TOKEN is required for live VIIRS collection")
        import earthaccess
        import h5py

        earthaccess.login(strategy="environment")
        cached = cached_granule(cache_dir, day, tile_id)
        if cached is not None:
            path = cached
            h, v = _parse_tile(tile_id)
            with h5py.File(path, "r") as handle:
                ntl, quality, cloud, lat, lon = _read_science_arrays(handle, h, v)
            return TileArrays(
                ntl=ntl,
                quality=quality,
                cloud=cloud,
                lat=lat,
                lon=lon,
                production_timestamp=path.name,
                tile_id=tile_id,
            )
        doy_tag = f"A{day:%Y%j}"
        pattern = f"VNP46A2.{doy_tag}.{tile_id}*"
        results = earthaccess.search_data(
            short_name="VNP46A2",
            version=CMR_VERSION,
            granule_name=pattern,
            count=10,
        )
        if not results:
            west, south, east, north = bbox
            results = earthaccess.search_data(
                short_name="VNP46A2",
                version=CMR_VERSION,
                bounding_box=(west, south, east, north),
                temporal=(f"{day.isoformat()}T00:00:00", f"{day.isoformat()}T23:59:59"),
                count=25,
            )
        granule = None
        for item in results:
            name = _granule_name(item)
            if tile_id in name and doy_tag in name:
                granule = item
                break
        if granule is None:
            return None
        total = granule_nbytes(granule)
        if self.progress is not None:
            self.progress.update(
                step="download", bytes=0, total_bytes=total, stalled=False
            )
        files = _download_granule(earthaccess, granule, cache_dir)
        if not files:
            return None
        path = Path(files[0])
        h, v = _parse_tile(tile_id)
        with h5py.File(path, "r") as handle:
            ntl, quality, cloud, lat, lon = _read_science_arrays(handle, h, v)
        return TileArrays(
            ntl=ntl,
            quality=quality,
            cloud=cloud,
            lat=lat,
            lon=lon,
            production_timestamp=path.name,
            tile_id=tile_id,
        )


def granule_nbytes(item: Any) -> int | None:
    umm = getattr(item, "umm", None)
    if umm is None and isinstance(item, dict):
        umm = item.get("umm")
    infos = []
    if isinstance(umm, dict):
        infos = (umm.get("DataGranule") or {}).get("ArchiveAndDistributionInformation") or []
    for info in infos:
        if not isinstance(info, dict):
            continue
        if info.get("SizeInBytes"):
            return int(float(info["SizeInBytes"]))
        size = info.get("Size")
        unit = str(info.get("SizeUnit") or "MB").upper()
        if size is None:
            continue
        value = float(size)
        if unit in {"KB", "KILOBYTES"}:
            return int(value * 1000)
        if unit in {"B", "BYTES"}:
            return int(value)
        return int(value * 1024 * 1024)
    size_fn = getattr(item, "size", None)
    if callable(size_fn):
        try:
            mb = float(size_fn())
        except Exception:  # noqa: BLE001
            mb = 0.0
        if mb > 0:
            return int(mb * 1024 * 1024)
    return None


def forget_day(cache_dir: Path, day: date) -> int:
    """Drop HDF5 granules for one day. Not used during collect; review must pass first."""
    if not cache_dir.is_dir():
        return 0
    doy_tag = f"A{day:%Y%j}"
    removed = 0
    for path in cache_dir.glob(f"VNP46A2.{doy_tag}.*"):
        if path.is_file():
            path.unlink(missing_ok=True)
            removed += 1
    return removed


def prune_viirs_cache(cache_dir: Path) -> dict[str, int]:
    """Delete cached VIIRS HDF5 and leftover partials. Call only after review."""
    files = 0
    bytes_removed = 0
    if not cache_dir.is_dir():
        return {"files": 0, "bytes": 0}
    for path in list(cache_dir.glob("VNP46A2.*.h5")) + list(cache_dir.glob("partial_*")):
        if not path.is_file():
            continue
        bytes_removed += path.stat().st_size
        path.unlink(missing_ok=True)
        files += 1
    return {"files": files, "bytes": bytes_removed}


def cached_granule(cache_dir: Path, day: date, tile_id: str) -> Path | None:
    doy_tag = f"A{day:%Y%j}"
    matches = [
        path
        for path in cache_dir.glob(f"VNP46A2.{doy_tag}.{tile_id}*.h5")
        if path.is_file() and path.stat().st_size > 1_000_000 and "COG" not in path.name
    ]
    if not matches:
        return None
    return max(matches, key=lambda path: path.stat().st_mtime)


def _download_granule(earthaccess: Any, granule: Any, cache_dir: Path) -> list[Any]:
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(earthaccess.download, [granule], str(cache_dir))
        try:
            files = future.result(timeout=DOWNLOAD_TIMEOUT_S)
        except FuturesTimeoutError as error:
            raise TimeoutError(
                f"VIIRS download timed out after {DOWNLOAD_TIMEOUT_S}s"
            ) from error
    return list(files or [])


def _watch_partials(progress: Any, cache_dir: Path, stop: threading.Event) -> None:
    last_size = -1
    last_change = time.monotonic()
    while not stop.wait(2):
        partials = [
            path for path in cache_dir.glob("partial_*") if path.is_file()
        ]
        if not partials:
            continue
        newest = max(partials, key=lambda path: path.stat().st_mtime)
        size = newest.stat().st_size
        if size != last_size:
            last_size = size
            last_change = time.monotonic()
        stalled = time.monotonic() - last_change >= STALL_S
        progress.update(step="download", bytes=size, stalled=stalled)


def zonal_mean(arrays: TileArrays, bbox: list[float]) -> float | None:
    west, south, east, north = bbox
    total = 0.0
    count = 0
    for row, ntl_row in enumerate(arrays.ntl):
        for col, raw in enumerate(ntl_row):
            lat = arrays.lat[row][col]
            lon = arrays.lon[row][col]
            if not (south <= lat <= north and west <= lon <= east):
                continue
            if raw is None or float(raw) <= NTL_FILL + 0.1:
                continue
            quality = int(arrays.quality[row][col])
            cloud_bits = (int(arrays.cloud[row][col]) >> CLOUD_DETECTION_SHIFT) & 0b11
            if quality not in QUALITY_VALID or cloud_bits not in CLOUD_CLEAR:
                continue
            total += float(raw)
            count += 1
    if count == 0:
        return None
    return total / count


def tile_ids_for_bbox(bbox: list[float]) -> set[tuple[int, int]]:
    west, south, east, north = bbox
    corners = ((west, south), (west, north), (east, south), (east, north))
    tiles: set[tuple[int, int]] = set()
    for lon, lat in corners:
        tiles.add(lonlat_to_tile(lon, lat))
    return tiles


def lonlat_to_tile(lon: float, lat: float) -> tuple[int, int]:
    """Collection 2 VNP46A2 uses 10-degree geographic tiles, not sinusoidal MODIS tiles."""
    h = int(math.floor((lon + 180.0) / TILE_DEGREES))
    v = int(math.floor((90.0 - lat) / TILE_DEGREES))
    return h, v


def tile_latlon(
    h: int, v: int, rows: int, cols: int
) -> tuple[list[list[float]], list[list[float]]]:
    west = h * TILE_DEGREES - 180.0
    north = 90.0 - v * TILE_DEGREES
    res_x = TILE_DEGREES / cols
    res_y = TILE_DEGREES / rows
    lat = [
        [north - (row + 0.5) * res_y for _col in range(cols)] for row in range(rows)
    ]
    lon = [
        [west + (col + 0.5) * res_x for col in range(cols)] for _row in range(rows)
    ]
    return lat, lon


def _read_science_arrays(handle: Any, h: int, v: int) -> tuple[Any, Any, Any, Any, Any]:
    group = _science_group(handle)
    ntl = _as_nested(group["DNB_BRDF-Corrected_NTL"])
    quality = _as_nested(group["Mandatory_Quality_Flag"])
    cloud = _as_nested(group["QF_Cloud_Mask"])
    if "lat" in group and "lon" in group:
        lat_1d = list(group["lat"])
        lon_1d = list(group["lon"])
        lat = [[float(lat_1d[row]) for _col in lon_1d] for row in range(len(lat_1d))]
        lon = [[float(value) for value in lon_1d] for _row in lat_1d]
    else:
        lat, lon = tile_latlon(h, v, len(ntl), len(ntl[0]))
    return ntl, quality, cloud, lat, lon


def _science_group(handle: Any) -> Any:
    grids = None
    if "HDFEOS" in handle and "GRIDS" in handle["HDFEOS"]:
        grids = handle["HDFEOS"]["GRIDS"]
    for name in ("VIIRS_Grid_DNB_2d", "VNP_Grid_DNB"):
        if grids is not None and name in grids:
            root = grids[name]
            return root["Data Fields"] if "Data Fields" in root else root
        if name in handle:
            root = handle[name]
            return root["Data Fields"] if "Data Fields" in root else root
    raise KeyError("VNP46A2 science group not found")


def _as_nested(dataset: Any) -> list[Any]:
    if hasattr(dataset, "tolist"):
        return dataset.tolist()
    return [list(row) for row in dataset]


def _granule_name(item: Any) -> str:
    for key in ("native_id", "producer_granule_id"):
        value = getattr(item, key, None)
        if value:
            return str(value)
    umm = getattr(item, "umm", None)
    if isinstance(umm, dict):
        producer = (umm.get("DataGranule") or {}).get("Identifiers") or []
        for ident in producer:
            if ident.get("IdentifierType") == "ProducerGranuleId":
                return str(ident.get("Identifier"))
        if umm.get("GranuleUR"):
            return str(umm["GranuleUR"])
    if hasattr(item, "data_links"):
        links = item.data_links()
        if links:
            return str(links[0])
    if isinstance(item, dict):
        return str(item.get("producer_granule_id") or item.get("title") or item)
    return str(item)


def _parse_tile(tile_id: str) -> tuple[int, int]:
    match = GRANULE_TILE.search(tile_id)
    if not match:
        raise ValueError(f"invalid VIIRS tile id: {tile_id}")
    return int(match.group(1)), int(match.group(2))
