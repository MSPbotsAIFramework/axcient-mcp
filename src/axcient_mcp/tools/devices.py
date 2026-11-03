# Copyright 2026 MSPbots.ai
# SPDX-License-Identifier: Apache-2.0
"""Device tools: inventory, restore points, and AutoVerify status."""

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
    async def axcient_list_devices(
        client_id: Annotated[
            int | None, Field(description="Optional — scope to one client's devices.")
        ] = None,
        limit: Annotated[
            int | None, Field(description="Max rows to return (default 50, hard max 200).")
        ] = None,
        cursor: Annotated[
            str | None, Field(description="Opaque cursor from a previous call's has_more page.")
        ] = None,
    ) -> str:
        """List protected devices, optionally scoped to one client."""
        client = client_or_none()
        if client is None:
            return NO_TOKEN
        path = f"/client/{client_id}/device" if client_id is not None else "/device"
        try:
            result = await client.get(path)
        except AxcientApiError as exc:
            return to_envelope(exc)
        items = _as_items(result, "devices")
        page, has_more, next_cursor = paginate(items, limit, cursor)
        out: dict = {"devices": page, "has_more": has_more}
        if next_cursor:
            out["cursor"] = next_cursor
        return dump_json(out)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def axcient_get_device(
        device_id: Annotated[int, Field(description="Axcient device ID.")],
    ) -> str:
        """Get one device's detail, including current and previous backup health status."""
        client = client_or_none()
        if client is None:
            return NO_TOKEN
        try:
            result = await client.get(f"/device/{device_id}")
        except AxcientApiError as exc:
            return to_envelope(exc)
        return dump_json(result)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def axcient_get_device_restore_points(
        device_id: Annotated[int, Field(description="Axcient device ID.")],
    ) -> str:
        """List a device's available restore points (backup snapshots in time)."""
        client = client_or_none()
        if client is None:
            return NO_TOKEN
        try:
            result = await client.get(f"/device/{device_id}/restore_point")
        except AxcientApiError as exc:
            return to_envelope(exc)
        items = _as_items(result, "restore_points")
        return dump_json({"restore_points": items, "has_more": False})

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def axcient_get_device_autoverify(
        device_id: Annotated[int, Field(description="Axcient device ID.")],
    ) -> str:
        """Get a device's latest AutoVerify (screenshot-verified recovery test) result and history."""
        client = client_or_none()
        if client is None:
            return NO_TOKEN
        try:
            result = await client.get(f"/device/{device_id}/autoverify")
        except AxcientApiError as exc:
            return to_envelope(exc)
        return dump_json(result)
