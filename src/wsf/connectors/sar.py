from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from wsf.connectors.base import ConnectorResult, PullRequest
from wsf.connectors.daily import daily_count_result
from wsf.connectors.firms import _skipped
from wsf.connectors.http import HttpTransport, post_with_retry, redact_url
from wsf.time import date_range

TOKEN_URL = (
    "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/"
    "protocol/openid-connect/token"
)
STATS_URL = "https://sh.dataspace.copernicus.eu/api/v1/statistics"
CRS84 = "http://www.opengis.net/def/crs/OGC/1.3/CRS84"
# Denser comparable pass on the frozen AOIs (RUS descending-only; DEU slightly
# denser descending; USA prefers ascending). Mixes of ASC+DESC are not comparable.
ORBIT_DIRECTION = "DESCENDING"
ACQUISITION_MODE = "IW"

# Linear gamma0 to dB. Asks how different the AOI is from itself, not what is there.
EVALSCRIPT = """
//VERSION=3
function setup() {
  return {
    input: [{ bands: ["VV", "dataMask"] }],
    output: [
      { id: "default", bands: 1, sampleType: "FLOAT32" },
      { id: "dataMask", bands: 1 }
    ]
  };
}
function evaluatePixel(samples) {
  return {
    default: [toDb(samples.VV)],
    dataMask: [samples.dataMask]
  };
}
function toDb(linear) {
  return 10 * Math.log(linear + 1e-6) / Math.LN10;
}
""".strip()


class SarConnector:
    source = "sar"

    def __init__(self, transport: HttpTransport, cache_dir: Path | None = None) -> None:
        self.transport = transport
        self.cache_dir = cache_dir
        self._token: str | None = None

    def pull(self, request: PullRequest) -> ConnectorResult:
        days = date_range(request.start, request.end)
        retrieved_at = request.retrieved_at or datetime.now(UTC)
        client_id = os.environ.get("COPERNICUS_CLIENT_ID", "")
        client_secret = os.environ.get("COPERNICUS_CLIENT_SECRET", "")
        if not client_id or not client_secret:
            return _skipped(
                request,
                days,
                retrieved_at,
                "COPERNICUS_CLIENT_ID/SECRET missing; free OAuth client at "
                "dataspace.copernicus.eu",
            )
        if not request.aois:
            return _skipped(request, days, retrieved_at, "Sentinel-1 requires AOI bboxes")
        progress = request.log()
        per_aoi: list[dict[date, float]] = []
        requests: list[dict[str, object]] = []
        for aoi in request.aois:
            bbox = [float(value) for value in aoi["bbox"]]
            payload, provenance = self._aoi_stats(bbox, request.start, request.end)
            requests.append(provenance)
            progress.status(f"sar {request.window_id} {aoi.get('id', bbox)}")
            if payload is None:
                continue
            per_aoi.append(parse_statistical_intervals(payload))
        counts = _mean_across_aois(days, per_aoi)
        progress.line(
            f"sar {request.window_id} observed_days="
            f"{sum(1 for day in days if day in counts)}/{len(days)}"
        )
        return daily_count_result(
            request,
            days,
            counts,
            retrieved_at=retrieved_at,
            requests=requests,
            absent_missing=True,
            extra={
                "orbit_direction": ORBIT_DIRECTION,
                "acquisition_mode": ACQUISITION_MODE,
            },
            notes=(
                f"Mean {ACQUISITION_MODE} VV backscatter (dB) of frozen AOIs on "
                f"comparable {ORBIT_DIRECTION.lower()} passes. Days without an "
                "overpass are unknown, not zero. Not equipment detection."
            ),
        )

    def _aoi_stats(
        self, bbox: list[float], start: date, end: date
    ) -> tuple[dict[str, Any] | None, dict[str, object]]:
        body = json.dumps(statistical_request(bbox, start, end), sort_keys=True).encode()
        cache_path = self._cache_path(body)
        if cache_path and cache_path.is_file():
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            return payload, {
                "url": redact_url(STATS_URL),
                "status": 200,
                "cache": True,
                "bbox": bbox,
            }
        token = self._access_token()
        if token is None:
            return None, {"url": redact_url(TOKEN_URL), "status": 401, "bbox": bbox}
        response = post_with_retry(
            self.transport,
            STATS_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            data=body,
            timeout=180,
            attempts=3,
            sleep=0.5,
        )
        provenance = {
            "url": redact_url(STATS_URL),
            "status": response.status,
            "bytes": len(response.body),
            "bbox": bbox,
        }
        if response.status != 200:
            return None, provenance
        try:
            payload = json.loads(response.body.decode("utf-8"))
        except json.JSONDecodeError:
            return None, provenance
        if cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(payload), encoding="utf-8")
        return payload, provenance

    def _access_token(self) -> str | None:
        if self._token:
            return self._token
        data = urlencode(
            {
                "grant_type": "client_credentials",
                "client_id": os.environ.get("COPERNICUS_CLIENT_ID", ""),
                "client_secret": os.environ.get("COPERNICUS_CLIENT_SECRET", ""),
            }
        ).encode()
        response = post_with_retry(
            self.transport,
            TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data=data,
            timeout=60,
            attempts=3,
            sleep=0.5,
        )
        if response.status != 200:
            return None
        try:
            payload = json.loads(response.body.decode("utf-8"))
        except json.JSONDecodeError:
            return None
        token = payload.get("access_token")
        if not isinstance(token, str) or not token:
            return None
        self._token = token
        return token

    def _cache_path(self, body: bytes) -> Path | None:
        if self.cache_dir is None:
            return None
        digest = hashlib.sha256(body).hexdigest()[:16]
        return self.cache_dir / f"{digest}.json"


def statistical_request(bbox: list[float], start: date, end: date) -> dict[str, Any]:
    start_stamp = f"{start.isoformat()}T00:00:00Z"
    end_stamp = f"{(end + timedelta(days=1)).isoformat()}T00:00:00Z"
    return {
        "input": {
            "bounds": {
                "bbox": bbox,
                "properties": {"crs": CRS84},
            },
            "data": [
                {
                    "type": "sentinel-1-grd",
                    "dataFilter": {
                        "timeRange": {"from": start_stamp, "to": end_stamp},
                        "acquisitionMode": ACQUISITION_MODE,
                        "polarization": "DV",
                        "orbitDirection": ORBIT_DIRECTION,
                    },
                    "processing": {
                        "orthorectify": True,
                        "backCoeff": "GAMMA0_ELLIPSOID",
                    },
                }
            ],
        },
        "aggregation": {
            "timeRange": {"from": start_stamp, "to": end_stamp},
            "aggregationInterval": {"of": "P1D"},
            "lastIntervalBehavior": "SHORTEN",
            "resx": 0.0004,
            "resy": 0.0004,
            "evalscript": EVALSCRIPT,
        },
    }


def parse_statistical_intervals(payload: dict[str, Any]) -> dict[date, float]:
    values: dict[date, float] = {}
    for item in payload.get("data") or []:
        interval = item.get("interval") or {}
        raw_from = str(interval.get("from") or "")[:10]
        if len(raw_from) < 10:
            continue
        try:
            day = date.fromisoformat(raw_from)
        except ValueError:
            continue
        outputs = ((item.get("outputs") or {}).get("default") or {}).get("bands") or {}
        band = outputs.get("B0") or next(iter(outputs.values()), None)
        if not isinstance(band, dict):
            continue
        stats = band.get("stats") or {}
        mean = stats.get("mean")
        sample = stats.get("sampleCount")
        nodata = stats.get("noDataCount")
        if mean is None:
            continue
        try:
            value = float(mean)
        except (TypeError, ValueError):
            continue
        if value != value:  # NaN
            continue
        if sample is not None and nodata is not None and float(sample) <= float(nodata):
            continue
        values[day] = value
    return values


def _mean_across_aois(days: list[date], per_aoi: list[dict[date, float]]) -> dict[date, float]:
    counts: dict[date, float] = {}
    for day in days:
        present = [series[day] for series in per_aoi if day in series]
        if present:
            counts[day] = sum(present) / len(present)
    return counts
