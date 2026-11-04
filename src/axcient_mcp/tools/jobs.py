# Copyright 2026 MSPbots.ai
# SPDX-License-Identifier: Apache-2.0
"""Backup job tools: per-device job status and run history."""

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
    async def axcient_list_backup_jobs(
        client_id: Annotated[int, Field(description="Axcient client ID that owns the device.")],
        device_id: Annotated[int, Field(description="Axcient device ID.")],
        limit: Annotated[
            int | None, Field(description="Max rows to return (default 50, hard max 200).")
        ] = None,
        cursor: Annotated[
            str | None, Field(description="Opaque cursor from a previous call's has_more page.")
        ] = None,
    ) -> str:
        """List backup jobs configured on one device."""
        client = client_or_none()
        if client is None:
            return NO_TOKEN
        try:
            result = await client.get(f"/client/{client_id}/device/{device_id}/job")
        except AxcientApiError as exc:
            return to_envelope(exc)
        items = _as_items(result, "jobs")
        page, has_more, next_cursor = paginate(items, limit, cursor)
        out: dict = {"jobs": page, "has_more": has_more}
        if next_cursor:
            out["cursor"] = next_cursor
        return dump_json(out)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def axcient_get_backup_job(
        client_id: Annotated[int, Field(description="Axcient client ID that owns the device.")],
        device_id: Annotated[int, Field(description="Axcient device ID.")],
        job_id: Annotated[int, Field(description="Axcient backup job ID.")],
    ) -> str:
        """Get one backup job's configuration, thresholds, and current health status."""
        client = client_or_none()
        if client is None:
            return NO_TOKEN
        try:
            result = await client.get(f"/client/{client_id}/device/{device_id}/job/{job_id}")
        except AxcientApiError as exc:
            return to_envelope(exc)
        return dump_json(result)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def axcient_get_backup_job_history(
        client_id: Annotated[int, Field(description="Axcient client ID that owns the device.")],
        device_id: Annotated[int, Field(description="Axcient device ID.")],
        job_id: Annotated[int, Field(description="Axcient backup job ID.")],
        limit: Annotated[
            int | None, Field(description="Max history rows to return (default 50, hard max 200).")
        ] = None,
    ) -> str:
        """List a backup job's run history (per-run status, timing, and restore-point count)."""
        client = client_or_none()
        if client is None:
            return NO_TOKEN
        try:
            result = await client.get(f"/client/{client_id}/device/{device_id}/job/{job_id}/history")
        except AxcientApiError as exc:
            return to_envelope(exc)
        items = _as_items(result, "history")
        page, has_more, _next_cursor = paginate(items, limit, None)
        return dump_json({"history": page, "has_more": has_more})
