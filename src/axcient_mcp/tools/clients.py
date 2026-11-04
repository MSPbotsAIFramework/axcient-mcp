# Copyright 2026 MSPbots.ai
# SPDX-License-Identifier: Apache-2.0
"""Client (end-customer) tools."""

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from ..client import AxcientApiError
from ..errors import dump_json, to_envelope
from ._common import NO_TOKEN, client_or_none, paginate


def _as_items(result, key: str) -> list:
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        return result.get(key, []) or []
    return []


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def axcient_list_clients(
        limit: Annotated[
            int | None, Field(description="Max rows to return (default 50, hard max 200).")
        ] = None,
        cursor: Annotated[
            str | None, Field(description="Opaque cursor from a previous call's has_more page.")
        ] = None,
    ) -> str:
        """List the end-customer clients visible to the calling organization's API key."""
        client = client_or_none()
        if client is None:
            return NO_TOKEN
        try:
            result = await client.get("/client")
        except AxcientApiError as exc:
            return to_envelope(exc)
        items = _as_items(result, "clients")
        page, has_more, next_cursor = paginate(items, limit, cursor)
        out: dict = {"clients": page, "has_more": has_more}
        if next_cursor:
            out["cursor"] = next_cursor
        return dump_json(out)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def axcient_get_client(
        client_id: Annotated[int, Field(description="Axcient client (end-customer) ID.")],
    ) -> str:
        """Get one client's detail, including its protected-systems counters."""
        client = client_or_none()
        if client is None:
            return NO_TOKEN
        try:
            result = await client.get(f"/client/{client_id}")
        except AxcientApiError as exc:
            return to_envelope(exc)
        return dump_json(result)
