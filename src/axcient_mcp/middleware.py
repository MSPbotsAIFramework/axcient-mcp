# Copyright 2026 MSPbots.ai
# SPDX-License-Identifier: Apache-2.0
"""Per-request credential isolation.

Reads X-Axcient-Api-Key off each /mcp request and stores it in a ContextVar
for the lifetime of that request only. asyncio copies the context per task,
so concurrent requests on the same server instance never observe each
other's key (AC10) — there is no global or module-level variable holding a
credential anywhere in this service.

Never falls back to an environment variable: this is a single container
serving many tenants concurrently, and a tenant's key is only ever valid for
the request that carried it (SOP section 3.1).
"""

import contextvars

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

CREDENTIAL_HEADER = "X-Axcient-Api-Key"

_api_key_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("axcient_api_key", default=None)


def current_api_key() -> str | None:
    """The API key bound to the in-flight request, or None outside a request context."""
    return _api_key_var.get()


def _missing_credential_response() -> JSONResponse:
    return JSONResponse(
        {
            "error": "Missing credentials",
            "message": f"Send the Axcient partner API key in the {CREDENTIAL_HEADER} header.",
            "required_headers": [CREDENTIAL_HEADER],
            "optional_headers": [],
        },
        status_code=401,
    )


class CredentialMiddleware:
    """Reads X-Axcient-Api-Key on /mcp requests and binds it to the request context."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope.get("path", "").startswith("/mcp"):
            await self.app(scope, receive, send)
            return

        api_key = Request(scope).headers.get(CREDENTIAL_HEADER)
        if not api_key:
            response = _missing_credential_response()
            await response(scope, receive, send)
            return

        token = _api_key_var.set(api_key)
        try:
            await self.app(scope, receive, send)
        finally:
            _api_key_var.reset(token)
