# Copyright 2026 MSPbots.ai
# SPDX-License-Identifier: Apache-2.0
"""tools/list snapshot + error-envelope mapping tests.

No real network calls: tool enumeration goes through FastMCP's in-process
list_tools()/call_tool(), and vendor responses are mocked with respx against
the real base URL (axcient_mcp.client.BASE_URL). Per-request credentials are
supplied by setting the same ContextVar the credential middleware sets
(axcient_mcp.middleware._api_key_var), the same technique test_middleware.py
uses to verify the middleware itself.
"""

import json

import pytest
import respx
from httpx import Response

from axcient_mcp.client import BASE_URL
from axcient_mcp.middleware import _api_key_var
from axcient_mcp.server import create_mcp_server
from axcient_mcp.settings import Settings

# required params + annotation hints expected for each of the 16 tools.
# Any signature change here is a breaking contract change (SOP section 13).
EXPECTED_TOOLS = {
    "axcient_list_organization": (set(), {"readOnlyHint": True}),
    "axcient_list_clients": (set(), {"readOnlyHint": True}),
    "axcient_get_client": ({"client_id"}, {"readOnlyHint": True}),
    "axcient_list_devices": (set(), {"readOnlyHint": True}),
    "axcient_get_device": ({"device_id"}, {"readOnlyHint": True}),
    "axcient_get_device_restore_points": ({"device_id"}, {"readOnlyHint": True}),
    "axcient_get_device_autoverify": ({"device_id"}, {"readOnlyHint": True}),
    "axcient_list_appliances": (set(), {"readOnlyHint": True}),
    "axcient_get_appliance": ({"appliance_id"}, {"readOnlyHint": True}),
    "axcient_list_vaults": (set(), {"readOnlyHint": True}),
    "axcient_get_vault": ({"vault_id"}, {"readOnlyHint": True}),
    "axcient_get_vault_connectivity_threshold": ({"vault_id"}, {"readOnlyHint": True}),
    "axcient_set_vault_connectivity_threshold": (
        {"vault_id", "value", "enabled"},
        {"idempotentHint": True, "destructiveHint": False},
    ),
    "axcient_list_backup_jobs": ({"client_id", "device_id"}, {"readOnlyHint": True}),
    "axcient_get_backup_job": ({"client_id", "device_id", "job_id"}, {"readOnlyHint": True}),
    "axcient_get_backup_job_history": ({"client_id", "device_id", "job_id"}, {"readOnlyHint": True}),
}


def _result_text(call_tool_result) -> str:
    """call_tool() returns (content_blocks, {'result': str}); tools always return a string."""
    _, structured = call_tool_result
    return structured["result"]


@pytest.mark.asyncio
async def test_tools_list_snapshot():
    mcp = create_mcp_server(Settings())
    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    assert names == set(EXPECTED_TOOLS), f"unexpected tool set: {names}"
    assert len(tools) == 16

    by_name = {t.name: t for t in tools}
    for name, (expected_required, expected_annotations) in EXPECTED_TOOLS.items():
        tool = by_name[name]
        required = set(tool.inputSchema.get("required", []))
        assert required == expected_required, f"{name}: required={required}"

        ann = tool.annotations
        for hint, value in expected_annotations.items():
            actual = getattr(ann, hint, None) if ann is not None else None
            assert actual == value, f"{name}: {hint}={actual}, expected {value}"

        description = tool.description or ""
        first_line = description.strip().splitlines()[0]
        assert len(first_line) <= 100, f"{name}: first line too long ({len(first_line)}): {first_line!r}"
        assert len(description) <= 500, f"{name}: description too long ({len(description)} chars)"


@pytest.mark.asyncio
async def test_service_instructions_present_and_bounded():
    mcp = create_mcp_server(Settings())
    assert mcp.instructions
    assert len(mcp.instructions) <= 1500


@pytest.mark.asyncio
@respx.mock
async def test_vendor_401_maps_to_unauthorized_envelope():
    respx.get(f"{BASE_URL}/device/999").mock(return_value=Response(401, json={"message": "Unauthorized"}))
    mcp = create_mcp_server(Settings())
    token = _api_key_var.set("bad-key")
    try:
        result = await mcp.call_tool("axcient_get_device", {"device_id": 999})
    finally:
        _api_key_var.reset(token)
    envelope = json.loads(_result_text(result))
    assert envelope["error"]["code"] == "unauthorized"
    assert envelope["error"]["retryable"] is False


@pytest.mark.asyncio
@respx.mock
async def test_vendor_404_maps_to_not_found_envelope():
    respx.get(f"{BASE_URL}/device/404").mock(return_value=Response(404, json={"message": "device not found"}))
    mcp = create_mcp_server(Settings())
    token = _api_key_var.set("a-key")
    try:
        result = await mcp.call_tool("axcient_get_device", {"device_id": 404})
    finally:
        _api_key_var.reset(token)
    envelope = json.loads(_result_text(result))
    assert envelope["error"]["code"] == "not_found"
    assert "device not found" in envelope["error"]["message"]


@pytest.mark.asyncio
@respx.mock
async def test_429_triggers_bounded_retry_then_rate_limited_envelope():
    route = respx.get(f"{BASE_URL}/vault").mock(
        side_effect=[
            Response(429, headers={"Retry-After": "0"}, json={"message": "rate limited"}),
            Response(429, headers={"Retry-After": "0"}, json={"message": "rate limited"}),
            Response(429, headers={"Retry-After": "0"}, json={"message": "rate limited"}),
            Response(429, headers={"Retry-After": "0"}, json={"message": "rate limited"}),
        ]
    )
    mcp = create_mcp_server(Settings())
    token = _api_key_var.set("a-key")
    try:
        result = await mcp.call_tool("axcient_list_vaults", {})
    finally:
        _api_key_var.reset(token)
    envelope = json.loads(_result_text(result))
    assert envelope["error"]["code"] == "rate_limited"
    assert envelope["error"]["retryable"] is True
    # 1 initial attempt + 3 retries = 4 calls total, then it gives up.
    assert route.call_count == 4


@pytest.mark.asyncio
@respx.mock
async def test_successful_list_respects_limit_and_sets_has_more():
    items = [{"id": i, "name": f"client-{i}"} for i in range(60)]
    respx.get(f"{BASE_URL}/client").mock(return_value=Response(200, json=items))
    mcp = create_mcp_server(Settings())
    token = _api_key_var.set("a-key")
    try:
        result = await mcp.call_tool("axcient_list_clients", {"limit": 50})
    finally:
        _api_key_var.reset(token)
    body = json.loads(_result_text(result))
    assert len(body["clients"]) == 50
    assert body["has_more"] is True
    assert body["cursor"] == "50"


@pytest.mark.asyncio
@respx.mock
async def test_set_vault_connectivity_threshold_sends_posted_body():
    route = respx.post(f"{BASE_URL}/vault/7/threshold/connectivity").mock(
        return_value=Response(200, json={"value": 15, "enabled": True, "overridden": True})
    )
    mcp = create_mcp_server(Settings())
    token = _api_key_var.set("a-key")
    try:
        result = await mcp.call_tool(
            "axcient_set_vault_connectivity_threshold", {"vault_id": 7, "value": 15, "enabled": True}
        )
    finally:
        _api_key_var.reset(token)
    body = json.loads(_result_text(result))
    assert body == {"value": 15, "enabled": True, "overridden": True}
    assert json.loads(route.calls.last.request.content) == {"value": 15, "enabled": True}
