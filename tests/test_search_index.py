import json

import pytest

from wsf.search_index import SearchIndex, SearchIndexBusy


def request(query="Russia   Ukraine February 2022"):
    return {
        "query": query,
        "max_results": 4,
        "topic": "general",
        "search_depth": "basic",
        "include_answer": False,
        "start_date": "2022-01-11",
        "end_date": "2022-02-12",
    }


def test_search_index_normalises_queries_and_verifies_content(tmp_path):
    index = SearchIndex(tmp_path)
    calls = []

    def fetch():
        calls.append(True)
        return [{"url": "https://example.com/report", "title": "Report", "content": "Lead"}]

    first, cached = index.fetch(request(), fetch)
    assert cached is False
    second, cached = index.fetch(request("  RUSSIA ukraine  february 2022  "), fetch)
    assert cached is True
    assert second == first
    assert len(calls) == 1
    records = list((index.root / "requests").glob("*.json"))
    objects = list((index.root / "objects").glob("*.json"))
    assert len(records) == len(objects) == 1
    assert json.loads(records[0].read_text())["result_count"] == 1


def test_corrupt_index_is_rejected_without_spending_another_call(tmp_path):
    index = SearchIndex(tmp_path)
    index.fetch(request(), lambda: [{"url": "https://example.com"}])
    object_path = next((index.root / "objects").glob("*.json"))
    object_path.write_text('{"results":[]}')
    called = False

    def forbidden():
        nonlocal called
        called = True
        return []

    with pytest.raises(ValueError, match="checksum"):
        index.fetch(request(), forbidden)
    assert called is False


def test_inflight_identical_search_is_not_duplicated(tmp_path):
    index = SearchIndex(tmp_path)
    _, lock_path = index._paths(request())
    lock_path.parent.mkdir(parents=True)
    lock_path.write_text("running")
    with pytest.raises(SearchIndexBusy, match="already in progress"):
        index.fetch(request(), lambda: pytest.fail("must not duplicate a search"))
