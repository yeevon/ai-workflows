# Task 04 — Tier-Override CLI Plumbing — Audit Issues

**Source task:** [../task_04_tier_override_cli.md](../task_04_tier_override_cli.md)
**Audited on:** 2026-04-20
**Audit scope:** `ai_workflows/workflows/_dispatch.py` (new
`UnknownTierError`, new `_apply_tier_overrides`, new `tier_overrides`
param on `run_workflow`); `ai_workflows/cli.py` (new
`_parse_tier_overrides`, new `--tier-override` option, new
surface-boundary `UnknownTierError` catch); `ai_workflows/graph/tiered_node.py`
(read-only verify — dispatch path unchanged);
`tests/cli/test_tier_override.py` (new, 7 tests);
`tests/workflows/test_dispatch_tier_override.py` (new, 6 tests); full
gate (pytest + lint-imports + ruff); architecture drift check (§4.4
tier-override surface contract, §8.4, KDR-003); CHANGELOG placement.
**Status:** ✅ PASS — 8/8 ACs green, no design drift, no open issues.

## Design-drift check

Cross-referenced against [architecture.md](../../../architecture.md)
and the cited KDRs. No drift found:

- **New dependency?** None. No `pyproject.toml` edits. Typer + stdlib
  only — Typer was added in M3 T04 for `aiw run`.
- **New module / layer?** None. All edits land in two existing files
  (`ai_workflows/cli.py` + `ai_workflows/workflows/_dispatch.py`);
  four-layer contract unchanged (`uv run lint-imports` 3 / 3 kept).
- **LLM call added?** None. T04 is pure surface plumbing —
  [`tiered_node.py:189`](../../../../ai_workflows/graph/tiered_node.py#L189)
  still reads `configurable["tier_registry"]` verbatim. No new
  `TieredNode` / `ValidatorNode` pair needed (KDR-004 N/A).
- **Retry / checkpointer / observability added?** None.
  `_apply_tier_overrides` is a dict-copy helper; no retry loop, no
  checkpointer surface, no new logger.
- **KDR-003 (no Anthropic API).** Grep on both touched files
  (`ai_workflows/cli.py` + `ai_workflows/workflows/_dispatch.py`)
  returns zero hits for `anthropic` import or `ANTHROPIC_API_KEY`.
- **Graph layer unchanged.** `git status` under `ai_workflows/graph/`
  is empty; the surface-only scope promised by the task spec is
  genuine.

Verdict: no drift. No HIGH / MEDIUM / LOW issues raised.

## Error-surface parity — T05 readiness

Task spec: *"The CLI translates it to `typer.Exit(2)`; the MCP surface
(T05) will raise the matching `ToolError`."* Verified:

- `UnknownTierError` is in
  [`_dispatch.__all__`](../../../../ai_workflows/workflows/_dispatch.py#L58-L64)
  → M5 T05 can `from ai_workflows.workflows._dispatch import
  UnknownTierError` without a return trip to `_dispatch.py`.
- CLI catches it at
  [`cli.py`](../../../../ai_workflows/cli.py) inside `_run_async` →
  `typer.echo(str(exc), err=True)` + `typer.Exit(code=2)`.
  `typer.BadParameter` (malformed-parse path) also exits 2, so both
  pre-dispatch and post-dispatch error paths share a code.
- Error message includes `kind` + `tier_name` + sorted `registered`
  list — actionable and surface-agnostic.

## Snapshot-semantics verification

`_apply_tier_overrides` allocates `new_registry = dict(registry)` then
writes each `new_registry[logical] = registry[replacement]`. RHS reads
from the **input** `registry`, not from `new_registry`. A two-way swap
`{a: b, b: a}` therefore picks up the original `b` for the `a ← b`
write even after the `b ← a` write, because both RHS lookups hit the
untouched source. Pinned by `test_swap_override_reads_rhs_from_source_not_from_partial_output`
(pure-function) and the CLI-level
`test_repeatable_override_swaps_both_tiers` (integration).

## AC grading

| #   | AC                                                                                                 | Status | Evidence                                                                                                                                                                                                                                                                                                                     |
| --- | -------------------------------------------------------------------------------------------------- | ------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `--tier-override` repeatable; malformed / unknown entries surface with readable error + exit code 2 | ✅      | Typer option in `cli.py` `run()`; `_parse_tier_overrides` raises `typer.BadParameter`; `_run_async` catches `UnknownTierError` → `Exit(2)`. Pinned by `test_malformed_override_without_equals_exits_two`, `test_malformed_override_with_empty_half_exits_two`, `test_unknown_logical_tier_exits_two_and_names_registered`, `test_unknown_replacement_tier_exits_two_and_names_registered`. |
| 2   | `_dispatch.run_workflow` accepts `tier_overrides: dict[str, str] \| None`; raises `UnknownTierError` on unknown names | ✅      | New kwarg threaded into `run_workflow`; `_apply_tier_overrides` helper raises `UnknownTierError` with `kind ∈ {"logical", "replacement"}`. Pinned by `test_unknown_logical_tier_raises_with_logical_kind` + `test_unknown_replacement_tier_raises_with_replacement_kind`.                                                                                                      |
| 3   | Stub-adapter-level assertion: the overridden tier is actually dispatched against the replacement route | ✅      | `_RecordingLiteLLMAdapter.__init__` captures `route`, `.complete()` records `self.route.model` per call. `test_override_synth_to_explorer_dispatches_against_explorer_route` asserts `models_seen == [_EXPLORER_MODEL, _EXPLORER_MODEL]` — proves adapter-boundary dispatch, not just terminal state. `test_repeatable_override_swaps_both_tiers` asserts `[_SYNTH_MODEL, _EXPLORER_MODEL]`. |
| 4   | No override keeps M3 / M5 T01–T03 behaviour byte-identical                                         | ✅      | `_apply_tier_overrides(None)` / `{}` short-circuits to a shallow copy. `test_no_override_preserves_existing_behaviour` asserts `[_EXPLORER_MODEL, _SYNTH_MODEL]` ordering. Full suite confirms existing `tests/cli/test_run.py` + MCP tests still pass (359 passed vs 346 at T03 — only additions).                                                                          |
| 5   | Registry not mutated across runs (immutability / copy guard)                                        | ✅      | `new_registry = dict(registry)` copy at helper entry; writes only to the copy; RHS read from source. `test_override_does_not_mutate_source_registry_across_repeated_calls` applies three overrides in sequence and asserts `src == snapshot`. Also covered by `test_empty_overrides_returns_copy_not_same_dict` (mutation-through-return guard).                                  |
| 6   | `uv run pytest tests/cli/ tests/workflows/` green                                                  | ✅      | Full suite: 359 passed / 1 skipped. T04 files: 7 CLI tests + 6 dispatch tests all pass.                                                                                                                                                                                                                                     |
| 7   | `uv run lint-imports` 3 / 3 kept                                                                   | ✅      | `Contracts: 3 kept, 0 broken.`                                                                                                                                                                                                                                                                                                |
| 8   | `uv run ruff check` clean                                                                          | ✅      | `All checks passed!`                                                                                                                                                                                                                                                                                                          |

## 🔴 HIGH

None.

## 🟡 MEDIUM

None.

## 🟢 LOW

None.

## Additions beyond spec — audited and justified

1. **`UnknownTierError.kind` field** with `"logical"` / `"replacement"`
   discriminator. Spec only asks for "offending name"; adding `kind`
   surfaces *which side of `=`* was bad, so CLI / MCP error messages
   are actionable. Zero coupling cost, high debug value. Pinned by
   both dispatch-level kind assertions in
   `test_dispatch_tier_override.py`.

2. **`_distinct_registry()` module-local fixture in `test_tier_override.py`**
   with two different LiteLLM models. Necessary consequence of AC-3's
   stub-boundary requirement: the directory-autouse `_hermetic_registry`
   from `tests/cli/conftest.py` pins both tiers to the same model,
   which would make "explorer was dispatched" indistinguishable from
   "synth was dispatched." The module-local fixture stacks on top
   (pytest LIFO) to override just this test file — the exact pattern
   the conftest docstring invited: *"Tests that specifically need the
   production heterogeneous registry can re-monkeypatch locally."*
   Documented in the file's module docstring.

3. **`call_count == 0` assertion** on the two unknown-tier CLI tests.
   Guards that the error fires *before* graph invocation, not mid-run.
   Zero cost, catches a real regression class (a future refactor that
   moved the validation inside the compile block would silently regress).

All three are necessary-consequence edits, not scope creep.

## Gate summary

| Gate                                                                                                | Result                                       |
| --------------------------------------------------------------------------------------------------- | -------------------------------------------- |
| `uv run pytest`                                                                                     | ✅ 359 passed, 1 skipped                     |
| `uv run pytest tests/cli/test_tier_override.py`                                                     | ✅ 7 passed                                   |
| `uv run pytest tests/workflows/test_dispatch_tier_override.py`                                      | ✅ 6 passed                                   |
| `uv run lint-imports`                                                                               | ✅ 3 / 3 kept                                 |
| `uv run ruff check`                                                                                 | ✅ All checks passed!                        |
| KDR-003 regression (`anthropic` / `ANTHROPIC_API_KEY` grep on touched files)                        | ✅ zero hits                                  |
| Graph-layer diff scoped to T04 (`git status ai_workflows/graph/`)                                   | ✅ empty — surface-only change genuine       |
| `tests/cli/conftest.py` + `tests/mcp/conftest.py` autouse fixtures still intact                     | ✅ present + functioning (LIFO-stackable)    |

## Issue log — cross-task follow-up

None raised; no forward-deferrals.

## Propagation status

No forward-deferrals. M5 T05 will consume `UnknownTierError` +
`tier_overrides` from `_dispatch.py` verbatim — no further exports
needed.
