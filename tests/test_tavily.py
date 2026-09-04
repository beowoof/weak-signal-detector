from datetime import date

from wsf.connectors.http import HttpResponse
from wsf.connectors.tavily import search_open_source, search_queries
from wsf.notice import CollectionPosture, Notice, NoticeTrigger


class FakeTransport:
    def __init__(self, payload: dict, status: int = 200) -> None:
        import json

        self.payload = payload
        self.status = status
        self.calls: list[dict] = []
        self._json = json

    def get(self, url, **kwargs):
        raise AssertionError("search uses POST")

    def post(self, url, *, headers=None, timeout=60, data=None):
        self.calls.append({"url": url, "data": data})
        return HttpResponse(
            url=url,
            status=self.status,
            body=self._json.dumps(self.payload).encode(),
            headers={},
        )


def test_drops_undated_after_cutoff_and_forbidden() -> None:
    transport = FakeTransport(
        {
            "results": [
                {
                    "title": "Contemporaneous report",
                    "url": "https://example.com/a",
                    "content": "exercises near the border",
                    "published_date": "2022-02-11",
                },
                {
                    "title": "No date",
                    "url": "https://example.com/b",
                    "content": "something",
                    "published_date": None,
                },
                {
                    "title": "FCDO leave advice",
                    "url": "https://www.gov.uk/government/news/british-nationals-advised-to-leave-ukraine",
                    "content": "British nationals advised to leave",
                    "published_date": None,
                },
                {
                    "title": "Later retrospective",
                    "url": "https://example.com/c",
                    "content": "overview",
                    "published_date": "2022-03-01",
                },
                {
                    "title": "Leak",
                    "url": "https://example.com/d",
                    "content": "full-scale invasion narrative",
                    "published_date": "2022-02-10",
                },
                {
                    "title": "Current FCDO page",
                    "url": "https://www.gov.uk/foreign-travel-advice/ukraine",
                    "content": "Still current at: 3 September 2026. Updated: 14 August 2026.",
                    "published_date": None,
                },
                {
                    "title": "State briefing",
                    "url": "https://2021-2025.state.gov/briefings/department-press-briefing-february-25-2022",
                    "content": "Press briefing",
                    "published_date": None,
                },
            ]
        }
    )
    result = search_open_source(
        "Russia Ukraine military exercises February 2022",
        start=date(2022, 1, 13),
        cutoff=date(2022, 2, 12),
        api_key="test",
        transport=transport,
        forbidden=["full-scale invasion"],
    )
    kept_urls = [hit["url"] for hit in result["kept"]]
    assert "https://example.com/a" in kept_urls
    assert any("gov.uk" in url for url in kept_urls)
    reasons = {row["url"]: row["reason"] for row in result["dropped"]}
    assert reasons["https://example.com/b"] == "undated"
    assert reasons["https://example.com/c"] == "after_cutoff"
    assert reasons["https://example.com/d"] == "forbidden_term"


def test_query_with_forbidden_term_is_not_sent() -> None:
    transport = FakeTransport({"results": []})
    result = search_open_source(
        "full-scale invasion of Ukraine",
        start=date(2022, 1, 13),
        cutoff=date(2022, 2, 12),
        api_key="test",
        transport=transport,
        forbidden=["full-scale invasion"],
    )
    assert transport.calls == []
    assert result["kept"] == []
    assert result["dropped"][0]["reason"] == "query_contains_forbidden_term"


def test_search_queries_are_contemporaneous() -> None:
    trigger = NoticeTrigger.model_validate(
        {
            "scenario_id": "desk-case",
            "window_id": "incident",
            "collection_id": "c",
            "measurement_id": "m",
            "policy_id": "coupling_k3_z15_p3",
            "policy_params": {"threshold_z": 1.5},
            "created_at": "2026-09-03T00:00:00Z",
            "start": "2022-02-10",
            "end": "2022-02-12",
            "duration_days": 3,
            "days_before_window_end": 11,
            "contributing_domains": ["information"],
            "contributing_series": ["talk.gdelt_cameo"],
            "observed": {},
            "derived": {},
            "heuristic": {},
            "unknowns": [],
            "imaging_status_by_day": {},
            "recommended_posture": CollectionPosture.focused,
            "recommended_posture_reason": "test",
        }
    )
    notice = Notice(notice_id="notice-abc", trigger=trigger)
    from pathlib import Path

    queries = search_queries(notice, Path("."))
    blob = " ".join(item["query"] for item in queries).lower()
    assert "invasion" not in blob
    assert "february 2022" in blob or "2022" in blob
