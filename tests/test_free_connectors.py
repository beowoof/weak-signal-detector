from __future__ import annotations

import json
from datetime import date

from tests.test_connectors import FakeTransport, _queries
from wsf.connectors.base import PullRequest
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

    result = FirmsConnector(FakeTransport(handler)).pull(
        _request(
            source="firms",
            series_id="tempo.firms_thermal",
            aois=[{"id": "capital", "bbox": [37.61, 55.745, 37.68, 55.78]}],
        )
    )
    assert result.observations[0].value == 1.0
    assert "NOAA-20" in result.item["notes"]


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
