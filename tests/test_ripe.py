from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from tests.test_connectors import FakeTransport, _queries
from wsf.connectors.base import PullRequest
from wsf.connectors.http import HttpResponse
from wsf.connectors.ripe import RipeConnector, daily_prefix_counts, fill_days


def test_prefix_count_points_are_carried_forward() -> None:
    payload = {
        "data": {
            "ipv4": [
                {"timestamp": "2022-02-03T00:00:00", "prefixes": 100},
                {"timestamp": "2022-02-09T00:00:00", "prefixes": 110},
            ],
            "ipv6": [
                {"timestamp": "2022-02-03T00:00:00", "prefixes": 5},
            ],
        }
    }
    points = daily_prefix_counts(payload)
    assert points[date(2022, 2, 3)] == 105.0
    days = [date(2022, 2, d) for d in range(3, 12)]
    filled = fill_days(days, points)
    assert filled[date(2022, 2, 3)] == 105.0
    assert filled[date(2022, 2, 8)] == 105.0
    assert filled[date(2022, 2, 9)] == 110.0


def test_ripe_uses_prefix_count_not_announced_list(tmp_path: Path) -> None:
    body = {
        "data": {
            "ipv4": [{"timestamp": "2022-02-17T00:00:00", "prefixes": 50}],
            "ipv6": [{"timestamp": "2022-02-17T00:00:00", "prefixes": 2}],
        }
    }

    def handler(url: str) -> HttpResponse:
        assert "prefix-count" in url
        assert "announced-prefixes" not in url
        return HttpResponse(url, 200, json.dumps(body).encode(), {})

    result = RipeConnector(FakeTransport(handler), cache_dir=tmp_path).pull(
        PullRequest(
            source="ripe",
            series_id="net.ripe_prefixes",
            scenario_id="ukraine2022",
            window_id="incident",
            start=date(2022, 2, 17),
            end=date(2022, 2, 18),
            queries=_queries(),
            max_workers=1,
        )
    )
    assert result.observations[0].value == 52.0 * 3  # three frozen RUS ASNs
    assert result.observations[0].quality == "ok"
