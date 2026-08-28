from __future__ import annotations

from types import SimpleNamespace

from wsf.connectors.base import PullRequest
from wsf.connectors.fred import FredConnector


class BrentConnector:
    source = "brent"

    def __init__(self, transport) -> None:
        self.inner = FredConnector(transport)

    def pull(self, request: PullRequest):
        queries = SimpleNamespace(**{**vars(request.queries), "fred_series": "DCOILBRENTEU"})
        patched = PullRequest(
            source=self.source,
            series_id=request.series_id,
            scenario_id=request.scenario_id,
            window_id=request.window_id,
            start=request.start,
            end=request.end,
            queries=queries,
            retrieved_at=request.retrieved_at,
            progress=request.progress,
        )
        result = self.inner.pull(patched)
        result.item["source"] = self.source
        result.item["item_id"] = f"{self.source}:{request.window_id}"
        if not result.item.get("notes"):
            result.item["notes"] = "ALFRED DCOILBRENTEU daily Brent; free with FRED_API_KEY."
        return result
