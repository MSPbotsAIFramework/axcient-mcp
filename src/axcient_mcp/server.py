# Copyright 2026 MSPbots.ai
# SPDX-License-Identifier: Apache-2.0
"""FastMCP server factory and HTTP app assembly."""

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from .middleware import CredentialMiddleware
from .settings import Settings
from .tools import appliances, clients, devices, jobs, organization, vaults

INSTRUCTIONS = (
    "Axcient x360Recover is a backup-and-disaster-recovery (BCDR) platform for MSPs: on-prem "
    "appliances and cloud vaults protect client devices, and jobs back each device up on a "
    "schedule. Inventory flows top-down: axcient_list_clients -> "
    "axcient_list_devices(client_id=...) -> axcient_get_device for one device's health, restore "
    "points (axcient_get_device_restore_points), and AutoVerify screenshot-verified recovery "
    "status (axcient_get_device_autoverify). Appliances (axcient_list_appliances / "
    "axcient_get_appliance) and vaults (axcient_list_vaults / axcient_get_vault) are the "
    "infrastructure devices back up to; axcient_get_vault_connectivity_threshold / "
    "axcient_set_vault_connectivity_threshold read and adjust the one configurable alert "
    "setting this API exposes. Backup job history (axcient_list_backup_jobs -> "
    "axcient_get_backup_job -> axcient_get_backup_job_history) answers 'did last night's backup "
    "run, and did it succeed.' Every tool is read-only except the one threshold-set tool."
)

MODULES = (organization, clients, devices, appliances, vaults, jobs)


def create_mcp_server(settings: Settings) -> FastMCP:
    mcp = FastMCP(
        name="axcient-mcp",
        instructions=INSTRUCTIONS,
        stateless_http=True,
        json_response=True,
        # The gateway forwards requests with its own Host header; DNS-rebinding
        # protection would otherwise reject them with 421.
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    for module in MODULES:
        module.register(mcp)
    return mcp


def create_app(settings: Settings) -> Starlette:
    mcp = create_mcp_server(settings)
    mcp_app = mcp.streamable_http_app()

    async def health(_: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    # Mount() does not run a sub-app's lifespan; without forwarding it the
    # streamable-http session manager's task group never starts, and /mcp
    # fails with "Task group is not initialized" while /health still passes.
    return Starlette(
        routes=[Route("/health", health), Mount("/", app=CredentialMiddleware(mcp_app))],
        lifespan=lambda app: mcp_app.router.lifespan_context(app),
    )
