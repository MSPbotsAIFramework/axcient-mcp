# axcient-mcp

MCP server for **Axcient x360Recover** (backup-and-disaster-recovery / BCDR), built for the
MSPbots Agent Platform.

<div align="center">

## MSPbots Connector

**The MCP Gateway built for MSPs: visible, controlled, and your data stays where it belongs.**

[**Get started at connect.mspbots.ai →**](https://connect.mspbots.ai)

</div>

---

MSPbots Connector gives your AI clients one MCP URL to reach your entire MSP stack (RMM, PSA, documentation, security, finance), and gives you control over who can call which tool and a record of everything that was called.

**Hosted service: [connect.mspbots.ai](https://connect.mspbots.ai)** · Free to use.

### Why Connector

![MSPbots Connector](https://stgoss.mspbots.ai/files/mcp/mspbots-mcp.png)

| | |
|---|---|
| **Visible** | Every tool call is logged: who, which vendor, when. Usage dashboard, CSV export, SIEM streaming. |
| **Controlled** | Role-based, per-tool allowlist. Deny by default. |
| **Protected** | Credentials encrypted per record. AI clients never see your vendor passwords or tokens. |
| **MSP-native** | Built for the MSP stack only: RMM, PSA, documentation, security, finance. |

### Quick start

1. **Sign up** at [connect.mspbots.ai](https://connect.mspbots.ai).
2. **Connect your vendors.** Pick from 150+ connectors and authorize each one on the vendor's own page, or bring your own API keys. No extra vendor accounts needed.
3. **Set access.** Create roles and decide which tools each role may call. Nothing is allowed until you allow it.
4. **Add your MCP URL to your AI client.** Copy the URL from your Connector dashboard into Claude, ChatGPT, Cursor, VS Code, Gemini, Codex, or any MCP-capable client.
5. **Ask your AI to do real work**, and watch every call appear in the audit log.

### Features

**Unified gateway**
- One MCP URL for all your AI clients
- 150+ connectors across the MSP stack
- Custom MCP servers supported, free
- Authorization happens on each vendor's own page; the AI never sees passwords or tokens
- Bring your own credentials: use the vendor API keys you already have
- Multiple accounts per app; connect once, reuse across AI clients
- Tool search: finds the right action for the task
- One sign-in; vendor credentials are injected behind the scenes and OAuth tokens refresh automatically

**Visibility**
- Audit log for every tool call (who, which vendor, when)
- Usage dashboard: call volume, top vendors, error rate, per-user activity
- Export audit logs to CSV, or stream to Loki, Graylog, or LogScale (SIEM)
- Optional recording of tool arguments and result summaries (off by default, enabled per organization)

**Control**
- Per-role, per-tool allowlist, deny by default
- owner / admin / member roles
- SCIM provisioning with Entra ID, Okta, JumpCloud, and Google Workspace

**Security**
- Credentials encrypted one record at a time (AES-256-GCM, per-record key)
- AI clients authenticate with OAuth 2.1 + PKCE
- Vendor responses are scanned for prompt-injection patterns and returned as structured data. This is one layer of defense, not a guarantee against every attack.
- Static egress IP for customer firewall and API allowlisting

### Pricing

**Free.**

Links: [connect.mspbots.ai](https://connect.mspbots.ai) · [mspbots.ai](https://mspbots.ai)

---

## Overview

Implements the [Model Context Protocol](https://modelcontextprotocol.io/) (Streamable HTTP
transport) and exposes **16 tools** over the x360Recover REST API, grouped by resource. Inventory
flows top-down — organization → clients → devices/appliances/vaults → backup jobs:

- "What clients do we protect, and how many devices does each have?" →
  `axcient_list_clients`, `axcient_list_devices`
- "Is this device's backup healthy right now?" → `axcient_get_device`
  (`current_health_status`)
- "When can we restore this machine to, and has AutoVerify confirmed the recovery actually
  works?" → `axcient_get_device_restore_points`, `axcient_get_device_autoverify`
- "Is the appliance/vault at this site online?" → `axcient_get_appliance` /
  `axcient_get_vault` (`tunnel_status`)
- "Raise the connectivity-alert threshold for this vault" → `axcient_get_vault_connectivity_threshold`
  then `axcient_set_vault_connectivity_threshold`
- "Did last night's backup job for this device actually run and succeed?" →
  `axcient_list_backup_jobs` → `axcient_get_backup_job` → `axcient_get_backup_job_history`

| Category | Tools | Annotations |
|---|---|---|
| Organization | `axcient_list_organization` | readOnly |
| Clients | `axcient_list_clients`, `axcient_get_client` | readOnly |
| Devices | `axcient_list_devices`, `axcient_get_device`, `axcient_get_device_restore_points`, `axcient_get_device_autoverify` | readOnly |
| Appliances | `axcient_list_appliances`, `axcient_get_appliance` | readOnly |
| Vaults | `axcient_list_vaults`, `axcient_get_vault`, `axcient_get_vault_connectivity_threshold` | readOnly |
| | `axcient_set_vault_connectivity_threshold` | idempotent (not destructive — replaces one alert setting) |
| Backup jobs | `axcient_list_backup_jobs`, `axcient_get_backup_job`, `axcient_get_backup_job_history` | readOnly |

Every tool is read-only except `axcient_set_vault_connectivity_threshold`, the only `POST`
operation the vendor API documents outside of device-enrollment token issuance (out of scope —
see Known Gaps).

## Authentication headers

Every request to `/mcp` must include the following HTTP header:

| Header | Type | Required | Description | Example |
|---|---|---|---|---|
| `X-Axcient-Api-Key` | string | Yes | Axcient partner API key. Obtain one at [partner.axcient.com](https://partner.axcient.com/) → **Settings → API Keys → Add API Key**. Sent to Axcient verbatim as the `x-api-key` header. | `X-Axcient-Api-Key: abcd1234...` |

Header names are case-insensitive. A request to `/mcp` without `X-Axcient-Api-Key` gets `401`
with the list of expected headers.

## Run locally

```bash
uv sync
uv run axcient-mcp              # listens on 0.0.0.0:8080
curl -s http://127.0.0.1:8080/health
curl -s http://127.0.0.1:8080/mcp \
  -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  -H "X-Axcient-Api-Key: $AXCIENT_API_KEY" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

Environment variables (all optional, unknown ones ignored): `MCP_HTTP_HOST` (default `0.0.0.0`),
`MCP_HTTP_PORT` (default `8080`). Credentials are never read from the environment.

## Docker

```bash
docker build --platform linux/amd64 -t axcient-mcp .
docker run --rm -p 8080:8080 axcient-mcp
```

## Development

```bash
uv sync
uv run pytest -q
```

Code is in `src/axcient_mcp/` (one module per resource under `tools/`), tests in `tests/`.

## Known gaps / implementation notes

- **No vendor test account was available at build time.** All read tools and the error-mapping
  paths are covered by mocked unit tests; test cases that need real response shapes (pagination
  behaviour, cross-tenant isolation, the threshold set/get round trip) are marked `manual · needs
  a real vendor account` in `docs/tickets/PRD-21270.ac.json`. This does not block delivery per the
  team's vendor-mcp SOP.
- **List pagination is applied client-side** (`limit`/`cursor`, capped at 200) on top of whatever
  the vendor's `GET` returns in one shot — the vendor's own native paging contract could not be
  confirmed without a partner API key. If a real account later shows the vendor paginates
  natively, only the internal request/response mapping in `tools/*.py` changes; the tool-facing
  `limit`/`cursor`/`has_more` contract does not.
- **Device-enrollment token issuance** (`POST /client/{client_id}/vault/{vault_id}/d2c_agent`) is
  intentionally not exposed as a tool — it is a provisioning write with no read counterpart to
  verify against, unrelated to this connector's "visibility into backup status" scope.
- **x360Cloud, x360Sync, and Billing** are separate Axcient products on the same developer portal
  and are out of scope for this connector (x360Recover only).
- Endpoint shapes are built from a community-maintained OpenAPI spec
  (`github.com/adamburley/AxcientAPI`), corroborated by a live, unauthenticated probe against the
  real base URL (confirmed route + `x-api-key` auth). No code from that or any other third-party
  project is included here — see [NOTICE](NOTICE).

## License

Copyright 2026 MSPbots.ai. Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE)
and [NOTICE](NOTICE).

Axcient is a trademark of its owner. This project is not affiliated with or endorsed by the owner
of Axcient.
