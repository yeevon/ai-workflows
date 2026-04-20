# Task 04 — Tier-Override CLI Plumbing

**Status:** 📝 Planned.

## What to Build

Add a repeatable `--tier-override <logical>=<registered>` option to `aiw run planner` that lets a caller swap a workflow-declared tier for any other tier already in the registry at invoke time. Example: `aiw run planner --goal '…' --tier-override planner-synth=planner-explorer` downshifts the synth call from Claude Code Opus back to Qwen without editing code. The graph-layer consumer lives in [`TieredNode`](../../../ai_workflows/graph/tiered_node.py)'s `config["configurable"]["tier_registry"]` read; this task only adds the surface plumbing.

Aligns with [architecture.md §4.4](../../architecture.md) — *"Tier overrides allow the caller to downshift a run to cheaper tiers"* ([§8.4](../../architecture.md)).

## Deliverables

### `ai_workflows/cli.py` — `run` command option

```python
@app.command("run")
def run(
    workflow: str,
    goal: str = typer.Option(..., "--goal"),
    run_id: str | None = typer.Option(None, "--run-id"),
    budget_usd: float | None = typer.Option(None, "--budget-usd"),
    tier_override: list[str] = typer.Option(
        [],
        "--tier-override",
        help="Override a tier: --tier-override <logical>=<replacement>. "
             "Repeatable. Example: --tier-override planner-synth=planner-explorer.",
    ),
) -> None:
    ...
```

Parse the `logical=replacement` form with a small helper that raises `typer.BadParameter` on a malformed entry (no `=`, empty halves, unknown tier name). Build `tier_overrides: dict[str, str]` and pass it to the shared [`workflows._dispatch.run_workflow`](../../../ai_workflows/workflows/_dispatch.py) via a new keyword argument.

### `ai_workflows/workflows/_dispatch.py` — consume overrides

Extend `run_workflow()` to accept `tier_overrides: dict[str, str] | None = None`. When non-empty, apply the mapping against the workflow's tier registry (`planner_tier_registry()` for the planner) **before** the graph compile step: for each `(logical, replacement)`, replace `registry[logical]` with `registry[replacement]` (sharing the same `TierConfig` instance is fine — `TieredNode` reads route + limits off the config at call time). Unknown `logical` or `replacement` names raise `UnknownTierError(ValueError)` with the offending name — the CLI translates it to `typer.Exit(2)`; the MCP surface ([T05](task_05_tier_override_mcp.md)) will raise the matching `ToolError`.

The surface-agnostic error class pattern mirrors the existing `UnknownWorkflowError` / `ResumePreconditionError` in `_dispatch.py`.

### Tests

`tests/cli/test_tier_override.py` (new):

- `aiw run planner --goal x --tier-override planner-synth=planner-explorer` runs to the gate; the tiered_node for `planner-synth` was dispatched against `planner-explorer`'s route (asserted via the stub adapter's recorded tier/model pair).
- Repeatable flag: `--tier-override planner-explorer=planner-synth --tier-override planner-synth=planner-explorer` swaps both tiers; both stub calls see the swapped routes.
- Malformed override `planner-synth` (no `=`) → `typer.BadParameter` → exit 2 with a readable message.
- Unknown logical tier `nonexistent=planner-synth` → `typer.Exit(2)` with the tier name in the message.
- Unknown replacement tier `planner-synth=nonexistent` → same.
- No override → existing M3 behaviour is byte-identical (regression guard).

`tests/workflows/test_dispatch_tier_override.py` (new):

- `_dispatch.run_workflow` with `tier_overrides={…}` applies the mapping and does not mutate the returned registry between runs (idempotency on repeated calls).

## Acceptance Criteria

- [ ] `aiw run planner --tier-override <logical>=<replacement>` repeatable option parsed; malformed / unknown entries surface with a readable error and exit code 2.
- [ ] `_dispatch.run_workflow` accepts `tier_overrides: dict[str, str] | None`; applies the mapping at invoke time; raises `UnknownTierError` on unknown names.
- [ ] Stub-adapter-level assertion: the overridden tier is actually dispatched against the replacement route (not the original).
- [ ] No override keeps M3 / M5 T01–T03 behaviour byte-identical.
- [ ] Registry not mutated across runs (immutability / copy guard).
- [ ] `uv run pytest tests/cli/ tests/workflows/` green.
- [ ] `uv run lint-imports` 3 / 3 kept.
- [ ] `uv run ruff check` clean.

## Dependencies

- [Task 03](task_03_subgraph_composition.md) — multi-tier planner must be green hermetic before overrides become meaningful.
- The graph-layer `TieredNode` already resolves tier from `config["configurable"]["tier_registry"]`, so no graph-layer change is required (verify in the Builder's first read).
