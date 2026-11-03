# PRD-21270 · Code review

## Round 1 · 2026-11-03 · reviewed af36f75 (base 19212eb)

Verdict: changes requested

### Findings

1. [must-fix] `src/axcient_mcp/tools/vaults.py:77` — `axcient_set_vault_connectivity_threshold` is registered with `ToolAnnotations(idempotentHint=True)` only. The tech design's Change list explicitly specifies `destructiveHint=false` for this tool (`docs/tickets/PRD-21270.md:101`), and the README documents it as "idempotent (not destructive — replaces one alert setting)" (`README.md:104`). The MCP SDK's `ToolAnnotations.destructiveHint` defaults to `true` when omitted (confirmed at `mcp/types.py:1267-1273` in this repo's own `.venv`, and by reading back the live annotation from `create_mcp_server(...).list_tools()`, which prints `destructiveHint=None` — meaning MCP clients must treat it as the `true` default). So the one write tool in this connector is currently advertised to agents/clients as destructive, the opposite of what the design and README both say it is. Fix: add `destructiveHint=False` to the `ToolAnnotations(...)` call on this tool, matching the Change list.

### Fixes

1. `src/axcient_mcp/tools/vaults.py:77` — added `destructiveHint=False` to the `ToolAnnotations(...)` call on `axcient_set_vault_connectivity_threshold`, matching the tech design's Change list (`docs/tickets/PRD-21270.md:101`) and the README. Live-verified via `create_mcp_server(Settings()).list_tools()`: the tool's `annotations` now read `destructiveHint=False idempotentHint=True` (previously `destructiveHint=None`, defaulting to `true` per the MCP SDK). Also strengthened `tests/test_tools.py`'s `EXPECTED_TOOLS` contract snapshot for this tool to assert `destructiveHint: False` alongside `idempotentHint: True`, so a regression here would fail `test_tools_list_snapshot` going forward — previously the test only checked `idempotentHint` and would not have caught this.
   - Commit: `599a139` on `dev/PRD-21270` (synced with `main @ 19212eb`, unchanged since round 1 — no merge needed).
   - Re-run: `uv run pytest -q` → `11 passed`. Confirmed the strengthened assertion actually catches the regression: temporarily restored the pre-fix `vaults.py` (`git show d936048:...`) on top of the new test and re-ran — `tests/test_tools.py::test_tools_list_snapshot` failed with `AssertionError: axcient_set_vault_connectivity_threshold: destructiveHint=None, expected False`, i.e. exactly the reviewer's finding. Restored the fixed `vaults.py` afterwards; full suite back to `11 passed`.
   - Other gates re-run on the fixed code: Chinese-text scan — same pre-existing hits as round 1, all inside the frozen `docs/tickets/PRD-21270.md` (quoted Chinese wiki/SOP terms, not source or README), nothing new introduced by this change; `gitleaks` not installed on this host, skipped (same as round 1).
