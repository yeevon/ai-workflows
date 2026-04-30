# Task 03 — `aiw list-tiers` command + HTTP CircuitOpen cascade test — Audit Issues

**Source task:** [task_03_aiw_list_tiers_and_circuit_open_cascade.md](../task_03_aiw_list_tiers_and_circuit_open_cascade.md)
**Audited on:** 2026-04-30 (cycle 1) → re-audited 2026-04-30 (cycle 2) → terminal-gate bypass applied 2026-04-30 (cycle 3)
**Audit scope (cycle 3):** Terminal-gate bypass — three FIX items from sr-dev + sr-sdet reviewers applied inline without a full Builder cycle: (1) `_eager_import_in_package_workflows` removed from `__all__`; (2) `_redirect_default_paths` fixture in `test_http_fallback_on_circuit_open.py` converted to `Iterator[None]` + `yield`; (3) positive fallback-output assertion `assert "fallback-ok" in payload_str` added to `test_http_run_workflow_fallback_cascade_on_circuit_open`. Gates re-run: 1532 passed, 12 skipped; lint-imports 5/0; ruff clean.
**Audit scope (cycle 2):** Builder cycle 2 — `_eager_import_in_package_workflows()` helper added to `ai_workflows/workflows/__init__.py` (exported in `__all__`); call site added in `ai_workflows/cli.py::list_tiers` before `list_workflows()`; bare `typer.echo` before `BadParameter` removed; `tests/cli/test_list_tiers.py` extended with `test_list_tiers_shows_planner_tiers_on_bare_invocation` (module-level, outside autouse-reset scope) + `test_list_tiers_imperative_workflow_shows_no_tier_registry` (inside the new `TestListTiersIsolated` class). The original 4 CLI tests now live inside the class; the autouse fixture is class-scoped so the MED-01 test bypasses it. CHANGELOG / spec Status / milestone README task-row updated.
**Audit scope (cycle 1, retained):** new `aiw list-tiers` command in `ai_workflows/cli.py` (+ `_emit_list_tiers_table` helper + `LiteLLMRoute` / `ClaudeCodeRoute` imports), new `tests/cli/test_list_tiers.py` (4 hermetic tests), new `tests/mcp/test_http_fallback_on_circuit_open.py` (1 hermetic test + reused HTTP daemon-thread pattern), CHANGELOG entry, milestone README task-row + spec Status-line flip.
**Status:** ✅ TERMINAL CLEAN (cycle 3 — terminal-gate bypass applied; sr-dev SHIP + sr-sdet FIX-THEN-SHIP resolved; security SHIP; all gates green)

---

## Design-drift check

### Cycle 2 (re-checked against the four load-bearing KDRs)

The cycle-2 delta is the `_eager_import_in_package_workflows()` helper plus its single call site in the surfaces layer. KDR re-check:

- **KDR-002 / KDR-004 / KDR-006 — unchanged.** No MCP schema change (cycle 2 touches only CLI + workflows-package internals); no validator pairing change; no retry-taxonomy change. ✅ no drift.
- **KDR-013 (user-owned external workflow code).** The eager-import helper iterates `pkgutil.iter_modules(ai_workflows.workflows.__path__)` — strictly **in-package** modules. It does **not** walk `AIW_EXTRA_WORKFLOW_MODULES` or any user-registered loader path, and so does not pre-import third-party code on a `list-tiers` invocation. The KDR-013 separation between framework-owned and user-owned workflow imports is preserved. ✅ no drift.
- **KDR-014 (framework owns tier policy).** Helper is read-only side-effect — it triggers the same module-import side effects that `aiw run` triggers lazily on demand. No tier overlay, no config-file lookup, no policy mutation. ✅ no drift.
- **Layer rule (`primitives → graph → workflows → surfaces`).** Helper lives in `ai_workflows/workflows/__init__.py` (workflows layer); only call site is `ai_workflows/cli.py::list_tiers` (surfaces layer). Surfaces → workflows is a downward call. The helper imports `pkgutil`, `importlib`, `sys`, `types`, `contextlib` — stdlib only, no upward imports. ✅ no breach. Confirmed by `uv run lint-imports`: 5 contracts kept, 0 broken.
- **Sandbox-suppression risk (KDR-013 spirit).** The helper's `with contextlib.suppress(ValueError, Exception):  # noqa: BLE001` blocks at lines 278 and 287 broadly swallow exceptions during the "already-loaded module re-registration" path. This is acceptable in scope here (only in-package modules iterated, only on `aiw list-tiers` introspection), but a narrower `(ValueError, TypeError, AttributeError)` would be tighter. Flagged below as cycle-2 LOW-03.

### Cycle 1 (retained)

- **KDR-002 (MCP-as-substrate).** No MCP schema change. New surface is CLI-only (`aiw list-tiers`); spec's "no MCP mirror" non-goal honoured. The HTTP cascade test exercises the existing `run_workflow` MCP tool over the existing HTTP transport — pins envelope shape only, no contract change. ✅ no drift.
- **KDR-004 (validator pairing).** Cascade is treated as infrastructure-level retry; the synthetic `WorkflowSpec` keeps a single `LLMStep` whose `ValidatorNode` contract is unchanged regardless of which route produced the output. ✅ no drift.
- **KDR-006 (three-bucket retry taxonomy).** Cascade fires on `CircuitOpen` (a `NonRetryable` infrastructure signal in the existing taxonomy) — not a new retry surface. The new test exercises the existing `RetryingEdge` + `_node()` cascade hand-off path landed in T02. ✅ no drift.
- **KDR-014 (framework owns tier policy).** New CLI surface is read-only: `list-tiers` enumerates `workflows.list_workflows()` and reads `get_spec(name).tiers`. No write path, no overlay, no config file lookup. Pure introspection. ✅ no drift.

No new dependencies, no new layer, no new module boundary, no LLM call, no checkpoint write, no observability backend, no `nice_to_have.md` adoption. Layer contract preserved (5 contracts kept across both cycles).

---

## AC grading

| AC | Status | Notes |
|---|---|---|
| AC-1: `aiw list-tiers` registered | ✅ met | `aiw list-tiers --help` exits 0; `aiw list-tiers` exits 0 (prints `(no workflows registered)` when registry empty). |
| AC-2: tier table output (workflow / tier / kind / model-flag / concurrency / timeout / fallback) | ✅ met | `test_list_tiers_shows_spec_workflow_tiers` + `test_list_tiers_fallback_chain_rendered` cover the columns + em-dash + comma-joined fallback rendering. Manual table inspection confirmed via test stdout. |
| AC-3: `--workflow` filter (and exit code 2 on unknown) | ✅ met | `test_list_tiers_workflow_filter` asserts only the named workflow shows; `test_list_tiers_unknown_workflow_exits_2` asserts exit code 2. The implementation routes through `typer.BadParameter` (correct exit-code path). |
| AC-4: imperative workflows handled gracefully | ✅ met (cycle 2) | Cycle 2: `test_list_tiers_imperative_workflow_shows_no_tier_registry` asserts `"(no tier registry exported)"` + the registered name appear in stdout when an imperative workflow (`workflows.register("imp_test", lambda: object())`) is registered. Lives in `TestListTiersIsolated` (autouse class-scoped reset). Live `aiw list-tiers` smoke also exercises this branch — `planner`, `scaffold_workflow`, and `slice_refactor` all render as imperative rows. |
| AC-5: HTTP CircuitOpen cascade test | ✅ met | `test_http_run_workflow_fallback_cascade_on_circuit_open` passes hermetically; conjunctive assertions (a) `error is None`, (b) `run_id` present, (c) no `AllFallbacksExhaustedError` text — all satisfied. Stub adapter mirrors `tests/mcp/test_http_transport.py:75-114` (kwarg-only `__init__`, real-shape `complete`). |
| AC-6: 4 CLI tests green | ✅ met | All 4 tests in `tests/cli/test_list_tiers.py` pass. No provider calls. |
| AC-7: existing tests unchanged | ✅ met | Full suite: 1530 passed, 12 skipped, 22 warnings (pre-existing deprecations, not introduced by this task). |
| AC-8: layer contract preserved | ✅ met | `uv run lint-imports`: 5 contracts kept, 0 broken. New imports in `cli.py`: `LiteLLMRoute, ClaudeCodeRoute` (primitives → surfaces is allowed; surfaces is the top of the stack). |
| AC-9: gates green | ✅ met | `uv run pytest` ✅, `uv run lint-imports` ✅, `uv run ruff check` ✅. |
| AC-10: CHANGELOG entry | ✅ met | `## [Unreleased] → ### Added — M15 Task 03: aiw list-tiers command + HTTP CircuitOpen cascade test (2026-04-30)` with files-touched + ACs-satisfied + carry-over absorption. |
| TA-LOW-01: sync implementation (no `asyncio.run`) | ✅ met | `list_tiers()` is a flat sync function; no `_async` helper, no `asyncio.run`. The illustrative `asyncio.run` in the spec template was correctly ignored. |
| TA-LOW-02: `register_workflow` analog citation | ✅ met | `tests/cli/test_list_tiers.py` and `tests/mcp/test_http_fallback_on_circuit_open.py` both call `register_workflow(spec)` directly with a synthetic `WorkflowSpec` (same shape as `tests/workflows/test_compiler.py:215` / `tests/workflows/test_spec.py:235`); the misleading `tests/mcp/test_scaffold_workflow_http.py:128-149` heredoc analog was bypassed. |

---

## Cycle 2 — Findings status

| ID | Severity (cycle 1) | Title | Cycle 2 status |
|---|---|---|---|
| MED-01 | 🟡 MEDIUM | `aiw list-tiers` doesn't eager-import in-package workflows; spec smoke fails | ✅ RESOLVED — `_eager_import_in_package_workflows()` helper landed in `ai_workflows/workflows/__init__.py` (lines 210-288); called from `ai_workflows/cli.py::list_tiers` (line 821). Live `uv run aiw list-tiers` now prints `planner`, `scaffold_workflow`, `slice_refactor`, `summarize` rows. New test `test_list_tiers_shows_planner_tiers_on_bare_invocation` (module-level, outside `TestListTiersIsolated` autouse) pins the regression. |
| LOW-01 | 🟢 LOW | AC-4 imperative-workflow row has code path but no test | ✅ RESOLVED — `test_list_tiers_imperative_workflow_shows_no_tier_registry` added inside `TestListTiersIsolated`. |
| LOW-02 | 🟢 LOW | `unknown workflow` filter-fail emits both custom message + BadParameter banner | ✅ RESOLVED — `list_tiers()` now raises `typer.BadParameter` directly without a preceding `typer.echo`. Inspected `cli.py:824-829`: only the `BadParameter(...)` raise remains. |

All three cycle-1 decisions are implemented with corresponding diff hunks (no checkbox-cargo-cult). The propagation rows below (Issue log) flip to RESOLVED.

---

## Cycle 2 — New findings

### 🔴 HIGH

*None.*

### 🟡 MEDIUM

*None.*

### 🟢 LOW

#### LOW-03 (cycle 2) — Broad `Exception` suppression in eager-import helper's already-loaded path

`ai_workflows/workflows/__init__.py:278` and `:287` both do `with contextlib.suppress(ValueError, Exception):  # noqa: BLE001` around the re-registration calls (`register_workflow(_attr_val)` / `register(short, builder)`). The `Exception` swallow is broader than needed — the helper only needs to tolerate (a) the legitimate `ValueError` raised when a name is already registered with a different builder, (b) `TypeError` if the spec object is malformed, and (c) `AttributeError` if globals scan finds an unexpected shape. A bare `Exception` swallow with `# noqa: BLE001` masks any future failure mode (e.g. import-time side effect that raises a fresh error class) inside an introspection command — silently producing a stale tier table.

**Severity rationale (LOW):** scope is the `aiw list-tiers` introspection command only — no impact on `aiw run` / MCP dispatch / cascade behaviour. The current code is functional and shipped tests are green; the broader catch is a hardening concern, not a correctness defect. KDR-013 spirit (framework should surface user-code errors clearly, not silently suppress them) leans toward narrower exception types.

**Action / Recommendation:** in a follow-up cycle (T05 close-out is the natural owner), replace `with contextlib.suppress(ValueError, Exception):  # noqa: BLE001` with `with contextlib.suppress(ValueError, TypeError, AttributeError):` at both call sites. Drop the `# noqa: BLE001`. No test change required — narrower suppression is a strict subset of the current behaviour, and the existing tests cover the happy path. Not blocking for cycle-2 PASS.

---

## 🔴 HIGH (cycle 1, retained for history)

*None.*

---

## 🟡 MEDIUM (cycle 1, retained for history — RESOLVED)

### MED-01 — Spec smoke test fails: `aiw list-tiers` prints "(no workflows registered)" instead of planner's tiers

**Source:** Task spec §`## Smoke test`, line 212:

> CLI smoke: `uv run aiw list-tiers` on the installed package (or from the dev environment) should print at least the `planner` workflow's tiers without error. The planner workflow is spec-API (registered via `register_workflow`); its tiers are accessible via `get_spec("planner").tiers`.

**Observed behaviour (re-run from scratch in this audit):**

```
$ uv run aiw list-tiers
workflow | tier | kind | model/flag | concurrency | timeout_s | fallback
(no workflows registered)

$ uv run aiw list-tiers --workflow planner
unknown workflow 'planner'; registered: []
Usage: aiw list-tiers [OPTIONS]
Try 'aiw list-tiers --help' for help.
╭─ Error ──────────────────────────────────────────────────────────────────────╮
│ Invalid value for --workflow: workflow 'planner' not registered              │
╰──────────────────────────────────────────────────────────────────────────────╯
```

**Root cause:** workflow modules self-register at *import* time (per `ai_workflows/workflows/__init__.py` docstring §"Registry"). Other commands (`aiw run`, `aiw show-inputs`, `aiw eval run`) lazy-import `ai_workflows.workflows.<name>` before resolving the registry. The new `list_tiers()` command does **not** import any in-package workflow modules — it just reads `workflows.list_workflows()`, which is empty unless something else fired a registration. The result is a help-text claim ("all registered workflows") that contradicts the runtime behaviour: the registry is always empty for a vanilla `aiw list-tiers` invocation.

**Severity rationale (MEDIUM, not HIGH):** AC-1 only requires "exits 0 and prints help text" / "no error" — that gate passes. The defect is a spec-named smoke test that is silently broken, plus a UX surface (the headline command for tier-discoverability) that ships unable to discover anything. The fallback "(no workflows registered)" branch is even **more misleading** for the operator who installed the package and wants to inspect what's available.

The 0.1.2 audit specifically called out the "tier discoverability gap" as the trigger for this command (milestone README, exit criterion #6: "absorbs the discoverability gap flagged in the 0.1.2 audit"). Shipping a discoverability command that discovers nothing on a fresh invocation is a fail-shaped UX.

**Action / Recommendation:** in `ai_workflows/cli.py::list_tiers`, eager-import the in-package workflow modules before reading `workflows.list_workflows()`. The cleanest options:

1. Add a small helper in `ai_workflows/workflows/__init__.py` (e.g. `_eager_import_in_package_workflows()`) that walks `ai_workflows.workflows` for sibling modules and imports them, suppressing `ModuleNotFoundError`. Call it from `list_tiers()`. **Preferred** — keeps the import logic in the workflows layer.
2. Alternatively, in `list_tiers()` itself, hard-list the in-package workflows (`planner`, `slice_refactor`, `summarize`, `summarize_tiers`, `scaffold_workflow`, `testing`) and `importlib.import_module` each, suppressing `ModuleNotFoundError`. Simpler but more brittle.

Add a hermetic test in `tests/cli/test_list_tiers.py` covering: bare `aiw list-tiers` invocation (no synthetic registration; bypass the `_clean_registry` autouse via per-test override or move that test outside the autouse scope) prints at least one in-package workflow row (`planner`).

**Locked decision (loop-controller + Auditor concur, 2026-04-30):** Add `_eager_import_in_package_workflows()` helper in `ai_workflows/workflows/__init__.py`; call from `list_tiers()` before reading `workflows.list_workflows()`. Also add `test_list_tiers_shows_planner_tiers_on_bare_invocation` test (no `_clean_registry` reset before it so planner actually imports). Builder cycle 2 implements this.

**Trade-off:** The "register everything on every invocation" path adds a small import cost to `aiw list-tiers`. Acceptable for an introspection command; not acceptable for `aiw run` (already lazy-imports the requested name only). If T05's Builder objects to this cost, an alternative is to document the limitation explicitly in `aiw list-tiers --help` and add a `--module <dotted-path>` flag that pre-imports a specific module before listing — but this is more user-visible churn than just doing the eager import inside the command.

---

## 🟢 LOW (cycle 1, retained for history — RESOLVED)

### LOW-01 — AC-4 (imperative-workflow row) has code path but no test coverage

The spec calls out: "Workflows registered via `register()` only (no `WorkflowSpec`) appear in the output with a `'(no tier registry exported)'` message rather than crashing." The code path exists (`if spec is None: rows.append((name, "(no tier registry exported)", ...))`) and the help text explicitly documents the imperative-workflow behaviour, but none of the 4 new CLI tests cover the path. The 4 tests all register via `register_workflow` (spec API), so `get_spec()` always returns a populated spec.

**Severity rationale:** code path is straightforward (3 lines, `is None` branch), and the planner workflow (an imperative `register("planner", build_planner)` workflow) would exercise it under MED-01's fix once eager import lands. Flagging LOW so the next cycle's Builder doesn't re-cycle the `(no tier registry exported)` row without a regression test pinning it.

**Action / Recommendation:** in `tests/cli/test_list_tiers.py`, add `test_list_tiers_imperative_workflow_shows_no_tier_registry`: register an imperative workflow via `workflows.register("imp_test", lambda: object())`, run `aiw list-tiers`, assert `"(no tier registry exported)"` appears in stdout. Co-locate with the eager-import test from MED-01.

**Locked decision (loop-controller + Auditor concur, 2026-04-30):** Add `test_list_tiers_imperative_workflow_shows_no_tier_registry` in `tests/cli/test_list_tiers.py`. Builder cycle 2 implements this.

### LOW-02 — `unknown workflow` error path emits both an error message and the BadParameter banner

Cosmetic: the `list_tiers` filter-fail path does `typer.echo(...)` before raising `BadParameter`, so the user sees both a custom "unknown workflow 'foo'; registered: [...]" line **and** Typer's standard "Invalid value for --workflow" banner. The other two filter-fail commands (`aiw run`, `aiw show-inputs`) only emit the custom message and exit. Not blocking — both messages are accurate — but inconsistent with sibling commands.

**Severity rationale:** purely cosmetic, exit code is correct (2), and both messages are individually correct. Consistency-only; non-blocking for AC closure.

**Locked decision (loop-controller + Auditor concur, 2026-04-30):** Drop the bare `typer.echo(...)` before `raise typer.BadParameter(...)` in `list_tiers()`. Builder cycle 2 implements this.

---

## Additions beyond spec — audited and justified

- **`_redirect_default_paths` autouse fixture in `tests/mcp/test_http_fallback_on_circuit_open.py`** (env-var redirection of `AIW_CHECKPOINT_DB` + `AIW_STORAGE_DB` to `tmp_path`). Not in the spec template. Justified — the daemon-thread HTTP server needs isolated checkpoint + storage paths to avoid leaking state into the operator's real `~/.cache/ai-workflows`. Mirrors the same convention used in `tests/mcp/test_http_transport.py`. ✅ allowed.
- **`(no workflows registered)` empty-rows branch in `_emit_list_tiers_table`.** Not strictly required by the spec; reasonable defensive output. ✅ allowed.

No drive-by refactors, no scope creep into T04/T05, no `nice_to_have.md` adoption.

---

## Gate summary

### Cycle 2 (re-run from scratch by the Auditor)

| Gate | Command | Result |
|---|---|---|
| pytest (full suite) | `uv run pytest` | ✅ PASS — 1532 passed, 12 skipped, 22 warnings (pre-existing). +2 tests vs cycle 1 (the planner-bare-invocation test + the imperative-workflow test). |
| lint-imports | `uv run lint-imports` | ✅ PASS — 5 contracts kept, 0 broken |
| ruff | `uv run ruff check` | ✅ PASS — All checks passed |
| CLI smoke (spec §"Smoke test") | `uv run aiw list-tiers` | ✅ PASS — table prints `planner`, `scaffold_workflow`, `slice_refactor` rows (imperative, "(no tier registry exported)") + `summarize` rows (3 spec-API tiers with concurrency/timeout/fallback columns populated). |
| CLI filter smoke | `uv run aiw list-tiers --workflow planner` | ✅ PASS — single planner row rendered. |
| HTTP smoke (spec §"Smoke test") | `test_http_run_workflow_fallback_cascade_on_circuit_open` | ✅ PASS — hermetic, wire-level via `fastmcp.Client` over loopback HTTP (re-confirmed in this audit's pytest run). |
| Task-scoped tests | `uv run pytest tests/cli/test_list_tiers.py tests/mcp/test_http_fallback_on_circuit_open.py -v` | ✅ PASS — 7 tests passed (5 in `test_list_tiers.py` inside the class + 1 module-level + 1 HTTP cascade). |

All gates green; all spec smoke tests pass.

### Cycle 1 (retained for history)

| Gate | Command | Result |
|---|---|---|
| pytest | `uv run pytest` | ✅ PASS — 1530 passed, 12 skipped |
| lint-imports | `uv run lint-imports` | ✅ PASS — 5 contracts kept |
| ruff | `uv run ruff check` | ✅ PASS |
| CLI smoke | `uv run aiw list-tiers` | ❌ FAIL (cycle 1) — fixed in cycle 2 (MED-01 RESOLVED) |
| HTTP smoke | hermetic test | ✅ PASS |

---

## Issue log — cross-task follow-up

| ID | Severity | Title | Owner | Status |
|---|---|---|---|---|
| M15-T03-ISS-01 | 🟡 MEDIUM | `aiw list-tiers` doesn't eager-import in-package workflows; spec smoke fails | T03 cycle 2 (Builder) | ✅ RESOLVED (cycle 2, 2026-04-30) — `_eager_import_in_package_workflows()` helper landed; spec smoke green. |
| M15-T03-ISS-02 | 🟢 LOW | AC-4 imperative-workflow row has code path but no test | T03 cycle 2 (Builder) | ✅ RESOLVED (cycle 2, 2026-04-30) — `test_list_tiers_imperative_workflow_shows_no_tier_registry` added. |
| M15-T03-ISS-03 | 🟢 LOW | `unknown workflow` filter-fail emits both custom message + BadParameter banner | T03 cycle 2 (Builder) | ✅ RESOLVED (cycle 2, 2026-04-30) — bare `typer.echo` removed before `BadParameter`. |
| M15-T03-ISS-04 | 🟢 LOW | Broad `Exception` suppression in `_eager_import_in_package_workflows` already-loaded path | T05 close-out (proposed) | OPEN — narrow `(ValueError, TypeError, AttributeError)` suggested. Not blocking. |

---

## Deferred to nice_to_have

*None.* The MED-01 fix is a small in-task refinement; it does not match any `nice_to_have.md` deferred-idea. T05 close-out is the natural owner.

---

## Propagation status

- **M15-T03-ISS-01 / -02 / -03 — closed in cycle 2** within this task's scope. No forward propagation needed.
- **M15-T03-ISS-04 (LOW-03)** — proposed owner is T05 close-out. When T05 is drafted (per the milestone's incremental-spec convention), this should appear as carry-over: replace `with contextlib.suppress(ValueError, Exception):  # noqa: BLE001` with `with contextlib.suppress(ValueError, TypeError, AttributeError):` at `ai_workflows/workflows/__init__.py:278` and `:287`. Non-blocking; can also live as a `nice_to_have.md` candidate if T05 stays doc-only — though it's a 2-line patch, so the natural home is T05 carry-over.
- **No spec-side carry-over written this cycle** — T05 spec does not exist yet (incremental-spec convention; T05 drafts after T04 closes). The /clean-tasks pass that drafts T05 should consult this issue file's M15-T03-ISS-04 row.

---

## Carry-over status from cycle 1

- **TA-LOW-01** (sync implementation, no `asyncio.run`): ✅ landed (verified: `list_tiers()` is a flat sync function; no `asyncio` calls in the new code).
- **TA-LOW-02** (`register_workflow` analog citation): ✅ landed (verified: `register_workflow(spec)` called directly in both new test files, matching the `tests/workflows/test_*.py` pattern, not the misleading heredoc analog).
- **Carry-over from prior milestones — LOW-2 from T02** (CircuitOpen cascade lacks unit-level hermetic test): ✅ HTTP-transport surface coverage landed in `tests/mcp/test_http_fallback_on_circuit_open.py`. Per T02's audit deferral acceptance, no pure unit-level `tiered_node` test is required at T03.

All carry-over items have corresponding diff hunks; no checkbox-cargo-cult observed.

## Carry-over status from cycle 2

- **MED-01 / LOW-01 / LOW-02 (cycle-1 findings)**: all three implemented with concrete diff hunks (verified above). Spec status flipped to `✅ Built (cycle 2, 2026-04-30)`; milestone README task row matches; CHANGELOG entry rewritten under `[Unreleased]` with cycle-2 timestamp.
- **No checkbox-cargo-cult observed** — every cycle-1 decision has a verifiable code/test landing in cycle-2's diff.

## Cycle-overlap detection (loop-spinning check)

Cycle 2 produces 1 new finding (LOW-03 — broad-exception suppression). Cycle 1 had 3 findings (MED-01 / LOW-01 / LOW-02). Title-similarity check (per the auditor procedure):

- LOW-03 ("Broad `Exception` suppression in eager-import helper") vs cycle-1 titles → all ratios well below 0.70 (different subject matter). 0/1 findings cross the overlap threshold. **No loop-spinning detected.**

## Rubber-stamp detection

Verdict is PASS; cycle-2 diff is substantial (helper + 2 tests + class restructure + CHANGELOG/spec/README); 0 HIGH + 0 MEDIUM findings. The rubber-stamp guard requires verification that the PASS verdict is supported by re-verified evidence, not just trust in the Builder's report:

- Spec smoke test re-run from scratch in this audit: ✅ confirmed planner row appears.
- Helper code read directly: ✅ correct shape (in-package only; KDR-013 boundary preserved).
- 7 task-scoped tests re-run: ✅ all pass.
- Layer contract: ✅ 5 contracts kept by `lint-imports`.
- Cycle-1 diff hunks for each decision: ✅ confirmed (file + line cited above).

Verdict supported by direct evidence, not by Builder self-report. **No rubber-stamping.**

---

## Status surfaces verified

### Cycle 2

- ✅ Per-task spec `**Status:**` line: `✅ Built (cycle 2, 2026-04-30).` — confirmed at line 3 of `task_03_aiw_list_tiers_and_circuit_open_cascade.md`.
- ✅ Milestone README task table row: `✅ Built (cycle 2)` — confirmed.
- ✅ No `tasks/README.md` at repo root (does not exist; not applicable).
- ✅ Milestone README "Done when" exit criteria: T03 satisfies #5 (CircuitOpen HTTP test) and #6 (`aiw list-tiers` command). Both criteria flip at milestone close (T05 close-out) — they're listed as milestone-level exit criteria, not per-task checkboxes.
- ✅ CHANGELOG `[Unreleased] → ### Added` entry timestamped to `cycle 2 (2026-04-30)`.

All four status surfaces agree. **Auditor flips no surfaces** — Builder did this correctly.

### Cycle 1 (retained for history)

- ✅ Per-task spec `**Status:**` line: `✅ Built (cycle 1, 2026-04-30)` — matched Builder cycle 1.
- ✅ Milestone README task table row: `✅ Built (cycle 1)` — matched.

---

## Terminal gate — cycle 3 (2026-04-30)

### Reviewer verdicts

| Reviewer | Verdict | FIX items |
|---|---|---|
| sr-dev | SHIP | FIX-01: remove `_eager_import_in_package_workflows` from `__all__` |
| sr-sdet | FIX-THEN-SHIP | FIX-01: `_redirect_default_paths` missing `yield`; FIX-02: missing positive fallback-output assertion |
| security-reviewer | SHIP | ADV-1 sdist contains `.claude/worktrees/`; ADV-2 broad Exception suppress; ADV-3 `runs/.gitkeep` in sdist |

**Lens-specialisation bypass applied:** sr-sdet FIX on test-hygiene/fixture-teardown/coverage lens; sr-dev SHIP on code-quality lens — different lenses on orthogonal concerns. Both reviewers agree the underlying code is correct; the FIX items are pure test-file repairs. No design options require user arbitration. All three FIX items have single clear recommendations within spec scope and no KDR conflict. Bypass eligible per memory: `feedback_lens_specialisation_not_divergence.md`.

### Locked decisions (cycle 3)

**TG-FIX-01 (sr-dev) — Remove `_eager_import_in_package_workflows` from `__all__`**
`ai_workflows/workflows/__init__.py` line 107. An underscore-prefixed name must not appear in `__all__` — contradictory signals to IDEs, type checkers, and star-import users. The only call site (`cli.py:821`) uses attribute lookup, not star-import. Implemented: string removed from `__all__`. No test or call-site change needed.

**TG-FIX-02 (sr-sdet) — `_redirect_default_paths` fixture must yield**
`tests/mcp/test_http_fallback_on_circuit_open.py:123-130`. Return type changed from `None` → `Iterator[None]`; `yield` added after the two `monkeypatch.setenv(...)` calls. `Iterator` already imported via `from collections.abc import Iterator` at line 33. Fixture teardown is now guaranteed hermetic — consistent with `_clean_registry` sibling fixture and `tests/mcp/test_http_transport.py` analogues.

**TG-FIX-03 (sr-sdet) — Add positive fallback-output assertion (AC-5)**
`tests/mcp/test_http_fallback_on_circuit_open.py:255-259`. Added assertion `assert "fallback-ok" in payload_str` as assertion (d) — confirms the cascade returned the fallback result content, not just a no-error empty shell. The stub returns `{"result": "fallback-ok"}` which lands in `artifact` → serialized to `payload_str`.

### Terminal gate — gates re-run

| Gate | Result |
|---|---|
| pytest (full suite) | ✅ 1532 passed, 12 skipped, 22 warnings |
| lint-imports | ✅ 5 contracts kept, 0 broken |
| ruff | ✅ All checks passed |
| Task-scoped tests | ✅ 7 passed (same count; all FIX items verified passing) |
