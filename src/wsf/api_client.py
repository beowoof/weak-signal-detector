"""Host-side client for operations owned by the running desk API.

Never falls back to executing work locally or retries a mutating request.
"""

from __future__ import annotations

import json
import math
import os
import time
from collections.abc import Callable
from http.client import HTTPException
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from wsf.connectors.http import HttpTransport, UrllibTransport
from wsf.env import load_project_env


def _api_config(project_root: Path) -> tuple[str, float]:
    load_project_env(project_root)
    base = (os.environ.get("WSD_API_BASE_URL") or "http://127.0.0.1:8000").strip().rstrip("/")
    parts = urlsplit(base)
    if (
        parts.scheme not in {"http", "https"}
        or not parts.hostname
        or parts.username
        or parts.password
        or parts.query
        or parts.fragment
        or parts.path
    ):
        raise ValueError("WSD_API_BASE_URL must be an HTTP(S) server root URL")
    try:
        timeout = float(os.environ.get("WSD_API_TIMEOUT_SECONDS", "1800"))
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError
    except ValueError as exc:
        raise ValueError("WSD_API_TIMEOUT_SECONDS must be a positive finite number") from exc
    return base, timeout


def post_api(
    project_root: Path,
    endpoint: str,
    body: dict[str, Any],
    *,
    transport: HttpTransport | None = None,
) -> dict[str, Any]:
    base, timeout = _api_config(project_root)
    client = transport or UrllibTransport()
    try:
        response = client.post(
            base + endpoint,
            headers={"Content-Type": "application/json"},
            data=json.dumps(body).encode("utf-8"),
            timeout=timeout,
        )
    except (TimeoutError, OSError) as exc:
        raise ValueError(
            f"Desk API request failed at {base}. Check that the API container is running "
            "and WSD_API_BASE_URL is reachable. No local fallback or automatic retry was "
            "attempted. If the connection timed out, server work may still be running; "
            "check the API logs and draft artefacts before retrying."
        ) from exc
    try:
        payload = json.loads(response.body.decode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise ValueError(
            f"Desk API returned a non-JSON response (HTTP {response.status}). "
            "Check WSD_API_BASE_URL; it must point to the API, not Ollama or the UI."
        ) from exc
    if response.status >= 400:
        detail = payload.get("detail", payload) if isinstance(payload, dict) else payload
        rendered = detail if isinstance(detail, str) else json.dumps(detail)
        raise ValueError(f"Desk API HTTP {response.status}: {rendered}")
    if not isinstance(payload, dict):
        raise ValueError("Desk API returned an unexpected response; expected a JSON object")
    return payload


def stream_draft_api(
    project_root: Path,
    body: dict[str, Any],
    *,
    progress: Callable[[dict[str, Any]], None],
) -> dict[str, Any]:
    base, timeout = _api_config(project_root)
    request = Request(
        base + "/api/packet/draft/stream",
        method="POST",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Accept": "application/x-ndjson"},
    )
    started = time.monotonic()
    try:
        with urlopen(request, timeout=timeout) as response:
            if "application/x-ndjson" not in response.headers.get("Content-Type", ""):
                raise ValueError(
                    "Desk API returned the wrong stream format; check WSD_API_BASE_URL"
                )
            for line in response:
                if time.monotonic() - started > timeout:
                    raise TimeoutError("Draft observation deadline exceeded")
                try:
                    event = json.loads(line)
                except (ValueError, UnicodeError) as exc:
                    raise ValueError("Desk API sent invalid progress JSON") from exc
                if not isinstance(event, dict):
                    raise ValueError("Desk API sent an invalid progress event")
                if event.get("type") == "result" and isinstance(event.get("result"), dict):
                    return event["result"]
                if event.get("type") == "error":
                    raise ValueError(f"Desk API HTTP {event.get('status')}: {event.get('detail')}")
                if event.get("type") != "progress":
                    raise ValueError("Desk API sent an unknown progress event")
                progress(event)
            raise OSError("Draft stream ended before a result")
    except HTTPError as exc:
        detail = exc.read(1000).decode(errors="replace")
        raise ValueError(f"Desk API HTTP {exc.code}: {detail}") from exc
    except (OSError, HTTPException) as exc:
        raise ValueError(
            f"Desk API stream failed at {base}. No retry or local fallback was attempted. "
            "Server work may still be running; check API logs and draft artefacts before retrying."
        ) from exc
