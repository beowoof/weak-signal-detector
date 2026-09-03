import json
from datetime import UTC, date, datetime
from types import SimpleNamespace

from tests.test_new_connectors import RecordingMockTransport
from wsf.connectors.base import PullRequest
from wsf.connectors.declared_posture import (
    DeclaredPostureConnector,
    reconstruct_events,
    state_at_cutoff,
)
from wsf.connectors.http import HttpResponse


def _history() -> list[dict[str, str]]:
    return [
        {
            "public_timestamp": "2022-01-24T07:58:46+00:00",
            "note": (
                "Some Embassy staff and dependants are being withdrawn from Kyiv "
                "in response to growing threat from Russia."
            ),
        },
        {
            "public_timestamp": "2022-02-11T18:21:23+00:00",
            "note": (
                "The FCDO now advises against all travel to Ukraine. British nationals "
                "in Ukraine should leave now while commercial means are still available."
            ),
        },
        {
            "public_timestamp": "2022-02-24T04:52:10+00:00",
            "note": "Russia has announced the start of military operations in Ukraine.",
        },
    ]


def test_cutoff_excludes_invasion_day_notes() -> None:
    cutoff = datetime(2022, 2, 12, 23, 59, 59, tzinfo=UTC)
    events = reconstruct_events({"ukraine": _history()}, cutoff)
    assert all(event["at"] <= cutoff for event in events)
    assert not any("military operations" in event["text"] for event in events)
    snapshot = state_at_cutoff(events, cutoff)
    assert snapshot["travel_risk"].get("UKR") == 4
    assert snapshot["diplomatic_drawdown"] is True
    assert snapshot["leave_advice"] is True
    assert snapshot["threat_language"] is False


def test_connector_builds_daily_series_from_govuk(monkeypatch) -> None:
    ukraine = {
        "details": {
            "change_history": _history(),
            "alert_status": ["avoid_all_travel_to_whole_country"],
        }
    }
    russia = {"details": {"change_history": [], "alert_status": []}}
    transport = RecordingMockTransport(
        responses={
            "foreign-travel-advice/ukraine": HttpResponse(
                url="https://www.gov.uk/api/content/foreign-travel-advice/ukraine",
                status=200,
                body=json.dumps(ukraine).encode(),
                headers={},
            ),
            "foreign-travel-advice/russia": HttpResponse(
                url="https://www.gov.uk/api/content/foreign-travel-advice/russia",
                status=200,
                body=json.dumps(russia).encode(),
                headers={},
            ),
            "TravelAdvisories": HttpResponse(
                url="https://cadataapi.state.gov/api/TravelAdvisories",
                status=200,
                body=json.dumps(
                    [
                        {
                            "Title": "Ukraine - Level 4: Do Not Travel",
                            "Updated": "2026-08-27T20:00:00-04:00",
                            "Published": "2026-08-27T20:00:00-04:00",
                        }
                    ]
                ).encode(),
                headers={},
            ),
            "cdx/search/cdx": HttpResponse(
                url="https://web.archive.org/cdx/search/cdx",
                status=200,
                body=json.dumps(
                    [
                        ["timestamp", "original", "statuscode"],
                        [
                            "20220210223359",
                            "https://travel.state.gov/content/travel/en/traveladvisories/traveladvisories/ukraine-travel-advisory.html",
                            "200",
                        ],
                    ]
                ).encode(),
                headers={},
            ),
            "web.archive.org/web/": HttpResponse(
                url="https://web.archive.org/web/20220210223359id_/https://travel.state.gov/x",
                status=200,
                body=b"<h1>Ukraine - Level 4: Do Not Travel</h1>",
                headers={},
            ),
        }
    )
    cutoff = datetime(2022, 2, 12, 23, 59, 59, tzinfo=UTC)
    conn = DeclaredPostureConnector(transport)
    result = conn.pull(
        PullRequest(
            source="declared_posture",
            series_id="posture.travel_risk",
            scenario_id="ukraine2022",
            window_id="incident",
            start=date(2022, 2, 10),
            end=date(2022, 2, 12),
            queries=SimpleNamespace(
                facility_actor="RUS", cameo_actor="RUS", wiki_titles=["Ukraine", "Russia"]
            ),
            retrieved_at=cutoff,
        )
    )
    travel = [row for row in result.observations if row.series_id == "posture.travel_risk"]
    assert travel
    by_day = {row.event_time.date(): row for row in travel}
    assert by_day[date(2022, 2, 11)].value == 4.0
    assert by_day[date(2022, 2, 12)].value == 4.0
    diplomatic = [
        row for row in result.observations if row.series_id == "posture.diplomatic_posture"
    ]
    assert diplomatic[0].value == 1.0
    us_events = [event for event in conn.last_events if event["government"] == "US/State"]
    assert us_events
    assert us_events[0]["severity"] == 4
    assert us_events[0]["at"].date() == date(2022, 2, 10)
