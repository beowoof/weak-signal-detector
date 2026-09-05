"""Cutoff-safe Tavily search. Results never vote in the notice."""

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timedelta
from typing import Any

from wsf.connectors.http import HttpTransport, UrllibTransport, post_with_retry
from wsf.env import load_project_env
from wsf.packet import _theatre_frame
from wsf.scenario import load_scenario
from wsf.search_index import SearchIndex, SearchIndexBusy

TAVILY_SEARCH_URL = "https://api.tavily.com/search"
MAX_QUERIES = 6
MAX_RESULTS = 6
OFFICIAL_DOMAINS = (
    "gov.uk",
    "state.gov",
    "whitehouse.gov",
    "nato.int",
    "un.org",
    "eeas.europa.eu",
)


def tavily_api_key(project_root) -> str:
    load_project_env(project_root)
    return (os.environ.get("TAVILY_API_KEY") or "").strip()


def forbidden_terms(project_root, scenario_id: str) -> list[str]:
    try:
        scenario = load_scenario(project_root, scenario_id)
    except (OSError, ValueError, FileNotFoundError):
        return []
    return [term.lower() for term in scenario.corpus_gates.forbidden_outcome_terms if term]


def _contains_forbidden(text: str, forbidden: list[str]) -> bool:
    lowered = text.lower()
    return any(term and term in lowered for term in forbidden)


def _parse_published(value: Any) -> date | None:
    if not value or not isinstance(value, str):
        return None
    text = value.strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _dates_in_text(text: str) -> list[date]:
    found: list[date] = []
    for match in re.finditer(r"\b(20\d{2})-(\d{2})-(\d{2})\b", text):
        parsed = _safe_date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        if parsed:
            found.append(parsed)
    for match in re.finditer(
        r"\b(\d{1,2})\s+(January|February|March|April|May|June|July|"
        r"August|September|October|November|December)\s+(20\d{2})\b",
        text,
        flags=re.I,
    ):
        parsed = _safe_date(
            int(match.group(3)), _MONTHS[match.group(2).lower()], int(match.group(1))
        )
        if parsed:
            found.append(parsed)
    for match in re.finditer(
        r"\b(January|February|March|April|May|June|July|August|September|"
        r"October|November|December)[-\s]+(\d{1,2}),?\s+(20\d{2})\b",
        text,
        flags=re.I,
    ):
        parsed = _safe_date(
            int(match.group(3)), _MONTHS[match.group(1).lower()], int(match.group(2))
        )
        if parsed:
            found.append(parsed)
    return found


def _date_from_url(url: str) -> date | None:
    match = re.search(r"/(20\d{2})/(\d{2})/(\d{2})(?:/|$)", url)
    if match:
        return _safe_date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    match = re.search(r"/(20\d{2})/(\d{2})(?:/|$)", url)
    if match:
        return _safe_date(int(match.group(1)), int(match.group(2)), 1)
    named = _dates_in_text(url.replace("-", " "))
    return named[-1] if named else None


def _host(url: str) -> str:
    try:
        return url.split("/")[2].lower()
    except IndexError:
        return ""


def _is_official(url: str) -> bool:
    host = _host(url)
    return any(host == domain or host.endswith("." + domain) for domain in OFFICIAL_DOMAINS)


def search_queries(notice, project_root) -> list[dict[str, str]]:
    """Contemporaneous queries. No outcome-encoded wording."""
    try:
        frame = _theatre_frame(project_root, notice.trigger.scenario_id)
    except (OSError, ValueError, FileNotFoundError):
        frame = {}
    forbidden = forbidden_terms(project_root, notice.trigger.scenario_id)
    focal = frame.get("focal_name") or "focal actor"
    others = frame.get("counterpart_names") or []
    counterpart = others[0] if others else "counterpart"
    start = notice.trigger.start
    month = start.strftime("%B %Y")
    year = str(start.year)
    planned = [
        ("official_uk", f"UK FCDO travel advice {counterpart} {year}"),
        ("official_us", f"US State Department travel advisory {counterpart} {year}"),
        ("diplomatic", f"{focal} {counterpart} embassy personnel {month}"),
        ("reporting", f"{focal} {counterpart} military exercises {month}"),
    ]
    for place in (frame.get("places") or [])[:2]:
        planned.append((f"place_{place}", f"{place} {focal} troops {month}"))
    out: list[dict[str, str]] = []
    for ident, query in planned:
        if _contains_forbidden(query, forbidden):
            continue
        out.append({"id": ident, "query": query})
        if len(out) >= MAX_QUERIES:
            break
    return out


def search_open_source(
    query: str,
    *,
    start: date,
    cutoff: date,
    api_key: str,
    transport: HttpTransport | None = None,
    forbidden: list[str] | None = None,
    max_results: int = MAX_RESULTS,
    search_index: SearchIndex | None = None,
) -> dict[str, Any]:
    """Search Tavily and keep only hits published on or before cutoff."""
    forbidden = forbidden or []
    if _contains_forbidden(query, forbidden):
        return {
            "query": query,
            "kept": [],
            "dropped": [{"reason": "query_contains_forbidden_term"}],
            "error": None,
        }
    historical = cutoff < date.today() - timedelta(days=45)
    payload = {
        "query": query,
        "search_depth": "basic",
        "topic": "general" if historical else "news",
        "max_results": max_results,
        "include_answer": False,
        "start_date": start.isoformat(),
        "end_date": cutoff.isoformat(),
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    client = transport or UrllibTransport()
    cache_hit = False

    def fetch() -> list[dict]:
        if not api_key:
            raise ValueError("TAVILY_API_KEY is not set and no indexed result exists")
        response = post_with_retry(
            client,
            TAVILY_SEARCH_URL,
            headers=headers,
            data=json.dumps(payload).encode(),
            timeout=45,
            # A search is potentially chargeable; never repeat an uncertain request silently.
            attempts=1,
        )
        if response.status >= 400:
            raise ValueError(f"tavily HTTP {response.status}")
        try:
            body = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("tavily invalid JSON") from exc
        rows = body.get("results")
        if not isinstance(rows, list):
            raise ValueError("tavily results are not a list")
        return rows

    try:
        if search_index:
            results, cache_hit = search_index.fetch(payload, fetch)
        else:
            results = fetch()
    except (OSError, ValueError, SearchIndexBusy) as exc:
        return {"query": query, "kept": [], "dropped": [], "error": str(exc)}
    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for row in results:
        title = str(row.get("title") or "")
        url = str(row.get("url") or "")
        snippet = str(row.get("content") or "")
        published = _parse_published(row.get("published_date")) or _date_from_url(url)
        blob = f"{title} {snippet} {url}"
        later = [item for item in _dates_in_text(blob) if item > cutoff]
        if later:
            dropped.append(
                {
                    "url": url,
                    "reason": "after_cutoff",
                    "published": max(later).isoformat(),
                }
            )
            continue
        unverified = False
        if published is None:
            dropped.append({"url": url, "reason": "undated"})
            continue
        if published is not None and published > cutoff:
            dropped.append(
                {"url": url, "reason": "after_cutoff", "published": published.isoformat()}
            )
            continue
        if published is not None and published < start:
            dropped.append(
                {"url": url, "reason": "before_window", "published": published.isoformat()}
            )
            continue
        if not historical and _contains_forbidden(blob, forbidden):
            dropped.append(
                {
                    "url": url,
                    "reason": "forbidden_term",
                    "published": published.isoformat() if published else None,
                }
            )
            continue
        kept.append(
            {
                "title": title,
                "url": url,
                "published": published.isoformat() if published else None,
                "date_unverified": unverified,
                "evidence_status": "lead_requires_content_version",
                "snippet": snippet[:800],
                "score": row.get("score"),
                "votes": False,
            }
        )
    return {
        "query": query,
        "kept": kept,
        "dropped": dropped,
        "error": None,
        "cache_hit": cache_hit,
    }


def harvest_searches(
    notice,
    project_root,
    *,
    start: date,
    cutoff: datetime | date,
    transport: HttpTransport | None = None,
) -> dict[str, Any]:
    cutoff_day = cutoff.date() if isinstance(cutoff, datetime) else cutoff
    key = tavily_api_key(project_root)
    forbidden = forbidden_terms(project_root, notice.trigger.scenario_id)
    queries = search_queries(notice, project_root)
    search_index = SearchIndex(project_root)
    hits: list[dict[str, Any]] = []
    dropped_n = 0
    errors: list[str] = []
    seen: set[str] = set()
    runs: list[dict[str, Any]] = []
    for item in queries:
        result = search_open_source(
            item["query"],
            start=start,
            cutoff=cutoff_day,
            api_key=key,
            transport=transport,
            forbidden=forbidden,
            search_index=search_index,
        )
        runs.append(
            {
                "id": item["id"],
                "query": item["query"],
                "n_kept": len(result["kept"]),
                "n_dropped": len(result["dropped"]),
                "error": result["error"],
                "cache_hit": result.get("cache_hit", False),
            }
        )
        if result["error"]:
            errors.append(f"{item['id']}: {result['error']}")
        dropped_n += len(result["dropped"])
        for hit in result["kept"]:
            url = hit["url"]
            if url in seen:
                continue
            seen.add(url)
            hits.append({**hit, "query_id": item["id"]})
    status = "complete" if hits or not errors else "blocked"
    if not hits and not errors:
        status = "complete"
    return {
        "status": status,
        "reason": "; ".join(errors) if errors and not hits else None,
        "queries": runs,
        "hits": hits,
        "dropped_n": dropped_n,
    }
