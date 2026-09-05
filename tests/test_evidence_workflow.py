import hashlib
import json
from copy import deepcopy
from datetime import UTC, datetime

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
from wsf.research import ResearchLimits, public_url, research_plan, run_research


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
            return HttpResponse(
                url,
                200,
                json.dumps(
                    [["timestamp", "original"], [stamp, "https://example.com/report"]]
                ).encode(),
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
    assert model_payload["schema_id"] == "desk_model_input_v1"
    assert len(stored["user"]) <= 32000
    assert "A supported draft" in result["notes"]
    response = TestClient(create_app(api_only=True, project_root=tmp_path)).get(
        "/api/packet/draft/review", params={"scenario": "desk-case", "notice_id": "notice-abc"}
    )
    assert response.status_code == 200
    assert response.json()["review"]["bundle_id"] == record["bundle_id"]
