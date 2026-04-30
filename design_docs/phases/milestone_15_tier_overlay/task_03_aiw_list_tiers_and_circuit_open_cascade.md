# Task 03 — `aiw list-tiers` command + HTTP CircuitOpen cascade test

**Status:** ✅ Built (cycle 2, 2026-04-30).
**Grounding:** [milestone README](README.md) · [architecture.md §4 + §9](../../architecture.md) · [ai_workflows/cli.py](../../../ai_workflows/cli.py) · [ai_workflows/workflows/__init__.py](../../../ai_workflows/workflows/__init__.py) · [ai_workflows/workflows/spec.py](../../../ai_workflows/workflows/spec.py) · [tests/mcp/test_http_transport.py](../../../tests/mcp/test_http_transport.py) · [KDR-002](../../architecture.md) (MCP-as-substrate) · [KDR-004](../../architecture.md) (validator pairing — cascade is infrastructure, not semantic retry) · [KDR-006](../../architecture.md) (three-bucket retry taxonomy) · [KDR-014](../../architecture.md) (framework owns tier policy).

## What to Build

Two independent deliverables in one task (different files — spec-compatible scope):

**Deliverable A — `aiw list-tiers`:** Add a new `@app.command("list-tiers")` subcommand to `ai_workflows/cli.py`. The command prints each registered workflow's effective tier registry as a table: tier name, route kind (`LiteLLM` or `ClaudeCode`), model/CLI-flag, max concurrency cap, per-call timeout, and any configured fallback chain (fallback routes in declaration order). Pure read; no dispatch side-effects. Accepts `--workflow` / `-w` to filter to a single workflow. For spec-API workflows (registered via `register_workflow`) the tier table comes from `get_spec(name).tiers`. Imperative workflows (registered via `register` only, no `WorkflowSpec`) are shown as a single row with route info unavailable.

**Deliverable B — HTTP CircuitOpen cascade test:** Add `tests/mcp/test_http_fallback_on_circuit_open.py`. A hermetic test that starts the MCP server in a background thread (same pattern as `tests/mcp/test_http_transport.py`), installs a stub `_FallbackStubLiteLLMAdapter` class (mirroring `tests/mcp/test_http_transport.py:75-114`) via `monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _FallbackStubLiteLLMAdapter)` so the primary route raises `CircuitOpen` and a fallback route succeeds, invokes `run_workflow` over the MCP HTTP transport, and asserts the successful fallback's output appears in the response envelope. This pins the HTTP-envelope shape when cascade fires under a tripped circuit breaker (milestone README exit criterion #5).

## Deliverables

### 1. `ai_workflows/cli.py` — `aiw list-tiers` command

Add the command after the `list-runs` section (around line 679). Pattern mirrors `list-runs`: a sync Typer entry point + a thin `_list_tiers_async` + a `_emit_list_tiers_table` formatter.

```python
@app.command("list-tiers")
def list_tiers(
    workflow: str | None = typer.Option(
        None,
        "--workflow",
        "-w",
        help="Filter to a single workflow (exact match). If omitted, all registered workflows are listed.",
    ),
) -> None:
    """Print the effective tier registry for registered workflows.

    Shows: tier name, route kind, model / CLI flag, max concurrency,
    per-call timeout (s), and any configured fallback chain (M15).
    Pure read — no dispatch is triggered.
    """
    configure_logging(level="WARNING")
    from ai_workflows import workflows as _workflows
    asyncio.run(_list_tiers_async(workflow_filter=workflow, workflows_mod=_workflows))
```

The `_list_tiers_async` helper:

1. Calls `workflows.list_workflows()` to enumerate all registered names.
2. If `workflow_filter` is given, filters to that name; raises `typer.BadParameter` if the name is not registered.
3. For each name calls `workflows.get_spec(name)`:
   - If a `WorkflowSpec` is returned: iterates `spec.tiers.items()` for the rows.
   - If `None` (imperative workflow): emits one row with `"(no tier registry exported)"`.
4. Delegates to `_emit_list_tiers_table(rows)` for rendering.

Column format for `_emit_list_tiers_table`:

| Column | Source |
|--------|--------|
| `workflow` | workflow name |
| `tier` | `tier_name` key in `spec.tiers` |
| `kind` | `"LiteLLM"` if `isinstance(tier.route, LiteLLMRoute)` else `"ClaudeCode"` |
| `model/flag` | `tier.route.model` (LiteLLM) or `tier.route.cli_model_flag` (ClaudeCode) |
| `concurrency` | `tier.max_concurrency` |
| `timeout_s` | `tier.per_call_timeout_s` |
| `fallback` | comma-joined `model`/`cli_model_flag` from each route in `tier.fallback`; `"—"` if empty |

Imports to add to `cli.py` (neither is currently imported; Builder adds this line):
`from ai_workflows.primitives.tiers import LiteLLMRoute, ClaudeCodeRoute`

The command reads no async resource (`list_workflows()`, `get_spec()`, and `spec.tiers.items()` are all synchronous). The Builder should ship a fully **sync** implementation (no `_async` helper, no `asyncio.run`). The `asyncio.run` sketch in the template above is illustrative only and should not be used.

### 2. `tests/cli/test_list_tiers.py` (new)

Hermetic CLI tests for `aiw list-tiers`. Pattern: register a synthetic `WorkflowSpec` with a known `tiers` dict, invoke the Typer command via `typer.testing.CliRunner`, assert output.

**Test-isolation pattern:** Every test that registers a synthetic workflow must use an `autouse=True` fixture that calls `workflows._reset_for_tests()` before (and after) each test, then re-registers only the synthetic spec needed by that test. This prevents registry leakage between tests. Template:

```python
import pytest
from ai_workflows import workflows

@pytest.fixture(autouse=True)
def _clean_registry():
    workflows._reset_for_tests()
    yield
    workflows._reset_for_tests()
```

Cite `tests/mcp/test_http_transport.py:117-121` as the analog.

Tests:

- **`test_list_tiers_shows_spec_workflow_tiers`** — register a synthetic `WorkflowSpec` with one tier (`LiteLLMRoute(model="gemini/test")`, no fallback); run `aiw list-tiers`; assert `"gemini/test"` appears in stdout and the tier name appears in stdout.

- **`test_list_tiers_fallback_chain_rendered`** — register a synthetic `WorkflowSpec` with one tier that has `fallback=[LiteLLMRoute(model="gemini/fallback")]`; run `aiw list-tiers`; assert the fallback model `"gemini/fallback"` appears in stdout.

- **`test_list_tiers_workflow_filter`** — register two synthetic workflows; run `aiw list-tiers --workflow <name1>`; assert only name1's tiers appear in stdout.

- **`test_list_tiers_unknown_workflow_exits_2`** — run `aiw list-tiers --workflow nonexistent`; assert exit code is exactly 2 (`typer.BadParameter` default via `CliRunner().invoke(...).exit_code == 2`).

### 3. `tests/mcp/test_http_fallback_on_circuit_open.py` (new)

One hermetic test for the HTTP-transport cascade envelope.

Pattern: identical to `tests/mcp/test_http_transport.py` — start the MCP server as a background daemon thread on an ephemeral port, poll until it answers, invoke via `fastmcp.Client`.

Test: **`test_http_run_workflow_fallback_cascade_on_circuit_open`**

**Test-isolation pattern:** Same `_clean_registry` autouse fixture as Deliverable A — `workflows._reset_for_tests()` before and after each test. Start the HTTP server **after** the synthetic workflow is registered (same daemon-thread ordering as `tests/mcp/test_http_transport.py:117-140`).

**Synthetic spec shape:** The spec must be fully valid for `register_workflow` to accept it.

```python
from pydantic import BaseModel
class _FallbackOutput(BaseModel):
    result: str

class _FallbackInput(BaseModel):
    goal: str
```

`WorkflowSpec` shape:
- `name = "fallback_cascade_test"` (required field; any unique non-shipped name)
- `input_schema = _FallbackInput`
- `output_schema = _FallbackOutput`
- `tiers = {"primary": TierConfig(name="primary", route=LiteLLMRoute(model="gemini/primary"), fallback=[LiteLLMRoute(model="gemini/fallback")])}`
- One `LLMStep(tier="primary", response_format=_FallbackOutput, prompt_template="goal: {goal}")`

Cite `tests/mcp/test_scaffold_workflow_http.py:128-149` as the analog for test-side `register_workflow` with a synthetic spec.

**Stub adapter:** Install a class-based stub, not a `.complete`-patched instance. The stub mirrors `tests/mcp/test_http_transport.py:75-114` exactly — kwarg-only `__init__`, no `tier_config` or `callbacks` params, `complete` with the real kwargs (`system`, `messages`, `response_format`):

```python
from ai_workflows.graph import tiered_node as tiered_node_module
from ai_workflows.primitives.cost import TokenUsage
from ai_workflows.primitives.circuit_breaker import CircuitOpen
from ai_workflows.primitives.tiers import LiteLLMRoute

class _FallbackStubLiteLLMAdapter:
    def __init__(self, *, route: LiteLLMRoute, per_call_timeout_s: int) -> None:
        self.route = route

    async def complete(self, *, system, messages, response_format=None):
        if self.route.model == "gemini/primary":
            raise CircuitOpen("breaker-open")
        return ("fallback-ok", TokenUsage(
            input_tokens=1, output_tokens=1, cost_usd=0.0, model=self.route.model,
        ))

monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _FallbackStubLiteLLMAdapter)
```

**Setup steps:**

1. `workflows._reset_for_tests()` (via autouse fixture)
2. Register the synthetic `WorkflowSpec` via `workflows.register_workflow(spec)`.
3. Install `_FallbackStubLiteLLMAdapter` via `monkeypatch.setattr`.
4. Start HTTP server in a daemon thread on an ephemeral port.

**Invocation:** call `run_workflow` via `fastmcp.Client` over HTTP with the synthetic workflow (input: `{"goal": "test"}`).

**Assertions:**
- Response does not contain `"AllFallbacksExhaustedError"` text in the payload.
- The response payload's error field is `None` (successful run, not error envelope).
- The run-ID field is present in the response (confirms the run completed, not crashed at dispatch).
- No exception escapes the `asyncio.run(client.call_tool(...))` call.

The test pins the HTTP-envelope shape when the cascade fires under a tripped circuit breaker. It does not test error-path (all-exhausted) HTTP shape — that is out of scope (T05 close-out task can add it if needed).

**Kind column note (M3):** The milestone README task-order row 03 says `code + test + doc`. The "doc" component for this task is the CHANGELOG entry only (no separate `docs/` file edit — those land in T04). This is the standard cross-cutting requirement, not a separate doc deliverable.

### 4. `CHANGELOG.md`

Entry under `## [Unreleased] → ### Added`:
`M15 Task 03: aiw list-tiers command + HTTP CircuitOpen cascade test (YYYY-MM-DD)`
naming files touched and ACs satisfied.

## Acceptance Criteria

- [x] **AC-1: `aiw list-tiers` command registered.** `aiw list-tiers --help` exits 0 and prints the command's help text. `aiw list-tiers` (no args) lists all registered workflows without error.

- [x] **AC-2: Tier table output.** For a workflow with a spec, the output includes: workflow name, tier name, route kind (`LiteLLM` or `ClaudeCode`), model/CLI flag, concurrency cap, timeout, fallback column (`—` when empty, comma-joined route identifiers when non-empty).

- [x] **AC-3: `--workflow` filter.** `aiw list-tiers --workflow <name>` shows only tiers for the named workflow. Unknown workflow name exits with exactly exit code 2 (`typer.BadParameter`); assert via `CliRunner().invoke(...).exit_code == 2`.

- [x] **AC-4: Imperative workflows handled gracefully.** Workflows registered via `register()` only (no `WorkflowSpec`) appear in the output with a `"(no tier registry exported)"` message rather than crashing.

- [x] **AC-5: HTTP CircuitOpen cascade test.** `test_http_run_workflow_fallback_cascade_on_circuit_open` in `tests/mcp/test_http_fallback_on_circuit_open.py` passes hermetically. The test uses stub adapters (no live provider calls). Assertions must be conjunctive: (a) the response payload error field is `None`, AND (b) the run-ID field is present in the response, AND (c) no `AllFallbacksExhaustedError` text appears in the payload. No "or" clauses in AC assertions.

- [x] **AC-6: CLI hermetic tests green.** `tests/cli/test_list_tiers.py` — 4 new tests, all pass. No provider calls.

- [x] **AC-7: Existing tests unchanged.** Full `uv run pytest` green. Existing `tests/cli/` and `tests/mcp/` tests pass without modification.

- [x] **AC-8: Layer contract preserved.** `uv run lint-imports` reports 5 contracts kept, 0 broken. `aiw list-tiers` lives in `cli.py` (surfaces layer); it imports from `workflows` (allowed: surfaces → workflows). No new `primitives → graph` or other violations.

- [x] **AC-9: Gates green.** `uv run pytest` + `uv run lint-imports` + `uv run ruff check` all pass.

- [x] **AC-10: CHANGELOG entry.** M15 T03 entry added under `[Unreleased]`.

## Dependencies

- **T01 + T02 must be built first.** `aiw list-tiers` reads `TierConfig.fallback` (T01's field); the HTTP CircuitOpen cascade test exercises `_node()`'s cascade logic (T02's implementation). Both are ✅ Built (cycle 1, 2026-04-30).
- Ships against 0.4.0 baseline. M15 ships as ≥ 0.5.0.

## Out of scope

- **ADR-0006.** T04 deliverable.
- **`tiers.yaml` relocation → `docs/tiers.example.yaml`.** T04 deliverable.
- **`docs/writing-a-workflow.md` tier-config section.** T04 deliverable.
- **HTTP all-exhausted envelope test.** `AllFallbacksExhaustedError` HTTP error shape is not pinned here. T05 close-out can add it if needed.
- **Per-fallback retry loop.** Each fallback route is attempted once. No retry loop inside the cascade.
- **Imperative workflow tier discovery.** Imperative workflows that don't use `WorkflowSpec` cannot expose their tier registry via the spec API. A future extension (tier registry hook on the builder function) is a `nice_to_have.md` candidate; not in scope here.
- **MCP `list_tiers` tool.** The milestone README non-goals include no MCP schema change. The CLI command is the deliverable; no MCP mirror.

## Smoke test

CLI smoke: `uv run aiw list-tiers` on the installed package (or from the dev environment) should print at least the `planner` workflow's tiers without error. The planner workflow is spec-API (registered via `register_workflow`); its tiers are accessible via `get_spec("planner").tiers`.

HTTP smoke: `test_http_run_workflow_fallback_cascade_on_circuit_open` is the wire-level smoke test (hermetic, via `fastmcp.Client` over a live loopback HTTP connection to the daemon thread server).

## Carry-over from prior milestones

- LOW-2 from T02 issue file: `CircuitOpen` cascade path lacks a unit-level hermetic test. T03's `test_http_run_workflow_fallback_cascade_on_circuit_open` covers the HTTP-transport surface, satisfying the audit deferral. A pure unit-level `tiered_node` test for `CircuitOpen` cascade is **not** required at T03 (deferred deferral already accepted in T02 audit).

## Carry-over from task analysis

- [x] **TA-LOW-01 — Sync implementation for `list-tiers` (no `asyncio.run`)** (severity: LOW, source: task_analysis.md round 3)
      The template sketch in §1 shows `asyncio.run(_list_tiers_async(...))` but the disclaimer immediately below says ship the sync form. The template is illustrative only — ship a fully synchronous `list_tiers` command. No `_async` helper, no `asyncio.run`. The function body should call `workflows.list_workflows()` and `workflows.get_spec(name)` directly inside the Typer entry point.
      **Recommendation:** Builder ignores the template sketch and ships a flat sync function.

- [x] **TA-LOW-02 — `register_workflow` analog citation** (severity: LOW, source: task_analysis.md round 3)
      The cited analog `tests/mcp/test_scaffold_workflow_http.py:128-149` is a heredoc string template, not a direct `register_workflow()` call site. Use `tests/workflows/test_compiler.py:215` or `tests/workflows/test_spec.py:235` as the pattern for `register_workflow(synthetic_spec)` in test setup.
      **Recommendation:** Builder uses one of those as the pattern, not the scaffold HTTP test.
