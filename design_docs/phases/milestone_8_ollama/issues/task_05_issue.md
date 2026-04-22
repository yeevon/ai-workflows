# Task 05 — Degraded-Mode End-to-End Test — Audit Issues

**Source task:** [../task_05_degraded_mode_e2e.md](../task_05_degraded_mode_e2e.md)
**Audited on:** 2026-04-21
**Audit scope:** `tests/workflows/test_ollama_outage.py` (hermetic suite, 6 tests), `tests/e2e/test_ollama_outage_smoke.py` (live smoke, 1 test), `ai_workflows/workflows/_dispatch.py` (new `_build_ollama_circuit_breakers` helper + `configurable` wiring), `tests/e2e/conftest.py` (unchanged — confirmed AIW_E2E gate still applies), `CHANGELOG.md` (new T05 entry). Cross-check against `design_docs/phases/milestone_8_ollama/README.md`, [design_docs/architecture.md §8.4](../../../architecture.md), KDR-003 / KDR-004 / KDR-006 / KDR-009, sibling M8 issue files (T01 / T02 / T03 / T04), and existing E2E suite style (`tests/e2e/test_planner_smoke.py`).

**Status:** ✅ PASS — all 7 ACs met, gates green, no design drift. Two LOW flags recorded for forward visibility; neither blocks the task.

---

## Design-drift check

Cross-checked every modification against `architecture.md` and the KDRs the task cites.

| Concern | Finding | Verdict |
|---|---|---|
| **New dependencies (§6)** | None. The hermetic suite imports `litellm.exceptions.APIConnectionError` for its failure injection; `litellm` is already in the architecture dependency list (KDR-007). No new packages. | ✅ |
| **Four-layer contract (§3)** | Dispatch helper lives in `workflows/`; imports only `primitives/` (`CircuitBreaker`, `LiteLLMRoute`). Hermetic suite lives in `tests/workflows/` and imports from all four layers (test-only, unrestricted). E2E smoke lives in `tests/e2e/` (test-only). `import-linter` — 4 contracts kept. | ✅ |
| **KDR-003 (no Anthropic API)** | `grep` for `anthropic`, `ANTHROPIC_API_KEY` across both new test files + the dispatch diff — only the `ClaudeCodeRoute`-via-CLI-subprocess path (via `_HealthyClaudeCodeStub`). No SDK import, no env-var lookup. | ✅ |
| **KDR-004 (validator-after-LLM)** | No new LLM-calling nodes. The tests only drive existing planner / slice_refactor graphs through `run_workflow` + `resume_run`; validator pairings ship with those graphs. | ✅ |
| **KDR-006 (three-bucket retry)** | `_FlakyLiteLLMAdapter` raises `litellm.exceptions.APIConnectionError`, which `classify()` routes to `RetryableTransient` — the only bucket that feeds `record_failure` on the breaker. No bespoke retry loops added. | ✅ |
| **KDR-009 (SqliteSaver-only)** | Hermetic suite relies on `_dispatch.run_workflow` / `resume_run`, which use LangGraph's native `SqliteSaver`. No hand-rolled checkpoint writes. `_injected_breakers` fixture monkey-patches only `_build_ollama_circuit_breakers`, which returns a plain dict (no checkpoint surface). | ✅ |
| **§8.4 provider-health policy** | Dispatch helper filters on `LiteLLMRoute` + `model.startswith("ollama/")`, matching the "circuit breaker around the Ollama daemon" wording. Gemini-backed LiteLLM tiers and `ClaudeCodeRoute` intentionally receive no breaker entry. | ✅ |
| **Observability (§8.1)** | No new log events. Existing `node_completed` / `node_failed` events (M8 T04) already carry `breaker_state`; the hermetic suite asserts state transitions via `CircuitBreaker.state` directly, not via log scraping. No external observability backend pulled in. | ✅ |
| **nice_to_have discipline** | Nothing adopted from `nice_to_have.md`. No CI runner with Ollama (§5); no Langfuse / OTel observability (§1). Task's own *Out of scope* section kept. | ✅ |

No drift found.

---

## AC grading

| # | Acceptance Criterion | Verdict | Evidence |
|---|---|---|---|
| 1 | `tests/workflows/test_ollama_outage.py` — six hermetic cases pass under `uv run pytest`. | ✅ | `uv run pytest tests/workflows/test_ollama_outage.py` — 6 passed. |
| 2 | `tests/e2e/test_ollama_outage_smoke.py` — skipped by default, runnable under `AIW_E2E=1`, docstring documents manual-intervention procedure. | ✅ | `uv run pytest tests/e2e/test_ollama_outage_smoke.py -v` → `1 skipped`. Collection goes through `tests/e2e/conftest.py::pytest_collection_modifyitems`. Docstring ([test_ollama_outage_smoke.py:42-91](../../../../tests/e2e/test_ollama_outage_smoke.py#L42-L91)) pins the 6-step operator procedure (daemon running → prereqs → `AIW_E2E=1 uv run pytest -s` → stop Ollama on banner → 120 s polling → restart). |
| 3 | Hermetic suite exercises all three `FallbackChoice` branches on both `planner` and `slice_refactor`. | ✅ (with LOW flag ISS-01) | Planner: `test_planner_outage_retry_succeeds`, `test_planner_outage_fallback_succeeds`, `test_planner_outage_abort_terminates`. slice_refactor: `test_slice_refactor_outage_single_gate` (cascade into gate, no resume-choice branch), `test_slice_refactor_outage_fallback_applies_to_siblings` (FALLBACK), `test_slice_refactor_outage_abort_cancels_pending_branches` (ABORT). Task spec's own deliverables list only these three slice_refactor cases — no explicit RETRY case — so the implementation matches the deliverables verbatim. See ISS-01 for the AC-vs-deliverables spec drift. |
| 4 | Single-gate-per-run invariant verified for `slice_refactor` (one `record_gate` call regardless of parallel branch count). | ✅ | `test_slice_refactor_outage_single_gate` wraps `SQLiteStorage.record_gate` via `unittest.mock.patch.object` and asserts exactly one `ollama_fallback` invocation across three parallel circuit-open slice emissions ([test_ollama_outage.py:515-557](../../../../tests/workflows/test_ollama_outage.py#L515-L557)). |
| 5 | `uv run pytest` — full suite green (no regression on M6/M7). | ✅ | 587 passed, 5 skipped (1 new e2e smoke + 4 pre-existing M3/M5/M6 e2e smokes), 2 warnings (pre-existing `yoyo` SQLite datetime adapter deprecation — unrelated). |
| 6 | `uv run lint-imports` — 4 contracts kept. | ✅ | `primitives → graph → workflows → surfaces` + `evals cannot import surfaces`. All 4 kept, 0 broken. |
| 7 | `uv run ruff check` clean. | ✅ | `All checks passed!` |

---

## Additions beyond spec — audited and justified

### 1. `_build_ollama_circuit_breakers` helper in `_dispatch.py`

**What changed:** [_dispatch.py:327-356](../../../../ai_workflows/workflows/_dispatch.py#L327-L356) adds a new module-level helper; [_dispatch.py:402](../../../../ai_workflows/workflows/_dispatch.py#L402) threads its output through `configurable["ollama_circuit_breakers"]`.

**Why it was necessary:** Task spec §"Hermetic suite" prescribes `_injected_breakers` as a fixture that "injects via `_dispatch`" — but before this task, `_dispatch.py` had no breaker-construction code. M8 T04 shipped the `configurable["ollama_circuit_breakers"]` read in `TieredNode`, but no production write of the key existed; every hermetic test in T04 constructed breakers locally and fed them through a direct graph `compile` (bypassing dispatch). T05's "goes through `run_workflow` / `resume_run`" invariant cannot be satisfied without a dispatch-side constructor. This helper fills that gap and is the minimum change that lets tests monkey-patch the constructor to override thresholds / clocks without duplicating the iteration over the tier registry.

**Why this is not scope creep:** The spec's fixture contract (`_injected_breakers` monkey-patches the dispatch boundary) is unsatisfiable without this wiring. Without it, M8 T04's production path would ship breakers-on-paper-only — the feature would not actually fire for real `aiw run` invocations, only for tests that compile graphs by hand. This was a silent T04 completeness gap; T05's ACs surfaced it, and fixing it here is the minimum fix.

### 2. E2E smoke uses `subprocess.Popen(uv run aiw run …)` rather than `CliRunner.invoke`

**What changed:** The live smoke drives `aiw run` through a subprocess that stays alive while the operator stops Ollama, then polls Storage for the gate row before resuming via a second subprocess.

**Why it was necessary:** `typer.testing.CliRunner.invoke` is synchronous and blocks until the command returns — which, for `aiw run`, is after the first `HumanGate` pause. But the T05 smoke needs the CLI process alive **across** the operator's manual `systemctl stop ollama` intervention, so Storage is in a pending-at-gate state when the polling loop observes it. Running the CLI in-process would serialize the test behind the CLI's own `asyncio.run(...)`, preventing the polling loop from observing Storage mid-run. `subprocess.Popen` is the minimum departure.

**Why this is not scope creep:** The spec asks for an operator-run live smoke matching `test_planner_smoke.py`'s shape but does not mandate the launching mechanism. The subprocess approach faithfully renders the "stop Ollama mid-run" invariant the hermetic suite cannot exercise; a `CliRunner`-based version would silently degrade to "stop Ollama before the run starts" which tests a different (and weaker) contract.

---

## Gate summary

| Gate | Command | Result |
|---|---|---|
| pytest (full) | `uv run pytest` | 587 passed, 5 skipped (5 e2e smokes gated on `AIW_E2E=1`), 2 warnings (pre-existing `yoyo` SQLite deprecation) |
| pytest (T05 target) | `uv run pytest tests/workflows/test_ollama_outage.py tests/e2e/test_ollama_outage_smoke.py` | 6 passed, 1 skipped |
| import-linter | `uv run lint-imports` | 4 contracts kept, 0 broken |
| ruff | `uv run ruff check` | All checks passed |
| E2E collection-not-error | `uv run pytest tests/e2e/test_ollama_outage_smoke.py --collect-only` | Collected-and-skipped via `conftest.py`; not an error |

---

## 🟢 LOW — ISS-01 — Spec AC-3 demands "all three `FallbackChoice` branches" but deliverables list only two for `slice_refactor`

**Severity:** LOW.

**Description:** Task spec AC-3 reads "Hermetic suite exercises all three `FallbackChoice` branches on both `planner` and `slice_refactor`." The spec's own deliverables section (§"Test cases") lists three `slice_refactor` test names, but only two of them resume with a `FallbackChoice` value: `test_slice_refactor_outage_fallback_applies_to_siblings` (`FALLBACK`) and `test_slice_refactor_outage_abort_cancels_pending_branches` (`ABORT`). The third — `test_slice_refactor_outage_single_gate` — is a topology/invariant check that approves `plan_review` but never resumes the fallback gate itself. Implementation follows the deliverables list verbatim.

**Impact:** The single-gate test does still implicitly exercise the cascade-before-resume path (three branches trip → one gate fires → test ends before resuming); `RETRY` semantics on `slice_refactor` are already covered at the unit level by M8 T04's `test_slice_refactor_ollama_fallback.py::test_retry_refires_affected_slices`. So the invariant **is** covered somewhere in the suite, just not at this specific test file's dispatch level.

**Action / Recommendation:** No code change required for T05. If a future reader wants dispatch-level RETRY coverage for `slice_refactor`, add a `test_slice_refactor_outage_retry_re_fires_affected_slices` case that mirrors the planner RETRY shape (advance clock past cooldown, resume with `"retry"`, flaky adapter healthy afterwards, assert only the previously circuit-open slices re-fire). File as a M8 retrospective follow-up, not a T05 blocker.

---

## 🟢 LOW — ISS-02 — Task spec §"Hermetic suite" says FALLBACK should route to `gemini_flash`, but T04 configured `planner-synth`

**Severity:** LOW.

**Description:** T05 task spec text (["planner-explorer re-routes through gemini_flash"](../task_05_degraded_mode_e2e.md)) and the `_healthy_gemini_stub` fixture description anticipate that `FallbackChoice.FALLBACK` switches the explorer tier to `gemini_flash` (a LiteLLM route). M8 T04's actual `PLANNER_OLLAMA_FALLBACK` / `SLICE_REFACTOR_OLLAMA_FALLBACK` config ([planner.py:116](../../../../ai_workflows/workflows/planner.py#L116), [slice_refactor.py:206](../../../../ai_workflows/workflows/slice_refactor.py#L206)) pins `fallback_tier="planner-synth"` — i.e. the Claude Code OAuth subprocess, not Gemini. T05 ACs do not name the replacement tier, so both choices are compatible; but the spec body and fixture naming in T05 are stale relative to T04's actual wiring.

**Impact:** My `test_planner_outage_fallback_succeeds` asserts `routed_flags == ["opus", "opus"]` (Claude Code opus), which matches T04's as-built config. The test is correct. The only cost is that future readers comparing the T05 spec to the implementation may briefly wonder why the "Gemini stub" the spec described is absent — the answer is "because the as-built fallback is Claude Code, and T04's audit already accepted that." No code change.

**Action / Recommendation:** No code change for T05. When writing the M8 T06 close-out, include a "T05 spec-vs-implementation delta" line noting that the FALLBACK replacement tier is `planner-synth` (Claude Code) rather than `gemini_flash`, so future readers hit the explanation once and don't dig.

---

## Issue log — cross-task follow-up

| ID | Severity | Description | Owner / next touch point |
|---|---|---|---|
| M8-T05-ISS-01 | LOW | Optional dispatch-level RETRY test for `slice_refactor`. | Track in M8 T06 close-out as a retrospective note; no owning task. |
| M8-T05-ISS-02 | LOW | Spec body references `gemini_flash` as fallback tier; as-built is `planner-synth`. | M8 T06 close-out to flag the delta. Task spec is frozen (post-landing convention); close-out doc is the right surface. |

---

## Deferred to nice_to_have

None applicable. T05 did not surface items that map to `nice_to_have.md` entries. (The "CI runner with live Ollama" gap is already covered by [nice_to_have §5](../../../nice_to_have.md) and is out-of-scope per the task's own *Out of scope* section.)

---

## Propagation status

ISS-01 and ISS-02 were forward-deferred to M8 T06 (milestone close-out) — both retrospective notes rather than implementation TODOs. Closed at T06 (2026-04-21):

- [x] `design_docs/phases/milestone_8_ollama/task_06_milestone_closeout.md` — ISS-01 / ISS-02 added to the "Carry-over from prior audits" section and absorbed into the T06 CHANGELOG close-out entry + the milestone README's "Spec drift observed during M8" section. `DEFERRED → RESOLVED`.

No other forward-deferrals. Task closes within its own scope.
