# Task 04 — Ship `summarize` workflow as in-tree spec-API proof point + wire-level e2e verification — Audit Issues

**Source task:** [../task_04_summarize_proof_point.md](../task_04_summarize_proof_point.md)
**Audited on:** 2026-04-26 (cycle 1) · re-audited 2026-04-26 (cycle 2)
**Audit scope (cycle 2):** Same files as cycle 1, plus the cycle-2 doc/test edits — `ai_workflows/workflows/summarize.py` (module docstring + `ValidateStep` inline-comment reframe), `tests/workflows/test_summarize.py` (`test_summarize_validator_step_runs` tightened: `status == "errored"` + reframed docstring), `tests/integration/test_spec_api_e2e.py` (`test_summarize_artefact_identical_across_surfaces` rewritten as sync test driving `CliRunner.invoke` for the CLI side + `asyncio.run(_mcp_call())` for the MCP side; `test_aiw_run_summarize_help_lists_input_fields` renamed to `test_aiw_show_inputs_summarize_lists_input_fields`), `tests/cli/test_run.py` (`assert "required" in combined.lower()` added to `test_run_missing_goal_exits_two`), `CHANGELOG.md` (cycle-1 entry's "AC-1 through AC-11" corrected to "AC-1 through AC-13"; cycle-2 entry appended), `task_04_summarize_proof_point.md` (15 `[ ]` → `[x]` checkboxes; Deliverable 1 line 102 rewritten to locked Path (i) framing), `issues/task_02_issue.md` ("Post-close T02 latent fixes" section appended; T02 status preserved as ✅ PASS). All three gates re-run from scratch on cycle 2: `uv run pytest` (697 passed, 9 skipped, 0 failed in 31.83 s), `uv run lint-imports` (4 contracts kept, 0 broken; 107 dependencies), `uv run ruff check` (all checks passed). Targeted spot-greps (`AC-1 through`, `test_aiw_run_summarize_help_lists_input_fields` absent, `[ ]` checkboxes count = 0).

**Audit scope (cycle 1):** `ai_workflows/workflows/summarize.py` (new), `ai_workflows/workflows/summarize_tiers.py` (new), `ai_workflows/cli.py` (modified — `--input KEY=VALUE`, `show-inputs` command, `--goal` made optional, `_parse_inputs` helper, `ValidationError → BadParameter` wrap), `ai_workflows/workflows/_compiler.py` (modified — `on_terminal` parameter on `_compile_llm_step`, `path_map_override` on `GraphEdge`, inter-step stitching skip for LLMStep exit nodes, pre-initialization of LLMStep intermediate keys + framework-internal keys in `initial_state`), `tests/workflows/test_summarize.py` (new — 5 hermetic tests), `tests/integration/test_spec_api_e2e.py` (new — 5 wire-level tests; new `tests/integration/` directory), `tests/cli/test_run.py` (`test_run_missing_goal_exits_two` migrated per Deliverable 4 §"Existing-test migration"), `CHANGELOG.md` (`### Added` block under `[Unreleased]`), milestone status surfaces. Cross-referenced against ADR-0008, `architecture.md` §3 + §6 + §9 (KDR-002 / KDR-003 / KDR-004 / KDR-006 / KDR-008 / KDR-009 / KDR-013), the M19 README (locked H1 + H2 framing), the predecessor T01 / T02 / T03 issue files, the T01 spec (step taxonomy contract), the T02 spec (compiler contract), and the T03 spec (artefact-field round-trip). All three task gates re-run from scratch (`uv run pytest`, `uv run lint-imports`, `uv run ruff check`) plus targeted greps (`anthropic`, `ANTHROPIC_API_KEY`, `import langgraph`, `mix_stderr`, `git diff main -- planner.py slice_refactor.py`) plus runtime trace of the `summarize` workflow's standalone-`ValidateStep` execution.

**Status:** ✅ PASS (cycle 2 — all 8 cycle-1 findings RESOLVED; HIGH=0, MEDIUM=0, LOW=0 still-open; gates green; all 13 ACs + 2 carry-overs met against spec text; status surfaces aligned).

Cycle 1 status (preserved for audit history): ⚠️ OPEN (HIGH=0, MEDIUM=2 — both required user direction; LOW=6 absorbed inline).

## Design-drift check

**Cycle 2 (2026-04-26 re-audit):** No new drift. Cycle-2 edits scope was confined to docstring text + test assertions + one test rename + a CHANGELOG count fix + a doc-trail backfill on T02's issue file. No source-code logic changed in `ai_workflows/`. The seven load-bearing KDRs + four-layer rule remain unbroken; `lint-imports` reports 4 contracts kept / 0 broken / 107 dependencies (unchanged from cycle 1). `grep -rn "anthropic\|ANTHROPIC_API_KEY"` against cycle-2 touched files returns zero hits. `grep -n "import langgraph" ai_workflows/workflows/summarize.py` returns zero hits.

**Cycle 1 (2026-04-26):** No KDR drift. Cross-reference against the seven load-bearing KDRs + the four-layer rule:

- **Four-layer rule.** `summarize.py` imports stdlib + `pydantic` + `ai_workflows.workflows` (spec types) + `ai_workflows.workflows.summarize_tiers` only. `summarize_tiers.py` imports `ai_workflows.primitives.tiers` only (`LiteLLMRoute` + `TierConfig` from the same module). `cli.py` extension stays inside the surfaces layer; the new `_parse_inputs` helper has no new external import. No `import langgraph` anywhere in `summarize.py` (verified via grep). `lint-imports` reports `4 contracts kept, 0 broken` (re-run from scratch this audit; 107 dependencies — three more than T03 cycle 2's 104 owing to the new modules and the `RetryPolicy`/`tiered_node`/`validator_node` hookups already in place from T02 + T03).
- **KDR-002 / KDR-008 (MCP wire surface).** No MCP tool added; `RunWorkflowOutput.artifact` round-trip exercised live by Test 4 in `test_spec_api_e2e.py` (resolves M18 inventory DOC-DG4 — the FastMCP `payload` wire shape is exercised against an in-process server). Schema unchanged.
- **KDR-003 (no Anthropic API).** `grep -rn "anthropic\|ANTHROPIC_API_KEY"` against `summarize.py`, `summarize_tiers.py`, `cli.py`: zero hits. `summarize-llm` tier routes to Gemini Flash via LiteLLM only.
- **KDR-004 (validator pairing — by construction).** `summarize.py`'s `LLMStep(response_format=SummarizeOutput, ...)` triggers automatic `ValidatorNode` pairing in T02's compiler. Verified live by `test_summarize_compiles_to_runnable_state_graph` (workflow completes against stub) and `test_summarize_validator_step_runs` (malformed JSON triggers retry path → NonRetryable). The standalone `ValidateStep` after the LLMStep is **a no-op in this configuration** — see MEDIUM-1; KDR-004 is upheld via the LLMStep-paired validator regardless.
- **KDR-006 (three-bucket retry via `RetryingEdge`).** `summarize.py`'s `RetryPolicy(max_transient_attempts=3, max_semantic_attempts=2, transient_backoff_base_s=0.5, transient_backoff_max_s=4.0)` flows through T02's `_compile_llm_step` → `retrying_edge(policy=...)` unchanged. Verified live by `test_summarize_retry_policy_on_transient_failure` (transient → success on retry; 2 LLM calls counted). No bespoke try/except retry loops added.
- **KDR-009 (LangGraph `SqliteSaver` checkpoints).** Dispatch path compiles graph with `AsyncSqliteSaver` from `build_async_checkpointer` unchanged. Test fixtures redirect `AIW_CHECKPOINT_DB` + `AIW_STORAGE_DB` to `tmp_path` (hermetic). The `_compiler.py` change pre-initialising LLMStep intermediate keys in `initial_state` is *necessary* for KDR-009 round-trip correctness on transient-failure recovery (see Phase 1 note below); it strengthens KDR-009, does not weaken it.
- **KDR-013 (user code is user-owned; in-package collision guard).** `register_workflow(_SPEC)` at module top of `summarize.py` defers to existing `register(name, builder)`. The collision guard fires reliably (T01 invariant unchanged). `summarize` is in-package, so it cannot be shadowed by an external workflow with the same name (T02 + M16 collision check). Verified by re-running `tests/workflows/test_registry.py::test_workflows_module_does_not_import_langgraph` (still green; the new `summarize.py` module does not pull LangGraph into the import graph at the spec layer).
- **External workflow loading.** Unchanged. The `summarize.py` ships in-package; M16's external-discovery surface still rejects collisions.
- **Workflow tier names.** `summarize-llm` is a per-workflow tier name declared via `summarize_tier_registry()` — matches the post-pivot per-workflow registry pattern. No pre-pivot names (`orchestrator`, `gemini_flash`, `local_coder`, `claude_code`) appear in any new code.
- **MCP tool surface.** Four shipped tools unchanged. No new tool added.

ADR-0008 §Step taxonomy + §Extension model: `summarize` ships as the M19 spec-API proof point per locked H2; planner + slice_refactor stay on the escape hatch per locked Q5 + H2 (verified via `git diff main -- ai_workflows/workflows/planner.py ai_workflows/workflows/slice_refactor.py` — zero diff to either file).

**Phase 1 special note — `_compiler.py` modifications are T02 latent-bug fixes, not scope creep.** The four `_compiler.py` edits all surface only when running a multi-step composed `WorkflowSpec` end-to-end through the actual dispatch path against a checkpointer. T02's `tests/workflows/test_compiler.py` (23 tests) exercises single-step specs and `StubLiteLLMAdapter` patterns that bypass the multi-step stitching + AsyncSqliteSaver `durability='sync'` round-trip. T04 is the first task that drives a real `aiw run` CLI invocation against a multi-step compiled `StateGraph` with full checkpointer wiring. The four edits are:
1. `on_terminal=` parameter on `_compile_llm_step` — without it, retrying_edge's success-path always routes to `END`, which is correct for an LLMStep-only spec but wrong for a multi-step spec where LLMStep should flow to the next step on success. Necessary fix.
2. `path_map_override` on `GraphEdge` — supports the on_terminal change by letting the compiler pass an explicit `{call: call, on_terminal: on_terminal, END: END}` path map instead of the default `{source, target, END}`. Necessary fix.
3. Inter-step stitching skip for LLMStep exit nodes — when retrying_edge wires from the validate node, an unconditional `validate → next_step.entry` would conflict with the conditional retrying_edge at the same source. Necessary fix.
4. `initial_state` pre-initialisation of LLMStep intermediate keys + framework-internal keys (`last_exception`, `_retry_counts`, `_non_retryable_failures`, `_mid_run_tier_overrides`) — without this, `AsyncSqliteSaver` + `durability='sync'` drops keys that weren't written before the first checkpoint, causing `KeyError` in the validate node on transient-failure retry. Necessary fix; verified by `test_summarize_retry_policy_on_transient_failure` exercising the path.

Spot-checked: T02's existing 23 tests in `test_compiler.py` plus T01's 16 tests in `test_spec.py` all still pass (39/39 green) with the cycle-1 changes loaded. No T02 regressions. The edits are within the spec's "T04 may need to extend the compiler to ship `summarize`" implicit scope. The right book-keeping is to backfill T02's issue file with a "latent bugs caught at T04" note — see LOW-6.

## AC grading

**Cycle 2 (2026-04-26 re-audit):** All 13 ACs PASS (no regressions); cycle-2 reframing of AC-4 (test now asserts `status == "errored"` not the permissive `in (...)` check) and AC-1 caveat resolved (Deliverable 1 line 102 rewritten + module docstring + `ValidateStep` inline comment all match locked Path (i)). All 13 AC `[ ]` checkboxes flipped to `[x]` in the spec. Both carry-over items TA-LOW-02 + TA-LOW-10 also flipped to `[x]`. Status-surface integrity preserved (T04 spec **Status:** ✅ Done; milestone README row 04 ✅ Implemented; no `tasks/README.md` for M19; milestone README uses numbered prose for exit criteria — no `[ ]` to flip).

**Cycle 1 grading preserved below.**

| AC | Status | Notes |
| -- | ------ | ----- |
| AC-1 — `summarize.py` exists with correct structure | ✅ PASS (cycle 2: AC-1 caveat resolved) | `SummarizeInput` + `SummarizeOutput` pydantic models; `_SPEC` is a `WorkflowSpec(name="summarize", input_schema=SummarizeInput, output_schema=SummarizeOutput, tiers=summarize_tier_registry(), steps=[LLMStep(...prompt_template+response_format+retry...), ValidateStep(...)])`. `register_workflow(_SPEC)` at module top level. Zero `import langgraph` (grep-verified). Module docstring cites M19 T04, ADR-0008, locked H2 (2026-04-26), and the dual purpose. **Cycle 2 update:** module docstring (lines 15-25) reframes `ValidateStep` as illustrative + runtime no-op when schema matches upstream LLMStep.response_format; spec Deliverable 1 line 102 rewritten consistently; `ValidateStep` inline comment at `summarize.py:103` matches. The cycle-1 MEDIUM-1 "deliberate-exercise-of-step-type" intent gap is now resolved by reframing rather than restructuring (locked Path (i)). |
| AC-2 — `summarize_tiers.py` exists | ✅ PASS | `summarize_tier_registry()` returns `dict[str, TierConfig]` with the `summarize-llm` tier routed to `LiteLLMRoute(model="gemini/gemini-2.5-flash")` + `max_concurrency=4` + `per_call_timeout_s=120`. Both `LiteLLMRoute` and `TierConfig` imported from `ai_workflows.primitives.tiers` (single module). |
| AC-3 — module docstring on `summarize.py` cites M19 T04 + ADR-0008 + locked H2 + dual purpose | ✅ PASS | Lines 1-36: cites M19 T04, ADR-0008, locked H2 (2026-04-26), dual purpose (proof point + worked-doc-example source for T05). Relationship-to-other-modules block adds T03 cross-reference. |
| AC-4 — `tests/workflows/test_summarize.py` with 5 tests, hermetic, <2s | ✅ PASS (cycle 2: caveat resolved) | 5 tests present and named per Deliverable 3: registers, compiles, round-trips, validator-step, retry-policy. Hermetic (stub LLM adapter at boundary; tmp_path SQLite redirect via env-var). All five pass; combined wall ~1.0 s on this machine. **Cycle 2 update:** `test_summarize_validator_step_runs` (now `tests/workflows/test_summarize.py:240-279`) tightened to `assert result["status"] == "errored"` + `assert result["error"] is not None`; docstring reframed to "LLMStep's paired validator (KDR-004) catches malformed LLM output — semantic-retry exhaustion → errored". The contract being asserted now matches what the test actually proves. Cycle-1 caveat resolved. |
| AC-5 — `aiw run --input KEY=VALUE` extension correct | ✅ PASS | `--input KEY=VALUE` (repeatable) added; planner flags (`--goal`, `--context`, `--max-steps`) preserved (manually verified `aiw run planner --goal "x"` still parses). Conflict between planner flag and `--input` raises `BadParameter` (Test 3 covers). Pydantic v2 type coercion automatic via `_dispatch.run_workflow`'s call to `input_schema(**inputs)` (Test 1 covers — `--input max_words=50` coerces "50" → int 50 successfully). Validation errors wrapped to `BadParameter` (`cli.py:386-400`). Help-text discoverability via separate `aiw show-inputs <workflow>` subcommand (Builder picked subcommand UX over `--help` callback per spec line 217 Builder discretion). `~30-50 lines` budget exceeded somewhat (~70 lines added between the new helper, the `show-inputs` command, and the dispatch-layer wrapping; not flagged — Builder discretion absorbed reasonable shape). No diff to `resume` / `list-runs` / `cancel` / `eval` commands. |
| AC-6 — `tests/integration/test_spec_api_e2e.py` with 5 wire-level tests | ✅ PASS (cycle 2: caveat resolved) | 5 wire-level tests present and named per Deliverable 5; all five pass against stub. Test 4 explicitly resolves M18 DOC-DG4 (the `payload` wire-shape wrapper exercised live via in-process `build_server().get_tool("run_workflow").fn(payload)`). **Cycle 2 update:** Test 5 (`test_summarize_artefact_identical_across_surfaces`, now at `tests/integration/test_spec_api_e2e.py:286-385`) rewritten as sync test: drives `aiw run summarize --input ...` via `CliRunner.invoke(app, [...])` for the CLI side; drives the MCP tool via `asyncio.run(_mcp_call())` wrapping `build_server().get_tool("run_workflow").fn(payload)` for the MCP side; asserts `cli_artefact == mcp_artefact == {"summary": stub_summary}`. The CLI side now genuinely drives the `aiw run` entry-point (no `_dispatch.run_workflow` shortcut). The cycle-1 MEDIUM-2 cross-surface byte-identity proof gap is resolved. |
| AC-7 — `FINAL_STATE_KEY = "summary"` round-trips through `RunWorkflowOutput.artifact` | ✅ PASS | Test 4 (`test_aiw_mcp_run_workflow_summarize_via_fastmcp_client`) asserts `result.artifact["summary"] == "A brief summary of the text."` via the MCP surface live. `test_summarize_round_trips_through_dispatch` asserts `result["artifact"]["summary"] == ...` AND `result["plan"] == result["artifact"]` (T03 lockstep alias). Both fields populated and equal — T03's bug fix composes correctly. |
| AC-8 — no port of planner / slice_refactor | ✅ PASS | `git diff main -- ai_workflows/workflows/planner.py ai_workflows/workflows/slice_refactor.py` returns empty. Both modules unchanged. The H2 + Q5 deferral framing is recorded in the README §Decisions item 7 + §Decisions item 4 + the milestone Exit-criterion 6 prose. No CHANGELOG `### Changed` entry mentions either workflow (correct per AC-12). |
| AC-9 — existing tests stay green or migrate; success path byte-identical; failure path migrated | ✅ PASS (cycle 2: LOW-2 caveat resolved) | Full pytest reports 697 passed, 9 skipped, 0 failed. `aiw run planner --goal "x"` success path manually verified to behave unchanged. Failure path (`aiw run planner` without `--goal`) migrated per Deliverable 4 §"Existing-test migration": exit code 2 preserved (`BadParameter` wraps the dispatch-layer pydantic `ValidationError`). **Cycle 2 update:** `tests/cli/test_run.py:test_run_missing_goal_exits_two` (line 261-278) now asserts BOTH `"goal" in combined.lower()` AND `"required" in combined.lower()` per spec Deliverable 4 §"Existing-test migration" requirement. Cycle-1 LOW-2 (under-assertion) resolved. |
| AC-10 — layer rule preserved; lint-imports 4/4 | ✅ PASS | `lint-imports`: `Contracts: 4 kept, 0 broken` (107 dependencies — three more than T03 owing to new modules). `summarize.py` imports stdlib + pydantic + `ai_workflows.workflows` + `ai_workflows.workflows.summarize_tiers`. `summarize_tiers.py` imports `ai_workflows.primitives.tiers` only. `cli.py` extension stays in the existing surfaces layer (no new layer crossings — `_parse_inputs` is local; `ValidationError` import is from pydantic; no new graph or workflows imports beyond what cli.py already had). |
| AC-11 — gates green on both branches | ✅ PASS (on `design_branch`; T08 owns cross-branch propagation) | This audit's gate runs (re-run from scratch): `uv run pytest` → 697 passed, 9 skipped, 0 failed in 30.77 s; `uv run lint-imports` → 4 contracts kept, 0 broken; `uv run ruff check` → All checks passed. T08's release ceremony owns the `main`-branch propagation. |
| AC-12 — CHANGELOG entry (Added) under `[Unreleased]` | ✅ PASS (cycle 2: LOW-3 caveat resolved) | Two `### Added — M19 Task 04` blocks under `[Unreleased]` — cycle-2 entry first (cycle-2 fixes), cycle-1 entry second (initial implementation). Cycle-1 entry's "ACs satisfied" line corrected to "AC-1 through AC-13" (was "AC-1 through AC-11"). All shipped files + behaviour + KDRs (KDR-004, KDR-006, KDR-009, KDR-013) cited. No `### Changed` entry for planner/slice_refactor (correct — those files are unchanged). Keep-a-Changelog vocabulary only. Cycle-1 LOW-3 (off-by-two AC count) resolved. |
| AC-13 — no new step types added to T01's taxonomy | ✅ PASS | `summarize.py` uses only `LLMStep` + `ValidateStep` from T01's five built-ins. No subclassing of `Step`, no novel types. `grep -rn "class.*Step.*:" ai_workflows/workflows/summarize.py ai_workflows/workflows/summarize_tiers.py` returns zero hits. The H2 lock's "stop and ask the user" hard-stop did not need to fire. |
| Carry-over TA-LOW-02 — module-restructuring fallback threshold | ✅ HANDLED (cycle 2: checkbox now ticked) | Builder kept `summarize_tiers.py` separate (no inline fallback); summarize.py docstring lines 28-29 explicitly note "split kept because no circular imports surfaced at implement time". Decision is sound; cycle-2 flipped the checkbox to `[x]` (LOW-1 resolved). |
| Carry-over TA-LOW-10 — straggler `_run_workflow` reference in spec sketch comment | ✅ HANDLED (cycle 2: checkbox now ticked) | The straggler reference was in spec Deliverable 4's *sketch* (line 214's Python comment). The actual `cli.py` shipped uses `_dispatch_run_workflow` (the renamed local alias for the imported `run_workflow` function — see `cli.py:89-91`). The sketch comment was illustrative only; nothing to fix in source. Cycle-2 flipped the checkbox to `[x]` (LOW-1 resolved). |

**Summary:** 13 ACs PASS; 2 carry-over items HANDLED. The two MEDIUMs (MEDIUM-1, MEDIUM-2) are spec-faithfulness questions — they do not turn any AC red because the AC *text* is met, but they undermine the spec's *intent* on two specific points (ValidateStep step-type exercise; cross-surface byte-identity proof through actual entry-points).

## Cycle 2 critical sweep (2026-04-26 re-audit)

Spot-checked the cycle-2 edits for new findings:

- **No silently-skipped deliverables.** All 8 cycle-1 findings addressed. Builder's report claim count (8) matches what landed.
- **No coverage drop from docstring rewrites.** `summarize.py` module docstring still cites M19 T04, ADR-0008, locked H2 (2026-04-26), dual purpose, and relationship to other modules. No required content lost; reframing is additive (more honest framing, not less detail).
- **No coverage drop from test rewrite.** `test_summarize_artefact_identical_across_surfaces` still asserts byte-identity from both surfaces; the rewrite *adds* coverage (CLI side now drives the actual `aiw run` entry-point) without removing any prior assertion. Test 1 (`test_aiw_run_summarize_via_input_kvs`) still drives `aiw run` end-to-end; Test 4 still drives MCP via FastMCP server; Test 5 now joins them with cross-surface byte-identity.
- **No coverage drop from `test_summarize_validator_step_runs` tightening.** Cycle 1's permissive `in (...)` accepted both branches; cycle 2 pins `errored` (the actual contract). The LLMStep paired-validator semantic-retry exhaustion path is now a hard pin (was permissive); the standalone-`ValidateStep` no-op claim is documented in the test docstring + module docstring (was buried in the audit issue file only).
- **No T02 reopening.** LOW-6 backfill on `issues/task_02_issue.md:352-365` is appended as a new section; T02 **Status:** line at line 6 is unchanged (`✅ PASS (cycle 2 — MEDIUM-1 + MEDIUM-2 + LOW-1 + LOW-3 resolved; LOW-2 + LOW-4 remain open as documented out-of-scope deferrals)`). T02's existing AC grading + cycle-1/cycle-2 history preserved. Backfill is purely additive doc-trail.
- **No new architectural drift.** Cycle 2 touched only docs + assertions + one test rename. No source-code logic changed. KDR-002 / KDR-003 / KDR-004 / KDR-006 / KDR-008 / KDR-009 / KDR-013 all unchanged. Layer rule unbroken (107 dependencies, 4 contracts kept).
- **No new gate-integrity drift.** All three gates re-run from scratch; all pass. No "passed at Builder, fails at Auditor" deltas.
- **Status-surface integrity post-cycle-2.** All four surfaces aligned: T04 spec **Status:** ✅ Done; milestone README task table row 04 ✅ Implemented; no `tasks/README.md` for M19 (inapplicable); milestone README uses numbered prose for exit criteria (no `[ ]` to flip; exit-criterion 5 prose matches landed work).

**Cycle 1 critical sweep preserved below for audit history.**

## Critical sweep — additional concerns

- **No silently-skipped deliverables.** Every Deliverable in the spec (1–7) is materialised in the diff; the H2-deferral framing decision (item 7 of the spec README §Decisions) is honoured (no CHANGELOG `### Changed` for the deferral framing — correct per AC-12).
- **No additions beyond spec for spec creep / coupling.** The four `_compiler.py` edits are latent-bug fixes (see Design-drift Phase 1 note); the new `aiw show-inputs` subcommand is within Builder discretion at spec line 217. The `_dispatch_run_workflow` alias rename in cli.py was already in place before T04.
- **Test gaps.** Two:
  - **MEDIUM-1**: `test_summarize_validator_step_runs` does not actually exercise the ValidateStep step type's validation behaviour because the standalone ValidateStep is a no-op in the summarize spec.
  - **MEDIUM-2**: Test 5 does not actually drive both surfaces through their entry-points; the CLI side bypasses `aiw run`.
- **Doc drift.** None within T04's scope. T05 (the doc rewrite) explicitly cites `summarize.py` as the worked-example source; that cross-reference is preserved. T05 will land at its own milestone task; T04 does not edit docs.
- **Secrets shortcuts.** None. `.env.example` placeholder unchanged; no new secrets surface.
- **Scope creep from `nice_to_have.md`.** None. The four `_compiler.py` edits are bug fixes within T02's scope (latent-bugs caught at T04); none introduce new step types, new graph primitives, or new MCP tools.
- **Status-surface drift.** Three of four surfaces aligned:
  1. Per-task spec **Status:** line — `task_04_summarize_proof_point.md:3` reads `**Status:** ✅ Done (implemented 2026-04-26).` — correct.
  2. Milestone README task table row — `README.md:160` reads `| 04 | ... | ✅ Implemented (2026-04-26) |` — correct.
  3. `tasks/README.md` — does not exist for milestone 19 (verified: `find design_docs/phases/milestone_19_declarative_surface/tasks/`returns no such directory). Inapplicable.
  4. Milestone README "Done when" / Exit criteria — Item 5 of the numbered Exit criteria block (line 108) describes T04's deliverables; all are landed. The README uses numbered prose, not `[ ]` markdown checkboxes, so there is nothing to flip per CLAUDE.md status-surface discipline literally — but the exit-criterion text matches the landed work. No drift.

  However: the spec's own **Acceptance Criteria** section uses `[ ]` checkboxes that the Builder did not flip — see **LOW-1**. Per CLAUDE.md "Carry-over section at the bottom of a spec = extra ACs. Tick each as it lands.", these should be flipped at task close. This is a Builder-discipline gap, not behavioural drift.

## 🔴 HIGH

*None.* All spec ACs are met against their text; KDRs preserved; gates green; layer rule unbroken. The two MEDIUMs below identify spec *intent* gaps that did not turn any AC red.

## 🟡 MEDIUM

### MEDIUM-1 — Standalone `ValidateStep` is a runtime no-op in `summarize.py`; the spec's "deliberately exercise the `ValidateStep` step type" intent is unmet — RESOLVED 2026-04-26 (cycle 2)

**Cycle 2 status — RESOLVED via locked Path (i) (accept no-op + reframe).** User locked Path (i) before cycle 2; Builder applied the reframing across four surfaces:

1. `ai_workflows/workflows/summarize.py:15-25` — module docstring now reads *"The `ValidateStep` after the `LLMStep` is illustrative — it shows downstream consumers how to compose `ValidateStep` syntactically, but in this exact configuration where its `schema` matches the upstream `LLMStep.response_format`, it is a runtime no-op (the LLMStep's paired validator already validated). T01's hermetic tests cover `ValidateStep`'s test surface standalone (`tests/workflows/test_spec.py` exercises `ValidateStep` construction + cross-step invariants) and T02's compiler tests cover its compile path (`tests/workflows/test_compiler.py::test_compile_validate_step_emits_validator_node`). M19's test surface for the step type is covered there, not here."* The pedagogical claim is reframed honestly — the workflow shows *syntactic composition* of `ValidateStep`, not its *runtime validation* behaviour, and the docstring points readers to T01/T02's coverage for the actual step-type proof.

2. `ai_workflows/workflows/summarize.py:103` inline comment — `ValidateStep(  # illustrative; runtime no-op when schema == upstream LLMStep.response_format`.

3. `task_04_summarize_proof_point.md:102` Deliverable 1 bullet — *"`response_format=SummarizeOutput` — the validator pairing is automatic (KDR-004 by construction per T01 + T02). The `ValidateStep` after the `LLMStep` is illustrative; in this exact configuration where its `schema` matches the upstream `LLMStep.response_format`, it is a runtime no-op (the LLMStep's paired validator already validated). The composition is shown for syntactic illustration only."* Matches the module docstring + inline comment.

4. `tests/workflows/test_summarize.py:240-279` test docstring + assertion — test renamed-via-docstring (test function name kept as `test_summarize_validator_step_runs` for stability of test IDs; docstring fully reframed): *"LLMStep's paired validator (KDR-004) catches malformed LLM output. ... The standalone `ValidateStep` in `_SPEC` is illustrative and a runtime no-op in this configuration (the LLMStep's paired validator already validated; the standalone ValidateStep receives a `SummarizeOutput` instance, not a JSON string). The contract being proven here is semantic-retry exhaustion → `errored` status with a validation-failure error message."* Assertion now reads `assert result["status"] == "errored"` + `assert result["error"] is not None` (was the permissive `result["status"] in ("errored", "completed")`); the LLMStep's paired-validator semantic-retry exhaustion path is now pinned hard. (LOW-5 resolved alongside.)

**Re-ran the test in isolation post-audit:** `tests/workflows/test_summarize.py::test_summarize_validator_step_runs PASSED [ 36%]`. Status `errored`, error populated.

**Cycle-1 finding text preserved below for audit history.**

---

**Where:**
- Spec source: Deliverable 1 line 102 — *"`response_format=SummarizeOutput` — the validator pairing is automatic (KDR-004 by construction per T01 + T02). The `ValidateStep` after the `LLMStep` is **redundant** validation against the same schema; it's there as a deliberate exercise of the `ValidateStep` step type so M19's test surface covers it."*
- Implementation site: `ai_workflows/workflows/summarize.py:91-94` — `ValidateStep(target_field="summary", schema=SummarizeOutput)`.
- Compile site: `ai_workflows/workflows/_compiler.py:631-654` (`_compile_validate_step`) — emits a `validator_node(schema=SummarizeOutput, input_key="summary", output_key="summary", max_attempts=1)` wrapped with `wrap_with_error_handler`.
- Dispatch precedence: `ai_workflows/workflows/_dispatch.py:829-863` — `_build_result_from_final` checks `final.get(final_state_key) is not None` BEFORE checking `last_exception`.

**Why it matters.** The compile path produces a `ValidatorNode` that calls `SummarizeOutput.model_validate_json(state["summary"])`. By the time this node runs, the upstream LLMStep's paired validator has already populated `state["summary"]` with a `SummarizeOutput` *instance* (not a JSON string). Pydantic's `model_validate_json` requires `str | bytes | bytearray`; passing a model instance raises `ValidationError`. With `max_attempts=1`, the node escalates immediately to `NonRetryable` via the validator's exhaustion path. The error handler catches the `NonRetryable` and writes `last_exception` to state. The unconditional edge then routes to `END`.

But: dispatch's completed-branch check (`final.get("summary") is not None`) fires BEFORE the `last_exception` check. Since `state["summary"]` is populated (the upstream validator wrote it), the workflow returns `status="completed"` and the `NonRetryable` from the standalone ValidateStep is silently swallowed.

**Verified by direct runtime trace** (Auditor reproduced via instrumented `validator_node`):
```
ValidatorNode step_0_llmstep_validate input_key='step_0_llmstep_call_output'
  state[input_key]=str value='{"summary": "hello"}'
ValidatorNode step_1_validatestep_validate input_key='summary'
  state[input_key]=SummarizeOutput value=SummarizeOutput(summary='hello')
Status: completed
```

**Impact.**
- The spec's intent ("M19's test surface covers the ValidateStep step type") is unmet at the spec API level. The five built-in step types ship and four are exercised end-to-end (LLMStep, GateStep, TransformStep, FanOutStep all have dedicated tests in `test_compiler.py`); ValidateStep's *standalone* compile path runs in `test_compile_minimal_validate_only_spec` (T02 — which DOES validate a pure-string state field through ValidateStep correctly), but the spec API at the *workflow* level (`summarize.py`) does not actually exercise the step type's validation behaviour because the upstream LLMStep already populated the channel with an instance.
- The Builder noticed and flagged this as deviation #4. Builder's reading: "The redundant ValidateStep doesn't add testable surface in this configuration." Auditor's reading: agreed, AND the spec's intent of using `summarize` as the deliberate ValidateStep exercise is unmet.
- `test_summarize_validator_step_runs` (the test the spec calls out as the "ValidateStep" coverage) is consequently structurally weak: it asserts `result["status"] in ("errored", "completed")` because the Builder couldn't predict which branch fires (it actually fires "errored" — the LLMStep's *paired* validator catches the malformed JSON before the standalone ValidateStep matters; verified at runtime). The test name promises ValidateStep coverage; what it actually covers is the LLMStep's paired-validator semantic-retry exhaustion path.
- Composability concern: a future spec author copying `summarize.py` as a template (per ADR-0008's worked-example framing) and adding their own `ValidateStep(target_field=..., schema=...)` after an LLMStep with the *same* schema will get a no-op ValidateStep too, with the same silent-swallow behaviour. This is a foot-gun for the spec API at the doc-surface layer (T05's worked-example doc).

**Why this is MEDIUM not HIGH.**
- The spec text is met (AC-1 says "ValidateStep" appears in `_SPEC.steps`; it does). KDR-004 is upheld via the LLMStep's paired validator (the load-bearing validator for the workflow's actual schema gate).
- The framework's KDR-004 invariant is not broken — the paired validator on the LLMStep is the effective KDR-004 gate; the standalone ValidateStep being a no-op doesn't weaken framework correctness, only the spec's pedagogical claim.
- The standalone ValidateStep at T02 (`test_compile_minimal_validate_only_spec` — a `WorkflowSpec` with a single ValidateStep against a pure-string state field) DOES exercise the step type's validation behaviour. T02's compiler-test surface covers ValidateStep correctly; only the workflow-level (T04) exercise is missing.

**Action / Recommendation — user decision needed.**

Two viable paths, both reasonable. The audit recommends path (i) for cycle 1 (the cheaper fix; preserves the spec's pedagogical claim by reframing what the ValidateStep test is asserting). Path (ii) is the more rigorous fix:

(i) **Accept the no-op + reframe the test surface.** Update `summarize.py:88-94`'s ValidateStep docstring to explicitly note "redundant against the LLMStep's paired validator under this configuration; included for spec-API surface coverage and as a placeholder a future author may rewire". Update `test_summarize_validator_step_runs` test name + docstring to "test_summarize_llm_step_paired_validator_catches_malformed_output" (the actual contract it tests) — and add a single new test `test_validate_step_step_type_compiles_and_runs_in_isolation` that builds a tiny `WorkflowSpec` with a `TransformStep → ValidateStep` shape (Transform writes a dict-like string to state; ValidateStep validates it as a JSON string against a small pydantic schema) so the ValidateStep step type's *validation* behaviour is actually proven. This adds ~30 lines of test surface; lands in `test_summarize.py` or as a new test in `test_compiler.py`.

(ii) **Restructure summarize to put a non-redundant ValidateStep.** Replace the redundant ValidateStep with a `TransformStep` that mutates `state["summary"]` (e.g. truncates it; adds a synthetic field) followed by a `ValidateStep` that validates against a *different* schema (e.g. `TruncatedSummaryOutput`). This makes the ValidateStep meaningful in the workflow and the spec's worked-example claim holds. Cost: more shape complexity in the proof-point workflow (small risk of obscuring the "simplest realistic spec" framing — Deliverable 1 line 31).

The audit recommends path (i). Path (ii) is closer to the spec's literal intent but trades the spec's "simplest realistic shape" framing.

**Forward-deferral target:** This task's cycle 2 (next Builder pass). The fix is small and self-contained.

### MEDIUM-2 — Cross-surface artefact identity test (Test 5) bypasses the actual CLI surface — RESOLVED 2026-04-26 (cycle 2)

**Cycle 2 status — RESOLVED.** Builder rewrote `test_summarize_artefact_identical_across_surfaces` as a synchronous test (no `@pytest.mark.asyncio`); verified at `tests/integration/test_spec_api_e2e.py:286-385`:

- **CLI side (sync — CliRunner internally calls asyncio.run):** `cli_result = _RUNNER.invoke(app, ["run", "summarize", "--input", "text=Identity test input text.", "--input", "max_words=20", "--run-id", "smry-identity-cli"])`. The Typer `aiw run` entry-point is now genuinely driven; no `_dispatch.run_workflow` shortcut. Artefact extracted from CLI stdout via a `json.JSONDecoder.raw_decode` loop that consumes the structured-log preamble and keeps the last JSON object before the `"total cost:"` footer (the workflow artefact `_emit_cli_run_result` prints).
- **MCP side (sync — `asyncio.run` wraps the async tool call):** `_asyncio.run(_mcp_call())` wrapping `await tool.fn(RunWorkflowInput(workflow_id="summarize", inputs={...}, run_id="smry-identity-mcp"))`. The actual MCP entry-point is driven (no async-test nesting conflict because the test is sync).
- **Cross-surface byte-identity assertions:** `assert cli_artefact == mcp_artefact` and `assert cli_artefact == {"summary": stub_summary}`. Both surfaces now genuinely produce their own artefacts and the byte-identity claim is no longer tautological.

**Re-ran the test in isolation post-audit:** `tests/integration/test_spec_api_e2e.py::test_summarize_artefact_identical_across_surfaces PASSED [ 90%]`. Both surfaces emit `{"summary": "Stub summary output for identity test."}` from the shared stub.

**Cycle-1 finding text preserved below for audit history.**

---

**Where (cycle 1):** `tests/integration/test_spec_api_e2e.py:284-345` — `test_summarize_artefact_identical_across_surfaces`.

**Symptom.** The test is the "load-bearing wire-level proof" per spec Deliverable 5 §Test 5 ("Pins refinement #5 (load-bearing wire-level proof — both surfaces produce the same result)"). The spec's intent: drive `summarize` through *both* surfaces using their actual entry-points (`CliRunner.invoke` for the CLI side; `fastmcp.Client` / `build_server().get_tool()` for the MCP side); assert byte-identical artefacts.

The Builder's implementation drives the MCP side via `build_server().get_tool("run_workflow").fn(payload)` (correct — exercises MCP's actual tool surface). The Builder's "CLI side" calls `_dispatch.run_workflow(...)` directly — bypassing `aiw run`'s actual entry-point.

**Builder's stated reason** (CHANGELOG line 23, deviation #1): *"Test 5 in `test_spec_api_e2e.py` uses direct `run_workflow` dispatch (not `CliRunner.invoke`) because `CliRunner` calls `asyncio.run()` internally — cannot be used inside a `@pytest.mark.asyncio` test without nested event-loop conflict."*

**Auditor verification of the conflict.** Real and reproducible. `aiw run` calls `asyncio.run(_run_async(...))` at `cli.py:336`. Inside an `@pytest.mark.asyncio` test (which runs in a pytest-asyncio managed event loop), invoking `CliRunner.invoke(app, ["run", ...])` would synchronously call `asyncio.run` from inside an already-running loop — Python raises `RuntimeError("asyncio.run() cannot be called from a running event loop")`. The Builder's deviation is technically necessary *given* the chosen test shape (async function + CliRunner inside it). The conflict is genuine.

**However: a clean fix exists.** The test can be made synchronous (drop the `@pytest.mark.asyncio` decorator) and call `asyncio.run(mcp_tool.fn(payload))` for the MCP side from the sync test. This works because the test isn't itself an async coroutine; the MCP-call awaiting happens inside a one-shot `asyncio.run` (the same pattern Test 1 uses — Test 1 is sync, calls `CliRunner.invoke` which internally runs `asyncio.run`, and exercises the CLI surface end-to-end). The Builder appears to have not considered the sync-test option — Test 4 (`test_aiw_mcp_run_workflow_summarize_via_fastmcp_client`) IS marked `@pytest.mark.asyncio` and works correctly because it doesn't also use CliRunner; the conflict is specific to the cross-surface test.

**Impact.**
- The CLI surface IS exercised end-to-end in **Test 1** (`test_aiw_run_summarize_via_input_kvs`) — that test uses `CliRunner.invoke` against `aiw run summarize --input ...` and verifies exit code 0 + artefact in stdout. So the CLI surface is *separately* proven.
- The MCP surface IS exercised end-to-end in **Test 4** — `result.artifact["summary"] == ...` against the FastMCP server.
- What's not proven: that *both* surfaces produce a byte-identical artefact for the same stub response in the same test. Spec Deliverable 5 §Test 5 calls this out as load-bearing ("the wire-level proof through both surfaces is load-bearing — α was rejected because shipping a brand-new authoring surface with no wire-level integration test = first external user becomes the integration test"). The hand-off to T08's release ceremony for live-Gemini cross-surface verification still happens later, so this is not an existential gap — it's a one-cycle weakening.

**Why this is MEDIUM not HIGH.**
- The CLI surface IS exercised end-to-end (Test 1).
- The MCP surface IS exercised end-to-end (Test 4).
- The byte-identity claim is technically observable: Test 5 asserts `dispatch_artefact == mcp_artefact` for the dispatch helper-routed path; both go through the *same* `_dispatch.run_workflow` underneath; the comparison is a tautological identity (same function, same inputs, same stub) rather than a cross-surface proof.
- The spec's "first external user becomes the integration test" risk is partially mitigated by Tests 1 + 4 covering both surfaces independently. The remaining residual risk is that the CLI-surface stdout-rendering path (`_emit_cli_run_result` at `cli.py:405-438`) might shape the artefact differently from the MCP-surface schema-rendering path (`RunWorkflowOutput` at `mcp/schemas.py:121-146`); Test 5's current shape doesn't exercise that.

**Action / Recommendation.**

Cheap fix (recommended for cycle 2): rewrite Test 5 as a synchronous test:

```python
def test_summarize_artefact_identical_across_surfaces() -> None:
    # CLI side (sync — CliRunner internally calls asyncio.run)
    _StubLiteLLMAdapter.script = [(stub_response, 0.0)]
    cli_result = _RUNNER.invoke(app, ["run", "summarize", "--input", "text=...",
                                      "--input", "max_words=20",
                                      "--run-id", "smry-identity-cli"])
    assert cli_result.exit_code == 0
    cli_artefact = json.loads(cli_result.output.split("\n")[0])  # first JSON line

    # MCP side (sync — asyncio.run wraps the async tool call)
    _StubLiteLLMAdapter.reset()
    _StubLiteLLMAdapter.script = [(stub_response, 0.0)]

    async def _mcp_call():
        server = build_server()
        tool = await server.get_tool("run_workflow")
        return await tool.fn(RunWorkflowInput(workflow_id="summarize",
                                              inputs={"text": "...", "max_words": 20},
                                              run_id="smry-identity-mcp"))

    mcp_result = asyncio.run(_mcp_call())

    # Cross-surface byte-identity
    assert cli_artefact == mcp_result.artifact == {"summary": stub_summary}
```

This drives the *actual CLI* and the *actual MCP* surfaces with no `_dispatch.run_workflow` shortcut, satisfies the spec's intent, and avoids the asyncio nesting issue. ~20-line edit; no behavioural change to the workflow.

**Forward-deferral target:** This task's cycle 2 (alongside MEDIUM-1 fix).

## 🟢 LOW

### LOW-1 — Acceptance-criteria + carry-over checkboxes not flipped at task close — RESOLVED 2026-04-26 (cycle 2)

**Cycle 2 status — RESOLVED.** Builder flipped all 13 AC checkboxes (AC-1 through AC-13) + both carry-over checkboxes (TA-LOW-02 + TA-LOW-10) from `- [ ]` to `- [x]`. Verified by `grep -c "^- \[x\]"` returning 15 and `grep -c "^- \[ \]"` returning 0 against `task_04_summarize_proof_point.md`. All four status surfaces now align: spec **Status:** ✅ Done; milestone README task table row 04 ✅ Implemented; no `tasks/README.md` exists for M19 (inapplicable); milestone README uses numbered prose for exit criteria (no `[ ]` to flip).

**Cycle-1 finding text preserved below for audit history.**

---

**Where (cycle 1):** `design_docs/phases/milestone_19_declarative_surface/task_04_summarize_proof_point.md:257-300`. AC-1 through AC-13 are still `- [ ]`; carry-over items TA-LOW-02 + TA-LOW-10 are still `- [ ]`.

**Symptom.** The Builder flipped the **Status:** line (line 3) to `✅ Done` and the milestone README task table row (line 160) to `✅ Implemented`, but did not flip the per-AC `[ ]` boxes inside the `## Acceptance Criteria` section nor the per-carry-over `[ ]` boxes inside `## Carry-over from task analysis`. Per CLAUDE.md `## Non-negotiables`: *"Carry-over section at the bottom of a spec = extra ACs. **Tick each as it lands.**"*

**Impact.** Cosmetic / doc-discipline. The status surfaces (top-level Status line, README table row) are correct; only the per-AC checkboxes inside the spec body are out of sync. A future reader scanning the spec would see "Status: Done" but every AC unchecked — a small "did this actually land?" confusion vector.

**Action / Recommendation.** Mechanical edit on the spec file: flip every `- [ ]` AC to `- [x]` AC for AC-1 through AC-13 + TA-LOW-02 + TA-LOW-10. ~15-line mechanical Builder follow-up, no source-code change.

**Owner:** This task (cycle 2 close-out) or the `/clean-implement` loop's final pass.

### LOW-2 — `test_run_missing_goal_exits_two` under-asserts vs. spec Deliverable 4 — RESOLVED 2026-04-26 (cycle 2)

**Cycle 2 status — RESOLVED.** Builder added `assert "required" in combined.lower()` after the existing `assert "goal" in combined.lower()` at `tests/cli/test_run.py:278`. Both substrings the test docstring promises are now asserted (matches spec Deliverable 4's "error message contains `'goal'` + `'required'`" requirement).

**Re-ran the test in isolation post-audit:** `tests/cli/test_run.py::test_run_missing_goal_exits_two PASSED [100%]`. Both `'goal'` and `'required'` present in the combined output.

**Cycle-1 finding text preserved below for audit history.**

---

**Where (cycle 1):** `tests/cli/test_run.py:261-277`.

**Symptom.** The migrated test's docstring promises (line 271) *"the error message still contains `goal` and `required`"*, mirroring the spec Deliverable 4 §"Existing-test migration" requirement (*"error message contains 'goal' + 'required'"*). But the assertion on line 277 only checks `"goal" in combined.lower()`. The actual runtime output (auditor manually verified) DOES contain "Field required" via the pydantic ValidationError wrapping — so the spec's behavioural intent is met; the test just doesn't assert it.

**Impact.** Cosmetic. If a future change to the BadParameter wrapping accidentally drops the "required" framing, this test would not catch it; a reader of the test docstring is led to believe both substrings are checked.

**Action / Recommendation.** Add `assert "required" in combined.lower()` to `tests/cli/test_run.py:278`. One-line edit.

**Owner:** This task (cycle 2 close-out) or absorb into the next test-touching task.

### LOW-3 — CHANGELOG entry says "ACs satisfied: AC-1 through AC-11"; spec has AC-1 through AC-13 — RESOLVED 2026-04-26 (cycle 2)

**Cycle 2 status — RESOLVED.** Builder rewrote the cycle-1 entry's count line to *"ACs satisfied: AC-1 through AC-13 (all task ACs; AC-12 = this entry; AC-13 = no new step types — only LLMStep + ValidateStep used)."* (verified at `CHANGELOG.md:35`). The cycle-2 entry (added immediately above the cycle-1 entry per Keep-a-Changelog ordering) cites the cycle-2 fixes; the cycle-1 entry is preserved with the corrected count line.

**Cycle-1 finding text preserved below for audit history.**

---

**Where (cycle 1):** `CHANGELOG.md:20`. The `### Added` block reads *"ACs satisfied: AC-1 through AC-11 (all task ACs)."* The spec lists AC-1 through AC-13.

**Symptom / Impact.** Under-counts the ACs. AC-12 (CHANGELOG entry exists) is self-referentially satisfied by the entry's existence; AC-13 (no new step types added) is implicitly satisfied (only LLMStep + ValidateStep used; verified). No actual coverage gap; just an off-by-two count in the prose.

**Action / Recommendation.** Edit `CHANGELOG.md:20` to read *"ACs satisfied: AC-1 through AC-13 (all task ACs; AC-12 = this entry; AC-13 = no new step types — only LLMStep + ValidateStep used)."* One-line edit.

**Owner:** This task (cycle 2 close-out).

### LOW-4 — Test name `test_aiw_run_summarize_help_lists_input_fields` does not match what it tests — RESOLVED 2026-04-26 (cycle 2)

**Cycle 2 status — RESOLVED.** Builder renamed the test to `test_aiw_show_inputs_summarize_lists_input_fields` (verified at `tests/integration/test_spec_api_e2e.py:198`). The test body remains the same — it invokes `_RUNNER.invoke(app, ["show-inputs", "summarize"])` and asserts both `text` and `max_words` field names in stdout — but the function name now matches the actual UX exercised. Module docstring updated at line 9 to match. `grep -n "test_aiw_run_summarize_help_lists_input_fields"` returns zero hits across the test tree (old name fully removed).

**Cycle-1 finding text preserved below for audit history.**

---

**Where (cycle 1):** `tests/integration/test_spec_api_e2e.py:198-213`.

**Symptom.** The test name promises `aiw run summarize --help` lists input fields. The test actually invokes `aiw show-inputs summarize` (the separate subcommand the Builder picked per spec line 217 Builder discretion). The spec's Deliverable 5 §Test 2 prescribes *"uses `CliRunner` to invoke `aiw run summarize --help` (or whatever the locked-H1 help-rendering UX shape lands as)"* — explicitly admits Builder UX choice — but the test name was not updated to reflect the chosen UX (`show-inputs`).

**Impact.** Cosmetic / discoverability. A reader scanning test names expecting `aiw run --help` coverage would not find the test (since it tests a different command); a future Builder grepping test names for `--help` rendering would miss this test.

**Action / Recommendation.** Rename to `test_aiw_show_inputs_summarize_lists_input_fields`. One-line rename. Optionally also add a separate small test that asserts `aiw run summarize --help` (the literal command from the spec) at least mentions the `--input` flag (which it does, manually verified). Two-line addition.

**Owner:** This task (cycle 2 close-out) or absorb into a future test-touching task.

### LOW-5 — `test_summarize_validator_step_runs` assertion is permissively under-specified to absorb MEDIUM-1's no-op behaviour — RESOLVED 2026-04-26 (cycle 2)

**Cycle 2 status — RESOLVED (composes with MEDIUM-1 resolution).** Builder tightened the assertion at `tests/workflows/test_summarize.py:273-279` to:

```python
# Semantic-retry exhaustion → errored status (not completed)
assert result["status"] == "errored", (
    f"Expected 'errored' after exhausting semantic retry budget, "
    f"got {result['status']!r}: {result.get('error')}"
)
assert result["error"] is not None, (
    "error field must be populated when status='errored'"
)
```

The cycle-1 permissive `result["status"] in ("errored", "completed")` is gone; the test now pins the LLMStep paired-validator semantic-retry exhaustion contract hard. Test docstring fully reframed (cycle 2) to describe what the test actually proves: *"LLMStep's paired validator (KDR-004) catches malformed LLM output. ... The standalone `ValidateStep` in `_SPEC` is illustrative and a runtime no-op in this configuration ..."*

**Re-ran the test in isolation post-audit:** PASSED in 0.32 s. Status `errored`, error populated.

**Cycle-1 finding text preserved below for audit history.**

---

**Where (cycle 1):** `tests/workflows/test_summarize.py:271-279`. The assertion reads `assert result["status"] in ("errored", "completed")` with the comment *"With all responses malformed, the workflow should error"*.

**Symptom.** The test was deliberately weakened to accept either branch because the Builder noticed (correctly) that the upstream LLMStep's paired validator catches the malformed JSON before the standalone ValidateStep runs, and that determining which path fires depends on retry-budget timing the test doesn't strictly control. With `max_semantic_attempts=2`, both attempts return malformed JSON, the LLMStep's paired validator escalates `RetryableSemantic → NonRetryable` on attempt 2; `state["summary"]` is never written; `last_exception` is set; dispatch returns `errored`. Auditor manually verified: the actual status fired is `errored`. So the assertion COULD pin `result["status"] == "errored"` confidently.

**Impact.** The test is permissively shaped to swallow either outcome; this hides a real contract (semantic-retry exhaustion → errored status). The test name promises ValidateStep coverage; what it covers is LLMStep paired-validator exhaustion — and even THAT contract is under-asserted by the permissive in-tuple check.

**Action / Recommendation.** Tighten to `assert result["status"] == "errored"` and `assert "semantic" in (result.get("error") or "").lower()` (or equivalent — the actual error message includes "exhausted semantic retry budget"). Pair with MEDIUM-1's recommended path (i): rename the test to reflect the actual contract being exercised.

**Owner:** This task (cycle 2 close-out, alongside MEDIUM-1 fix).

### LOW-6 — Backfill T02's issue file with "latent bugs caught at T04" — RESOLVED 2026-04-26 (cycle 2)

**Cycle 2 status — RESOLVED.** Builder appended a `## Post-close T02 latent fixes — surfaced + applied during M19 T04 (2026-04-26)` section to `design_docs/phases/milestone_19_declarative_surface/issues/task_02_issue.md:352-365` documenting all four `_compiler.py` latent fixes:

1. `on_terminal` parameter on `_compile_llm_step` (multi-step routing)
2. `path_map_override` on `GraphEdge` (path-map routing preservation)
3. Inter-step stitching skip for LLMStep exit nodes (avoid duplicate edges)
4. `initial_state` pre-init of LLMStep intermediate keys + framework-internal keys (AsyncSqliteSaver `durability='sync'` round-trip correctness)

The section explicitly notes *"These are post-T02-close findings that don't reopen T02's audit — the issue file remains ✅ PASS. Documenting here for traceability + so the T07 documentation pass can reference them if relevant. None of the four fixes affect the user-facing spec API; all are compile-path internals."* T02 **Status:** line at line 6 is unchanged (`✅ PASS (cycle 2 — MEDIUM-1 + MEDIUM-2 + LOW-1 + LOW-3 resolved; LOW-2 + LOW-4 remain open as documented out-of-scope deferrals)`) — backfill did not re-open T02. New `M19-T02-ISS-07` row appended to T02's issue log table at line 365 (RESOLVED 2026-04-26 at T04 cycle 1; regression tests cited).

**Cycle-1 finding text preserved below for audit history.**

---

**Where (cycle 1):** Four `_compiler.py` edits made during T04 cycle (see Phase 1 note in §Design-drift check).

**Symptom.** T02's issue file (`task_02_issue.md`) is closed as `✅ PASS` (cycle 2). T04 surfaced four latent bugs in T02's compiler that only manifest when running a multi-step composed `WorkflowSpec` end-to-end through the actual dispatch path against an `AsyncSqliteSaver`. T02's test surface was incomplete (only single-step or stub-builder scenarios). The bugs are real and now fixed in `_compiler.py` (verified — all 23 T02 tests + 16 T01 tests still green; 39/39).

**Impact.** Doc-trail / future-audit clarity. A future audit reading T02's issue file sees `✅ PASS` and might miss that T02's compiler had latent multi-step composition + AsyncSqliteSaver durability bugs that were later caught and fixed at T04. The fix landed correctly; the audit-trail provenance is what's missing.

**Action / Recommendation.** Append a short "Cycle 3 (caught at T04 audit)" subsection to `task_02_issue.md`'s `## Issue log` table:

```
| M19-T02-ISS-07 | LOW (latent at T02; surfaced + fixed at T04) | T04 cycle 1 — `_compile_llm_step` now takes `on_terminal=` for multi-step routing; `GraphEdge` gained `path_map_override`; inter-step stitching skips LLMStep exit nodes; `initial_state` pre-initialises LLMStep intermediate keys + framework-internal keys for AsyncSqliteSaver `durability='sync'` round-trip correctness. T02 cycle-3-by-proxy. | RESOLVED 2026-04-26 (at T04 cycle 1) — `_compiler.py:436-459 + 296-348 + 372-391 + 217-253`; regression tests at `test_summarize.py::test_summarize_compiles_to_runnable_state_graph` + `test_summarize_retry_policy_on_transient_failure`. |
```

This is doc-trail housekeeping; no source-code change required, no T02 ACs flip.

**Owner:** Auditor (this task) or a future "audit hygiene" pass on the M19 issue files.

## Additions beyond spec — audited and justified

Five additions; all directly traceable to the spec's intent and necessary for safety. None add coupling, scope creep, or `nice_to_have.md` adoption.

### Addition 1 — `_compile_llm_step` takes `on_terminal=` parameter (compiler edit)

**Where:** `_compiler.py:489-496` + the `_next_entry_for_step` helper at `_compiler.py:314-348`.

**Justification.** Without this, retrying_edge's success path always routes to `END` for every LLMStep, which is correct for a single-step LLMStep-only spec (T02's test surface) but wrong for a multi-step spec where LLMStep should flow to the next step on success. T04's `summarize` is the first multi-step composed spec running end-to-end; the bug surfaces immediately. Latent T02 bug; necessary T04 fix.

### Addition 2 — `path_map_override` field on `GraphEdge`

**Where:** `_compiler.py:125` + path-map resolution at `_compiler.py:430-441`.

**Justification.** Supports Addition 1 — without an explicit path map, `add_conditional_edges` defaults to `{source, target, END}` which doesn't include the next-step entry that retrying_edge now routes to. Implementation detail of the on-terminal change.

### Addition 3 — Inter-step stitching skips LLMStep exit nodes

**Where:** `_compiler.py:377-391` (the `exit_has_conditional` check + `continue`).

**Justification.** When retrying_edge wires from the validate node, an unconditional `validate → next_step.entry` would conflict with the conditional retrying_edge at the same source. The skip prevents LangGraph from getting two competing edges from the same source node. Necessary fix.

### Addition 4 — `initial_state` pre-initialises LLMStep intermediate keys + framework-internal keys

**Where:** `_compiler.py:217-225` + `_compiler.py:246-253`.

**Justification.** AsyncSqliteSaver + `durability='sync'` writes a checkpoint after each node. If an LLMStep call node fails on the first attempt, its output key (`f"{step_id}_call_output"`) was never written to state. On the next checkpoint restore (before the validate node runs) the key is absent, causing `KeyError` inside validator_node. Initialising these keys to `None` in initial_state ensures they are present in the very first checkpoint and survive round-trips through the SQLite serialiser. Verified by `test_summarize_retry_policy_on_transient_failure` (which runs the transient-retry path end-to-end through the real checkpointer). Necessary fix; latent T02 + KDR-009 round-trip-correctness bug.

### Addition 5 — `aiw show-inputs <workflow>` subcommand

**Where:** `cli.py:446-512`.

**Justification.** Spec Deliverable 4 line 217 explicitly admits Builder discretion on the help-text discoverability UX (refinement #4 — "Builder picks the exact UX at implement time"). Builder picked a separate `show-inputs` subcommand over a custom `--help` callback. The chosen UX is cleaner and surfaces field types + required/optional + defaults in a parseable form; the test asserts every input field name appears in the output. Within Builder discretion; no scope creep.

All five additions are within the spec's intent. The four `_compiler.py` edits are latent-bug fixes; the `show-inputs` subcommand is an explicit Builder-discretion item from the spec.

## Gate summary

### Cycle 2 (2026-04-26 re-run)

| Gate | Command | Result |
| -- | ------ | ----- |
| Pytest (full suite, cycle-2 re-run) | `uv run pytest` | ✅ PASS — 697 passed, 9 skipped, 0 failed in 31.83 s. Same total count as cycle 1 (no test added/removed; all cycle-2 changes were doc/assertion edits inside existing tests + one rename). |
| Pytest (M19 T04 tests only — cycle 2) | `uv run pytest tests/workflows/test_summarize.py tests/integration/test_spec_api_e2e.py tests/cli/test_run.py::test_run_missing_goal_exits_two -v` | ✅ PASS — 11 passed in 1.08 s. The renamed `test_aiw_show_inputs_summarize_lists_input_fields` runs at id `[ 63%]`. The tightened `test_summarize_validator_step_runs` runs at id `[ 36%]`. The rewritten sync `test_summarize_artefact_identical_across_surfaces` runs at id `[ 90%]`. The strengthened `test_run_missing_goal_exits_two` runs at id `[100%]`. All four cycle-2-target tests pass. |
| Layer rule | `uv run lint-imports` | ✅ PASS — `Contracts: 4 kept, 0 broken` (re-run from scratch). 107 dependencies (unchanged from cycle 1). |
| Lint | `uv run ruff check` | ✅ PASS — `All checks passed!` |
| MEDIUM-1 reframing — module docstring | `grep -n "ValidateStep" ai_workflows/workflows/summarize.py` | ✅ PASS — module docstring lines 15-25 reframe ValidateStep as illustrative + runtime no-op when `schema` matches upstream `LLMStep.response_format`; redirects readers to T01/T02 for ValidateStep test surface coverage. Inline comment at line 103 matches. |
| MEDIUM-1 reframing — spec Deliverable 1 | `grep -n "ValidateStep after" task_04_summarize_proof_point.md` | ✅ PASS — line 102 rewritten: *"The `ValidateStep` after the `LLMStep` is illustrative; ... it is a runtime no-op (the LLMStep's paired validator already validated). The composition is shown for syntactic illustration only."* |
| MEDIUM-2 fix — sync rewrite | Manual: read `tests/integration/test_spec_api_e2e.py:286-385` | ✅ PASS — no `@pytest.mark.asyncio`; CLI side via `_RUNNER.invoke(app, ["run", "summarize", ...])`; MCP side via `_asyncio.run(_mcp_call())`; both surfaces genuinely driven; `assert cli_artefact == mcp_artefact == {"summary": stub_summary}` pins byte-identity. |
| LOW-1 — checkbox flip | `grep -c "^- \[x\]" task_04_summarize_proof_point.md && grep -c "^- \[ \]" task_04_summarize_proof_point.md` | ✅ PASS — 15 checked, 0 unchecked. All 13 ACs + 2 carry-overs ticked. |
| LOW-2 — assertion strengthening | `grep -A2 "test_run_missing_goal_exits_two" tests/cli/test_run.py` | ✅ PASS — both `assert "goal" in combined.lower()` and `assert "required" in combined.lower()` present at lines 277-278. |
| LOW-3 — CHANGELOG count | `grep -n "AC-1 through" CHANGELOG.md` | ✅ PASS — cycle-1 entry now cites "AC-1 through AC-13" (line 35); cycle-2 entry added above (line 10) with cycle-2-only file list. |
| LOW-4 — test rename | `grep -n "test_aiw_run_summarize_help_lists_input_fields\|test_aiw_show_inputs_summarize_lists_input_fields" tests/integration/test_spec_api_e2e.py` | ✅ PASS — only the new name `test_aiw_show_inputs_summarize_lists_input_fields` appears (lines 9, 198). Old name fully removed. |
| LOW-5 — assertion tightening | Manual: read `tests/workflows/test_summarize.py:272-279` | ✅ PASS — `assert result["status"] == "errored"` (was `in ("errored", "completed")`); `assert result["error"] is not None`; docstring fully reframed (LLMStep paired-validator semantic-retry exhaustion). |
| LOW-6 — T02 backfill | Manual: read `issues/task_02_issue.md:352-365` | ✅ PASS — "Post-close T02 latent fixes" section appended; four fixes named; explicit "T02 Status doesn't reopen" note included; T02 **Status:** line at line 6 unchanged (still ✅ PASS). |

All cycle-2 gates green. No new findings introduced by the cycle-2 doc/assertion edits.

### Cycle 1 (2026-04-26 first audit)

| Gate | Command | Result |
| -- | ------ | ----- |
| Pytest (full suite) | `uv run pytest` | ✅ PASS — 697 passed, 9 skipped, 24 warnings (11 are intentional `DeprecationWarning`s for the T03 `plan` alias) in 30.77 s. |
| Pytest (M19 T04 tests only — summarize + integration + migrated test) | `uv run pytest tests/workflows/test_summarize.py tests/integration/test_spec_api_e2e.py tests/cli/test_run.py::test_run_missing_goal_exits_two -v` | ✅ PASS — 11 passed in 1.04 s. |
| Pytest (T01 + T02 regression spot-check) | `uv run pytest tests/workflows/test_compiler.py tests/workflows/test_spec.py -v` | ✅ PASS — 39 passed in 1.60 s. T02 + T01 surfaces fully preserved by the four `_compiler.py` edits. |
| Layer rule | `uv run lint-imports` | ✅ PASS — `Contracts: 4 kept, 0 broken.` 107 dependencies (3 more than T03 cycle 2's 104, owing to the new `summarize.py` + `summarize_tiers.py` modules). |
| Lint | `uv run ruff check` | ✅ PASS — `All checks passed!` |
| `git diff` against `main` for AC-8 | `git diff main -- ai_workflows/workflows/planner.py ai_workflows/workflows/slice_refactor.py` | ✅ PASS — empty diff. Both files unchanged. |
| KDR-003 grep | `grep -rn "anthropic\|ANTHROPIC_API_KEY" ai_workflows/workflows/summarize.py ai_workflows/workflows/summarize_tiers.py ai_workflows/cli.py` | ✅ PASS — zero hits. |
| `import langgraph` grep on summarize.py | `grep -n "import langgraph" ai_workflows/workflows/summarize.py ai_workflows/workflows/summarize_tiers.py` | ✅ PASS — zero hits. AC-1 satisfied. |
| `mix_stderr` removal | `grep -n "mix_stderr" tests/integration/test_spec_api_e2e.py tests/cli/test_run.py` | ✅ PASS — zero hits. Builder's deviation #3 verified. |
| `aiw show-inputs summarize` smoke | `uv run aiw show-inputs summarize` | ✅ PASS — emits both `text` and `max_words` field lines with type/required framing; exit 0. |
| `aiw run --help` smoke | `uv run aiw run --help` | ✅ PASS — `--input` flag listed; M19 T04 docstring visible; planner flags + `--input` coexist. |
| `aiw show-inputs <unknown>` error path | `uv run aiw show-inputs nonexistent_workflow` | ✅ PASS — exits 2 with "unknown workflow ... registered: ..." message. |
| `aiw run planner` (no `--goal`) error path | `uv run python -c "...CliRunner.invoke(['run', 'planner'])..."` | ✅ PASS — exits 2 with `"Invalid value: input 'goal': Field required"` (BadParameter wrapping ValidationError). Per spec AC-9 + Deliverable 4 §"Existing-test migration" — failure path migrated correctly. |
| Standalone-`ValidateStep` runtime trace | Instrumented `validator_node` to print input/output | ⚠️ MEDIUM-1 confirmed — standalone ValidateStep receives `state["summary"] = SummarizeOutput(...)` instance, not a JSON string; pydantic raises ValidationError; NonRetryable swallowed by completed-branch precedence in dispatch. |

All M19 T04-attributable gates green. The two MEDIUMs are spec-faithfulness questions, not gate failures.

## Issue log — cross-task follow-up

| ID | Severity | Owner / next touch point | Status |
| -- | -------- | ------------------------ | ------ |
| M19-T04-ISS-01 | MEDIUM | T04 cycle 2 — standalone ValidateStep no-op (MEDIUM-1). User locked Path (i) (accept no-op + reframe). | RESOLVED 2026-04-26 (cycle 2) — `summarize.py:15-25,103` + `task_04_summarize_proof_point.md:102` + `tests/workflows/test_summarize.py:240-279`. |
| M19-T04-ISS-02 | MEDIUM | T04 cycle 2 — Test 5 cross-surface identity bypasses CLI entry-point (MEDIUM-2). Rewrite as sync test using `CliRunner.invoke` + `asyncio.run(mcp_call())`. | RESOLVED 2026-04-26 (cycle 2) — `tests/integration/test_spec_api_e2e.py:286-385`; both surfaces genuinely driven. |
| M19-T04-ISS-03 | LOW | T04 cycle 2 close-out — flip AC + carry-over `[ ]` checkboxes on `task_04_summarize_proof_point.md` (LOW-1). Mechanical. | RESOLVED 2026-04-26 (cycle 2) — 15 checkboxes flipped (13 ACs + 2 carry-overs); 0 unchecked remaining. |
| M19-T04-ISS-04 | LOW | T04 cycle 2 — add `assert "required" in combined.lower()` to `test_run_missing_goal_exits_two` (LOW-2). One-line edit. | RESOLVED 2026-04-26 (cycle 2) — `tests/cli/test_run.py:278`; both `'goal'` and `'required'` now asserted. |
| M19-T04-ISS-05 | LOW | T04 cycle 2 — fix CHANGELOG "AC-1 through AC-11" → "AC-1 through AC-13" (LOW-3). One-line edit. | RESOLVED 2026-04-26 (cycle 2) — `CHANGELOG.md:35`. |
| M19-T04-ISS-06 | LOW | T04 cycle 2 — rename `test_aiw_run_summarize_help_lists_input_fields` → `test_aiw_show_inputs_summarize_lists_input_fields` (LOW-4). | RESOLVED 2026-04-26 (cycle 2) — `tests/integration/test_spec_api_e2e.py:198`. |
| M19-T04-ISS-07 | LOW | T04 cycle 2 — tighten `test_summarize_validator_step_runs` assertion to `result["status"] == "errored"` (LOW-5). Composes with M19-T04-ISS-01. | RESOLVED 2026-04-26 (cycle 2) — `tests/workflows/test_summarize.py:273-279`. |
| M19-T04-ISS-08 | LOW | Auditor / audit-hygiene pass — backfill T02 issue file with "latent bugs caught at T04" entry (LOW-6). Doc-trail only. | RESOLVED 2026-04-26 (cycle 2) — `issues/task_02_issue.md:352-365`; T02 `**Status:**` preserved as ✅ PASS (no re-open). |

**Cycle 2:** All 8 cycle-1 findings RESOLVED. No HIGH at any point. No new findings introduced by cycle-2 edits. T04 is now ✅ PASS.

## Deferred to nice_to_have

*Not applicable.* No findings naturally map to `nice_to_have.md` entries. MEDIUM-1 + MEDIUM-2 are within the spec's existing scope (resolution lives inside T04 cycle 2). The six LOWs are all mechanical fixes against existing spec text, no parking-lot trigger fires.

## Propagation status

**Cycle 2 close-out (2026-04-26):** No findings forward-deferred to a specific future task by this re-audit. All eight cycle-1 findings RESOLVED inline at T04 cycle 2; LOW-6's T02 backfill landed at `issues/task_02_issue.md:352-365` without re-opening T02 (T02 **Status:** preserved as ✅ PASS). No carry-over edits to other task specs are required by this audit cycle.

**Cycle 1 propagation footer preserved below for audit history.**

---

**Cycle 1 (2026-04-26):** No findings forward-deferred to a future task. All eight findings (2 MEDIUM + 6 LOW) land in T04 cycle 2 (or, for LOW-6, the auditor's own follow-up to backfill T02). No carry-over edits to other task specs are required by this audit.

T03's MEDIUM-1 carry-over (the `slice_refactor` gate-pause regression — locked Path A by user) was previously routed to T07's spec (`task_07_extension_model_propagation.md` line 202); that propagation is unchanged by this audit and remains the responsibility of T07's audit close.

The T05 spec's grounding section already cites `summarize.py` as the worked-example source; that cross-reference is preserved by this cycle and does not require carry-over edits.

## Security review (2026-04-26)

Threat model: single-user, local-machine, MIT-licensed. Two real attack surfaces: (1) published wheel on PyPI, (2) subprocess execution. Reviewed against threat-model items 1–8 from the security-reviewer system prompt.

### Checked items and results

**1. Wheel contents** — `uv build` then `unzip -l dist/jmdl_ai_workflows-0.2.0-py3-none-any.whl`. The wheel contains `ai_workflows/workflows/summarize.py` + `ai_workflows/workflows/summarize_tiers.py` (both under `ai_workflows/` — intended public package surface). No `.env*`, no `design_docs/`, no `runs/`, no `*.sqlite3`, no `htmlcov/`, no `.coverage`, no `.pytest_cache/`, no `.claude/`, no `.github/`. Tests live under `tests/` which is excluded from the wheel. The `migrations/` directory is present in the wheel (pre-existing inclusion, folded to T08 per T01 HIGH-1 tracking). No new leakage introduced by T04.

**Sdist (`jmdl_ai_workflows-0.2.0.tar.gz`)**: contains `.env.example`, `.claude/`, `design_docs/`, `.github/` — this is the pre-existing T01 HIGH-1 finding (folded to T08 milestone closeout). T04 adds `design_docs/phases/milestone_19_declarative_surface/issues/task_04_issue.md` to the sdist, which is design-doc content only, no secrets. `.env.example` contains only empty placeholder values (`GEMINI_API_KEY=`) — no real credentials.

**2. `--input KEY=VALUE` argument-injection** (`ai_workflows/cli.py:_parse_inputs`) — split is `kv.split("=", 1)` (split-once); `KEY=VALUE=other` parses correctly to `key="KEY"`, `value="VALUE=other"`. No-`=` inputs raise `typer.BadParameter` immediately. Malicious key names (`__class__`, `foo[bar]`, dotted paths) are silently dropped by pydantic v2 strict-field resolution — they are not declared schema fields and therefore never reach framework state. The planner-flag / `--input` conflict check at `cli.py:328-333` raises `BadParameter` before dispatch. The merge is not silently overridden either way.

**3. `aiw show-inputs` info-disclosure** (`ai_workflows/cli.py:show_inputs`) — renders `input_schema.model_fields` field names + types. Schema is author-defined at registration time, not end-user-supplied at command-line time. No format-string injection: `typer.echo(f"  - {field_name} ({type_name}…")` interpolates field metadata only, using pydantic's `field_info.annotation.__name__` or `str(annotation)`. No YAML loader or eval involved. The field list is the intended-public API (`SummarizeInput.text`, `SummarizeInput.max_words`). No credential fields in any in-package workflow input schema.

**4. Subprocess / network surface** — no new subprocess invocations in any T04 file. MCP integration test uses `build_server().get_tool("run_workflow").fn(payload)` (in-process, no network). CLI integration test uses `CliRunner.invoke` (in-process). Hermetic tests use `StubLLMAdapter` (no provider call). Verified by grep: zero `subprocess.` / `os.system` / `os.popen` calls in `summarize.py`, `summarize_tiers.py`, `_compiler.py`, or test files.

**5. `ANTHROPIC_API_KEY` / `anthropic` SDK leakage** — `grep -rn "ANTHROPIC_API_KEY" ai_workflows/` returns zero hits. `grep -rn "import anthropic" ai_workflows/` returns zero hits. `summarize_tiers.py` routes to `LiteLLMRoute(model="gemini/gemini-2.5-flash")` — a LiteLLM model alias string, not a credential. KDR-003 boundary intact.

**6. `prompt_template` format-string injection** — `template.format(**state)` at `_compiler.py:547`. The template is author-defined (in `summarize.py`). End-user-supplied `text` content (via `--input text="..."`) can include `{`-style placeholders; `str.format(**state)` will attempt to substitute them against graph state keys. Worst case: if a user supplies `text="{summary}"` the rendered prompt will have the current `summary` field value (initially `None`) substituted. This produces a confusing LLM prompt, not a framework escape. The prompt goes to Gemini, not to a path-traversal-capable surface. The trust boundary is the workflow author (who wrote the template) vs. the end-user (who supplies field values). End-user cannot escape into framework state or reach non-LLM surfaces through this path.

**7. `_compiler.py` latent fixes — framework-internal key collision** — the four T04 latent fixes include `initial_state` pre-init at `_compiler.py:242-253`. The sequence is: (a) `state["run_id"] = run_id` (framework sets run_id), (b) `state.update(parsed.model_dump())` (user input fields merged). If an author's `input_schema` declares a field named `run_id`, `last_exception`, `_retry_counts`, `_non_retryable_failures`, or `_mid_run_tier_overrides`, the `model_dump()` would overwrite (a) or bypass the `setdefault()` guards at lines 250-253. This is a KDR-013 "author-owned risk" — the framework does not police schema field names. The `setdefault` pattern correctly protects `last_exception` / `_retry_counts` / `_non_retryable_failures` / `_mid_run_tier_overrides` (set after `update()`), but `run_id` at line 242 would be overwritten by `update()` if the author declares it as an input field. Practical impact: only an author who deliberately names an input field `run_id` is affected; no end-user CLI/MCP caller can trigger this. Tracked below as Advisory per KDR-013 boundary.

**8. Test surface hermeticity** — all tests in `tests/workflows/test_summarize.py` and `tests/integration/test_spec_api_e2e.py` redirect SQLite paths to `tmp_path` via `monkeypatch.setenv("AIW_CHECKPOINT_DB", ...)` + `monkeypatch.setenv("AIW_STORAGE_DB", ...)`. No subprocess calls. No real network calls (stub adapter intercepts all LLM calls). No `.env*` reads. In-process MCP call via `build_server().get_tool(...).fn(payload)`. Stub response values are generic strings (`"A brief summary of the text."`, `"Stub summary output for identity test."`) — no real API keys, no real Gemini output, no credential-shaped values.

**9. Logging hygiene** — no `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `Bearer `, or `Authorization` strings in any T04 file. No `prompt=` kwargs that surface full prompts in log records in the T04 code paths.

### 🔴 Critical — must fix before publish/ship

None.

### 🟠 High — should fix before publish/ship

None.

### 🟡 Advisory — track; not blocking

**ADV-1. `run_id` overwrite by author-declared input field** (`ai_workflows/workflows/_compiler.py:242-243`). If a workflow author declares a field named `run_id` in their `input_schema`, `state.update(parsed.model_dump())` at line 243 overwrites the framework-generated `run_id` that was set at line 242. The `setdefault` pattern at lines 250-253 correctly protects `last_exception` / `_retry_counts` / `_non_retryable_failures` / `_mid_run_tier_overrides` but `run_id` is not protected the same way. Threat-model item 7 (state-key collision). Scope: author-owned risk per KDR-013; no end-user exploit path. Action: document in ADR-0008 or the `WorkflowSpec`/`input_schema` docstring that `run_id` (plus the framework-internal key names) are reserved and must not appear as `input_schema` field names. A `compile_spec`-time validation guard (`raise ValueError if "run_id" in spec.input_schema.model_fields`) would convert this to a hard error — deferred to T08 or as a carry-over to the spec-API hardening pass.

**ADV-2. `prompt_template` `str.format(**state)` — user-controlled `{…}` substitution** (`ai_workflows/workflows/_compiler.py:547`). End-user-supplied text values can contain `{field_name}` placeholders that are substituted from graph state, producing a potentially unexpected rendered prompt. Worst case is LLM confusion, not framework escape. Threat-model item 6 (prompt template trust boundary). The risk is bounded: the renderer does not call `eval`, does not access the filesystem, and the result goes to an LLM provider only. Action: document in `docs/writing-a-workflow.md` (T05) that `prompt_template` values are passed through `str.format(**state)` and that end-user-controlled fields may inadvertently substitute against state keys — authors who need literal braces should use `{{` / `}}` escaping, or use the `prompt_fn=` Tier 2 path.

**ADV-3. Pre-existing sdist leakage (T01 HIGH-1 inherited)** — `design_docs/` + `.claude/` + `.env.example` + `.github/` appear in the sdist `jmdl_ai_workflows-0.2.0.tar.gz`. T04 adds the T04 issue file to the sdist via `design_docs/`. No credential values in `.env.example` (placeholder only). Action: tracked to T08 milestone closeout per T01 HIGH-1 fold.

### Verdict: SHIP

T04's net-new threat surface is small: two new workflow modules (pure pydantic + spec-types, no subprocess, no credentials, no new network), a CLI flag extension with correct split-once parsing and pydantic v2 validation, and four compiler latent-bug fixes using `setdefault` patterns. No `ANTHROPIC_API_KEY` leak, no `import anthropic`, no subprocess calls, no new manifest deps. Wheel contents are clean (new files are in the intended `ai_workflows/` package surface). All three advisory items are author-owned or pre-existing. No critical or high findings introduced by T04.

## Dependency audit (2026-04-26)

**Skipped — no manifest changes.** T04 cycles 1+2 modified `ai_workflows/workflows/summarize.py` (new), `ai_workflows/workflows/summarize_tiers.py` (new), `ai_workflows/cli.py`, `ai_workflows/workflows/_compiler.py` (latent T02 fixes per LOW-6), `tests/workflows/test_summarize.py` (new), `tests/integration/test_spec_api_e2e.py` (new), `tests/cli/test_run.py`, `CHANGELOG.md`, and a few design-docs / issue files only. Neither `pyproject.toml` nor `uv.lock` was touched, so the dependency-auditor pass is not triggered per /clean-implement S2.
