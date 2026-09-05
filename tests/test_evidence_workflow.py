import gzip
import hashlib
import json
from copy import deepcopy
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from test_draft import FakeChat, _notice

from dashboard.server import create_app
from wsf.assessment_review import review_assessment
from wsf.connectors.http import HttpResponse
from wsf.draft import _system_prompt, run_desk_draft
from wsf.evidence_bundle import (
    build_bundle,
    canonical,
    document_rejection,
    model_input,
    save_bundle,
)
from wsf.packet import EvidenceItem, Packet, packet_path
from wsf.research import (
    ResearchLimits,
    _urls_equivalent,
    lead_skip_reason,
    public_url,
    research_plan,
    run_research,
)


@pytest.fixture
def packet(tmp_path):
    _notice(tmp_path)
    result = Packet.model_validate_json(
        packet_path(tmp_path, "desk-case", "packet-test").read_text()
    )
    result.collected_evidence = [
        EvidenceItem(
            item_id="obs-fixture",
            kind="observation",
            series_id="market.test",
            source="fixture",
            evidence_time=datetime(2022, 2, 10, tzinfo=UTC),
            available_at=datetime(2022, 2, 11, tzinfo=UTC),
            retrieved_at=datetime(2026, 9, 1, tzinfo=UTC),
            relationship="financial",
            text="The measured value is 3.",
        )
    ]
    result.product.collection = [{"title": "Physical posture", "why": "Check movements at Yelnya"}]
    return result


def task(kind, items):
    return {
        "kind": kind,
        "items": items,
        "knowledge_cutoff": "2022-02-12T23:59:59Z",
        "ran_at": "2026-09-04T00:00:00Z",
        "notes": ["CONTAMINATED SUMMARY"],
    }


def document(text="A contemporaneous warning of invasion.", stamp="20220211090000"):
    url = "https://example.com/report"
    when = datetime.strptime(stamp, "%Y%m%d%H%M%S").replace(tzinfo=UTC).isoformat()
    return {
        "url": url,
        "text": text,
        "version_at": when,
        "version_basis": "archive_capture",
        "archive_url": f"https://web.archive.org/web/{stamp}id_/{url}",
        "retrieved_at": "2026-09-04T00:00:00Z",
        "content_sha256": hashlib.sha256(text.encode()).hexdigest(),
    }


def test_bundle_revalidates_cached_leads_and_drops_derived_prose(packet):
    packet.product.assessment = ["CONTAMINATED SUMMARY"]
    packet.geopolitical_context = {"notes": ["2024 maps prove deployment"]}
    collection = {
        "tasks": [
            task(
                "open_source_search",
                [
                    {
                        "url": "https://gov.uk/current",
                        "snippet": "2024 maps prove deployment",
                        "date_unverified": True,
                    },
                    {
                        "url": "https://example.com/2022/02/11/report",
                        "published": "2022-02-11",
                        "snippet": "UNVERIFIED SNIPPET",
                    },
                ],
            )
        ]
    }
    before = canonical(collection)
    bundle = build_bundle(packet, collection)
    assert len(bundle["excluded"]) == 2
    assert "CONTAMINATED SUMMARY" not in canonical(bundle)
    assert "2024 maps prove deployment" not in canonical(bundle)
    assert "UNVERIFIED SNIPPET" not in canonical(bundle)
    assert canonical(collection) == before


def test_bundle_includes_details_with_honest_provenance(packet):
    collection = {
        "tasks": [
            task(
                "official_pack",
                [{"kind": "declared_posture", "at": "2022-02-11T18:00:00Z", "text": "Leave now"}],
            ),
            task(
                "refresh_physical",
                [
                    {
                        "kind": "catalogue_granule",
                        "available_at": "2022-02-11",
                        "published_at": "2024-01-01",
                        "knowable": True,
                        "reconstructed": True,
                        "aoi_name": "Yelnya",
                    },
                    {"available_at": "2022-02-15", "knowable": False, "value": 99},
                ],
            ),
            task("chronology", [{"day": "2022-02-09", "series": [{"value": 2}]}]),
        ]
    }
    bundle = build_bundle(packet, collection)
    assert {r["kind"] for r in bundle["items"]} == {
        "observation",
        "official_event",
        "catalogue_pointer",
        "chronology",
    }
    pointer = next(r for r in bundle["items"] if r["kind"] == "catalogue_pointer")
    assert pointer["verification"] == "reconstructed_catalogue_availability_not_imagery"
    assert len(bundle["excluded"]) == 1
    assert "Leave now" in canonical(bundle)


def test_preferred_documents_are_kept_when_budget_is_tight(packet):
    long_fallback = document("Fallback chrome. " * 800)
    long_fallback["url"] = "https://example.com/fallback"
    long_fallback["archive_url"] = (
        "https://web.archive.org/web/20220211090000id_/https://example.com/fallback"
    )
    preferred = document("TikTok videos show Russian forces advancing closer to Ukraine. " * 20)
    preferred["url"] = "https://www.washingtonpost.com/world/2022/02/11/story"
    preferred["source_tier"] = "preferred"
    preferred["archive_url"] = (
        "https://web.archive.org/web/20220211090000id_/"
        "https://www.washingtonpost.com/world/2022/02/11/story"
    )
    bundle = build_bundle(packet, {}, documents=[long_fallback, preferred], max_chars=12000)
    docs = [row for row in bundle["items"] if row["kind"] == "document"]
    assert {row["data"]["url"] for row in docs} == {
        long_fallback["url"],
        preferred["url"],
    }
    assert any("TikTok videos" in row["data"]["text"] for row in docs)
    omitted_docs = [row for row in bundle["omitted"] if row["kind"] == "document"]
    assert omitted_docs == []


def test_model_input_uses_retrieved_passages_not_whole_pages(packet):
    body = ("Satellite images show new tents. " * 40) + ("Cookie banner chrome. " * 40)
    doc = {
        "url": "https://www.washingtonpost.com/world/2022/02/11/story",
        "text": body,
        "content_sha256": hashlib.sha256(body.encode()).hexdigest(),
        "version_at": "2022-02-11T09:00:00+00:00",
        "version_basis": "archive_capture",
        "archive_url": (
            "https://web.archive.org/web/20220211090000id_/"
            "https://www.washingtonpost.com/world/2022/02/11/story"
        ),
        "retrieved_at": "2026-09-05T00:00:00+00:00",
        "source_tier": "preferred",
    }
    bundle = build_bundle(packet, {}, documents=[doc])
    stored = next(row for row in bundle["items"] if row["kind"] == "document")
    assert stored["data"]["text"] == body
    view = model_input(
        bundle,
        max_chars=8000,
        passages=[
            {
                "content_sha256": doc["content_sha256"],
                "url": doc["url"],
                "text": "Satellite images show new tents. " * 2,
                "start": 0,
                "end": 66,
                "source_tier": "preferred",
                "retrieval": "embedding",
                "version_at": doc["version_at"],
            }
        ],
    )
    passages = [row for row in view["evidence"] if row["kind"] == "document_passage"]
    stubs = [row for row in view["evidence"] if row["kind"] == "document"]
    assert passages
    assert passages[0]["id"] == stored["id"]
    assert "Satellite images show new tents" in passages[0]["data"]["text"]
    assert all("Cookie banner" not in (row.get("data") or {}).get("text", "") for row in stubs)


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"text": "tampered"}, "hash"),
        ({"version_at": "2024-01-01"}, "after_cutoff"),
        ({"version_basis": "publication_date"}, "unverified"),
        ({"archive_url": "https://example.com/archive"}, "provenance"),
        ({"url": "https://example.com/report?version=different"}, "mismatch"),
        (
            {
                "archive_url": "https://web.archive.org/web/20220212000000id_/https://example.com/report"
            },
            "mismatch",
        ),
    ],
)
def test_document_admission_checks_content_versions(packet, change, reason):
    row = {**document(), **change}
    assert reason in document_rejection(row, packet.clocks.knowledge_cutoff, "replay")


def test_pre_cutoff_warning_is_not_removed_for_outcome_words(packet):
    bundle = build_bundle(packet, {"tasks": []}, documents=[document()])
    assert any("warning of invasion" in canonical(r) for r in bundle["items"])
    assert not bundle["excluded"]


def test_live_rejects_future_retrieval_and_unavailable_records(packet):
    packet.clocks.mode = "live"
    bundle = build_bundle(packet, {"tasks": []}, documents=[document()])
    assert not bundle["items"]
    assert len(bundle["excluded"]) == 2


def test_bundle_snapshot_and_omissions_are_reproducible(packet, tmp_path):
    packet.collected_evidence[0].text = "x" * 3000
    bundle = build_bundle(packet, {"tasks": []}, max_chars=1000)
    assert bundle == build_bundle(packet, {"tasks": []}, max_chars=1000)
    assert len(bundle["omitted"]) == 1
    path = save_bundle(tmp_path, bundle)
    assert save_bundle(tmp_path, bundle) == path
    path.write_text("different")
    with pytest.raises(ValueError, match="overwrite"):
        save_bundle(tmp_path, bundle)


def test_model_input_is_bounded_balanced_and_does_not_replace_audit_bundle(packet):
    collection = {
        "tasks": [
            task(
                "official_pack",
                [
                    {
                        "kind": "declared_posture",
                        "at": "2022-02-11",
                        "text": f"Event {i} " + ("detail " * 100),
                    }
                    for i in range(12)
                ],
            ),
            task(
                "refresh_physical",
                [{"available_at": "2022-02-11", "knowable": True, "value": i} for i in range(12)],
            ),
        ]
    }
    bundle = build_bundle(packet, collection)
    before = canonical(bundle)
    view = model_input(bundle, max_chars=8000)
    assert len(canonical(view)) <= 8000
    assert view["bundle_id"] == bundle["bundle_id"]
    assert {row["kind"] for row in view["evidence"]} >= {
        "observation",
        "official_event",
        "physical_observation",
    }
    assert view["admission_summary"]["not_selected_for_model"] > 0
    assert canonical(bundle) == before


def test_hypothesis_update_and_grounding_checks(packet):
    bundle = build_bundle(packet, {"tasks": []})
    ref = bundle["items"][0]["id"]
    payload = {
        "claims": [
            {
                "statement": "The value is 3.",
                "evidence_ids": [ref],
                "quotes": {ref: "The measured value is 3."},
            }
        ],
        "hypothesis_updates": [
            {
                "hypothesis": bundle["hypotheses"][0],
                "change": "lowered",
                "supporting_evidence": [],
                "contradicting_evidence": [ref],
                "rationale": "A proposed revision for analyst review.",
            }
        ],
        "decision": "collect_more",
    }
    review = review_assessment(payload, bundle)
    assert review["status"] == "references_checked"
    assert review["hypothesis_updates"][0]["change"] == "lowered"
    wrong = deepcopy(payload)
    wrong["claims"][0]["quotes"][ref] = "An invented quotation"
    wrong["citations"] = [{"url": "https://invented.example/report"}]
    result = review_assessment(wrong, bundle)
    assert result["status"] == "needs_review"
    assert result["citations"][0]["reference_check"] == "unverified_url"
    assert any("quote_not_in_evidence" in i for i in result["issues"])


def test_claim_evidence_invariants_flag_mismatches(packet):
    bundle = build_bundle(packet, {"tasks": []})
    ref = bundle["items"][0]["id"]
    # First item: market.test, 2022-02-10, "The measured value is 3."

    # 1. Date mismatch: claim specifies 2022-02-12, but evidence is 2022-02-10
    date_mismatch = {
        "claims": [
            {
                "statement": "The value was 3 on 2022-02-12.",
                "evidence_ids": [ref],
                "quotes": {ref: "The measured value is 3."},
            }
        ]
    }
    res = review_assessment(date_mismatch, bundle)
    assert res["claims"][0]["reference_check"] == "needs_review"
    assert f"claim_evidence_date_mismatch:{ref}" in res["claims"][0]["issues"]

    # 2. Value mismatch: claim specifies value 15.0, but evidence has 3.0
    val_mismatch = {
        "claims": [
            {
                "statement": "The value was 15.0 on 2022-02-10.",
                "evidence_ids": [ref],
                "quotes": {ref: "The measured value is 3."},
            }
        ]
    }
    res = review_assessment(val_mismatch, bundle)
    assert res["claims"][0]["reference_check"] == "needs_review"
    assert f"claim_evidence_value_mismatch:{ref}" in res["claims"][0]["issues"]

    # 3. Series mismatch: statement claims Wikipedia pageviews, but evidence is market.test
    bundle["items"][0]["data"]["series_id"] = "attn.wiki_pageviews"
    series_mismatch = {
        "claims": [
            {
                "statement": "CBR funding spread z-score was 2.54 on 2022-02-10.",
                "evidence_ids": [ref],
                "quotes": {ref: "The measured value is 3."},
            }
        ]
    }
    res = review_assessment(series_mismatch, bundle)
    assert res["claims"][0]["reference_check"] == "needs_review"
    assert f"claim_evidence_series_mismatch:{ref}" in res["claims"][0]["issues"]

    # 4. Correct match: date, series, and value align
    bundle["items"][0]["data"]["text"] = "z=0.47396039; raw=66480.0; quality=ok"
    correct = {
        "claims": [
            {
                "statement": "Wikipedia pageviews z-score was 0.47 on 2022-02-10.",
                "evidence_ids": [ref],
                "quotes": {ref: "z=0.47396039; raw=66480.0; quality=ok"},
            }
        ]
    }
    res = review_assessment(correct, bundle)
    assert res["claims"][0]["issues"] == []
    assert res["claims"][0]["reference_check"] == "references_match"


def test_missing_hypotheses_and_unknown_evidence_stay_unresolved(packet):
    bundle = build_bundle(packet, {"tasks": []})
    result = review_assessment(
        {"claims": [{"statement": "Claim", "evidence_ids": ["missing"]}]}, bundle
    )
    assert result["status"] == "needs_review"
    assert result["hypothesis_updates"][0]["change"] == "unresolved"
    assert "exact ID" in _system_prompt("cutoff", [])
    assert "keep causal explanations at realistic possibility" not in _system_prompt("cutoff", [])


class ArchiveFixture:
    def __init__(self, later=False):
        self.calls = []
        self.later = later

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return HttpResponse(
            url,
            200,
            json.dumps(
                {"results": [{"url": "https://example.com/report", "title": "Public report"}]}
            ).encode(),
            {},
        )

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if "/cdx/" in url:
            stamp = "20240101000000" if self.later else "20220211090000"
            original = parse_qs(urlsplit(url).query).get("url", ["https://example.com/report"])[0]
            return HttpResponse(
                url,
                200,
                json.dumps([["timestamp", "original"], [stamp, original]]).encode(),
                {},
            )
        return HttpResponse(
            url,
            200,
            b"<p>Contemporaneous reporting.</p><script>HIDDEN</script>",
            {"content-type": "text/html"},
        )


def test_research_is_requirement_led_bounded_and_resumable(packet, tmp_path, monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "fixture-key")
    fake = ArchiveFixture()
    limits = ResearchLimits(queries=3, documents=1, seconds=5)
    assert len(research_plan(packet, limits)) == 3
    assert "withdrawal" in research_plan(packet, limits)[-1]["query"]
    result = run_research(
        tmp_path, packet, tmp_path, collection={"tasks": []}, transport=fake, limits=limits
    )
    assert len(fake.calls) == 5  # Three searches, one index, one archived document.
    assert result["run_usage"] == {
        "search_requests": 3,
        "search_cache_hits": 0,
        "document_attempts": 1,
    }
    assert result["admitted_documents"] == 1
    assert all(
        row["status"] == "documents_obtained"
        for row in result["collection_outcomes"]
        if row.get("query")
    )
    assert "HIDDEN" not in result["documents"][0]["text"]
    assert "title" not in result["documents"][0]
    second = run_research(
        tmp_path, packet, tmp_path, collection={"tasks": []}, transport=fake, limits=limits
    )
    assert len(fake.calls) == 5
    assert second["documents"] == result["documents"]
    assert second["run_usage"] == {
        "search_requests": 0,
        "search_cache_hits": 0,
        "document_attempts": 0,
    }
    # API credentials are never persisted.
    assert all("fixture-key" not in p.read_text() for p in (tmp_path / "research").glob("*.json"))

    # A different packet-local research record reuses the project-wide indexed searches.
    monkeypatch.delenv("TAVILY_API_KEY")
    third = run_research(
        tmp_path / "another-packet",
        packet,
        tmp_path,
        collection={"tasks": []},
        transport=fake,
        limits=limits,
    )
    assert len(fake.calls) == 7  # Only the archive index and document fetch are new.
    assert third["run_usage"] == {
        "search_requests": 0,
        "search_cache_hits": 3,
        "document_attempts": 1,
    }


def test_counterevidence_survives_many_requirements(packet):
    packet.product.collection *= 10
    plan = research_plan(packet, ResearchLimits())
    assert len(plan) == 6
    assert plan[-1]["requirement_id"] == "counterevidence"
    assert plan[-2]["requirement_id"] == "physical-corroboration"


def test_research_plan_uses_places_and_keeps_a_broader_fallback(packet):
    packet.product.keys = [
        "Russia",
        "Ukraine",
        "Moscow",
        "Ukrainian border",
        "Yelnya",
        "Klintsy",
    ]
    plan = research_plan(packet, ResearchLimits(queries=3, documents=1, seconds=5))
    assert len(plan) == 3
    assert "Yelnya" in plan[0]["query"]
    assert "satellite imagery" in plan[0]["query"]
    assert "Physical posture" in plan[0]["fallback_query"]
    assert "withdrawal" in plan[-1]["query"]
    assert plan[0]["query"] != plan[0]["fallback_query"]


def test_collection_outcomes_explain_disabled_and_unplanned_questions(packet, tmp_path):
    packet.product.collection *= 10
    result = run_research(tmp_path, packet, tmp_path, collection={}, allow_network=False)
    assert all(row["status"] == "not_attempted" for row in result["collection_outcomes"])
    reasons = {row["reason"] for row in result["collection_outcomes"]}
    assert "Research query budget exhausted" in reasons
    assert any("Network research disabled" in reason for reason in reasons)


def test_archive_failure_is_attached_to_question(packet, tmp_path, monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "fixture-key")

    class NoArchive(ArchiveFixture):
        def get(self, url, **kwargs):
            return HttpResponse(url, 200, b"[]", {})

    result = run_research(
        tmp_path,
        packet,
        tmp_path,
        collection={},
        transport=NoArchive(),
        limits=ResearchLimits(queries=3, documents=1, seconds=5),
    )
    outcome = next(row for row in result["collection_outcomes"] if row.get("attempts"))
    assert outcome["status"] == "no_admitted_documents"
    assert outcome["attempts"][0]["reason"] == "No usable pre-cutoff archive capture"


def test_more_document_allowance_continues_after_failed_urls(packet, tmp_path, monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "fixture-key")

    class FailedArchives(ArchiveFixture):
        def post(self, url, **kwargs):
            self.calls.append((url, kwargs))
            return HttpResponse(
                url,
                200,
                json.dumps(
                    {"results": [{"url": f"https://example.com/{i}"} for i in range(4)]}
                ).encode(),
                {},
            )

        def get(self, url, **kwargs):
            self.calls.append((url, kwargs))
            return HttpResponse(url, 200, b"[]", {})

    fake = FailedArchives()
    first = run_research(
        tmp_path,
        packet,
        tmp_path,
        collection={},
        transport=fake,
        limits=ResearchLimits(queries=3, documents=1, seconds=5),
    )
    assert first["limit_reached"] == "documents"
    first_urls = [url for url, _ in fake.calls if "/cdx/" in url]
    second = run_research(
        tmp_path,
        packet,
        tmp_path,
        collection={},
        transport=fake,
        limits=ResearchLimits(queries=3, documents=2, seconds=10),
    )
    assert second["run_usage"]["search_requests"] == 0
    assert second["run_usage"]["document_attempts"] == 2
    assert second["usage"]["failed_documents"] == 3
    assert [url for url, _ in fake.calls if "/cdx/" in url].count(first_urls[0]) == 1


def test_malformed_revision_stays_reviewable(packet):
    bundle = build_bundle(packet, {})
    result = review_assessment(
        {"hypothesis_updates": [{"hypothesis": bundle["hypotheses"][0], "change": ["raised"]}]},
        bundle,
    )
    assert result["status"] == "needs_review"
    assert "Missing/invalid direction of change" in result["issues"]


def test_late_archive_and_failed_requests_are_not_retried(packet, tmp_path, monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "fixture-key")
    fake = ArchiveFixture(later=True)
    limits = ResearchLimits(queries=1, documents=1, seconds=5)
    result = run_research(
        tmp_path, packet, tmp_path, collection={"tasks": []}, transport=fake, limits=limits
    )
    assert not result["documents"]
    assert any(r["status"] == "failed" for r in result["requests"].values())
    count = len(fake.calls)
    run_research(
        tmp_path, packet, tmp_path, collection={"tasks": []}, transport=fake, limits=limits
    )
    assert len(fake.calls) == count


def test_missing_search_key_defers_cache_miss_for_later_retry(packet, tmp_path, monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    fake = ArchiveFixture()
    limits = ResearchLimits(queries=1, documents=1, seconds=5)
    first = run_research(
        tmp_path, packet, tmp_path, collection={"tasks": []}, transport=fake, limits=limits
    )
    assert not fake.calls
    assert first["requests"]["query-0"]["status"] == "deferred"
    monkeypatch.setenv("TAVILY_API_KEY", "fixture-key")
    second = run_research(
        tmp_path, packet, tmp_path, collection={"tasks": []}, transport=fake, limits=limits
    )
    assert second["requests"]["query-0"]["status"] == "complete"
    assert second["run_usage"]["search_requests"] == 1


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/a",
        "http://127.0.0.1/a",
        "file:///tmp/a",
        "http://10.0.0.1/a",
        "https://user:password@example.com/a",
    ],
)
def test_non_public_document_targets_are_rejected(url):
    assert not public_url(url)


def test_archive_accepts_equivalent_wayback_urls(packet, tmp_path, monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "fixture-key")
    assert _urls_equivalent(
        "https://www.washingtonpost.com/world/2022/02/11/story",
        "http://washingtonpost.com/world/2022/02/11/story/",
    )
    assert not _urls_equivalent(
        "https://www.washingtonpost.com/world/2022/02/11/story",
        "https://www.washingtonpost.com/world/2022/02/12/story",
    )

    class SlashCapture(ArchiveFixture):
        def get(self, url, **kwargs):
            self.calls.append((url, kwargs))
            if "/cdx/" in url:
                original = parse_qs(urlsplit(url).query).get("url", ["https://example.com/report"])[
                    0
                ]
                return HttpResponse(
                    url,
                    200,
                    json.dumps(
                        [["timestamp", "original"], ["20220211090000", original + "/"]]
                    ).encode(),
                    {},
                )
            return HttpResponse(
                url,
                200,
                b"<p>Canonicalised archive capture.</p>",
                {"content-type": "text/html"},
            )

    result = run_research(
        tmp_path,
        packet,
        tmp_path,
        collection={},
        transport=SlashCapture(),
        limits=ResearchLimits(queries=1, documents=1, seconds=5),
    )
    assert result["admitted_documents"] == 1
    assert result["documents"][0]["url"].endswith("/")


def test_gzip_archive_html_is_admitted_and_binary_is_not(packet, tmp_path, monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "fixture-key")

    class GzipArchive(ArchiveFixture):
        def get(self, url, **kwargs):
            self.calls.append((url, kwargs))
            if "/cdx/" in url:
                original = parse_qs(urlsplit(url).query).get("url", ["https://example.com/report"])[
                    0
                ]
                return HttpResponse(
                    url,
                    200,
                    json.dumps([["timestamp", "original"], ["20220211090000", original]]).encode(),
                    {},
                )
            return HttpResponse(
                url,
                200,
                gzip.compress(b"<p>Archived warning from a contemporaneous page.</p>"),
                {"content-type": "text/html", "content-encoding": "gzip"},
            )

    result = run_research(
        tmp_path,
        packet,
        tmp_path,
        collection={},
        transport=GzipArchive(),
        limits=ResearchLimits(queries=1, documents=1, seconds=5),
    )
    assert result["admitted_documents"] == 1
    assert "Archived warning" in result["documents"][0]["text"]

    class BinaryGzip(GzipArchive):
        def get(self, url, **kwargs):
            self.calls.append((url, kwargs))
            if "/cdx/" in url:
                original = parse_qs(urlsplit(url).query).get("url", ["https://example.com/report"])[
                    0
                ]
                return HttpResponse(
                    url,
                    200,
                    json.dumps([["timestamp", "original"], ["20220211090000", original]]).encode(),
                    {},
                )
            return HttpResponse(
                url,
                200,
                gzip.compress(b"\x00\x01\x02\xff binary"),
                {"content-type": "text/html"},
            )

    failed = run_research(
        tmp_path / "binary",
        packet,
        tmp_path / "binary",
        collection={},
        transport=BinaryGzip(),
        limits=ResearchLimits(queries=1, documents=1, seconds=5),
    )
    assert failed["admitted_documents"] == 0
    assert any("binary" in (row.get("reason") or "") for row in failed["requests"].values())


def test_unusable_leads_are_skipped_without_burning_attempts(packet, tmp_path, monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "fixture-key")
    cutoff = packet.clocks.knowledge_cutoff
    assert lead_skip_reason("https://www.youtube.com/watch?v=abc", cutoff)
    assert lead_skip_reason("https://example.com/report.pdf", cutoff)
    assert lead_skip_reason("https://example.com/2023/07/30/later", cutoff)

    class MixedLeads(ArchiveFixture):
        def post(self, url, **kwargs):
            self.calls.append((url, kwargs))
            return HttpResponse(
                url,
                200,
                json.dumps(
                    {
                        "results": [
                            {"url": "https://www.youtube.com/watch?v=abc", "title": "Video"},
                            {"url": "https://example.com/report.pdf", "title": "PDF"},
                            {
                                "url": "https://example.com/2023/07/30/later",
                                "title": "Later",
                            },
                            {"url": "https://example.com/report", "title": "Usable"},
                        ]
                    }
                ).encode(),
                {},
            )

    fake = MixedLeads()
    result = run_research(
        tmp_path,
        packet,
        tmp_path,
        collection={},
        transport=fake,
        limits=ResearchLimits(queries=1, documents=1, seconds=5),
    )
    assert result["run_usage"]["document_attempts"] == 1
    assert result["admitted_documents"] == 1
    skipped = [row for row in result["requests"].values() if row.get("status") == "skipped"]
    assert len(skipped) == 3
    cdx_urls = [url for url, _ in fake.calls if isinstance(url, str) and "/cdx/" in url]
    assert not any("/watch?v=abc" in url for url in cdx_urls)


def test_preferred_domains_are_fetched_before_fallback_leads(packet, tmp_path, monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "fixture-key")

    class RankedLeads(ArchiveFixture):
        def post(self, url, **kwargs):
            self.calls.append((url, kwargs))
            return HttpResponse(
                url,
                200,
                json.dumps(
                    {
                        "results": [
                            {"url": "https://example.com/report", "title": "Broad"},
                            {
                                "url": "https://www.france24.com/en/europe/20220212-satellite",
                                "title": "Imagery",
                            },
                        ]
                    }
                ).encode(),
                {},
            )

    result = run_research(
        tmp_path,
        packet,
        tmp_path,
        collection={},
        transport=RankedLeads(),
        limits=ResearchLimits(queries=1, documents=1, seconds=5),
    )
    assert result["admitted_documents"] == 1
    assert result["documents"][0]["source_tier"] == "preferred"
    assert "france24.com" in result["documents"][0]["url"]
    outcome = next(row for row in result["collection_outcomes"] if row["documents"])
    assert outcome["source_tier"] == "preferred"


def test_fallback_search_runs_when_preferred_leads_are_unusable(packet, tmp_path, monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "fixture-key")

    class PreferredThenFallback(ArchiveFixture):
        def post(self, url, **kwargs):
            self.calls.append((url, kwargs))
            query = json.loads(kwargs["data"])["query"]
            if "satellite imagery" in query or "released imagery" in query or "withdrawal" in query:
                results = [{"url": "https://www.youtube.com/watch?v=abc", "title": "Video"}]
            else:
                results = [{"url": "https://example.com/report", "title": "Broader hit"}]
            return HttpResponse(url, 200, json.dumps({"results": results}).encode(), {})

    result = run_research(
        tmp_path,
        packet,
        tmp_path,
        collection={},
        transport=PreferredThenFallback(),
        limits=ResearchLimits(queries=2, documents=1, seconds=5),
    )
    assert result["run_usage"]["search_requests"] == 2
    assert result["admitted_documents"] == 1
    assert result["documents"][0]["source_tier"] == "fallback"
    outcome = next(row for row in result["collection_outcomes"] if row["documents"])
    assert "Preferred sources unavailable" in outcome["reason"]
    assert any(key.endswith("-fallback") for key in result["requests"])


def test_no_search_makes_no_requests(packet, tmp_path):
    class Forbidden:
        def post(self, *a, **kw):
            pytest.fail("No new search authorized")

        get = post

    result = run_research(
        tmp_path, packet, tmp_path, collection={}, transport=Forbidden(), allow_network=False
    )
    assert result["documents"] == []
    assert not (tmp_path / "research").exists()


@pytest.mark.parametrize("apply", [False, True])
def test_draft_saves_exact_input_and_review_without_modifying_originals(
    packet, tmp_path, monkeypatch, apply
):
    monkeypatch.setenv("OLLAMA_MODEL", "fixture-model")
    monkeypatch.setenv("OLLAMA_MAX_OUTPUT_TOKENS", "4096")
    path = packet_path(tmp_path, "desk-case", "packet-test")
    path.write_text(packet.model_dump_json())
    original = path.read_bytes()
    bundle = build_bundle(packet, {"packet_id": "packet-test", "tasks": []})
    ref = bundle["items"][0]["id"]
    reply = {
        "summary": "A supported draft for human review.",
        "claims": [
            {
                "statement": "The value is 3.",
                "evidence_ids": [ref],
                "quotes": {ref: "The measured value is 3."},
            }
        ],
        "hypothesis_updates": [
            {
                "hypothesis": bundle["hypotheses"][0],
                "change": "unchanged",
                "rationale": "More evidence is required.",
                "supporting_evidence": [ref],
            }
        ],
        "decision": "collect_more",
    }
    fake = FakeChat(json.dumps(reply))
    result = run_desk_draft(
        tmp_path,
        "desk-case",
        "notice-abc",
        replay=True,
        search=False,
        chat_transport=fake,
        apply=apply,
    )
    assert result["applied"] is apply
    assert path.read_bytes() == original
    assert result["review"]["status"] == "references_checked"
    assert result["input_stats"]["prompt_chars"] <= 35000
    assert result["input_stats"]["max_output_tokens"] == 4096
    record = json.loads(__import__("pathlib").Path(result["path"]).read_text())
    stored = json.loads(__import__("pathlib").Path(record["input_path"]).read_text())
    sent = json.loads(fake.requests[0][1]["data"])
    assert stored["system"] == sent["messages"][0]["content"]
    assert stored["user"] == sent["messages"][1]["content"]
    model_payload = json.loads(stored["user"])
    assert (
        model_payload["collection_outcomes"] == result["review"]["research"]["collection_outcomes"]
    )
    assert any(
        "Network research disabled" in row["reason"] for row in model_payload["collection_outcomes"]
    )
    assert model_payload["schema_id"] == "desk_model_input_v1"
    assert len(stored["user"]) <= 32000
    assert "A supported draft" in result["notes"]
    response = TestClient(create_app(api_only=True, project_root=tmp_path)).get(
        "/api/packet/draft/review", params={"scenario": "desk-case", "notice_id": "notice-abc"}
    )
    assert response.status_code == 200
    assert response.json()["review"]["bundle_id"] == record["bundle_id"]
