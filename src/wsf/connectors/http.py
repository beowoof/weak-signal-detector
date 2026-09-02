from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from http.client import IncompleteRead
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

DEFAULT_HEADERS = {
    "User-Agent": (
        "WeakSignalFusion/0.1 "
        "(https://github.com/beowoof/weak-signal-detector; research poc)"
    )
}


@dataclass(frozen=True)
class HttpResponse:
    url: str
    status: int
    body: bytes
    headers: dict[str, str]


class HttpTransport(Protocol):
    def get(
        self, url: str, *, headers: dict[str, str] | None = None, timeout: float = 60
    ) -> HttpResponse:
        """Return the response for GET url. HTTP error statuses are returned, not raised."""

    def post(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: float = 60,
        data: bytes | None = None,
    ) -> HttpResponse:
        """Return the response for POST url. HTTP error statuses are returned, not raised."""


def _request(
    url: str,
    method: str,
    *,
    headers: dict[str, str] | None,
    timeout: float,
    data: bytes | None = None,
) -> HttpResponse:
    merged = {**DEFAULT_HEADERS, **(headers or {})}
    request = Request(url, data=data, headers=merged, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read()
            status = int(getattr(response, "status", 200))
            raw_headers = dict(response.headers.items()) if response.headers else {}
    except HTTPError as error:
        body = error.read() if error.fp is not None else b""
        status = int(error.code)
        raw_headers = dict(error.headers.items()) if error.headers else {}
    except IncompleteRead as error:
        raise TimeoutError(
            f"request failed: {url}: incomplete read ({len(error.partial)} bytes)"
        ) from error
    except URLError as error:
        raise TimeoutError(f"request failed: {url}: {error.reason}") from error
    headers_out = {key.lower(): value for key, value in raw_headers.items()}
    return HttpResponse(url=url, status=status, body=body, headers=headers_out)


class UrllibTransport:
    def get(
        self, url: str, *, headers: dict[str, str] | None = None, timeout: float = 60
    ) -> HttpResponse:
        return _request(url, "GET", headers=headers, timeout=timeout)

    def post(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: float = 60,
        data: bytes | None = None,
    ) -> HttpResponse:
        return _request(url, "POST", headers=headers, timeout=timeout, data=data)


def get_with_retry(
    transport: HttpTransport,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 60,
    attempts: int = 3,
    retry_statuses: tuple[int, ...] = (429, 500, 502, 503, 504),
    sleep: float = 0.0,
) -> HttpResponse:
    return _retry(
        lambda: transport.get(url, headers=headers, timeout=timeout),
        url=url,
        attempts=attempts,
        retry_statuses=retry_statuses,
        sleep=sleep,
    )


def post_with_retry(
    transport: HttpTransport,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
    timeout: float = 60,
    attempts: int = 3,
    retry_statuses: tuple[int, ...] = (429, 500, 502, 503, 504),
    sleep: float = 0.0,
) -> HttpResponse:
    return _retry(
        lambda: transport.post(url, headers=headers, timeout=timeout, data=data),
        url=url,
        attempts=attempts,
        retry_statuses=retry_statuses,
        sleep=sleep,
    )


def _retry(
    call: Callable[[], HttpResponse],
    *,
    url: str,
    attempts: int,
    retry_statuses: tuple[int, ...],
    sleep: float,
) -> HttpResponse:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            response = call()
        except TimeoutError as error:
            last_error = error
            if attempt + 1 == attempts:
                raise
            if sleep:
                time.sleep(sleep * (attempt + 1))
            continue
        if response.status in retry_statuses and attempt + 1 < attempts:
            if sleep:
                time.sleep(sleep * (attempt + 1))
            continue
        return response
    if last_error:
        raise last_error
    raise TimeoutError(f"request failed after {attempts} attempts: {url}")


def redact_url(url: str) -> str:
    parts = urlsplit(url)
    if not parts.query:
        return url
    redacted = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        lowered = key.lower()
        if "key" in lowered or "token" in lowered or "secret" in lowered:
            redacted.append((key, "REDACTED"))
        else:
            redacted.append((key, value))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(redacted), parts.fragment))
