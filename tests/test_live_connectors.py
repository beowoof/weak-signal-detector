from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from wsf.connectors.base import PullRequest
from wsf.connectors.http import UrllibTransport
from wsf.connectors.wikipedia import WikipediaConnector


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
