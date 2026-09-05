"""Content-addressed, project-wide index for bounded OSINT search results."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from wsf.evidence_bundle import canonical, digest


class SearchIndexBusy(ValueError):
    """An identical query is already running and must not be duplicated."""


def normalise_request(request: dict[str, Any]) -> dict[str, Any]:
    value = dict(request)
    value["query"] = " ".join(str(value.get("query", "")).split()).casefold()
    return value


class SearchIndex:
    def __init__(self, project_root: Path):
        # `scenarios` is mounted into the API container; this index is shared by all scenarios.
        self.root = project_root / "scenarios" / ".osint_search_index"

    def request_hash(self, request: dict[str, Any]) -> str:
        return digest({"schema": "tavily_search_request_v1", **normalise_request(request)})

    def _paths(self, request: dict[str, Any]) -> tuple[Path, Path]:
        key = self.request_hash(request)
        return self.root / "requests" / f"{key}.json", self.root / "locks" / f"{key}.lock"

    def read(self, request: dict[str, Any]) -> list[dict] | None:
        index_path, _ = self._paths(request)
        if not index_path.exists():
            return None
        index = json.loads(index_path.read_text(encoding="utf-8"))
        expected_request = self.request_hash(request)
        if index.get("request_sha256") != expected_request:
            raise ValueError("Search request index checksum mismatch")
        response_hash = index.get("response_sha256")
        if not isinstance(response_hash, str):
            raise ValueError("Search request index has no response checksum")
        object_path = self.root / "objects" / f"{response_hash}.json"
        result = json.loads(object_path.read_text(encoding="utf-8"))
        rows = result.get("results")
        if not isinstance(rows, list) or digest(rows) != response_hash:
            raise ValueError("Indexed search result checksum mismatch")
        return rows

    def fetch(
        self, request: dict[str, Any], operation: Callable[[], list[dict]]
    ) -> tuple[list[dict], bool]:
        cached = self.read(request)
        if cached is not None:
            return cached, True
        index_path, lock_path = self._paths(request)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            handle = lock_path.open("x", encoding="utf-8")
        except FileExistsError as exc:
            # Do not spend a second search credit while an identical request is in flight.
            cached = self.read(request)
            if cached is not None:
                return cached, True
            raise SearchIndexBusy("Identical Tavily search already in progress") from exc
        handle.write(datetime.now(UTC).isoformat() + "\n")
        handle.close()
        try:
            cached = self.read(request)
            if cached is not None:
                return cached, True
            rows = operation()
            if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
                raise ValueError("Tavily search results must be a list of objects")
            response_hash = digest(rows)
            object_path = self.root / "objects" / f"{response_hash}.json"
            object_path.parent.mkdir(parents=True, exist_ok=True)
            object_content = (
                canonical({"schema_id": "tavily_search_results_v1", "results": rows}) + "\n"
            )
            if object_path.exists():
                if object_path.read_text(encoding="utf-8") != object_content:
                    raise ValueError("Search result object checksum collision")
            else:
                with object_path.open("x", encoding="utf-8") as output:
                    output.write(object_content)
            index_path.parent.mkdir(parents=True, exist_ok=True)
            index_record = {
                "schema_id": "tavily_search_index_v1",
                "provider": "tavily",
                "request": normalise_request(request),
                "request_sha256": self.request_hash(request),
                "response_sha256": response_hash,
                "result_count": len(rows),
                "indexed_at": datetime.now(UTC).isoformat(),
            }
            content = canonical(index_record) + "\n"
            if index_path.exists():
                existing = self.read(request)
                return existing if existing is not None else rows, True
            with index_path.open("x", encoding="utf-8") as output:
                output.write(content)
            return rows, False
        finally:
            lock_path.unlink(missing_ok=True)
