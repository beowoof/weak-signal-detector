import json
from datetime import date
from pathlib import Path

import pytest

from wsf.connectors.http import HttpResponse
from wsf.draft import (
    OllamaConfig,
    _extract_json_with_grounded_repairs,
    _leakage_hits,
    _normalise_sections,
    _recoverable_completion,
    _section_markdown,
    complete_chat,
    ollama_config,
    run_desk_draft,
)
from wsf.notice import (
    CollectionPosture,
    Notice,
    NoticeTrigger,
    NoticeWorkflow,
    save_notice,
)
from wsf.packet import Packet, PacketClocks, ProductBrief, packet_path
from wsf.report import load_report, save_report
from wsf.scenario import create_scenario


class FakeChat:
    def __init__(self, content: str) -> None:
        self.content = content
        self.requests = []

    def get(self, url, **kwargs):
        raise AssertionError("chat uses POST")

    def post(self, url, **kwargs):
        self.requests.append((url, kwargs))
        body = {
            "model": "local-test-model",
            "message": {"role": "assistant", "content": self.content},
            "done": True,
            "done_reason": "stop",
            "eval_count": 12,
            "eval_duration": 1_000_000_000,
        }
        return HttpResponse(url, 200, json.dumps(body).encode(), {})


def _notice(root: Path) -> Notice:
    create_scenario(root, "desk-case")
    notice = Notice(
        notice_id="notice-abc",
        trigger=NoticeTrigger.model_validate(
            {
                "scenario_id": "desk-case",
                "window_id": "incident",
                "collection_id": "collection-1",
                "measurement_id": "measure-1",
                "policy_id": "coupling_k3_z15_p3",
                "policy_params": {"threshold_z": 1.5},
                "created_at": "2026-09-03T00:00:00Z",
                "start": date(2022, 2, 10),
                "end": date(2022, 2, 12),
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
        ),
        workflow=NoticeWorkflow(packet_id="packet-test"),
    )
    save_notice(root, notice, overwrite_trigger=True)
    clocks = PacketClocks.model_validate(
        {
            "mode": "replay",
            "knowledge_cutoff": "2022-02-12T23:59:59Z",
            "built_at": "2026-09-04T00:00:00Z",
            "notice_emitted_at": "2026-09-03T00:00:00Z",
            "knowledge_rule": "available_at",
        }
    )
    product = ProductBrief(
        headline="Ukraine: Preparatory Activity Watch",
        period="10–12 February 2022",
        available_by="12 February",
        analytic_state="watch",
        analytic_state_label="Watch",
        change="Broadening multi-domain anomaly",
        confidence="Low",
        assessment=["Abnormal activity is present."],
        watchlist=[],
        supports=[],
        does_not_support=[],
        caveats=[],
        hypotheses=[
            {
                "hypothesis": "Routine variation",
                "fit": "Realistic possibility",
                "discriminate": "Decay.",
            }
        ],
        collection=[],
        keys=["Russia", "Ukraine"],
        geographic_frame="",
        availability_warnings=[],
        analyst_note="",
    )
    packet = Packet(
        packet_id="packet-test",
        notice_id="notice-abc",
        scenario_id="desk-case",
        clocks=clocks,
        layers={},
        measurement_snapshot={},
        information_environment={},
        geopolitical_context={},
        collected_evidence=[],
        unknowns=[],
        dependencies=[],
        hypotheses=[],
        collection_log=[],
        product=product,
    )
    path = packet_path(root, "desk-case", "packet-test")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(packet.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return notice


def test_leakage_scan_catches_invasion_language() -> None:
    hits = _leakage_hits("This preceded the full-scale invasion", ["full-scale invasion"])
    assert "full-scale invasion" in hits


def test_only_uniquely_grounded_unescaped_quote_is_repaired() -> None:
    evidence_id = "ev-bc45cd56e49f8138"
    bundle = {
        "items": [
            {
                "id": evidence_id,
                "data": {"day": "2022-02-12", "value": 1.0},
            }
        ]
    }
    raw = "\n".join(
        [
            "{",
            '  "claims": [{',
            '    "quotes": {',
            f'      "{evidence_id}": "value": 1.0"',
            "    }",
            "  }]",
            "}",
        ]
    )
    parsed, repairs = _extract_json_with_grounded_repairs(raw, bundle)
    assert parsed["claims"][0]["quotes"][evidence_id] == '"value": 1.0'
    assert repairs[0]["kind"] == "grounded_unescaped_quote"
    with pytest.raises(json.JSONDecodeError):
        _extract_json_with_grounded_repairs(raw, {"items": []})


def test_rejected_completion_can_be_revalidated_without_model_call(tmp_path) -> None:
    run = tmp_path / "draft_runs" / "attempt"
    run.mkdir(parents=True)
    (run / "input.json").write_text(json.dumps({"prompt_sha256": "prompt"}))
    completion = {"model": "model", "done": True, "done_reason": "stop"}
    (run / "completion.json").write_text(json.dumps(completion))
    (run / "rejected.json").write_text(json.dumps({"reason": "invalid JSON"}))
    recovered = _recoverable_completion(tmp_path, "prompt", "model")
    assert recovered == (completion, str(run / "completion.json"))
    assert _recoverable_completion(tmp_path, "different", "model") is None


def test_draft_writes_sidecar_and_does_not_clobber_report(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OLLAMA_MODEL", "local-test-model")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    _notice(tmp_path)
    save_report(tmp_path, "desk-case", "notice-abc", notes="Human already wrote this.\n")
    content = json.dumps(
        {
            "notes": "Machine draft. Cue only.\n",
            "sections": {"assessment": "Cue."},
            "citations": [],
            "ancr": "Low",
            "leakage_self_check": "none",
        }
    )
    result = run_desk_draft(
        tmp_path,
        "desk-case",
        "notice-abc",
        search=False,
        apply=True,
        chat_transport=FakeChat(content),
    )
    assert result["applied"] is False
    assert (tmp_path / "scenarios/desk-case/interpretation/packet-test/machine_draft.md").is_file()
    saved = load_report(tmp_path, "desk-case", "notice-abc")
    assert "Human already wrote this" in saved["notes"]
    record = json.loads(Path(result["path"]).read_text())
    assert record["provider"] == "ollama"
    assert record["model"] == "local-test-model"
    assert record["raw_response"] == content
    assert record["generation"]["eval_count"] == 12
    assert record["votes"] is False


@pytest.fixture
def ollama_env(monkeypatch):
    for key in (
        "OLLAMA_BASE_URL",
        "OLLAMA_MODEL",
        "OLLAMA_TIMEOUT_SECONDS",
        "OLLAMA_MAX_OUTPUT_TOKENS",
        "OLLAMA_NUM_CTX",
        "XAI_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)


def test_project_env_selects_native_ollama_without_any_api_key(tmp_path, ollama_env):
    (tmp_path / ".env").write_text(
        "OLLAMA_MODEL=qwen3.8:27b-mlx\nOLLAMA_BASE_URL=http://localhost:11435/\n"
        "OLLAMA_TIMEOUT_SECONDS=1200\nOLLAMA_MAX_OUTPUT_TOKENS=2048\n"
    )
    config = ollama_config(tmp_path)
    fake = FakeChat('{"notes":"A cue."}')
    complete_chat(config=config, system="Use the packet.", user="Evidence", transport=fake)
    url, kwargs = fake.requests[0]
    assert url == "http://localhost:11435/api/chat"
    assert "Authorization" not in kwargs["headers"]
    assert kwargs["timeout"] == 1200
    payload = json.loads(kwargs["data"])
    assert payload["model"] == "qwen3.8:27b-mlx"
    assert payload["stream"] is False
    assert payload["think"] is False
    assert payload["format"] == "json"
    assert payload["options"] == {
        "temperature": 0,
        "seed": 42,
        "num_predict": 2048,
        "num_ctx": 32768,
    }


def test_shell_environment_takes_precedence(tmp_path, monkeypatch, ollama_env):
    (tmp_path / ".env").write_text("OLLAMA_MODEL=file-model\n")
    monkeypatch.setenv("OLLAMA_MODEL", "shell-model")
    assert ollama_config(tmp_path).model == "shell-model"


def test_missing_model_fails_before_collection(tmp_path, monkeypatch, ollama_env):
    def forbidden(*args, **kwargs):
        pytest.fail("Invalid configuration must not start search or load a notice")

    monkeypatch.setattr("wsf.draft.run_research", forbidden)
    monkeypatch.setattr("wsf.draft.load_notice", forbidden)
    with pytest.raises(ValueError, match="OLLAMA_MODEL"):
        run_desk_draft(tmp_path, "desk-case", "notice-abc")


@pytest.mark.parametrize(
    "setting,value",
    [
        ("OLLAMA_BASE_URL", "file:///tmp/model"),
        ("OLLAMA_BASE_URL", "http://localhost:11434/api"),
        ("OLLAMA_TIMEOUT_SECONDS", "nan"),
        ("OLLAMA_MAX_OUTPUT_TOKENS", "0"),
        ("OLLAMA_NUM_CTX", "1024"),
    ],
)
def test_invalid_settings_are_actionable(tmp_path, monkeypatch, ollama_env, setting, value):
    monkeypatch.setenv("OLLAMA_MODEL", "model")
    monkeypatch.setenv(setting, value)
    with pytest.raises(ValueError, match="OLLAMA|Ollama"):
        ollama_config(tmp_path)


class FixedResponse:
    def __init__(self, body, status=200):
        self.body = body
        self.status = status
        self.calls = 0

    def post(self, url, **kwargs):
        self.calls += 1
        if isinstance(self.body, Exception):
            raise self.body
        return HttpResponse(url, self.status, self.body, {})


@pytest.mark.parametrize(
    "body,status,expected",
    [
        (b'{"error":"model not found"}', 404, "Ollama HTTP 404"),
        (b'{"error":"server failure"}', 200, "Ollama error"),
        (b"not json", 200, "invalid JSON"),
        (b"[]", 200, "must be an object"),
        (b'{"done":true,"message":{"content":""}}', 200, "empty content"),
        (b'{"done":false,"message":{"content":"partial"}}', 200, "incomplete"),
        (
            b'{"done":true,"done_reason":"length","message":{"content":"partial"}}',
            200,
            "token-limited",
        ),
        (TimeoutError("connection failed"), 200, "Ollama request failed"),
    ],
)
def test_chat_failures_are_clear_and_never_retry_generation(body, status, expected):
    fake = FixedResponse(body, status)
    with pytest.raises(ValueError, match=expected):
        complete_chat(
            config=OllamaConfig("http://localhost:11434", "model"),
            system="system",
            user="packet",
            transport=fake,
        )
    assert fake.calls == 1


def test_token_limited_run_preserves_partial_response(tmp_path, monkeypatch, ollama_env):
    monkeypatch.setenv("OLLAMA_MODEL", "model")
    _notice(tmp_path)
    directory = tmp_path / "scenarios/desk-case/interpretation/packet-test"
    (directory / "machine_draft.md").write_text("Previous draft")
    response = {
        "done": True,
        "done_reason": "length",
        "message": {"content": '{"summary":"partial'},
        "eval_count": 4096,
    }
    with pytest.raises(ValueError, match="partial response was retained"):
        run_desk_draft(
            tmp_path,
            "desk-case",
            "notice-abc",
            search=False,
            chat_transport=FixedResponse(json.dumps(response).encode(), 200),
        )
    rejected = list((directory / "draft_runs").glob("*/rejected_completion.json"))
    assert len(rejected) == 1
    assert json.loads(rejected[0].read_text())["eval_count"] == 4096
    assert (directory / "machine_draft.md").read_text() == "Previous draft"


def test_structured_output_rejection_uses_prompt_json_once():
    class CompatibleChat(FakeChat):
        def post(self, url, **kwargs):
            if not self.requests:
                self.requests.append((url, kwargs))
                return HttpResponse(url, 501, b'{"error":"structured output is unavailable"}', {})
            return super().post(url, **kwargs)

    fake = CompatibleChat('{"notes":"Grounded assessment"}')
    stages = []
    result = complete_chat(
        config=OllamaConfig("http://localhost:11434", "model"),
        system="JSON only",
        user="packet",
        transport=fake,
        progress=lambda stage, completed: stages.append(stage),
    )
    first = json.loads(fake.requests[0][1]["data"])
    second = json.loads(fake.requests[1][1]["data"])
    assert first.pop("format") == "json"
    assert first == second
    assert len(fake.requests) == 2
    assert result["output_mode"] == "prompt_json"
    assert "structured output unavailable" in stages[0]


@pytest.mark.parametrize(
    "message,calls", [("structured output is unavailable", 2), ("other unsupported feature", 1)]
)
def test_compatibility_retry_is_narrow_and_bounded(message, calls):
    fake = FixedResponse(json.dumps({"error": message}).encode(), 501)
    with pytest.raises(ValueError, match="Ollama HTTP 501"):
        complete_chat(
            config=OllamaConfig("http://localhost:11434", "model"),
            system="JSON only",
            user="packet",
            transport=fake,
        )
    assert fake.calls == calls


@pytest.mark.parametrize(
    "content,valid", [('{"notes":"A grounded cue."}', True), ("not JSON", False)]
)
def test_prompt_json_mode_still_validates_and_records_provenance(
    tmp_path, monkeypatch, ollama_env, content, valid
):
    monkeypatch.setenv("OLLAMA_MODEL", "model")
    _notice(tmp_path)
    directory = tmp_path / "scenarios/desk-case/interpretation/packet-test"
    (directory / "machine_draft.md").write_text("Previous draft")

    class PromptChat(FakeChat):
        def post(self, url, **kwargs):
            if not self.requests:
                self.requests.append((url, kwargs))
                return HttpResponse(url, 501, b'{"error":"structured output is unavailable"}', {})
            return super().post(url, **kwargs)

    chat = PromptChat(content)
    stages = []

    def run():
        return run_desk_draft(
            tmp_path,
            "desk-case",
            "notice-abc",
            replay=True,
            search=False,
            chat_transport=chat,
            progress=lambda stage, completed: stages.append((stage, completed)),
        )

    if valid:
        result = run()
        record = json.loads(Path(result["path"]).read_text())
        assert record["output_mode"] == "prompt_json"
        assert [count for _, count in stages] == [0, 2, 2, 3, 4, 5]
    else:
        with pytest.raises(ValueError, match="did not match the assessment structure"):
            run()
        assert (directory / "machine_draft.md").read_text() == "Previous draft"
        assert all(count < 4 for _, count in stages)
    assert len(chat.requests) == 2


@pytest.mark.parametrize("content", ["not JSON", "{}", '{"notes":123}', '{"sections":[]}'])
def test_bad_output_preserves_previous_draft(tmp_path, monkeypatch, ollama_env, content):
    monkeypatch.setenv("OLLAMA_MODEL", "model")
    _notice(tmp_path)
    directory = tmp_path / "scenarios/desk-case/interpretation/packet-test"
    (directory / "machine_draft.json").write_text('{"notes":"Previous draft"}')
    (directory / "machine_draft.md").write_text("Previous draft")
    with pytest.raises(ValueError, match="Ollama draft"):
        run_desk_draft(
            tmp_path, "desk-case", "notice-abc", search=False, chat_transport=FakeChat(content)
        )
    assert (directory / "machine_draft.md").read_text() == "Previous draft"
    assert json.loads((directory / "machine_draft.json").read_text())["notes"] == "Previous draft"


@pytest.mark.parametrize("standalone_notes", ["", "A concise assessment."])
def test_structured_sections_are_saved_as_markdown_with_raw_provenance(
    tmp_path, monkeypatch, ollama_env, standalone_notes
):
    monkeypatch.setenv("OLLAMA_MODEL", "model")
    _notice(tmp_path)
    body = {
        "notes": standalone_notes,
        "sections": {
            "hypotheses": [
                {
                    "hypothesis": "Routine activity",
                    "likelihood": "Realistic possibility",
                    "discriminators": ["Needs baseline validation.", "Check declared activity."],
                }
            ],
            "collected": ["CBR funding spread: 3.7", "Declared activity (14–19 Feb)."],
            "findings": ["Financial anomaly is the strongest cue.", "Critical period is missing."],
        },
    }
    raw = json.dumps(body)
    fake = FakeChat(raw)
    original_packet = packet_path(tmp_path, "desk-case", "packet-test").read_bytes()
    result = run_desk_draft(tmp_path, "desk-case", "notice-abc", search=False, chat_transport=fake)
    record = json.loads(Path(result["path"]).read_text())
    assert record["raw_response"] == raw
    assert record["normalisation"]["converted_sections"] == ["hypotheses", "collected", "findings"]
    assert (
        record["sections"]["collected"]
        == "- CBR funding spread: 3.7\n- Declared activity (14–19 Feb)."
    )
    assert "**hypothesis:** Routine activity" in record["sections"]["hypotheses"]
    assert "Needs baseline validation." in record["sections"]["hypotheses"]
    assert "Critical period is missing." in record["sections"]["findings"]
    if standalone_notes:
        assert result["notes"] == standalone_notes + "\n"
    else:
        assert "Routine activity" in result["notes"]
        assert "CBR funding spread: 3.7" in Path(result["markdown"]).read_text()
    assert len(fake.requests) == 1
    assert packet_path(tmp_path, "desk-case", "packet-test").read_bytes() == original_packet


def test_normalisation_preserves_strings_and_named_scalar_values():
    original = {
        "sections": {
            "assessment": "  Original Markdown.\n",
            "findings": {
                "count": 0,
                "confirmed": False,
                "unknown": None,
                "context": ["A", "B"],
            },
        }
    }
    normalised, converted = _normalise_sections(original)
    assert normalised["sections"]["assessment"] == original["sections"]["assessment"]
    assert converted == ["findings"]
    assert "**count:** 0" in normalised["sections"]["findings"]
    assert "**confirmed:** false" in normalised["sections"]["findings"]
    assert "**unknown:** null" in normalised["sections"]["findings"]
    assert isinstance(original["sections"]["findings"], dict)


@pytest.mark.parametrize("value", [None, 123, True, [123], [None], {"": "unlabelled"}])
def test_malformed_sections_are_not_blindly_stringified(value):
    with pytest.raises(ValueError, match="section"):
        _normalise_sections({"sections": {"findings": value}})


def test_section_nesting_is_bounded():
    value = "text"
    for _ in range(10):
        value = [value]
    with pytest.raises(ValueError, match="nesting"):
        _section_markdown(value)


@pytest.mark.parametrize("value", [[], {}, {"placeholder": []}])
def test_empty_structure_does_not_become_an_assessment(tmp_path, monkeypatch, ollama_env, value):
    monkeypatch.setenv("OLLAMA_MODEL", "model")
    _notice(tmp_path)
    with pytest.raises(ValueError, match="no assessment text"):
        run_desk_draft(
            tmp_path,
            "desk-case",
            "notice-abc",
            search=False,
            chat_transport=FakeChat(json.dumps({"sections": {"findings": value}})),
        )


def test_leakage_in_structured_sections_blocks_apply_even_with_clean_notes(
    tmp_path, monkeypatch, ollama_env
):
    monkeypatch.setenv("OLLAMA_MODEL", "model")
    _notice(tmp_path)
    result = run_desk_draft(
        tmp_path,
        "desk-case",
        "notice-abc",
        search=False,
        apply=True,
        chat_transport=FakeChat(
            json.dumps(
                {
                    "notes": "A cue.",
                    "sections": {"findings": ["full-scale invasion"]},
                }
            )
        ),
    )
    assert "full-scale invasion" in result["leakage"]
    assert result["applied"] is False


@pytest.mark.parametrize("leaky,applied", [(False, False), (True, False)])
def test_apply_does_not_seed_ungrounded_report_even_with_clean_language(
    tmp_path,
    monkeypatch,
    ollama_env,
    leaky,
    applied,
):
    monkeypatch.setenv("OLLAMA_MODEL", "model")
    _notice(tmp_path)
    path = packet_path(tmp_path, "desk-case", "packet-test")
    original_packet = path.read_bytes()
    notice_path = tmp_path / "scenarios/desk-case/notices/notice-abc/notice.json"
    original_notice = notice_path.read_bytes()
    result = run_desk_draft(
        tmp_path,
        "desk-case",
        "notice-abc",
        search=False,
        apply=True,
        chat_transport=FakeChat(
            json.dumps({"notes": "full-scale invasion" if leaky else "A cue."})
        ),
    )
    assert result["applied"] is applied
    assert bool(result["leakage"]) is leaky
    assert path.read_bytes() == original_packet
    # Explicit --apply may attach a report_id, but never changes the trigger or verdict.
    current = json.loads(notice_path.read_bytes())
    original = json.loads(original_notice)
    assert current["trigger"] == original["trigger"]
    assert current["workflow"]["state"] == original["workflow"]["state"]
    if not applied:
        assert notice_path.read_bytes() == original_notice
