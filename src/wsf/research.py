"""Bounded requirement-led public-source research with persisted request checkpoints."""

from __future__ import annotations

import gzip
import hashlib
import ipaddress
import json
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import unquote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from wsf.connectors.http import HttpResponse, HttpTransport, UrllibTransport
from wsf.connectors.tavily import (
    OFFICIAL_DOMAINS,
    TAVILY_SEARCH_URL,
    _date_from_url,
    tavily_api_key,
)
from wsf.evidence_bundle import canonical, digest, document_rejection
from wsf.packet import Packet
from wsf.search_index import SearchIndex, SearchIndexBusy


class ResearchDeferred(ValueError):
    """A request not attempted because a required runtime capability is unavailable."""


@dataclass(frozen=True)
class ResearchLimits:
    queries: int = 6
    documents: int = 6
    seconds: int = 180
    document_chars: int = 12000

    def __post_init__(self):
        if not (
            1 <= self.queries <= 12
            and 1 <= self.documents <= 48
            and 1 <= self.seconds <= 600
            and 100 <= self.document_chars <= 20000
        ):
            raise ValueError("Research limits exceed bounded desk policy")


def public_url(url: str) -> bool:
    try:
        p = urlsplit(url)
        if (
            p.scheme not in {"http", "https"}
            or p.username
            or p.password
            or p.port not in {None, 80, 443}
        ):
            return False
        host = p.hostname or ""
        if "." not in host or host.endswith((".local", ".internal", ".localhost")):
            return False
        try:
            return ipaddress.ip_address(host).is_global
        except ValueError:
            return True
    except ValueError:
        return False


PREFERRED_DOMAINS = OFFICIAL_DOMAINS + (
    "maxar.com",
    "france24.com",
    "reuters.com",
    "apnews.com",
    "bbc.co.uk",
    "bbc.com",
    "citeam.org",
    "bellingcat.com",
    "theguardian.com",
    "nytimes.com",
    "washingtonpost.com",
    "aljazeera.com",
    "dw.com",
)
SKIP_HOSTS = frozenset(
    {
        "youtube.com",
        "youtu.be",
        "facebook.com",
        "fb.com",
        "twitter.com",
        "x.com",
        "instagram.com",
        "tiktok.com",
        "reddit.com",
    }
)
SKIP_SUFFIXES = (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".zip")


def _hostname(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return host.removeprefix("www.")


def preferred_source(url: str) -> bool:
    host = _hostname(url)
    return any(host == domain or host.endswith("." + domain) for domain in PREFERRED_DOMAINS)


def _urls_equivalent(left: str, right: str) -> bool:
    def parts(url: str):
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower().removeprefix("www.")
        path = unquote(parsed.path).rstrip("/") or "/"
        return host, path, parsed.query

    try:
        return parts(left) == parts(right)
    except ValueError:
        return False


def lead_skip_reason(url: str, cutoff: datetime) -> str | None:
    if not public_url(url):
        return "not a public document URL"
    host = _hostname(url)
    if host in SKIP_HOSTS or any(host.endswith("." + item) for item in SKIP_HOSTS):
        return "Unsupported media host; remains a lead"
    path = urlsplit(url).path.lower()
    if path.endswith(SKIP_SUFFIXES):
        return "Archive document type unsupported; imagery/PDF remains a lead"
    dated = _date_from_url(url)
    if dated and dated > cutoff.date():
        return "URL date is after the knowledge cutoff"
    return None


def _actor_place_period(packet: Packet) -> tuple[str, str, str]:
    keys = list(packet.product.keys if packet.product else [])
    period = packet.clocks.knowledge_cutoff.strftime("%B %Y")
    actors = " ".join(keys[:2]) if keys else packet.scenario_id
    places = [key for key in keys[4:] if key]
    place_clause = " ".join(places[:5]) or " ".join(keys[2:4])
    return actors, place_clause, period


def _preferred_query(title: str, actors: str, places: str, period: str) -> str:
    lowered = title.lower()
    where = " ".join(part for part in (actors, places, period) if part)
    if any(
        word in lowered for word in ("physical", "imagery", "preparation", "movement", "deployment")
    ):
        return f"{where} satellite imagery troop deployment Maxar"[:400]
    if any(word in lowered for word in ("official", "government", "travel", "embassy", "posture")):
        return f"{actors} {period} FCDO travel advice State Department embassy"[:400]
    if any(word in lowered for word in ("financial", "bank", "funding")):
        return f"{actors} {period} central bank interbank funding rate"[:400]
    if any(word in lowered for word in ("information", "reporting", "statements")):
        return f"{actors} {period} official public statements"[:400]
    return f"{where} {title}"[:400]


def _fallback_query(title: str, why: str, actors: str, places: str, period: str) -> str:
    frame = " ".join(part for part in (actors, places) if part) or actors
    return f"{frame} {period} {title} {why}"[:400]


def _decode_archive_body(body: bytes, headers: dict) -> bytes:
    encoding = {k.lower(): v for k, v in headers.items()}.get("content-encoding", "").lower()
    if body.startswith(b"\x1f\x8b") or "gzip" in encoding:
        try:
            return gzip.decompress(body)
        except gzip.BadGzipFile as exc:
            raise ValueError("Archive body is compressed but not valid gzip") from exc
    return body


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Archive redirected; version not verified")


class ResearchTransport(UrllibTransport):
    def get(self, url, *, headers=None, timeout=30):
        # Fetch archive hosts only; never follow a redirect to a live or private endpoint.
        if urlsplit(url).netloc != "web.archive.org" or not url.startswith("https://"):
            raise ValueError("Only the public archive may be fetched directly")
        opener = build_opener(_NoRedirect())
        request_headers = {"Accept-Encoding": "identity", **(headers or {})}
        try:
            with opener.open(Request(url, headers=request_headers), timeout=timeout) as response:
                body = response.read(2_000_001)
                if len(body) > 2_000_000:
                    raise ValueError("Archive response exceeds 2 MB limit")
                return HttpResponse(response.url, response.status, body, dict(response.headers))
        except HTTPError as exc:
            return HttpResponse(url, exc.code, b"", {})


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self.skip += 1
        if tag in {"p", "div", "br", "li", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"}:
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def _archive_text(body: bytes, content_type: str) -> str:
    if b"\x00" in body[:1024]:
        raise ValueError("Archive document is binary; imagery/PDF remains a lead")
    try:
        decoded = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Archive document is not UTF-8 text; imagery/PDF remains a lead") from exc
    if "text/html" in content_type:
        parser = _Text()
        parser.feed(decoded)
        decoded = "".join(parser.parts)
    text = "\n".join(line.strip() for line in decoded.splitlines() if line.strip())
    if not text:
        raise ValueError("Document contains no usable text")
    return text


def research_plan(packet: Packet, limits: ResearchLimits) -> list[dict]:
    product = packet.product
    actors, places, period = _actor_place_period(packet)
    requirements = product.collection if product else []
    plan = []
    for index, requirement in enumerate(requirements):
        title = requirement.get("title", "Context")
        why = requirement.get("why", "")
        ident = "requirement-" + str(index + 1)
        plan.append(
            {
                "requirement_id": ident,
                "purpose": title,
                "query": _preferred_query(title, actors, places, period),
                "fallback_query": _fallback_query(title, why, actors, places, period),
            }
        )
    if requirements and limits.queries > 1:
        extra = [
            {
                "requirement_id": "physical-corroboration",
                "purpose": "Independent physical corroboration",
                "query": f"{actors} {places} {period} released imagery geolocated movement".strip()[
                    :400
                ],
                "fallback_query": (
                    f"{actors} {places} {period} released imagery geolocated movement reporting"
                ).strip()[:400],
            },
            {
                "requirement_id": "counterevidence",
                "purpose": "Counterevidence and alternative explanations",
                "query": f"{actors} {period} verified withdrawal exercise completion"[:400],
                "fallback_query": (
                    f"{actors} {places} {period} verified withdrawal exercise completion"
                ).strip()[:400],
            },
        ]
        # Keep at least one original requirement and reserve a counterevidence slot.
        reserved = extra if limits.queries >= 3 else extra[-1:]
        plan = plan[: limits.queries - len(reserved)] + reserved
    return plan[: limits.queries]


def _save(path: Path, value: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(canonical(value) + "\n")
    tmp.replace(path)


def collection_outcomes(state: dict, packet: Packet) -> list[dict]:
    """Account for every question; acquisition is not an analytical answer."""
    outcomes = []
    for i, entry in enumerate(state["plan"]):
        requirement = entry["requirement_id"]
        query = state["requests"].get(f"query-{i}", {})
        leads = [r for r in state["leads"] if r.get("requirement_id") == requirement]
        lead_urls = {r["url"] for r in leads}
        documents = [
            d
            for d in state["documents"]
            if d.get("requirement_id") == requirement or d.get("url") in lead_urls
        ]
        usable = [
            d
            for d in documents
            if not document_rejection(d, packet.clocks.knowledge_cutoff, packet.clocks.mode)
        ]
        attempts = []
        for url in dict.fromkeys(r["url"] for r in leads):
            request = state["requests"].get("document-" + digest(url)[:16], {})
            reason = request.get("reason")
            for document in documents:
                if document.get("url") == url:
                    reason = (
                        document_rejection(
                            document, packet.clocks.knowledge_cutoff, packet.clocks.mode
                        )
                        or reason
                    )
            if not request:
                reason = state.get("blocked") or (
                    f"Research {state['limit_reached']} budget exhausted"
                    if state.get("limit_reached")
                    else "Document not attempted"
                )
            attempts.append(
                {"url": url, "status": request.get("status", "not_attempted"), "reason": reason}
            )
        if usable:
            tiers = {d.get("source_tier") for d in usable}
            if tiers <= {"fallback"}:
                status, reason = (
                    "documents_obtained",
                    "Preferred sources unavailable; retained fallback public reporting. "
                    "Assess whether the retrieved material answers the question",
                )
            else:
                status, reason = (
                    "documents_obtained",
                    "Assess whether the retrieved material answers the question",
                )
        elif query.get("status") == "complete" and not leads:
            status, reason = "no_usable_leads", "Search returned no usable public document links"
        elif attempts:
            status, reason = "no_admitted_documents", "See source-specific retrieval outcomes"
        else:
            status = query.get("status", "not_attempted")
            reason = (
                query.get("reason")
                or state.get("blocked")
                or state.get("network_status")
                or (
                    f"Research {state['limit_reached']} budget exhausted"
                    if state.get("limit_reached")
                    else "Search not attempted"
                )
            )
        outcomes.append(
            {
                "requirement_id": requirement,
                "question": entry["purpose"],
                "query": entry["query"],
                "fallback_query": entry.get("fallback_query"),
                "status": status,
                "reason": reason,
                "source_tier": (
                    "preferred"
                    if any(d.get("source_tier") == "preferred" for d in usable)
                    else "fallback"
                    if usable
                    else "none"
                ),
                "documents": [d["url"] for d in usable],
                "attempts": attempts,
            }
        )
    planned = {entry["requirement_id"] for entry in state["plan"]}
    for i, requirement in enumerate(packet.product.collection if packet.product else []):
        ident = f"requirement-{i + 1}"
        if ident not in planned:
            outcomes.append(
                {
                    "requirement_id": ident,
                    "question": requirement["title"],
                    "status": "not_attempted",
                    "reason": "Research query budget exhausted",
                    "documents": [],
                    "attempts": [],
                }
            )
    return outcomes


def _document(
    url: str, packet: Packet, transport: HttpTransport, headers: dict, timeout, max_chars: int
) -> dict:
    cutoff = packet.clocks.knowledge_cutoff
    if packet.clocks.mode == "replay":
        query = urlencode(
            {
                "url": url,
                "output": "json",
                "fl": "timestamp,original",
                "filter": "statuscode:200",
                "to": cutoff.strftime("%Y%m%d%H%M%S"),
                "limit": "-1",
                "matchType": "exact",
            }
        )
        response = transport.get(
            "https://web.archive.org/cdx/search/cdx?" + query, timeout=timeout()
        )
        if response.status != 200:
            raise ValueError(f"Archive index HTTP {response.status}")
        rows = json.loads(_decode_archive_body(response.body, response.headers))
        if len(rows) < 2 or rows[0] != ["timestamp", "original"]:
            raise ValueError("No usable pre-cutoff archive capture")
        stamp, original = rows[-1]
        when = datetime.strptime(stamp, "%Y%m%d%H%M%S").replace(tzinfo=UTC)
        if when > cutoff:
            raise ValueError("Archive returned a later version")
        if not _urls_equivalent(original, url):
            raise ValueError("Archive returned a different URL or later version")
        archive = f"https://web.archive.org/web/{stamp}id_/{original}"
        response = transport.get(archive, timeout=timeout())
        if response.status != 200 or response.url != archive:
            raise ValueError("Archive content unavailable or redirected")
        body = _decode_archive_body(response.body, response.headers)
        content_type = {k.lower(): v for k, v in response.headers.items()}.get("content-type", "")
        if not any(t in content_type for t in ("text/html", "text/plain")):
            raise ValueError("Archive document type unsupported; imagery/PDF remains a lead")
        text = _archive_text(body, content_type)
        url = original
        provenance = {
            "archive_url": archive,
            "version_at": when.isoformat(),
            "version_basis": "archive_capture",
        }
    else:
        # Fixed API endpoint avoids directly fetching arbitrary model/search URLs on the host.
        response = transport.post(
            "https://api.tavily.com/extract",
            headers=headers,
            data=json.dumps({"urls": [url], "format": "text"}).encode(),
            timeout=timeout(),
        )
        if response.status != 200:
            raise ValueError(f"Document extraction HTTP {response.status}")
        rows = json.loads(response.body).get("results", [])
        if not rows or rows[0].get("url") != url:
            raise ValueError("Document extraction returned no matching document")
        text = rows[0].get("raw_content", "")
        provenance = {
            "version_at": datetime.now(UTC).isoformat(),
            "version_basis": "contemporaneous_retrieval",
        }
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Document contains no usable text")
    clipped = text[:max_chars]
    return {
        "url": url,
        "text": clipped,
        **provenance,
        "retrieved_at": (
            provenance["version_at"]
            if packet.clocks.mode == "live"
            else datetime.now(UTC).isoformat()
        ),
        "content_sha256": hashlib.sha256(clipped.encode()).hexdigest(),
        "full_text_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "truncated": len(text) > max_chars,
        "original_chars": len(text),
        "originating_source": urlsplit(url).hostname,
        "independence": "unverified",
    }


def run_research(
    directory: Path,
    packet: Packet,
    root: Path,
    *,
    collection: dict,
    transport: HttpTransport | None = None,
    limits: ResearchLimits | None = None,
    progress=None,
    allow_network: bool = True,
) -> dict:
    limits = limits or ResearchLimits()
    plan = research_plan(packet, limits)
    key = digest(
        {
            "schema": "research_v1",
            "cutoff": str(packet.clocks.knowledge_cutoff),
            "mode": packet.clocks.mode,
            "plan": plan,
            "document_chars": limits.document_chars,
        }
    )[:20]
    folder = directory / "research"
    path = folder / f"research-{key}.json"
    legacy_state = None
    if not path.exists():
        # Reuse old checkpoints when only attempt/time allowances changed.
        for old_path in folder.glob("research-*.json"):
            candidate = json.loads(old_path.read_text())
            old_key = digest(
                {
                    "schema": "research_v1",
                    "cutoff": str(packet.clocks.knowledge_cutoff),
                    "mode": packet.clocks.mode,
                    "plan": plan,
                    "limits": candidate.get("limits"),
                }
            )[:20]
            if old_path.stem == f"research-{old_key}" and candidate.get("plan") == plan:
                if legacy_state is None or len(candidate["requests"]) > len(
                    legacy_state["requests"]
                ):
                    legacy_state = candidate
    state = (
        json.loads(path.read_text())
        if path.exists()
        else legacy_state
        or {
            "schema_id": "research_v1",
            "plan": plan,
            "limits": asdict(limits),
            "requests": {},
            "documents": [],
            "leads": [],
            "elapsed_s": 0,
        }
    )
    state["limits"] = asdict(limits)
    state["run_usage"] = {
        "search_requests": 0,
        "search_cache_hits": 0,
        "document_attempts": 0,
    }
    if not allow_network:
        state["network_status"] = (
            "Network research disabled for this run; only saved documents are available"
        )
        state["collection_outcomes"] = collection_outcomes(state, packet)
        return state
    api_key = tavily_api_key(root)
    folder.mkdir(parents=True, exist_ok=True)
    # One writer per plan. A process crash leaves an explicit lock for operator inspection.
    lock = path.with_suffix(".lock")
    try:
        handle = lock.open("x")
    except FileExistsError as exc:
        raise ValueError(
            "Research already running or interrupted; inspect its lock before retrying"
        ) from exc
    handle.close()
    client = transport or ResearchTransport()
    search_index = SearchIndex(root)
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    started = time.monotonic()
    state.pop("limit_reached", None)
    state.pop("blocked", None)
    if progress:
        progress(
            f"Research limits: {limits.queries} queries, {limits.documents} document attempts, "
            f"{limits.seconds}s; each request waits at most 30s. Failures count as attempts.",
            1,
        )

    def timeout():
        left = limits.seconds - (time.monotonic() - started)
        if left <= 0:
            raise TimeoutError("Research time budget exhausted")
        return min(30, left)

    def checkpoint_request(ident, operation):
        if ident in state["requests"] and state["requests"][ident].get("status") != "deferred":
            return None  # Complete, failed and uncertain paid requests are never silently retried.
        timeout()
        if ident.startswith("document-"):
            state["run_usage"]["document_attempts"] += 1
        state["requests"][ident] = {
            "status": "pending",
            "started_at": datetime.now(UTC).isoformat(),
        }
        _save(path, state)
        try:
            value = operation()
            state["requests"][ident] = {
                "status": "complete",
                "result_count": len(value) if isinstance(value, list) else 1,
            }
            return value
        except (SearchIndexBusy, ResearchDeferred) as exc:
            state["requests"][ident] = {"status": "deferred", "reason": str(exc)}
            return None
        except (OSError, ValueError, KeyError, TypeError) as exc:
            reason = str(exc)[:200] or type(exc).__name__
            state["requests"][ident] = {"status": "failed", "reason": reason}
            if progress:
                progress(f"Research request failed: {reason}", 1)
            return None
        finally:
            _save(path, state)

    cutoff = packet.clocks.knowledge_cutoff

    def add_leads(found, requirement_id, search_tier):
        seen = {row["url"] for row in state["leads"] if row.get("requirement_id") == requirement_id}
        added = []
        for rank, lead in enumerate(found or []):
            if not isinstance(lead, dict):
                continue
            url = str(lead.get("url", ""))
            if not public_url(url) or url in seen:
                continue
            row = {
                "url": url,
                "title": lead.get("title", ""),
                "requirement_id": requirement_id,
                "result_rank": rank,
                "search_tier": search_tier,
            }
            state["leads"].append(row)
            seen.add(url)
            added.append(row)
        return added

    def fetchable(rows):
        return [row for row in rows if lead_skip_reason(row["url"], cutoff) is None]

    def search_query(query_text):
        request_body = {
            "query": query_text,
            "max_results": 4,
            "topic": "general",
            "search_depth": "basic",
            "include_answer": False,
            "start_date": (cutoff - timedelta(days=32)).date().isoformat(),
            "end_date": cutoff.date().isoformat(),
        }

        def fetch():
            if not api_key:
                state["blocked"] = (
                    "TAVILY_API_KEY is not set; only indexed search results are usable"
                )
                raise ResearchDeferred("No indexed result and TAVILY_API_KEY is not set")
            state["run_usage"]["search_requests"] += 1
            response = client.post(
                TAVILY_SEARCH_URL,
                headers=headers,
                timeout=timeout(),
                data=json.dumps(request_body).encode(),
            )
            if response.status != 200:
                raise ValueError(f"Search HTTP {response.status}")
            return json.loads(response.body).get("results", [])[:4]

        found, cache_hit = search_index.fetch(request_body, fetch)
        if cache_hit:
            state["run_usage"]["search_cache_hits"] += 1
        return found

    def can_search():
        return state["run_usage"]["search_requests"] < limits.queries

    def admitted_for(requirement_id):
        lead_urls = {
            row["url"] for row in state["leads"] if row.get("requirement_id") == requirement_id
        }
        return [
            doc
            for doc in state["documents"]
            if (doc.get("requirement_id") == requirement_id or doc.get("url") in lead_urls)
            and not document_rejection(doc, cutoff, packet.clocks.mode)
        ]

    def preferred_fetchable(requirement_id):
        return [
            row
            for row in state["leads"]
            if row.get("requirement_id") == requirement_id
            and row.get("search_tier") != "fallback"
            and lead_skip_reason(row["url"], cutoff) is None
        ]

    def consider_documents(leads):
        ordered = sorted(
            leads,
            key=lambda lead: (
                0 if preferred_source(lead["url"]) else 1,
                lead.get("result_rank", 4),
            ),
        )
        for lead in ordered:
            if packet.clocks.mode == "live" and not api_key:
                state["blocked"] = "TAVILY_API_KEY is not set; live document extraction cannot run"
                return
            ident = "document-" + digest(lead["url"])[:16]
            if ident in state["requests"]:
                continue
            skip = lead_skip_reason(lead["url"], cutoff)
            if skip:
                state["requests"][ident] = {"status": "skipped", "reason": skip}
                _save(path, state)
                continue
            attempted = state["run_usage"]["document_attempts"]
            if attempted >= limits.documents:
                state["limit_reached"] = "documents"
                return
            if progress:
                progress(f"Checking document version {attempted + 1}/{limits.documents}", 1)
            doc = checkpoint_request(
                ident,
                lambda lead=lead: _document(
                    lead["url"], packet, client, headers, timeout, limits.document_chars
                ),
            )
            if doc:
                state["documents"].append(
                    {
                        **doc,
                        # A present-day search title is not part of the archived document.
                        "requirement_id": lead.get("requirement_id"),
                        "source_tier": "preferred" if preferred_source(lead["url"]) else "fallback",
                    }
                )
                _save(path, state)

    def run_fallback_search(i, entry):
        fallback_ident = f"query-{i}-fallback"
        if (
            fallback_ident in state["requests"]
            or not entry.get("fallback_query")
            or not can_search()
            or admitted_for(entry["requirement_id"])
            or preferred_fetchable(entry["requirement_id"])
        ):
            return
        if progress:
            progress(f"Preferred sources unavailable; fallback search for {entry['purpose']}", 1)
        fallback = checkpoint_request(
            fallback_ident,
            lambda text=entry["fallback_query"]: search_query(text),
        )
        add_leads(fallback, entry["requirement_id"], "fallback")
        _save(path, state)

    try:
        for i, entry in enumerate(plan):
            if not can_search() and "query-" + str(i) not in state["requests"]:
                break
            if progress:
                progress(f"Research query {i + 1}/{len(plan)}: {entry['purpose']}", 1)
            found = checkpoint_request(
                "query-" + str(i), lambda text=entry["query"]: search_query(text)
            )
            added = (
                add_leads(found, entry["requirement_id"], "preferred") if found is not None else []
            )
            _save(path, state)
            if found is not None and not fetchable(added):
                run_fallback_search(i, entry)
        cached = [
            r
            for t in collection.get("tasks", [])
            if t.get("kind") == "open_source_search"
            for r in t.get("items", [])
        ]
        candidates = list(
            {
                r["url"]: r for r in [*state["leads"], *cached] if public_url(str(r.get("url", "")))
            }.values()
        )
        consider_documents(candidates)
        if state["run_usage"]["document_attempts"] < limits.documents:
            for i, entry in enumerate(plan):
                run_fallback_search(i, entry)
            consider_documents(state["leads"])
    except TimeoutError:
        state["limit_reached"] = "time"
    finally:
        state["elapsed_s"] += round(time.monotonic() - started, 2)
        state["admitted_documents"] = sum(
            not document_rejection(d, packet.clocks.knowledge_cutoff, packet.clocks.mode)
            for d in state["documents"]
        )
        state["usage"] = {
            "search_requests": sum(k.startswith("query-") for k in state["requests"]),
            "document_attempts": sum(
                k.startswith("document-") and v.get("status") != "skipped"
                for k, v in state["requests"].items()
            ),
            "elapsed_s": state["elapsed_s"],
            "cost": "not_measured",
            "independent_sources": "not_verified",
        }
        state["collection_outcomes"] = collection_outcomes(state, packet)
        state["stop_reason"] = (
            f"Stopped at the {limits.documents}-document attempt limit for this run; "
            "failed retrievals count toward this limit."
            if state.get("limit_reached") == "documents"
            else f"Stopped at the {limits.seconds}-second research time limit."
            if state.get("limit_reached") == "time"
            else state.get("blocked")
            or "Finished the planned searches and available document candidates."
        )
        failures = sum(
            k.startswith("document-") and v.get("status") == "failed"
            for k, v in state["requests"].items()
        )
        state["usage"]["failed_documents"] = failures
        if progress:
            progress(
                f"{state['stop_reason']} {state['admitted_documents']} usable documents retained; "
                f"{failures} failed retrievals recorded. Tavily credit balance was not checked.",
                1,
            )
        _save(path, state)
        lock.unlink()
    return state
