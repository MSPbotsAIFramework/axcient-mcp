# Copyright 2026 MSPbots.ai
# SPDX-License-Identifier: Apache-2.0
"""Organization tool: the single Axcient partner organization tied to the calling API key."""

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from ..client import AxcientApiError
from ..errors import dump_json, to_envelope
from ._common import NO_TOKEN, client_or_none


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def axcient_list_organization() -> str:
        """Return the Axcient partner organization tied to the calling API key.

        The vendor API ties exactly one organization to each key, so this
        always returns a single-item collection (named list_ for naming
        consistency with the other resource tools).
        """
        client = client_or_none()
        if client is None:
            return NO_TOKEN
        try:
            result = await client.get("/organization")
        except AxcientApiError as exc:
            return to_envelope(exc)
        if isinstance(result, list):
            orgs = result
        elif result:
            orgs = [result]
        else:
            orgs = []
        return dump_json({"organizations": orgs, "has_more": False})
