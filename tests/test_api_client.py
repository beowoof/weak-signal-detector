import io
import json
from urllib.error import HTTPError

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from dashboard import server
from wsf.api_client import post_api
from wsf.cli import app
from wsf.connectors.http import HttpResponse
from wsf.research import ResearchLimits


@pytest.fixture(autouse=True)
def clean_api_env(monkeypatch):
    for key in ("WSD_API_BASE_URL", "WSD_API_TIMEOUT_SECONDS"):
        # Register restoration even when dotenv later sets an initially absent key.
        monkeypatch.setenv(key, "")
        monkeypatch.delenv(key, raising=False)


class FakeTransport:
    def __init__(self, body=b'{"ok": true}', status=200, error=None):
        self.body, self.status, self.error = body, status, error
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.error:
            raise self.error
        return HttpResponse(url, self.status, self.body, {})


def test_default_api_request(tmp_path):
    transport = FakeTransport()
    assert post_api(tmp_path, "/api/packet/draft", {"scenario": "case"}, transport=transport) == {
        "ok": True
    }
    assert len(transport.calls) == 1
    url, kwargs = transport.calls[0]
    assert url == "http://127.0.0.1:8000/api/packet/draft"
    assert kwargs["timeout"] == 1800
    assert kwargs["headers"] == {"Content-Type": "application/json"}
    assert json.loads(kwargs["data"]) == {"scenario": "case"}


def test_project_env_and_export_precedence(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        "WSD_API_BASE_URL=http://api:8000/\nWSD_API_TIMEOUT_SECONDS=45\n"
    )
    transport = FakeTransport()
    post_api(tmp_path, "/api/packet/draft", {}, transport=transport)
    assert transport.calls[0][0] == "http://api:8000/api/packet/draft"
    assert transport.calls[0][1]["timeout"] == 45
    monkeypatch.setenv("WSD_API_BASE_URL", "http://localhost:9000")
    post_api(tmp_path, "/api/packet/draft", {}, transport=transport)
    assert transport.calls[1][0] == "http://localhost:9000/api/packet/draft"


@pytest.mark.parametrize(
    "value", ["file:///tmp/api", "http://api/path", "http://user:secret@api", "http://api?key=x"]
)
def test_bad_api_url(tmp_path, monkeypatch, value):
    monkeypatch.setenv("WSD_API_BASE_URL", value)
    transport = FakeTransport()
    with pytest.raises(ValueError, match="server root URL"):
        post_api(tmp_path, "/api/packet/draft", {}, transport=transport)
    assert not transport.calls


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf", "bad"])
def test_bad_timeout(tmp_path, monkeypatch, value):
    monkeypatch.setenv("WSD_API_TIMEOUT_SECONDS", value)
    with pytest.raises(ValueError, match="positive finite"):
        post_api(tmp_path, "/api/packet/draft", {}, transport=FakeTransport())


def test_no_retry_on_timeout(tmp_path):
    transport = FakeTransport(error=TimeoutError("slow"))
    with pytest.raises(ValueError, match="server work may still be running"):
        post_api(tmp_path, "/api/packet/draft", {}, transport=transport)
    assert len(transport.calls) == 1


@pytest.mark.parametrize(
    ("body", "status", "message"),
    [
        (b'{"detail":"Unknown notice"}', 404, "HTTP 404: Unknown notice"),
        (b'{"detail":[{"msg":"field required"}]}', 422, "field required"),
        (b"<html>wrong server</html>", 200, "non-JSON"),
        (b"[]", 200, "expected a JSON object"),
    ],
)
def test_response_errors(tmp_path, body, status, message):
    with pytest.raises(ValueError, match=message):
        post_api(tmp_path, "/api/packet/draft", {}, transport=FakeTransport(body, status))


@pytest.mark.parametrize("leakage", [[], ["outcome-term"]])
@pytest.mark.parametrize("flags", [[], ["--replay", "--no-search", "--apply"]])
def test_cli_routes_through_api(tmp_path, monkeypatch, leakage, flags):
    host_root, api_root = tmp_path / "host", tmp_path / "server"
    host_root.mkdir()
    api_root.mkdir()
    monkeypatch.chdir(host_root)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://invalid-host-setting:11434")
    calls = []

    def draft(root, scenario, notice_id, **kwargs):
        progress = kwargs.pop("progress")
        progress("Ollama generating", 2)
        calls.append((root, scenario, notice_id, kwargs))
        return {
            "notice_id": notice_id,
            "packet_id": "packet-test",
            "path": "/app/scenarios/case/machine_draft.json",
            "markdown": "/app/scenarios/case/machine_draft.md",
            "provider": "ollama",
            "model": "server-model",
            "leakage": leakage,
            "applied": kwargs["apply"],
            "n_citations": 2,
        }

    monkeypatch.setattr(server, "run_desk_draft", draft)

    def forbidden_local(*args, **kwargs):
        raise AssertionError("CLI must not run a local draft")

    monkeypatch.setattr("wsf.draft.run_desk_draft", forbidden_local)
    client = TestClient(server.create_app(api_only=True, project_root=api_root))

    def bridge(request, **kwargs):
        assert request.full_url == "http://127.0.0.1:8000/api/packet/draft/stream"
        body = json.loads(request.data)
        assert set(body) == {"scenario", "notice_id", "replay", "search", "apply"}
        response = client.post("/api/packet/draft/stream", json=body)
        return StreamResponse(response.content)

    monkeypatch.setattr("wsf.api_client.urlopen", bridge)
    result = CliRunner().invoke(
        app, ["packet", "draft", "--scenario", "case", "--notice", "notice-test", *flags]
    )
    assert result.exit_code == (2 if leakage else 0), result.output
    output = json.loads(result.stdout)
    assert output["model"] == "server-model"
    assert output["path"].startswith("/app/")
    assert output["votes"] is False
    assert output["leakage"] == leakage
    assert "Ollama generating" in result.stderr
    assert "2/5 stages" in result.stderr
    assert calls == [
        (
            api_root,
            "case",
            "notice-test",
            {
                "replay": bool(flags),
                "search": not bool(flags),
                    "apply": bool(flags),
                    "research_limits": ResearchLimits(),
            },
        )
    ]
    assert not list(host_root.iterdir())


@pytest.mark.parametrize(
    "transport",
    [
        FakeTransport(error=OSError("connection refused")),
        FakeTransport(b'{"detail":"Ollama is unavailable"}', 400),
        FakeTransport(b"{}"),
    ],
)
def test_cli_reports_api_failure(tmp_path, monkeypatch, transport):
    monkeypatch.chdir(tmp_path)

    def bridge(request, **kwargs):
        response = transport.post(request.full_url)
        if response.status >= 400:
            raise HTTPError(
                request.full_url, response.status, "failed", {}, io.BytesIO(response.body)
            )
        return StreamResponse(response.body)

    monkeypatch.setattr("wsf.api_client.urlopen", bridge)
    result = CliRunner().invoke(
        app, ["packet", "draft", "--scenario", "case", "--notice", "notice-test"]
    )
    assert result.exit_code == 1
    assert "error: Desk API" in result.output
    assert len(transport.calls) == 1


class StreamResponse(io.BytesIO):
    headers = {"Content-Type": "application/x-ndjson"}


@pytest.mark.parametrize("quiet", [False, True])
def test_cli_quiet_and_midstream_error(tmp_path, monkeypatch, quiet):
    monkeypatch.chdir(tmp_path)
    events = [
        {"type": "progress", "job_id": "Job-test", "stage": "Searching", "completed": 1},
        {"type": "error", "status": 400, "detail": "Ollama failed"},
    ]
    monkeypatch.setattr(
        "wsf.api_client.urlopen",
        lambda *a, **kw: StreamResponse(
            "".join(json.dumps(event) + "\n" for event in events).encode()
        ),
    )
    result = CliRunner().invoke(
        app,
        [
            "packet",
            "draft",
            "--scenario",
            "case",
            "--notice",
            "notice-test",
            *(["--quiet"] if quiet else []),
        ],
    )
    assert result.exit_code == 1
    assert result.stdout == ""
    assert "Desk API HTTP 400: Ollama failed" in result.stderr
    assert ("Job-test" in result.stderr) is not quiet


def test_stream_disconnect_does_not_retry(tmp_path, monkeypatch):
    from wsf.api_client import stream_draft_api

    calls = []

    def disconnected(*args, **kwargs):
        calls.append(args)
        return StreamResponse(b'{"type":"progress","stage":"Generating"}\n')

    monkeypatch.setattr("wsf.api_client.urlopen", disconnected)
    with pytest.raises(ValueError, match="Server work may still be running"):
        stream_draft_api(tmp_path, {}, progress=lambda event: None)
    assert len(calls) == 1


def test_stream_deadline_is_not_extended_by_heartbeats(tmp_path, monkeypatch):
    from wsf.api_client import stream_draft_api

    monkeypatch.setenv("WSD_API_TIMEOUT_SECONDS", "1")
    ticks = iter([0, 2])
    monkeypatch.setattr("wsf.api_client.time.monotonic", lambda: next(ticks))
    monkeypatch.setattr(
        "wsf.api_client.urlopen",
        lambda *a, **kw: StreamResponse(b'{"type":"progress","stage":"Generating"}\n'),
    )
    with pytest.raises(ValueError, match="Server work may still be running"):
        stream_draft_api(tmp_path, {}, progress=lambda event: None)
