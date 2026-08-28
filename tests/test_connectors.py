from __future__ import annotations

import io
import json
import zipfile
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from run_test import run_experiment
from wsf.connectors.base import PullRequest
from wsf.connectors.fred import FredConnector
from wsf.connectors.gdelt import GdeltConnector, count_talk_events
from wsf.connectors.http import HttpResponse, redact_url
from wsf.connectors.viirs import (
    TileArrays,
    ViirsConnector,
    _read_science_arrays,
    _science_group,
    lonlat_to_tile,
    viirs_extra_available,
    zonal_mean,
)
from wsf.connectors.wikipedia import WikipediaConnector
from wsf.corpus import collect_corpus
from wsf.review import review_corpus
from wsf.scenario import create_scenario, load_scenario, require_collection_ready
from wsf.time import date_range


class FakeTransport:
    def __init__(self, handler) -> None:
        self.handler = handler
        self.calls: list[str] = []

    def get(
        self, url: str, *, headers: dict[str, str] | None = None, timeout: float = 60
    ) -> HttpResponse:
        self.calls.append(url)
        return self._dispatch(url, method="GET", data=None)

    def post(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: float = 60,
        data: bytes | None = None,
    ) -> HttpResponse:
        self.calls.append(url)
        return self._dispatch(url, method="POST", data=data)

    def _dispatch(self, url: str, *, method: str, data: bytes | None) -> HttpResponse:
        try:
            return self.handler(url, method=method, data=data)
        except TypeError:
            return self.handler(url)


def _complete_scenario(project_root: Path, scenario_id: str = "ukraine2022") -> Path:
    directory = create_scenario(project_root, scenario_id)
    path = directory / "scenario.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["actors"] = {"focal": "RUS", "counterparts": ["UKR"]}
    value["incident"].update(
        {
            "start": "2022-02-17",
            "end": "2022-02-18",
            "target_start": "2022-02-24",
            "target_end": "2022-03-02",
            "selection_reason": "Two-day connector fixture window.",
        }
    )
    value["controls"][0].update(
        {
            "start": "2021-02-18",
            "end": "2021-02-19",
            "selection_reason": "Two-day control fixture window.",
        }
    )
    value["queries"].update(
        {
            "wiki_titles": ["Russia", "Ukraine"],
            "cameo_actor": "RUS",
            "facility_actor": "RUS",
        }
    )
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return directory


def _queries(**overrides):
    values = {
        "wiki_titles": ["Russia", "Ukraine"],
        "cameo_actor": "RUS",
        "cameo_root_codes": ["01", "02", "04", "13"],
        "fred_series": None,
        "facility_actor": "RUS",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _request(**overrides) -> PullRequest:
    payload = {
        "source": "wikipedia",
        "series_id": "attn.wiki_pageviews",
        "scenario_id": "ukraine2022",
        "window_id": "incident",
        "start": date(2022, 2, 17),
        "end": date(2022, 2, 18),
        "queries": _queries(),
        "max_workers": 1,
    }
    payload.update(overrides)
    return PullRequest(**payload)


def _wiki_body(title: str, views: dict[str, int]) -> bytes:
    items = [
        {"article": title, "timestamp": f"{day.replace('-', '')}00", "views": count}
        for day, count in views.items()
    ]
    return json.dumps({"items": items}).encode()


def test_date_range_is_inclusive() -> None:
    days = date_range(date(2022, 2, 17), date(2022, 2, 18))
    assert days == [date(2022, 2, 17), date(2022, 2, 18)]


def test_wikipedia_sums_frozen_titles() -> None:
    def handler(url: str) -> HttpResponse:
        if "/Russia/daily/" in url:
            body = _wiki_body("Russia", {"2022-02-17": 10, "2022-02-18": 20})
            return HttpResponse(url, 200, body, {})
        if "/Ukraine/daily/" in url:
            body = _wiki_body("Ukraine", {"2022-02-17": 3, "2022-02-18": 7})
            return HttpResponse(url, 200, body, {})
        return HttpResponse(url, 404, b"", {})

    result = WikipediaConnector(FakeTransport(handler)).pull(_request())
    assert result.item["coverage"] == 1.0
    assert [item.value for item in result.observations] == [13.0, 27.0]
    lag = result.observations[0].available_at.date() - result.observations[0].event_time.date()
    assert lag == timedelta(days=1)


def test_wikipedia_failed_title_makes_aggregate_missing() -> None:
    def handler(url: str) -> HttpResponse:
        if "/Russia/daily/" in url:
            body = _wiki_body("Russia", {"2022-02-17": 10, "2022-02-18": 20})
            return HttpResponse(url, 200, body, {})
        return HttpResponse(url, 404, b"missing", {})

    result = WikipediaConnector(FakeTransport(handler)).pull(_request())
    assert result.item["coverage"] == 0.0
    assert all(item.quality == "missing" for item in result.observations)


def test_fred_null_series_is_not_applicable() -> None:
    result = FredConnector(FakeTransport(lambda url: HttpResponse(url, 500, b"", {}))).pull(
        _request(source="alfred", series_id="dyad.fx")
    )
    assert result.item["not_applicable"] is True
    assert result.item["coverage"] == 1.0
    assert result.requests == []


def test_fred_uses_alfred_vintages_and_redacts_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRED_API_KEY", "secret-token")

    def handler(url: str) -> HttpResponse:
        body = {
            "observations": [
                {
                    "realtime_start": "2022-02-17",
                    "realtime_end": "2022-02-18",
                    "date": "2022-02-17",
                    "value": "1.10",
                },
                {
                    "realtime_start": "2022-02-18",
                    "realtime_end": "9999-12-31",
                    "date": "2022-02-17",
                    "value": "1.11",
                },
                {
                    "realtime_start": "2022-02-18",
                    "realtime_end": "9999-12-31",
                    "date": "2022-02-18",
                    "value": ".",
                },
            ]
        }
        return HttpResponse(url, 200, json.dumps(body).encode(), {})

    transport = FakeTransport(handler)
    result = FredConnector(transport).pull(
        _request(source="alfred", series_id="dyad.fx", queries=_queries(fred_series="DEXUSEU"))
    )
    assert "secret-token" not in result.requests[0]["url"]
    assert "REDACTED" in result.requests[0]["url"]
    assert result.observations[0].value == pytest.approx(1.11)
    assert result.observations[1].quality == "missing"
    assert redact_url("https://api.stlouisfed.org/fred?api_key=secret-token") == (
        "https://api.stlouisfed.org/fred?api_key=REDACTED"
    )


def _gdelt_row(actor: str, root: str) -> str:
    columns = [""] * 61
    columns[7] = actor
    columns[28] = root
    return "\t".join(columns)


def _gdelt_zip(rows: list[str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("export.CSV", "\n".join(rows) + "\n")
    return buffer.getvalue()


def test_gdelt_counts_talk_events_from_export_zip() -> None:
    payload = _gdelt_zip(
        [
            _gdelt_row("RUS", "01"),
            _gdelt_row("RUS", "04"),
            _gdelt_row("UKR", "01"),
            _gdelt_row("RUS", "19"),
        ]
    )
    count = count_talk_events(payload, "RUS", {"01", "02", "04", "13"})
    assert count == 2


def test_gdelt_harvests_daily_counts_and_caches(tmp_path: Path) -> None:
    zip_bytes = _gdelt_zip([_gdelt_row("RUS", "01"), _gdelt_row("RUS", "02")])

    def handler(url: str) -> HttpResponse:
        if url.endswith(".export.CSV.zip"):
            return HttpResponse(url, 200, zip_bytes, {})
        return HttpResponse(url, 404, b"", {})

    transport = FakeTransport(handler)
    connector = GdeltConnector(transport, cache_dir=tmp_path)
    first = connector.pull(_request(source="gdelt", series_id="talk.gdelt_cameo"))
    assert first.item["coverage"] == 1.0
    assert first.observations[0].value == 2.0 * 96
    second = connector.pull(_request(source="gdelt", series_id="talk.gdelt_cameo"))
    assert second.observations[0].value == first.observations[0].value
    assert len(second.requests) == 0


def test_viirs_requires_two_valid_aois() -> None:
    bbox = [37.60, 55.74, 37.63, 55.76]
    arrays = TileArrays(
        ntl=[[10.0, 10.0], [10.0, -999.9]],
        quality=[[0, 0], [0, 0]],
        cloud=[[0, 0], [0, 192]],
        lat=[[55.75, 55.75], [55.75, 55.75]],
        lon=[[37.61, 37.61], [37.61, 37.61]],
        tile_id="h21v03",
    )
    assert zonal_mean(arrays, bbox) == pytest.approx(10.0)
    assert lonlat_to_tile(37.61, 55.75) == (21, 3)

    class Backend:
        def read_tile(self, day, tile_id, requested_bbox, cache_dir):
            return arrays

    connector = ViirsConnector(cache_dir=Path("."), backend=Backend())
    one_aoi = connector.pull(
        _request(
            source="viirs",
            series_id="tempo.viirs_aoi",
            aois=[{"id": "RUS-capital", "bbox": bbox}],
        )
    )
    assert one_aoi.observations[0].quality == "missing"

    two_aois = connector.pull(
        _request(
            source="viirs",
            series_id="tempo.viirs_aoi",
            aois=[
                {"id": "RUS-capital", "bbox": bbox},
                {"id": "RUS-airport", "bbox": bbox},
            ],
        )
    )
    assert two_aois.item["coverage"] == 1.0
    assert two_aois.observations[0].value == pytest.approx(10.0)


def test_viirs_extracts_from_cached_collection2_granule() -> None:
    if not viirs_extra_available():
        pytest.skip("viirs extra not installed")
    granules = sorted(Path("data/raw/viirs").glob("VNP46A2.A2021050.h21v03*.h5"))
    if not granules:
        pytest.skip("no cached VNP46A2 control-week granule")
    import h5py

    with h5py.File(granules[0], "r") as handle:
        ntl, quality, cloud, lat, lon = _read_science_arrays(handle, 21, 3)
    arrays = TileArrays(
        ntl=ntl,
        quality=quality,
        cloud=cloud,
        lat=lat,
        lon=lon,
        tile_id="h21v03",
    )
    mean = zonal_mean(arrays, [37.60, 55.74, 37.63, 55.76])
    assert mean is not None and mean > 0


def test_viirs_reads_collection2_hdfeos_grid_path() -> None:
    fields = {"DNB_BRDF-Corrected_NTL": [[1.0]]}
    handle = {
        "HDFEOS": {
            "GRIDS": {
                "VIIRS_Grid_DNB_2d": {"Data Fields": fields},
                "VNP_Grid_DNB": {"Data Fields": {"wrong": True}},
            }
        }
    }
    assert _science_group(handle) is fields


def test_live_collect_writes_observation_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("EARTHDATA_TOKEN", raising=False)
    _complete_scenario(tmp_path)
    path = tmp_path / "scenarios" / "ukraine2022" / "scenario.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    for source in value["sources"]:
        if source not in {"wikipedia", "alfred"}:
            value["sources"][source]["enabled"] = False
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def handler(url: str) -> HttpResponse:
        if "wikimedia.org" in url:
            title = "Russia" if "/Russia/daily/" in url else "Ukraine"
            return HttpResponse(
                url,
                200,
                _wiki_body(
                    title,
                    {"2022-02-17": 4, "2022-02-18": 5, "2021-02-18": 1, "2021-02-19": 1},
                ),
                {},
            )
        return HttpResponse(url, 404, b"", {})

    from wsf.connectors import default_connectors

    connectors = default_connectors(tmp_path, transport=FakeTransport(handler))
    directory, manifest = collect_corpus(
        tmp_path, "ukraine2022", mock=False, connectors=connectors
    )
    assert manifest["mode"] == "live_harvest"
    wiki_items = [item for item in manifest["items"] if item["source"] == "wikipedia"]
    assert wiki_items
    assert (directory / wiki_items[0]["observations"]).is_file()
    alfred = [item for item in manifest["items"] if item["source"] == "alfred"]
    assert alfred[0]["not_applicable"] is True


def test_partial_source_selection_is_a_review_no_go(tmp_path: Path) -> None:
    _complete_scenario(tmp_path)
    collect_corpus(tmp_path, "ukraine2022", mock=True, only=["wikipedia"])
    _, review = review_corpus(tmp_path, "ukraine2022", mock_model=True)
    assert review["decision"] == "no_go"
    gaps = review["deterministic"]["gaps"]
    assert any(gap["gap_id"].startswith("missing_source") for gap in gaps)


def test_live_preflight_blocks_viirs_without_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("EARTHDATA_TOKEN", raising=False)
    _complete_scenario(tmp_path)
    with pytest.raises(ValueError, match="VIIRS|EARTHDATA|viirs"):
        collect_corpus(tmp_path, "ukraine2022", mock=False)


def test_experiment_harness_still_defaults_to_rehearsal(tmp_path: Path) -> None:
    _complete_scenario(tmp_path)
    _, summary = run_experiment(
        scenario_id="ukraine2022",
        through="review",
        run_id="experiment-connectors",
        mock=True,
        project_root=tmp_path,
    )
    assert summary["mode"] == "synthetic_rehearsal"
    require_collection_ready(load_scenario(tmp_path, "ukraine2022"))
