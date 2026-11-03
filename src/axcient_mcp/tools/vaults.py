# Copyright 2026 MSPbots.ai
# SPDX-License-Identifier: Apache-2.0
"""Vault tools: cloud backup vault inventory and the one configurable alert setting."""

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
    async def axcient_list_vaults(
        limit: Annotated[
            int | None, Field(description="Max rows to return (default 50, hard max 200).")
        ] = None,
        cursor: Annotated[
            str | None, Field(description="Opaque cursor from a previous call's has_more page.")
        ] = None,
    ) -> str:
        """List cloud backup vaults visible to the calling organization's API key."""
        client = client_or_none()
        if client is None:
            return NO_TOKEN
        try:
            result = await client.get("/vault")
        except AxcientApiError as exc:
            return to_envelope(exc)
        items = _as_items(result, "vaults")
        page, has_more, next_cursor = paginate(items, limit, cursor)
        out: dict = {"vaults": page, "has_more": has_more}
        if next_cursor:
            out["cursor"] = next_cursor
        return dump_json(out)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def axcient_get_vault(
        vault_id: Annotated[int, Field(description="Axcient vault ID.")],
    ) -> str:
        """Get one vault's detail: connectivity status, storage, and replication data."""
        client = client_or_none()
        if client is None:
            return NO_TOKEN
        try:
            result = await client.get(f"/vault/{vault_id}")
        except AxcientApiError as exc:
            return to_envelope(exc)
        return dump_json(result)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def axcient_get_vault_connectivity_threshold(
        vault_id: Annotated[int, Field(description="Axcient vault ID.")],
    ) -> str:
        """Get a vault's connectivity-alert threshold (minutes offline before alerting)."""
        client = client_or_none()
        if client is None:
            return NO_TOKEN
        try:
            result = await client.get(f"/vault/{vault_id}/threshold/connectivity")
        except AxcientApiError as exc:
            return to_envelope(exc)
        return dump_json(result)

    @mcp.tool(annotations=ToolAnnotations(idempotentHint=True))
    async def axcient_set_vault_connectivity_threshold(
        vault_id: Annotated[int, Field(description="Axcient vault ID.")],
        value: Annotated[
            int, Field(description="New connectivity-alert threshold (vendor-defined unit, typically minutes offline).")
        ],
        enabled: Annotated[bool, Field(description="Whether the connectivity alert is enabled at this threshold.")],
    ) -> str:
        """Set a vault's connectivity-alert threshold.

        Replaces the whole setting in one call; repeating it with the same
        arguments is a no-op in effect, so it is safe to retry.
        """
        client = client_or_none()
        if client is None:
            return NO_TOKEN
        try:
            result = await client.post(
                f"/vault/{vault_id}/threshold/connectivity",
                json_body={"value": value, "enabled": enabled},
            )
        except AxcientApiError as exc:
            return to_envelope(exc)
        return dump_json(result)
