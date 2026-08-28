from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from tests.test_connectors import FakeTransport, _queries
from wsf.connectors.base import PullRequest
from wsf.connectors.http import HttpResponse
from wsf.connectors.sar import SarConnector, parse_statistical_intervals, statistical_request


def _request(tmp_path: Path | None = None, **overrides) -> PullRequest:
    payload = {
        "source": "sar",
        "series_id": "tempo.s1_backscatter",
        "scenario_id": "ukraine2022",
        "window_id": "incident",
        "start": date(2022, 2, 17),
        "end": date(2022, 2, 18),
        "queries": _queries(),
        "aois": [
            {"id": "capital", "bbox": [37.61, 55.745, 37.68, 55.78]},
            {"id": "airport", "bbox": [37.35, 55.94, 37.48, 56.02]},
        ],
        "max_workers": 1,
        "output_dir": tmp_path,
    }
    payload.update(overrides)
    return PullRequest(**payload)


def _stats_body(mean: float, day: str) -> bytes:
    payload = {
        "status": "OK",
        "data": [
            {
                "interval": {"from": f"{day}T00:00:00Z", "to": f"{day}T00:00:00Z"},
                "outputs": {
                    "default": {
                        "bands": {
                            "B0": {
                                "stats": {
                                    "mean": mean,
                                    "sampleCount": 100,
                                    "noDataCount": 0,
                                }
                            }
                        }
                    }
                },
            }
        ],
    }
    return json.dumps(payload).encode()


def test_parse_statistical_intervals_skips_empty_overpasses() -> None:
    payload = {
        "data": [
            {
                "interval": {"from": "2022-02-17T00:00:00Z"},
                "outputs": {
                    "default": {
                        "bands": {
                            "B0": {
                                "stats": {
                                    "mean": -12.5,
                                    "sampleCount": 80,
                                    "noDataCount": 0,
                                }
                            }
                        }
                    }
                },
            },
            {
                "interval": {"from": "2022-02-18T00:00:00Z"},
                "outputs": {
                    "default": {
                        "bands": {
                            "B0": {
                                "stats": {
                                    "mean": None,
                                    "sampleCount": 80,
                                    "noDataCount": 80,
                                }
                            }
                        }
                    }
                },
            },
        ]
    }
    parsed = parse_statistical_intervals(payload)
    assert parsed == {date(2022, 2, 17): -12.5}


def test_statistical_request_freezes_ascending_iw() -> None:
    request = statistical_request(
        [37.61, 55.745, 37.68, 55.78], date(2022, 2, 17), date(2022, 2, 18)
    )
    filt = request["input"]["data"][0]["dataFilter"]
    assert filt["acquisitionMode"] == "IW"
    assert filt["orbitDirection"] == "ASCENDING"
    assert request["aggregation"]["aggregationInterval"]["of"] == "P1D"


def test_sar_skips_without_credentials(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("COPERNICUS_CLIENT_ID", raising=False)
    monkeypatch.delenv("COPERNICUS_CLIENT_SECRET", raising=False)
    result = SarConnector(FakeTransport(lambda url: HttpResponse(url, 500, b"", {}))).pull(
        _request(tmp_path)
    )
    assert result.item["not_applicable"] is True


def test_sar_averages_aoi_means_and_marks_missing_overpasses(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("COPERNICUS_CLIENT_ID", "id")
    monkeypatch.setenv("COPERNICUS_CLIENT_SECRET", "secret")
    cache = tmp_path / "sar"

    def handler(url: str, method: str = "GET", data: bytes | None = None) -> HttpResponse:
        if "openid-connect/token" in url:
            return HttpResponse(
                url, 200, json.dumps({"access_token": "tok", "expires_in": 600}).encode(), {}
            )
        if "statistics" in url:
            body = json.loads(data.decode()) if data else {}
            bbox = body["input"]["bounds"]["bbox"]
            mean = -10.0 if bbox[0] == 37.61 else -14.0
            return HttpResponse(url, 200, _stats_body(mean, "2022-02-17"), {})
        return HttpResponse(url, 404, b"", {})

    result = SarConnector(FakeTransport(handler), cache_dir=cache).pull(_request(tmp_path))
    assert result.observations[0].quality == "ok"
    assert result.observations[0].value == -12.0
    assert result.observations[1].quality == "missing"
    assert result.observations[1].value is None
    assert "equipment" in result.item["notes"].lower() or "Not equipment" in result.item["notes"]
