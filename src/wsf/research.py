"""Bounded requirement-led public-source research with persisted request checkpoints."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from wsf.connectors.http import HttpResponse, HttpTransport, UrllibTransport
from wsf.connectors.tavily import TAVILY_SEARCH_URL, tavily_api_key
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


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Archive redirected; version not verified")


class ResearchTransport(UrllibTransport):
    def get(self, url, *, headers=None, timeout=30):
        # Fetch archive hosts only; never follow a redirect to a live or private endpoint.
        if urlsplit(url).netloc != "web.archive.org" or not url.startswith("https://"):
            raise ValueError("Only the public archive may be fetched directly")
        opener = build_opener(_NoRedirect())
        try:
            with opener.open(Request(url, headers=headers or {}), timeout=timeout) as response:
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


def research_plan(packet: Packet, limits: ResearchLimits) -> list[dict]:
    product = packet.product
    frame = " ".join((product.keys if product else [])[:4]) or packet.scenario_id
    period = packet.clocks.knowledge_cutoff.strftime("%B %Y")
    requirements = product.collection if product else []
    plan = []
    for index, requirement in enumerate(requirements):
        title = requirement.get("title", "Context")
        ident = "requirement-" + str(index + 1)
        plan.append(
            {
                "requirement_id": ident,
                "purpose": title,
                "query": f"{frame} {period} {title} {requirement.get('why', '')}"[:400],
            }
        )
    if requirements and limits.queries > 1:
        extra = [
            {
                "requirement_id": "physical-corroboration",
                "purpose": "Independent physical corroboration",
                "query": f"{frame} {period} released imagery geolocated movement reporting",
            },
            {
                "requirement_id": "counterevidence",
                "purpose": "Counterevidence and alternative explanations",
                "query": f"{frame} {period} verified withdrawal exercise completion",
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
                "status": status,
                "reason": reason,
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
        rows = json.loads(response.body)
        if len(rows) < 2 or rows[0] != ["timestamp", "original"]:
            raise ValueError("No usable pre-cutoff archive capture")
        stamp, original = rows[-1]
        when = datetime.strptime(stamp, "%Y%m%d%H%M%S").replace(tzinfo=UTC)
        if original != url or when > cutoff:
            raise ValueError("Archive returned a different URL or later version")
        archive = f"https://web.archive.org/web/{stamp}id_/{url}"
        response = transport.get(archive, timeout=timeout())
        if response.status != 200 or response.url != archive:
            raise ValueError("Archive content unavailable or redirected")
        content_type = {k.lower(): v for k, v in response.headers.items()}.get("content-type", "")
        if not any(t in content_type for t in ("text/html", "text/plain")):
            raise ValueError("Archive document type unsupported; imagery/PDF remains a lead")
        decoded = response.body.decode("utf-8", errors="replace")
        if "text/html" in content_type:
            parser = _Text()
            parser.feed(decoded)
            decoded = "".join(parser.parts)
        text = "\n".join(line.strip() for line in decoded.splitlines() if line.strip())
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

    try:
        for i, entry in enumerate(plan):
            if progress:
                progress(f"Research query {i + 1}/{len(plan)}: {entry['purpose']}", 1)

            def search(entry=entry):
                request_body = {
                    "query": entry["query"],
                    "max_results": 4,
                    "topic": "general",
                    "search_depth": "basic",
                    "include_answer": False,
                    "start_date": (packet.clocks.knowledge_cutoff - timedelta(days=32))
                    .date()
                    .isoformat(),
                    "end_date": packet.clocks.knowledge_cutoff.date().isoformat(),
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

            found = checkpoint_request("query-" + str(i), search)
            if found is not None:
                for rank, lead in enumerate(found):
                    if isinstance(lead, dict) and public_url(str(lead.get("url", ""))):
                        state["leads"].append(
                            {
                                "url": lead["url"],
                                "title": lead.get("title", ""),
                                "requirement_id": entry["requirement_id"],
                                "result_rank": rank,
                            }
                        )
                _save(path, state)
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
        # Visit the first result of each query before spending the budget on its remainder.
        candidates.sort(key=lambda lead: lead.get("result_rank", 4))
        for lead in candidates:
            if packet.clocks.mode == "live" and not api_key:
                state["blocked"] = "TAVILY_API_KEY is not set; live document extraction cannot run"
                break
            attempted = state["run_usage"]["document_attempts"]
            ident = "document-" + digest(lead["url"])[:16]
            if ident in state["requests"]:
                continue
            if attempted >= limits.documents:
                state["limit_reached"] = "documents"
                break
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
                    }
                )
                _save(path, state)
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
            "document_attempts": sum(k.startswith("document-") for k in state["requests"]),
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
