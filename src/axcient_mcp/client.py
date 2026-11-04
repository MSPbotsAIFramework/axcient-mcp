# Copyright 2026 MSPbots.ai
# SPDX-License-Identifier: Apache-2.0
"""Thin async client for the Axcient x360Recover REST API.

Reference: a community-maintained OpenAPI 3.0 spec for this exact API
(github.com/adamburley/AxcientAPI, x360Recover.yaml, spec v0.3.1), corroborated
by a live, unauthenticated probe against the real base URL during design
(docs/tickets/PRD-21270.md "Current state"): an unauthenticated GET 403s with
"Missing Authentication Token" (AWS API Gateway, no matching route) and a GET
with a bogus x-api-key value on a real route 401s "Unauthorized" — confirming
both the base URL and the x-api-key auth header name. Axcient's own
human-readable endpoint reference (developer.axcient.com) is a client-rendered
SPA that could not be scraped read-only at design time.

If a real partner API key later proves a response field or pagination
parameter differs from what is assumed here, only this module's
request/response handling changes — the tool-facing contract in tools/*.py
does not (see docs/tickets/PRD-21270.md "Decisions made by DEV01").
"""

import asyncio
from typing import Any

import httpx

BASE_URL = "https://axapi.axcient.com/x360recover"

_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3
_MAX_BACKOFF_SECONDS = 20.0

# One shared connection pool for the process lifetime (SOP section 5: reuse a
# client, don't open one per call). It holds no credentials — the API key
# travels per-call as a request header built from the caller's own request
# context (see middleware.py) — so sharing this pool across tenants and
# concurrent requests is safe.
_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=_TIMEOUT)
    return _http_client


class AxcientApiError(Exception):
    """Raised for any non-2xx response or network failure.

    Tools catch this and map it to the structured error envelope (see
    errors.py) — it never propagates out of a tool handler.
    """

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Axcient API error {status_code}: {message}")


class AxcientClient:
    """Wraps one tenant's partner API key against the x360Recover REST API."""

    def __init__(self, api_key: str):
        self._api_key = api_key

    def _headers(self) -> dict[str, str]:
        return {"x-api-key": self._api_key, "Accept": "application/json"}

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self._request("GET", path, params=params)

    async def post(self, path: str, json_body: Any = None) -> Any:
        return await self._request("POST", path, json_body=json_body)

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
    ) -> Any:
        client = _get_http_client()
        url = f"{BASE_URL}{path}"
        clean_params = {k: v for k, v in (params or {}).items() if v is not None}
        headers = self._headers()

        for attempt in range(_MAX_RETRIES + 1):
            try:
                resp = await client.request(method, url, headers=headers, params=clean_params, json=json_body)
            except httpx.RequestError as exc:
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(min(2**attempt, _MAX_BACKOFF_SECONDS))
                    continue
                raise AxcientApiError(0, f"Could not reach Axcient: {exc or type(exc).__name__}") from exc

            if resp.status_code in _RETRYABLE_STATUS and attempt < _MAX_RETRIES:
                await asyncio.sleep(self._retry_delay(resp, attempt))
                continue

            return self._handle(resp)

        # Unreachable: the loop above always returns or raises. Kept so type
        # checkers see every path return, and as a guard against future edits.
        raise AxcientApiError(0, "request failed with no response")

    def _retry_delay(self, resp: httpx.Response, attempt: int) -> float:
        retry_after = resp.headers.get("Retry-After")
        if retry_after:
            try:
                return min(float(retry_after), _MAX_BACKOFF_SECONDS)
            except ValueError:
                pass
        return min(2**attempt, _MAX_BACKOFF_SECONDS)

    def _handle(self, resp: httpx.Response) -> Any:
        if resp.status_code == 204:
            return {}
        try:
            body = resp.json()
        except ValueError:
            body = None
        if resp.status_code >= 400:
            raise AxcientApiError(resp.status_code, self._extract_message(body, resp))
        return body if body is not None else {}

    def _extract_message(self, body: Any, resp: httpx.Response) -> str:
        if isinstance(body, dict):
            for key in ("message", "error", "detail"):
                value = body.get(key)
                if isinstance(value, str) and value:
                    return value
        text = resp.text.strip()[:300]
        return text or f"Axcient returned {resp.status_code} with no body"
