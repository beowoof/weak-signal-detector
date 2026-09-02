from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from wsf.connectors.base import PullRequest
from wsf.connectors.cbr import CbrConnector
from wsf.connectors.gazette_cadence import GazetteCadenceConnector
from wsf.connectors.http import HttpResponse, HttpTransport
from wsf.connectors.navarea import NavareaConnector
from wsf.connectors.notam import NotamConnector


class RecordingMockTransport(HttpTransport):
    def __init__(self, responses: dict[str, HttpResponse] | None = None, default_response: HttpResponse | None = None) -> None:
        self.calls: list[tuple[str, str, dict[str, str] | None, bytes | None]] = []
        self.responses = responses or {}
        self.default_response = default_response or HttpResponse(url="mock://default", status=200, body=b"{}", headers={})

    def get(self, url: str, *, headers: dict[str, str] | None = None, timeout: float = 60) -> HttpResponse:
        self.calls.append(("GET", url, headers, None))
        for pattern, resp in self.responses.items():
            if pattern in url:
                return resp
        return self.default_response

    def post(self, url: str, *, headers: dict[str, str] | None = None, timeout: float = 60, data: bytes | None = None) -> HttpResponse:
        self.calls.append(("POST", url, headers, data))
        soap_action = (headers or {}).get("SOAPAction", "")
        for pattern, resp in self.responses.items():
            if pattern in soap_action or pattern in url:
                return resp
        return self.default_response


def test_gazette_cadence_connector_usa():
    fr_body = b'{"2022-02-01": {"count": 12}, "2022-02-02": {"count": 25}}'
    transport = RecordingMockTransport(
        responses={"federalregister.gov": HttpResponse(url="https://fr.gov", status=200, body=fr_body, headers={})}
    )
    conn = GazetteCadenceConnector(transport)
    req = PullRequest(
        source="gazette_cadence",
        series_id="official.gazette_cadence",
        scenario_id="usachn2018trade",
        window_id="incident",
        start=date(2022, 2, 1),
        end=date(2022, 2, 3),
        queries=SimpleNamespace(cameo_actor="USA", facility_actor="USA"),
        retrieved_at=datetime(2022, 2, 4, tzinfo=timezone.utc),
    )
    res = conn.pull(req)
    assert any("federalregister.gov" in call[1] for call in transport.calls)
    assert res.item["source"] == "gazette_cadence"
    assert len(res.observations) == 3
    obs_by_date = {ob.event_time.date(): ob for ob in res.observations}
    assert obs_by_date[date(2022, 2, 1)].value == 12.0
    assert obs_by_date[date(2022, 2, 2)].value == 25.0
    assert obs_by_date[date(2022, 2, 3)].value == 0.0
    assert all(ob.quality == "ok" for ob in res.observations)


def test_gazette_cadence_connector_deu_pagination():
    page1 = b'{"results": [{"date": "2018-06-15T00:00:00"}], "next": "https://api.offenegesetze.de/v1/veroeffentlichung/?page=2&year=2018"}'
    page2 = b'{"results": [{"date": "2018-06-12T00:00:00"}], "next": null}'
    transport = RecordingMockTransport(
        responses={
            "page=2": HttpResponse(url="https://api.offenegesetze.de/?page=2", status=200, body=page2, headers={}),
            "offenegesetze.de": HttpResponse(url="https://api.offenegesetze.de/", status=200, body=page1, headers={}),
        }
    )
    conn = GazetteCadenceConnector(transport)
    req = PullRequest(
        source="gazette_cadence",
        series_id="official.gazette_cadence",
        scenario_id="deu2018quiet",
        window_id="incident",
        start=date(2018, 6, 10),
        end=date(2018, 6, 16),
        queries=SimpleNamespace(cameo_actor="DEU", facility_actor="DEU"),
        retrieved_at=datetime(2018, 6, 17, tzinfo=timezone.utc),
    )
    res = conn.pull(req)
    # Check that pagination was followed
    assert len(transport.calls) == 2
    obs_by_date = {ob.event_time.date(): ob for ob in res.observations}
    assert obs_by_date[date(2018, 6, 15)].value == 1.0
    assert obs_by_date[date(2018, 6, 12)].value == 1.0
    assert obs_by_date[date(2018, 6, 11)].value == 0.0


def test_gazette_cadence_source_down():
    transport = RecordingMockTransport(default_response=HttpResponse(url="https://fr.gov", status=503, body=b"", headers={}))
    conn = GazetteCadenceConnector(transport)
    req = PullRequest(
        source="gazette_cadence",
        series_id="official.gazette_cadence",
        scenario_id="usachn2018trade",
        window_id="incident",
        start=date(2022, 2, 1),
        end=date(2022, 2, 3),
        queries=SimpleNamespace(cameo_actor="USA", facility_actor="USA"),
        retrieved_at=datetime(2022, 2, 4, tzinfo=timezone.utc),
    )
    res = conn.pull(req)
    assert all(ob.quality == "source_down" for ob in res.observations)
    assert res.item["coverage"] == 0.0


def test_navarea_connector():
    warn_body = b'{"broadcast-warn": [{"issueDate": "011200Z FEB 2022"}, {"issueDate": "011800Z FEB 2022"}, {"issueDate": "031400Z FEB 2022"}]}'
    transport = RecordingMockTransport(
        responses={"broadcast-warn": HttpResponse(url="https://msi.nga.mil", status=200, body=warn_body, headers={})}
    )
    conn = NavareaConnector(transport)
    req = PullRequest(
        source="navarea",
        series_id="nav.spatial_warnings",
        scenario_id="ukraine2022",
        window_id="incident",
        start=date(2022, 2, 1),
        end=date(2022, 2, 3),
        queries=SimpleNamespace(cameo_actor="RUS", facility_actor="RUS"),
        retrieved_at=datetime(2022, 2, 4, tzinfo=timezone.utc),
    )
    res = conn.pull(req)
    assert any("broadcast-warn" in call[1] for call in transport.calls)
    obs_by_date = {ob.event_time.date(): ob for ob in res.observations}
    # 2 warnings on 2022-02-01 across 2 queried areas (HYDROLANT 'A' and HYDROARC 'C') = 4.0
    assert obs_by_date[date(2022, 2, 1)].value == 4.0
    assert obs_by_date[date(2022, 2, 2)].value == 0.0
    assert obs_by_date[date(2022, 2, 3)].value == 2.0
    assert all(ob.quality == "ok" for ob in res.observations)


def test_cbr_connector():
    ruonia_body = b"<Ruonia><ro><D0>2022-02-01T00:00:00</D0><ruo>8.13</ruo></ro><ro><D0>2022-02-02T00:00:00</D0><ruo>8.17</ruo></ro><ro><D0>2022-02-03T00:00:00</D0><ruo>8.12</ruo></ro><ro><D0>2022-02-04T00:00:00</D0><ruo>8.01</ruo></ro></Ruonia>"
    keyrate_body = b"<KeyRate><KR><DT>2022-02-01T00:00:00</DT><Rate>8.50</Rate></KR></KeyRate>"
    transport = RecordingMockTransport(
        responses={
            "RuoniaXML": HttpResponse(url="https://cbr.ru", status=200, body=ruonia_body, headers={}),
            "KeyRateXML": HttpResponse(url="https://cbr.ru", status=200, body=keyrate_body, headers={}),
        }
    )
    conn = CbrConnector(transport)
    # Weekdays: 2022-02-01 (Tue) .. 2022-02-04 (Fri)
    req = PullRequest(
        source="cbr",
        series_id="market.cbr_funding_spread",
        scenario_id="ukraine2022",
        window_id="incident",
        start=date(2022, 2, 1),
        end=date(2022, 2, 4),
        queries=SimpleNamespace(cameo_actor="RUS", facility_actor="RUS"),
        retrieved_at=datetime(2022, 2, 5, tzinfo=timezone.utc),
    )
    res = conn.pull(req)
    assert any("RuoniaXML" in (call[2] or {}).get("SOAPAction", "") for call in transport.calls)
    assert any("KeyRateXML" in (call[2] or {}).get("SOAPAction", "") for call in transport.calls)
    obs_by_date = {ob.event_time.date(): ob for ob in res.observations}
    # Spread on 2022-02-01: (8.13 - 8.50) * 100 = -37.0 bps
    assert pytest.approx(obs_by_date[date(2022, 2, 1)].value, 0.01) == -37.0
    assert pytest.approx(obs_by_date[date(2022, 2, 4)].value, 0.01) == -49.0
    assert all(ob.quality == "ok" for ob in res.observations)


def test_notam_connector():
    transport = RecordingMockTransport()
    conn = NotamConnector(transport)
    req = PullRequest(
        source="notam",
        series_id="air.notam_restrictions",
        scenario_id="ukraine2022",
        window_id="incident",
        start=date(2022, 2, 1),
        end=date(2022, 2, 5),
        queries=SimpleNamespace(cameo_actor="RUS", facility_actor="RUS"),
        retrieved_at=datetime(2022, 2, 6, tzinfo=timezone.utc),
    )
    res = conn.pull(req)
    assert res.item["source"] == "notam"
    assert len(res.observations) == 5

