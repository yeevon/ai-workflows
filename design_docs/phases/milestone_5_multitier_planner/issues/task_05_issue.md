# Task 05 — Tier-Override MCP Plumbing — Audit Issues

**Source task:** [../task_05_tier_override_mcp.md](../task_05_tier_override_mcp.md)
**Audited on:** 2026-04-20
**Audit scope:** `ai_workflows/mcp/schemas.py` (new
`RunWorkflowInput.tier_overrides` field); `ai_workflows/mcp/server.py`
(`run_workflow` tool body — `UnknownTierError` import + forwarding +
error-translation extension); `tests/mcp/test_tier_override.py` (new,
7 tests); `tests/mcp/test_server_smoke.py` (step 7 addition);
`tests/mcp/conftest.py` (LIFO re-monkeypatch interaction verified);
`ai_workflows/workflows/_dispatch.py` (read-only — unchanged since
T04); full gate (pytest + lint-imports + ruff); architecture drift
check (§3 four-layer, §4.4 MCP surface, KDR-002, KDR-003, KDR-004,
KDR-008, KDR-009, KDR-010 / ADR-0002); CHANGELOG placement; sibling
issue files [`task_01_issue.md`](task_01_issue.md) –
[`task_04_issue.md`](task_04_issue.md) for M5 cumulative continuity.
**Status:** ✅ PASS — 7 / 7 ACs green, no design drift, no open issues.

## Design-drift check

Cross-referenced against [architecture.md](../../../architecture.md)
and the cited KDRs. No drift found:

- **New dependency?** None. `pydantic` (already a core dep since M1)
  and `fastmcp` (M4 T01) are both already in
  [`pyproject.toml`](../../../../pyproject.toml). No line added.
- **New module / layer?** None. Both files
  (`ai_workflows/mcp/schemas.py` + `ai_workflows/mcp/server.py`)
  pre-exist in the surfaces layer. `uv run lint-imports` reports
  3 / 3 contracts kept.
- **LLM call added?** None. T05 is pure surface plumbing — no new
  `TieredNode` / `ValidatorNode` pair required (KDR-004 N/A).
- **Checkpoint / retry / observability added?** None.
  ``_dispatch.run_workflow`` already carries the ``tier_overrides``
  kwarg since T04, and no new retry loop, checkpointer surface, or
  logger was introduced.
- **KDR-002 (MCP portable surface).** The new field is declared on a
  pydantic model that `@mcp.tool()` binds to the tool signature;
  FastMCP auto-derives the JSON-RPC schema from the annotation. Every
  MCP host (Claude Code, Cursor, Zed, …) sees the same portable
  contract that the CLI's ``--tier-override`` flag exposes — surface
  parity matches the §4.4 contract.
- **KDR-003 (no Anthropic API).** Grep on both touched files returns
  zero hits for ``anthropic`` / ``ANTHROPIC_API_KEY`` (case-insensitive).
- **KDR-004 (validator-after-every-LLM-node).** No node added, nothing
  touched — clean.
- **KDR-008 (FastMCP schema-first).** The field is declared as a plain
  pydantic field annotation
  (``tier_overrides: dict[str, str] | None = Field(default=None,
  description=...)``). FastMCP auto-derives the JSON-RPC schema from
  this; no hand-rolled schema plumbing was introduced. ``None``-default
  keeps the payload contract backward-compatible with M4-era callers
  — schema parity is preserved byte-for-byte.
- **KDR-009 (LangGraph checkpointer).** Untouched.
- **KDR-010 / ADR-0002 (bare-typed response schemas).** N/A at the MCP
  boundary — ADR-0002 scopes bare-typed specifically to LLM
  ``response_format`` schemas; MCP I/O models are out of scope per the
  schemas-module docstring (``schemas.py:22-27``). The added
  ``description=`` + ``default=None`` on ``Field`` is squarely inside
  what the ADR allows for MCP I/O.
- **``from None`` traceback-suppression parity.** The new
  ``except (UnknownWorkflowError, UnknownTierError) as exc: raise
  ToolError(str(exc)) from None`` branch at
  [`server.py:99-100`](../../../../ai_workflows/mcp/server.py#L99-L100)
  uses the same ``from None`` suppression the existing three MCP tools
  (``run_workflow`` for ``UnknownWorkflowError``, ``resume_run``,
  ``cancel_run``) use — confirmed by
  ``grep 'raise ToolError.*from None' ai_workflows/mcp/server.py``
  (three matches: lines 100, 121, 164). So the new branch keeps the
  JSON-RPC error response clean of Python-level traceback noise, which
  is the behaviour M4 T02 pinned.

Verdict: no drift. No HIGH / MEDIUM / LOW issues raised.

## AC grading

| # | AC | Verdict | Evidence |
|---|----|---------|----------|
| 1 | `RunWorkflowInput.tier_overrides: dict[str, str] \| None` with clear description; `None`-default preserves M4 backward compat | ✅ | `schemas.py:69-76` has the field with a clear description ("Optional {logical: replacement} map to swap tiers at invoke time. Both names must already exist in the workflow's tier registry."). Docstring at `schemas.py:56-63` cross-references the CLI mirror and explains the `None`-default. Pinned by `test_run_workflow_input_round_trip_without_tier_overrides` (absent → `None`, round-trip preserves absence). |
| 2 | MCP `run_workflow` forwards `tier_overrides` to `_dispatch.run_workflow`; `UnknownTierError` surfaces as `ToolError` | ✅ | `server.py:92-100`: `payload.tier_overrides` threaded into `_dispatch_run_workflow(..., tier_overrides=...)`; `except (UnknownWorkflowError, UnknownTierError) as exc: raise ToolError(str(exc)) from None` pattern. Pinned by `test_run_workflow_unknown_logical_tier_raises_tool_error` (message contains `nonexistent` + `logical`) and `test_run_workflow_unknown_replacement_tier_raises_tool_error` (message contains `nonexistent` + `replacement`). |
| 3 | Hermetic MCP tests cover: override applied, no override, empty-dict override, unknown logical, unknown replacement | ✅ | All five cases in `test_tier_override.py`. Override applied → `_RecordingLiteLLMAdapter.models_seen == [_EXPLORER_MODEL, _EXPLORER_MODEL]` (proves the synth call was dispatched against the explorer's route at the adapter boundary). No-override baseline → `[_EXPLORER_MODEL, _SYNTH_MODEL]` (byte-identical to M4 ordering). Empty-dict override → same baseline ordering. Both unknown cases → `ToolError` raised pre-graph (`call_count == 0` asserted on both). |
| 4 | `tests/mcp/test_server_smoke.py` gains one call with `tier_overrides` (still hermetic, still always-run) | ✅ | Step 7 at `test_server_smoke.py:233-253` issues a third `run_workflow` with `tier_overrides={"planner-synth": "planner-explorer"}` using `run-id="smoke-run-3"`. No `@pytest.mark.skipif` / no env-gate: the test is always-run under default `uv run pytest`. The directory-local `conftest.py` pins both tiers to Gemini Flash so the override is a dispatch-layer no-op there, but the `status == "pending"` + `awaiting == "gate"` + `ToolError`-free path proves the field is plumbed end-to-end. |
| 5 | `uv run pytest` green — includes the smoke | ✅ | 366 passed / 1 skipped (the 1 skipped is `tests/e2e/test_planner_smoke.py`, gated behind `AIW_E2E=1`, pre-existing). Baseline at T04 was 359 passed / 1 skipped — exactly seven new passes from `test_tier_override.py`; the smoke file gained a new step but the test-count stays at one (existing test wraps it). Net delta 359 → 366 matches the spec. |
| 6 | `uv run lint-imports` 3 / 3 kept | ✅ | `Contracts: 3 kept, 0 broken.` |
| 7 | `uv run ruff check` clean | ✅ | `All checks passed!` |

## Contract-level spot checks

- **Dispatch-boundary assertion genuinely proves route-level swap.**
  `_RecordingLiteLLMAdapter.__init__` captures `route` from its
  `TieredNode`-side construction, and ``.complete()`` appends
  ``self.route.model`` per call. The override test seeds
  ``models_seen = [_EXPLORER_MODEL, _EXPLORER_MODEL]``; the no-override
  test seeds ``[_EXPLORER_MODEL, _SYNTH_MODEL]`` — the differential
  proves the adapter actually receives the replacement ``TierConfig``
  at the dispatch boundary, not just a state-key swap. Matches the
  stronger guarantee T04 AC-3 pinned. `_EXPLORER_MODEL =
  "gemini/gemini-2.5-flash"` vs `_SYNTH_MODEL = "gemini/gemini-2.5-pro"`
  are distinct LiteLLM model strings so the assertion is
  unambiguous.
- **Directory-conftest LIFO stacking works as documented.**
  [`tests/mcp/conftest.py:42-47`](../../../../tests/mcp/conftest.py#L42-L47)
  pins `planner_tier_registry` to `_hermetic_registry` (both tiers on
  Flash). The T05 test file's own autouse
  `_install_distinct_registry` fixture (lines 108-112) then
  re-monkeypatches to `_distinct_registry` (Flash + Pro). pytest
  applies autouse fixtures LIFO within the same scope so the
  module-local fixture wins — this is the exact pattern the conftest
  docstring invited at
  [`conftest.py:12-15`](../../../../tests/mcp/conftest.py#L12-L15).
  Full suite stays green, which confirms no neighbouring MCP test
  file is inadvertently affected.
- **Backward-compat `call_count == 0` semantics.** Both unknown-tier
  tests assert `_RecordingLiteLLMAdapter.call_count == 0` — proves
  `_apply_tier_overrides` validation runs before `compile()` /
  `ainvoke()`, matching the `test_unknown_*_exits_two_and_names_registered`
  CLI tests at T04. This is a free, regression-class-proof side
  assertion: a future refactor that moved validation inside the
  compile block would silently regress.
- **Round-trip both ways.** `test_run_workflow_input_round_trip_preserves_tier_overrides`
  covers the set-field case and `test_run_workflow_input_round_trip_without_tier_overrides`
  covers the absent-field case. Both `.model_dump()` results are
  round-tripped through `.model_validate(dumped)` and the field value
  is re-asserted. Matches the Builder's claim of "both with and
  without `tier_overrides` set."
- **CHANGELOG placement.** [`CHANGELOG.md:10`](../../../../CHANGELOG.md#L10)
  — `### Added — M5 Task 05: Tier-Override MCP Plumbing (2026-04-20)`
  under `## [Unreleased]`. Matches the CLAUDE.md convention exactly
  (title + YYYY-MM-DD). Files-touched list enumerates the four
  modified files + the new test module. ACs mapped to tests; gate
  snapshot cited (366 / 1 skipped, 3 / 3 kept, ruff clean).
- **Import-linter layer check.** `server.py` imports
  `ai_workflows.workflows._dispatch` (workflows layer) and
  `ai_workflows.primitives.storage` (primitives layer); nothing
  imports `server.py` from non-surface layers. Confirmed by
  `uv run lint-imports` passing.

## 🔴 HIGH

None.

## 🟡 MEDIUM

None.

## 🟢 LOW

None.

## Additions beyond spec — audited and justified

1. **Second round-trip test for the absent-field case**
   (`test_run_workflow_input_round_trip_without_tier_overrides`). The
   spec lists one round-trip test; the Builder shipped two. The extra
   one asserts that an unset `tier_overrides` dumps to `None` and
   round-trips as `None`. Zero coupling cost, closes the "default is
   genuinely `None`, not silently elided" regression class. Kept.
2. **`call_count == 0` side-assertion on both unknown-tier tests.**
   Not in the spec's bullet list, but matches the T04 precedent and
   catches a future refactor that moved validation inside the compile
   block. Zero cost, catches a real regression class.
3. **`_RecordingLiteLLMAdapter.models_seen` list** (vs T04's script
   pop mechanism). The recording list is how the MCP test proves
   adapter-boundary dispatch — necessary consequence of AC-3's
   "stub adapter recorded tier/model pair matches the replacement
   route." Mirrors the T04 CLI-side `_RecordingLiteLLMAdapter` (same
   name, same pattern) so a reader jumping between T04 and T05 sees
   the same recording API. Small naming duplication vs T04's test
   file, but scope-discipline-wise correct: hermetic MCP tests
   cannot import fixtures from `tests/cli/`, and lifting the stub to
   a shared conftest would expand scope beyond the task.

All three are necessary-consequence edits, not scope creep.

## Gate summary

| Gate | Result |
|------|--------|
| `uv run pytest` | ✅ 366 passed, 1 skipped |
| `uv run pytest tests/mcp/test_tier_override.py` | ✅ 7 passed |
| `uv run pytest tests/mcp/test_server_smoke.py` | ✅ 1 passed (includes step 7) |
| `uv run lint-imports` | ✅ 3 / 3 kept |
| `uv run ruff check` | ✅ All checks passed! |
| KDR-003 regression (`anthropic` / `ANTHROPIC_API_KEY` grep on `ai_workflows/mcp/`) | ✅ zero hits |
| `from None` parity with sibling `ToolError` raises | ✅ 3 matches in `server.py` (lines 100, 121, 164) |
| CHANGELOG placement | ✅ `## [Unreleased]` + `### Added — M5 Task 05: <Title> (YYYY-MM-DD)` format |

## Issue log — cross-task follow-up

None raised; no forward-deferrals.

## Propagation status

No forward-deferrals. T06 (hermetic + `AIW_E2E=1` live smoke) can
consume `RunWorkflowInput.tier_overrides` and the T04 CLI
``--tier-override`` flag verbatim for its e2e scenarios — no further
exports needed.
