# PRD-21270 · Code review

## Round 1 · 2026-11-03 · reviewed af36f75 (base 19212eb)

Verdict: changes requested

### Findings

1. [must-fix] `src/axcient_mcp/tools/vaults.py:77` — `axcient_set_vault_connectivity_threshold` is registered with `ToolAnnotations(idempotentHint=True)` only. The tech design's Change list explicitly specifies `destructiveHint=false` for this tool (`docs/tickets/PRD-21270.md:101`), and the README documents it as "idempotent (not destructive — replaces one alert setting)" (`README.md:104`). The MCP SDK's `ToolAnnotations.destructiveHint` defaults to `true` when omitted (confirmed at `mcp/types.py:1267-1273` in this repo's own `.venv`, and by reading back the live annotation from `create_mcp_server(...).list_tools()`, which prints `destructiveHint=None` — meaning MCP clients must treat it as the `true` default). So the one write tool in this connector is currently advertised to agents/clients as destructive, the opposite of what the design and README both say it is. Fix: add `destructiveHint=False` to the `ToolAnnotations(...)` call on this tool, matching the Change list.

### Fixes

(to be filled in by the dev leg)
