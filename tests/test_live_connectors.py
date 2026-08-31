from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from wsf.connectors.base import PullRequest
from wsf.connectors.ctlogs import CtConnector
from wsf.connectors.firms import FirmsConnector
from wsf.connectors.http import UrllibTransport
from wsf.connectors.wikipedia import WikipediaConnector
from wsf.corpus import load_actor_aois
from wsf.env import load_project_env

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.live
def test_wikipedia_live_pageviews_for_one_title() -> None:
    connector = WikipediaConnector(UrllibTransport())
    result = connector.pull(
        PullRequest(
            source="wikipedia",
            series_id="attn.wiki_pageviews",
            scenario_id="live-smoke",
            window_id="incident",
            start=date(2022, 2, 17),
            end=date(2022, 2, 17),
            queries=SimpleNamespace(wiki_titles=["Russia"]),
        )
    )
    assert result.requests[0]["status"] == 200
    assert result.observations[0].quality in {"ok", "missing"}
    if result.observations[0].quality == "ok":
        assert result.observations[0].value is not None
        assert result.observations[0].value > 0


@pytest.mark.live
def test_firms_live_one_day_does_not_turn_http_failure_into_zero() -> None:
    load_project_env(PROJECT_ROOT)
    if not os.environ.get("FIRMS_MAP_KEY"):
        pytest.skip("FIRMS_MAP_KEY missing")
    aois, _ = load_actor_aois(PROJECT_ROOT, "RUS")
    result = FirmsConnector(UrllibTransport()).pull(
        PullRequest(
            source="firms",
            series_id="tempo.firms_thermal",
            scenario_id="live-smoke",
            window_id="incident",
            start=date(2022, 2, 12),
            end=date(2022, 2, 12),
            queries=SimpleNamespace(),
            aois=aois,
        )
    )
    obs = result.observations[0]
    assert obs.quality in {"ok", "source_down"}
    if obs.quality == "ok":
        assert obs.value is not None
        assert obs.value >= 0
    else:
        assert obs.value is None
    assert all("REDACTED" in str(item.get("url")) for item in result.requests)


@pytest.mark.live
def test_ct_live_one_day_does_not_record_502_as_zero() -> None:
    result = CtConnector(UrllibTransport()).pull(
        PullRequest(
            source="ct",
            series_id="official.ct_certs",
            scenario_id="live-smoke",
            window_id="incident",
            start=date(2022, 2, 12),
            end=date(2022, 2, 12),
            queries=SimpleNamespace(facility_actor="RUS", cameo_actor="RUS"),
        )
    )
    obs = result.observations[0]
    assert obs.quality in {"ok", "source_down"}
    if obs.quality == "source_down":
        assert obs.value is None
    else:
        assert obs.value is not None
        assert obs.value >= 0
