# Copyright 2026 MSPbots.ai
# SPDX-License-Identifier: Apache-2.0
"""Appliance tools: on-prem backup appliance inventory."""

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
    async def axcient_list_appliances(
        client_id: Annotated[
            int | None, Field(description="Optional — scope to one client's appliances.")
        ] = None,
        limit: Annotated[
            int | None, Field(description="Max rows to return (default 50, hard max 200).")
        ] = None,
        cursor: Annotated[
            str | None, Field(description="Opaque cursor from a previous call's has_more page.")
        ] = None,
    ) -> str:
        """List backup appliances, optionally scoped to one client."""
        client = client_or_none()
        if client is None:
            return NO_TOKEN
        path = f"/client/{client_id}/appliance" if client_id is not None else "/appliance"
        try:
            result = await client.get(path)
        except AxcientApiError as exc:
            return to_envelope(exc)
        items = _as_items(result, "appliances")
        page, has_more, next_cursor = paginate(items, limit, cursor)
        out: dict = {"appliances": page, "has_more": has_more}
        if next_cursor:
            out["cursor"] = next_cursor
        return dump_json(out)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def axcient_get_appliance(
        appliance_id: Annotated[int, Field(description="Axcient appliance ID.")],
        include_devices: Annotated[
            bool,
            Field(description="Include the list of devices backing up to this appliance (default true)."),
        ] = True,
    ) -> str:
        """Get one appliance's detail: tunnel/connectivity status and storage usage."""
        client = client_or_none()
        if client is None:
            return NO_TOKEN
        try:
            result = await client.get(f"/appliance/{appliance_id}", params={"include_devices": include_devices})
        except AxcientApiError as exc:
            return to_envelope(exc)
        return dump_json(result)
