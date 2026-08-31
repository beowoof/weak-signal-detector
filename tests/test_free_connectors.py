from __future__ import annotations

import json
from datetime import date

from tests.test_connectors import FakeTransport, _queries
from wsf.connectors.base import PullRequest
from wsf.connectors.ctlogs import CtConnector
from wsf.connectors.firms import FirmsConnector
from wsf.connectors.http import HttpResponse
from wsf.connectors.moex import MoexConnector
from wsf.connectors.wiki_edits import WikiEditsConnector


def _request(**overrides) -> PullRequest:
    payload = {
        "source": "moex",
        "series_id": "dyad.moex_usdrub",
        "scenario_id": "ukraine2022",
        "window_id": "incident",
        "start": date(2022, 2, 17),
        "end": date(2022, 2, 18),
        "queries": _queries(),
        "max_workers": 1,
    }
    payload.update(overrides)
    return PullRequest(**payload)


def test_firms_uses_noaa20_not_snpp(monkeypatch) -> None:
    monkeypatch.setenv("FIRMS_MAP_KEY", "test-key")
    monkeypatch.delenv("FIRMS_SENSOR", raising=False)
    csv_body = "latitude,longitude,acq_date\n55.75,37.62,2022-02-17\n"

    def handler(url: str) -> HttpResponse:
        assert "VIIRS_NOAA20_SP" in url
        assert "VIIRS_SNPP" not in url
        return HttpResponse(url, 200, csv_body.encode(), {})

    transport = FakeTransport(handler)
    result = FirmsConnector(transport).pull(
        _request(
            source="firms",
            series_id="tempo.firms_thermal",
            aois=[{"id": "capital", "bbox": [37.61, 55.745, 37.68, 55.78]}],
        )
    )
    assert result.observations[0].value == 1.0
    assert "NOAA-20" in result.item["notes"]
    assert transport.calls
    assert "/10/" not in transport.calls[0]


def test_firms_http_invalid_range_is_source_down_not_zero(monkeypatch) -> None:
    monkeypatch.setenv("FIRMS_MAP_KEY", "test-key")

    def handler(url: str) -> HttpResponse:
        assert "/10/" not in url
        return HttpResponse(url, 400, b"Invalid day range. Expects [1..5].", {})

    result = FirmsConnector(FakeTransport(handler)).pull(
        _request(
            source="firms",
            series_id="tempo.firms_thermal",
            start=date(2022, 2, 12),
            end=date(2022, 2, 12),
            aois=[{"id": "capital", "bbox": [37.61, 55.745, 37.68, 55.78]}],
        )
    )
    assert result.observations[0].quality == "source_down"
    assert result.observations[0].value is None
    assert result.item["n_source_down"] == 1
    assert result.item["coverage"] == 0.0


def test_firms_empty_200_is_observed_zero(monkeypatch) -> None:
    monkeypatch.setenv("FIRMS_MAP_KEY", "test-key")
    csv_body = (
        "latitude,longitude,acq_date\n"
    )

    def handler(url: str) -> HttpResponse:
        return HttpResponse(url, 200, csv_body.encode(), {})

    result = FirmsConnector(FakeTransport(handler)).pull(
        _request(
            source="firms",
            series_id="tempo.firms_thermal",
            start=date(2022, 2, 12),
            end=date(2022, 2, 12),
            aois=[{"id": "capital", "bbox": [37.61, 55.745, 37.68, 55.78]}],
        )
    )
    assert result.observations[0].quality == "ok"
    assert result.observations[0].value == 0.0


def test_ct_http_502_is_source_down_not_zero(monkeypatch) -> None:
    monkeypatch.setattr("wsf.connectors.http.time.sleep", lambda _seconds: None)

    def handler(url: str) -> HttpResponse:
        return HttpResponse(url, 502, b"<html>Bad Gateway</html>", {})

    result = CtConnector(FakeTransport(handler)).pull(
        _request(
            source="ct",
            series_id="official.ct_certs",
            start=date(2022, 2, 12),
            end=date(2022, 2, 12),
            queries=_queries(facility_actor="RUS"),
        )
    )
    assert result.observations[0].quality == "source_down"
    assert result.observations[0].value is None
    assert result.item["n_source_down"] == 1


def test_ct_json_200_counts_not_before_on_window_day() -> None:
    body = [
        {
            "not_before": "2022-02-12T00:00:00",
            "common_name": "letters.kremlin.ru",
        },
        {
            "not_before": "2022-02-11T00:00:00",
            "common_name": "ignored.kremlin.ru",
        },
    ]

    def handler(url: str) -> HttpResponse:
        if "kremlin.ru" in url:
            return HttpResponse(url, 200, json.dumps(body).encode(), {})
        return HttpResponse(url, 200, b"[]", {})

    result = CtConnector(FakeTransport(handler)).pull(
        _request(
            source="ct",
            series_id="official.ct_certs",
            start=date(2022, 2, 12),
            end=date(2022, 2, 12),
            queries=_queries(facility_actor="RUS"),
        )
    )
    assert result.observations[0].quality == "ok"
    assert result.observations[0].value == 1.0


def test_moex_parses_usdrub_close() -> None:
    body = {
        "history": {
            "columns": ["TRADEDATE", "CLOSE"],
            "data": [["2022-02-17", 77.1], ["2022-02-18", 77.4]],
        }
    }

    def handler(url: str) -> HttpResponse:
        return HttpResponse(url, 200, json.dumps(body).encode(), {})

    result = MoexConnector(FakeTransport(handler)).pull(_request())
    assert result.observations[0].value == 77.1
    assert result.observations[0].quality == "ok"


def test_moex_coverage_uses_weekdays_not_calendar_days() -> None:
    body = {
        "history": {
            "columns": ["TRADEDATE", "CLOSE"],
            "data": [["2022-02-18", 77.4], ["2022-02-21", 79.8]],
        }
    }

    def handler(url: str) -> HttpResponse:
        return HttpResponse(url, 200, json.dumps(body).encode(), {})

    result = MoexConnector(FakeTransport(handler)).pull(
        _request(start=date(2022, 2, 18), end=date(2022, 2, 21))
    )
    assert result.item["n_expected"] == 2
    assert result.item["coverage"] == 1.0


def test_moex_exchange_holidays_do_not_fail_coverage() -> None:
    body = {
        "history": {
            "columns": ["TRADEDATE", "CLOSE"],
            "data": [["2020-03-06", 66.1], ["2020-03-10", 67.2]],
        }
    }

    def handler(url: str) -> HttpResponse:
        return HttpResponse(url, 200, json.dumps(body).encode(), {})

    result = MoexConnector(FakeTransport(handler)).pull(
        _request(start=date(2020, 3, 6), end=date(2020, 3, 10))
    )
    weekday_missing = [
        item
        for item in result.observations
        if item.quality == "missing" and item.event_time.weekday() < 5
    ]
    assert [item.event_time.date().isoformat() for item in weekday_missing] == [
        "2020-03-09"
    ]
    assert result.item["coverage"] == 1.0
    assert result.item["n_ok"] == 2


def test_moex_http_error_is_source_down_not_zero() -> None:
    def handler(url: str) -> HttpResponse:
        return HttpResponse(url, 504, b"", {})

    result = MoexConnector(FakeTransport(handler)).pull(_request())
    assert result.item["n_source_down"] == 2
    assert result.item["coverage"] == 0.0
    assert all(item.quality == "source_down" for item in result.observations)


def test_wiki_edits_bins_revision_timestamps() -> None:
    body = {
        "query": {
            "pages": {
                "1": {
                    "revisions": [
                        {"timestamp": "2022-02-17T10:00:00Z"},
                        {"timestamp": "2022-02-17T18:00:00Z"},
                        {"timestamp": "2022-02-18T01:00:00Z"},
                    ]
                }
            }
        }
    }

    def handler(url: str) -> HttpResponse:
        return HttpResponse(url, 200, json.dumps(body).encode(), {})

    result = WikiEditsConnector(FakeTransport(handler)).pull(
        _request(
            source="wiki_edits",
            series_id="attn.wiki_edits",
            queries=_queries(wiki_titles=["Russia"]),
        )
    )
    assert result.observations[0].value == 2.0
    assert result.observations[1].value == 1.0
