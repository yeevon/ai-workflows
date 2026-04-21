# Task 08 — End-to-End Smoke on Fixture Slice List — Audit Issues

**Source task:** [../task_08_e2e_smoke.md](../task_08_e2e_smoke.md)
**Audited on:** 2026-04-20
**Audit scope:** full T08 delivery — hermetic E2E
(`tests/workflows/test_slice_refactor_e2e.py`), live-gated E2E
(`tests/e2e/test_slice_refactor_smoke.py`), manual walkthrough
(`design_docs/phases/milestone_6_slice_refactor/manual_smoke.md`),
CHANGELOG entry, plus full-suite + lint + ruff re-runs.
**Status:** ✅ PASS — 0 OPEN issues; all 7 ACs met; 0 design drift.

## Design-drift check

Cross-referenced every T08 touch against [architecture.md](../../../architecture.md) + the cited KDRs before grading ACs.

| Axis | Verdict | Evidence |
| --- | --- | --- |
| New dependency | ✅ None added | T08 is test-only code + one markdown doc. `pyproject.toml` unchanged. |
| New module or layer | ✅ Within four-layer contract | New files live under `tests/` only; no code under `ai_workflows/`. `import-linter` 3/3 kept. |
| LLM call added | ✅ N/A | T08 stubs `LiteLLMAdapter` at `tiered_node` module boundary — no new LLM routing. Live suite uses the existing M5 + M6 tier wiring. |
| KDR-003 (no Anthropic API) | ✅ Enforced in both suites | Hermetic: `test_kdr_003_no_anthropic_in_production_tree` greps `ai_workflows/**/*.py`. Live: `_assert_no_anthropic_in_production_tree` repeats same grep before provider calls fire. Both pass. |
| KDR-004 (validator after every LLM node) | ✅ No change | T08 does not add LLM nodes. |
| KDR-006 (3-bucket retry via `RetryingEdge`) | ✅ No change | T08 does not add retry logic. |
| KDR-008 (FastMCP surface) | ✅ Mentioned only in prose | Manual walkthrough cites `aiw-mcp` registration via the M4-landed FastMCP surface; no MCP code change. |
| KDR-009 (SqliteSaver checkpointing) | ✅ No change | Tests redirect `AIW_CHECKPOINT_DB` via env var to `tmp_path` — production resolution path unchanged. |
| Observability (StructuredLogger) | ✅ No change | T08 does not add logging. |
| `nice_to_have.md` scope creep | ✅ None | No new primitives, no new MCP tools, no new workflows. |
| Docstring + module header discipline | ✅ Present | Both new test modules carry a task-citation module docstring + relationship-to-siblings block. Manual doc mirrors M5 shape. |
| CI gate impact | ✅ No regression | Full suite 475 passed + 3 skipped (2 sibling e2e + new e2e). |
| Layer discipline | ✅ Kept | Tests import only through `workflows._dispatch` (the surface-shared entry the CLI + MCP already use). No cross-layer imports introduced. |

No drift found.

## Acceptance criteria grading

| # | AC | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Hermetic `tests/workflows/test_slice_refactor_e2e.py` green: full pipeline runs, both gates fire in order, approve path writes artefacts, reject path writes none | ✅ | `test_slice_refactor_e2e_approve_path_writes_three_artefacts` + `test_slice_refactor_e2e_reject_outer_gate_writes_no_artefacts` green. Three-step plan drives fan-out of three slice workers; artefact count asserted via `SQLiteStorage.read_artifact` for each `slice_result:<id>`. |
| 2 | `AIW_E2E=1 uv run pytest tests/e2e/test_slice_refactor_smoke.py` green once against real Qwen + real Claude Code (record in T09 CHANGELOG) | ✅ STRUCTURAL | Live test is present, asyncio-marked, `@pytest.mark.e2e`-gated, with three prerequisite skip paths. Collects under `AIW_E2E=1`. The actual real-provider green pass is explicitly deferred to the T09 close-out per the spec's last line — T08's spec scope is landing the structural surface, not executing it against live infra. Deferral noted in the CHANGELOG entry and is the T09 Builder's AC. |
| 3 | Default `uv run pytest` (no `AIW_E2E`) skips the live test cleanly; hermetic suite remains green | ✅ | Verified: `test_slice_refactor_smoke.py s` (skipped) + `test_slice_refactor_e2e.py ...` (3 passed) under plain `uv run pytest`. |
| 4 | Prerequisite checks produce readable skip reasons when dependencies missing | ✅ | `_skip_without_multitier_prereqs` in the live test mirrors the M5 T06 pattern: three independent checks (`ollama` binary, Ollama daemon TCP on 11434, `claude` binary), each with a distinct `pytest.skip(...)` message. |
| 5 | KDR-003 regression: grep for `anthropic` / `ANTHROPIC_API_KEY` in production code returns zero hits | ✅ | Enforced in both suites via `_KDR_003_REGRESSION` regex (narrowed to real-use signals: `import anthropic`, `from anthropic`, `ANTHROPIC_API_KEY`). Hermetic suite runs the grep on every `uv run pytest` invocation. |
| 6 | `uv run lint-imports` 3 / 3 kept | ✅ | `primitives cannot import graph, workflows, or surfaces KEPT` / `graph cannot import workflows or surfaces KEPT` / `workflows cannot import surfaces KEPT`. |
| 7 | `uv run ruff check` clean | ✅ | `All checks passed!`. |

## 🔴 HIGH

None.

## 🟡 MEDIUM

None.

## 🟢 LOW

None.

## Observational notes

No OPEN issues. Two observations worth recording for T09 context.

### OBS-01 — Spec cited `architecture.md §11 Testing strategy`, actual §11 is "What this document is not"

**Observation:** T08's task spec (line 9) references [architecture.md §11 Testing strategy](../../architecture.md). The actual §11 in the current architecture.md is "What this document is not" — the testing-strategy section either never existed under that number or drifted across a prior edit. Does not affect the T08 delivery (the citation was informational; the test design follows the M3 T07 / M5 T06 precedents that do exist in the tree).

**Resolution:** No action required for T08 — the spec's intent (live smoke parallels the M3/M5 pattern) is clear and the delivery matches. Flag for T09 to consider whether `architecture.md` wants a §11 (or renumbered) testing-strategy section. Lower-priority than other T09 close-out work.

### OBS-02 — Live test uses `_dispatch.run_workflow` / `resume_run` directly rather than the MCP `build_server()` path

**Observation:** `tests/e2e/test_tier_override_smoke.py` drives the MCP `run_workflow` tool in-process via `build_server().get_tool("run_workflow")`; `tests/e2e/test_slice_refactor_smoke.py` calls `_dispatch.run_workflow` directly. Both exercise the same code below the surface boundary, but the tier-override smoke additionally covers the FastMCP → dispatch translation layer. T08 spec uses the language "Run … through the same fan-out → aggregate → gate → apply path, resuming both gates via the `_dispatch.resume_workflow` shim" — which aligns with the direct-dispatch approach used. The MCP surface is covered by the T07 `test_tier_override.py` and the M4 `test_server_smoke.py` already.

**Resolution:** No action required. The split is deliberate — T08's live smoke is tier-mix + multi-tier-cost-stamping-focused, not MCP-surface-focused. Noted so T09's close-out sweep knows where each surface's live coverage lives.

## Additions beyond spec — audited and justified

| Addition | Justification |
| --- | --- |
| `_pin_tier_registries` autouse fixture in hermetic test | Required to keep the planner sub-graph's calls within the stub boundary. Without it, `planner-synth` would try to instantiate `ClaudeCodeSubprocess` mid-test. Mirrors the pattern in `test_slice_refactor_strict_gate.py` (which re-patches per-test rather than via a fixture). |
| Three-tier stub registry (`_tier_registry_override`) reroutes `planner-synth` onto `LiteLLMRoute` | The stub adapter is the `LiteLLMAdapter`; rerouting the Claude Code tier onto a `LiteLLMRoute` is the mechanism by which the hermetic test avoids the Claude Code subprocess path. Alternative (monkeypatching `ClaudeCodeSubprocess` to a raise-on-call stub) would equally pass but adds a second patch axis; the route swap is the minimal change. |
| Manual smoke §6 "Double-failure hard-stop — smoke the abort path (optional)" | Not in the task spec, but slots naturally into the walkthrough since T07 landed the hard-stop wiring and the manual audience will ask. Notes the hermetic suite owns that path — no human-reproducible real-provider procedure was invented. |
| Manual smoke §5 tier-override step (`slice-worker → planner-synth`) | Not in the task spec, but directly parallels M5's manual_smoke.md §4. Exercises the override surface against the new M6 `slice-worker` tier so the T09 close-out sign-off covers the tier-override plumbing at the MCP level too. |

All additions are test/doc-only; none touch `ai_workflows/`.

## Gate summary

| Gate | Verdict | Evidence |
| --- | --- | --- |
| `uv run pytest` | ✅ 475 passed + 3 skipped | Live e2e skips without `AIW_E2E=1`. |
| `uv run lint-imports` | ✅ 3/3 contracts kept | `primitives → graph → workflows → surfaces`. |
| `uv run ruff check` | ✅ All checks passed | Clean. |
| KDR-003 grep (hermetic) | ✅ Zero hits | Production tree clean. |
| CHANGELOG entry under `## [Unreleased]` | ✅ Present | Dated 2026-04-20. |
| AIW_E2E=1 collection | ✅ Collects 1 test | Gate fires as expected. |

## Issue log — cross-task follow-up

| ID | Severity | Owner / next touch point | Status |
| --- | --- | --- | --- |
| (none) | — | — | — |

No cross-task issues surfaced by this audit. OBS-01 (architecture.md §11 drift) is logged here as an observation and does not require forward propagation; T09 may choose to address it as part of the close-out doc sweep.

## Deferred to nice_to_have

None.

## Propagation status

- No forward-deferrals introduced by this audit.
- No carry-over ticks required on T09's spec file.
