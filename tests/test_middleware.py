# Copyright 2026 MSPbots.ai
# SPDX-License-Identifier: Apache-2.0
"""Credential middleware tests: missing-header 401 (AC2), and per-request
isolation of X-Axcient-Api-Key across concurrent requests (AC10).
"""

import asyncio

import pytest
from starlette.testclient import TestClient

from axcient_mcp.middleware import CREDENTIAL_HEADER, CredentialMiddleware, current_api_key
from axcient_mcp.server import create_app
from axcient_mcp.settings import Settings


def _make_app():
    settings = Settings()
    return create_app(settings)


def test_health_is_local_and_does_not_require_credentials():
    app = _make_app()
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


def test_missing_credential_header_returns_401_with_required_header_name():
    app = _make_app()
    with TestClient(app) as client:
        resp = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            headers={"Accept": "application/json, text/event-stream"},
        )
        assert resp.status_code == 401
        body = resp.json()
        assert body["required_headers"] == [CREDENTIAL_HEADER]


def test_present_header_reaches_request_context():
    # Drives the middleware directly (no full MCP protocol round trip):
    # confirms the header value lands in the contextvar and is reset after.
    seen = {}

    async def fake_app(scope, receive, send):
        seen["key"] = current_api_key()
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    middleware = CredentialMiddleware(fake_app)

    async def run():
        scope = {"type": "http", "path": "/mcp", "headers": [(b"x-axcient-api-key", b"test-key-123")]}

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            pass

        await middleware(scope, receive, send)

    asyncio.run(run())
    assert seen["key"] == "test-key-123"
    # Outside any request context the contextvar must be back to its default.
    assert current_api_key() is None


@pytest.mark.asyncio
async def test_concurrent_requests_do_not_leak_credential_across_contextvars():
    """Two truly-concurrent requests with different keys must never observe
    each other's credential (AC10). Each request runs as its own asyncio
    Task, which asyncio gives its own copy of the contextvars context, and a
    deliberate await between set() and read() forces interleaving so a
    shared-state bug could not pass by accident.
    """
    seen: dict[str, str | None] = {}

    async def fake_app_factory(name: str):
        async def fake_app(scope, receive, send):
            await asyncio.sleep(0)  # yield control so the other task can run first
            seen[name] = current_api_key()
            await asyncio.sleep(0)
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        return fake_app

    async def drive(name: str, key: str):
        app = await fake_app_factory(name)
        middleware = CredentialMiddleware(app)
        scope = {
            "type": "http",
            "path": "/mcp",
            "headers": [(CREDENTIAL_HEADER.lower().encode(), key.encode())],
        }

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            pass

        await middleware(scope, receive, send)

    await asyncio.gather(
        drive("tenant-a", "key-for-tenant-a"),
        drive("tenant-b", "key-for-tenant-b"),
    )

    assert seen["tenant-a"] == "key-for-tenant-a"
    assert seen["tenant-b"] == "key-for-tenant-b"
    assert current_api_key() is None
