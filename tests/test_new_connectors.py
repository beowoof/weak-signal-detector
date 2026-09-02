from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from wsf.connectors.base import PullRequest
from wsf.connectors.cbr import CbrConnector
from wsf.connectors.gazette_cadence import GazetteCadenceConnector
from wsf.connectors.http import HttpTransport
from wsf.connectors.navarea import NavareaConnector
from wsf.connectors.notam import NotamConnector


class DummyQueries:
    cameo_actor = "RUS"
    facility_actor = "RUS"


class MockTransport(HttpTransport):
    def get(self, url: str, headers: dict[str, str] | None = None) -> bytes:
        return b"<xml>dummy</xml>"

    def get_json(self, url: str, headers: dict[str, str] | None = None) -> Any:
        return {"data": []}


def test_gazette_cadence_connector():
    transport = MockTransport()
    conn = GazetteCadenceConnector(transport)
    req = PullRequest(
        source="gazette_cadence",
        series_id="official.gazette_cadence",
        scenario_id="ukraine2022",
        window_id="incident",
        start=date(2022, 2, 1),
        end=date(2022, 2, 5),
        queries=DummyQueries(),
        retrieved_at=datetime(2022, 2, 6, tzinfo=timezone.utc),
    )
    res = conn.pull(req)
    assert res.item["source"] == "gazette_cadence"
    assert res.item["series_id"] == "official.gazette_cadence"
    assert len(res.observations) == 5
    assert all(ob.quality == "ok" for ob in res.observations)


def test_navarea_connector():
    transport = MockTransport()
    conn = NavareaConnector(transport)
    req = PullRequest(
        source="navarea",
        series_id="nav.spatial_warnings",
        scenario_id="ukraine2022",
        window_id="incident",
        start=date(2022, 2, 1),
        end=date(2022, 2, 5),
        queries=DummyQueries(),
        retrieved_at=datetime(2022, 2, 6, tzinfo=timezone.utc),
    )
    res = conn.pull(req)
    assert res.item["source"] == "navarea"
    assert res.item["series_id"] == "nav.spatial_warnings"
    assert len(res.observations) == 5


def test_notam_connector():
    transport = MockTransport()
    conn = NotamConnector(transport)
    req = PullRequest(
        source="notam",
        series_id="air.notam_restrictions",
        scenario_id="ukraine2022",
        window_id="incident",
        start=date(2022, 2, 1),
        end=date(2022, 2, 5),
        queries=DummyQueries(),
        retrieved_at=datetime(2022, 2, 6, tzinfo=timezone.utc),
    )
    res = conn.pull(req)
    assert res.item["source"] == "notam"
    assert res.item["series_id"] == "air.notam_restrictions"
    assert len(res.observations) == 5


def test_cbr_connector():
    transport = MockTransport()
    conn = CbrConnector(transport)
    # Weekday range (2022-02-01 is Tue, 2022-02-04 is Fri)
    req = PullRequest(
        source="cbr",
        series_id="market.cbr_funding_spread",
        scenario_id="ukraine2022",
        window_id="incident",
        start=date(2022, 2, 1),
        end=date(2022, 2, 4),
        queries=DummyQueries(),
        retrieved_at=datetime(2022, 2, 6, tzinfo=timezone.utc),
    )
    res = conn.pull(req)
    assert res.item["source"] == "cbr"
    assert res.item["series_id"] == "market.cbr_funding_spread"
    assert len(res.observations) == 4
    assert all(ob.quality == "ok" for ob in res.observations)
