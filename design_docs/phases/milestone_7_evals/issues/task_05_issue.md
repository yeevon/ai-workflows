# Task 05 — CI Hookup + Seed Fixtures for `planner` + `slice_refactor` — Audit Issues

**Source task:** [../task_05_ci_hookup_seed_fixtures.md](../task_05_ci_hookup_seed_fixtures.md)
**Audited on:** 2026-04-21
**Audit scope:** `evals/planner/{explorer,planner}/happy-path-01.json`, `evals/slice_refactor/slice_worker/happy-path-01.json`, `ai_workflows/evals/runner.py` (subgraph resolution extension), `ai_workflows/workflows/slice_refactor.py` (new `slice_refactor_eval_node_schemas`), `.github/workflows/ci.yml` (new `eval-replay` job), `tests/evals/test_seed_fixtures_deterministic.py` (new), `tests/evals/test_runner_deterministic.py` (two new tests), `tests/cli/test_eval_commands.py` (context — fixture interaction), `design_docs/phases/milestone_7_evals/issues/task_03_issue.md` (M7-T03-ISS-02 retrofit propagation), `CHANGELOG.md`, cross-check against [architecture.md](../../../architecture.md) §3 / §4 / §6 / §7 / §8.2 / §10, KDR-003, KDR-004, KDR-006, KDR-009, KDR-010.
**Status:** ✅ PASS — no OPEN issues.

---

## Design-drift check

| Axis | Finding |
| --- | --- |
| New dependency | No new Python dependencies. The CI job uses `dorny/paths-filter@v3` (a third-party GitHub Actions step) — architecture.md §6 governs Python runtime dependencies and does not list CI actions; the CI-infra boundary is out of architecture.md's scope. Flag-only below (M7-T05-ISS-02). |
| New module / layer | No new modules. `_resolve_node_scope` + `_node_exists_anywhere` added to the existing `ai_workflows/evals/runner.py`; `slice_refactor_eval_node_schemas` added to `ai_workflows/workflows/slice_refactor.py`. Import-linter still KEPT on all 4 contracts. |
| LLM call added | None. Replay is deterministic-only in CI; live mode unchanged. The subgraph resolution extension reuses `StubLLMAdapter` via the existing `_patched_adapters` context manager. |
| KDR-003 no Anthropic API | Confirmed. No `anthropic` import, no `ANTHROPIC_API_KEY` read. Captures were performed against Gemini + local Qwen + Claude Code CLI (OAuth) only. Stub adapter rewrites every tier to `LiteLLMRoute("stub/{name}")` including `ClaudeCodeRoute`, keeping subprocesses off the deterministic path. |
| KDR-004 validator pairing | `_resolve_node_scope` requires target + paired validator to resolve in the **same scope** (top-level or same sub-graph). Cross-scope pairing returns `None` and `_invoke_replay` raises `_EvalCaseError`. No replay-only bypass of the validator. |
| KDR-006 three-bucket retry | N/A — replay runner inherits `retrying_edge` + `wrap_with_error_handler` chain from the workflow's nodes (no new retry logic). |
| KDR-009 SqliteSaver | N/A — replay graphs are single-shot `compile().ainvoke(...)` invocations, no checkpointer. |
| KDR-010 bare-typed | N/A — no new `response_format` schemas. |
| Observability | `StructuredLogger` inherited via `TieredNode`. No Langfuse / OTel / LangSmith imports. `nice_to_have.md` §1 / §3 triggers untouched. |
| Four-layer contract | 4 contracts KEPT (`primitives` / `graph` / `workflows` / `evals` vs surfaces). `evals` still cannot import surfaces; `evals → workflows` still permitted (M7-T01-ISS-03 amendment from T03 stands). |
| nice_to_have.md | No adoption. Live-mode CI replay and nightly scheduled runs remain explicitly out-of-scope per task spec. |

**Verdict:** no HIGH drift. The one new third-party action is CI infrastructure, not a Python runtime dependency; architecture.md §6 does not govern it.

---

## AC grading

| # | Criterion | Status | Evidence |
| --- | --- | --- | --- |
| 1 | ≥3 seed fixtures under `evals/` spanning both workflows, min one per LLM node | ✅ PASS | Three committed: [planner/explorer/happy-path-01.json](../../../../evals/planner/explorer/happy-path-01.json), [planner/planner/happy-path-01.json](../../../../evals/planner/planner/happy-path-01.json), [slice_refactor/slice_worker/happy-path-01.json](../../../../evals/slice_refactor/slice_worker/happy-path-01.json). Each covers one distinct LLM node (`explorer`, `planner`/`planner-synth`, `slice_worker`). |
| 2 | `aiw eval run planner` + `aiw eval run slice_refactor` green on HEAD | ✅ PASS | `aiw eval run planner` → `2 passed, 0 failed`; `aiw eval run slice_refactor` → `1 passed, 0 failed` (subgraph walk reaches `slice_worker` via `_resolve_node_scope`). |
| 3 | New `eval-replay` CI job gated by paths `workflows/**`, `graph/**`, `evals/**` | ✅ PASS | [.github/workflows/ci.yml:61-89](../../../../.github/workflows/ci.yml#L61-L89) — `dorny/paths-filter@v3` emits `relevant` output; subsequent steps gated by `steps.paths.outputs.relevant == 'true' \|\| github.event_name == 'push'` so pushes-to-main always run. `needs: test` keeps the ordering after the main test job. |
| 4 | `uv run pytest tests/evals/test_seed_fixtures_deterministic.py` green under default pytest | ✅ PASS | Three tests green under `uv run pytest` (no env gates required). |
| 5 | CHANGELOG records capture procedure + live-provider run_ids + post-capture edits | ✅ PASS | CHANGELOG `## [Unreleased]` → `### Added — M7 Task 05: CI Hookup + Seed Fixtures (2026-04-21)` documents: per-fixture `output_schema_fqn` + tolerance; reproducible capture bash block with `eval-seed-planner` + `eval-seed-slice2` run_ids; three post-capture edits (flat layout consolidation, case-id rename, explorer `notes → summary` tolerance swap for the missing-field fix); subgraph-resolution retrofit linked to M7-T03-ISS-02. |
| 6 | `uv run pytest && uv run lint-imports && uv run ruff check` green | ✅ PASS | 538 passed, 4 skipped; 4 kept 0 broken; `All checks passed!`. |

---

## 🔴 HIGH

None.

## 🟡 MEDIUM

### M7-T05-ISS-01 — `tests/cli/test_eval_commands.py` autouse fixture leaves session-wide registry pollution

[`tests/cli/test_eval_commands.py:94-98`](../../../../tests/cli/test_eval_commands.py#L94-L98) defines an autouse fixture `_reensure_planner_registered` that calls `workflows._reset_for_tests()` then re-registers only `planner` — with no post-yield teardown. After the last test in that module runs, the session-wide `_REGISTRY` contains only `planner`; any later test that needs `slice_refactor` (or any other workflow) must re-register it, because Python's import cache makes `importlib.import_module(...)` a no-op the second time.

This is a T04-landed fixture that the T05 seed-fixtures test tripped on (`test_slice_refactor_seed_fixtures_replay_green_deterministic` → `KeyError: "unknown workflow 'slice_refactor'; registered workflows: planner"`). T05 worked around the pollution by adding its own `_ensure_workflows_registered` autouse fixture that idempotently re-registers both builders before each case — band-aid, not root-cause fix.

**Action / Recommendation:** **Not T05's to fix.** The correct owner is the T04 fixture. Propagate as carry-over to T06 (milestone close-out) so the fixture grows a post-yield teardown: `yield; workflows._reset_for_tests(); workflows.register("planner", build_planner); workflows.register("slice_refactor", build_slice_refactor)` (or a session-scoped fixture that snapshots + restores the registry as a whole). Leaving the T05 band-aid in place under `test_seed_fixtures_deterministic.py` is reasonable defence-in-depth even after the T04 fix lands.

**Severity:** 🟡 MEDIUM — silent test pollution that masquerades as a seed-fixture bug, not a code correctness issue.

## 🟢 LOW

### M7-T05-ISS-02 — `dorny/paths-filter@v3` is a third-party CI action not enumerated in architecture.md §6

[`.github/workflows/ci.yml:69`](../../../../.github/workflows/ci.yml#L69) pins `dorny/paths-filter@v3`. Architecture.md §6 enumerates Python runtime dependencies and is silent on CI-infrastructure actions, so strictly no architecture-drift rule is violated. Noted here so a future reviewer questioning the pin has an audit trail.

**Action / Recommendation:** No action. If the team wants to formalise a CI-action allowlist, that is a separate process decision, not a T05 follow-up. Pinning the major version (`@v3`) rather than a commit SHA is the standard ergonomic trade-off; upgrade path is a minor rev within `v3`.

**Severity:** 🟢 LOW — flag-only.

### M7-T05-ISS-03 — CI job uses `uv sync --all-extras` instead of the spec sketch's `uv sync --dev`

The T05 spec pseudocode reads `run: uv sync --dev`; the landed job uses `uv sync --all-extras` for consistency with the sibling `test` and `e2e` jobs (both use `--all-extras`). This repo has no dev-only extras defined in `pyproject.toml`, so the two commands produce an identical environment today. Spec deviation is immaterial.

**Action / Recommendation:** No action. Align the spec to the landed sync command on the next T05 re-read, or leave the sketch as illustrative. Consistency with sibling jobs wins.

**Severity:** 🟢 LOW — flag-only; no behavioural difference under current `pyproject.toml`.

### M7-T05-ISS-04 — Spec deviation: explorer tolerance `field_overrides={"notes": "substring"}` → `{"summary": "substring"}`

The T05 spec's explorer-fixture example pins `field_overrides={"notes": "substring"}`, but `ai_workflows.workflows.planner.ExplorerReport` has no `notes` field — only `summary`, `considerations`, `assumptions`. The committed fixture substitutes `summary` as the free-text field getting substring tolerance; intent (allow the free-text field to vary under live replay while holding the structured fields strict) is preserved.

**Action / Recommendation:** No action at T05 — deviation is documented in CHANGELOG. Consider whether the T05 spec text should be updated to match reality as part of T06 milestone close-out (non-blocking).

**Severity:** 🟢 LOW — documented spec deviation.

### M7-T05-ISS-05 — Only one `slice_refactor` fixture committed; spec mentions "optionally a full-trajectory case"

Milestone README exit criterion 5 asks for `slice_refactor` "≥1 case covering the slice_worker node; optionally a full-trajectory case." T05 ships exactly one fixture (one of the four slices from the `eval-seed-slice2` run). The full-trajectory option was intentionally deferred — capturing all four slices from the run would have committed ~4× the bytes without exercising the harness differently, and live-replay coverage is the better forum for trajectory drift.

**Action / Recommendation:** No action at T05. If a future incident shows per-slice drift the eval harness would have caught, add the remaining three slices as `happy-path-02..04.json` under the same `slice_worker` directory — no wiring change needed.

**Severity:** 🟢 LOW — spec-optional; meets the required minimum.

### M7-T05-ISS-06 — Deserialization warnings during slice_refactor capture path

During the seed-run for `eval-seed-slice2`, LangGraph's msgpack deserializer emitted warnings like `Deserializing unregistered type ai_workflows.workflows.planner.PlannerInput / ExplorerReport / PlannerPlan / SliceSpec / SliceResult / SliceAggregate from checkpoint`. These are advisory for the current LangGraph version but a future release will block. Not introduced by T05 — observed during capture and worth noting.

**Action / Recommendation:** Track as a LOW across T06 milestone close-out for later pickup — likely a `nice_to_have.md` candidate (register the pydantic classes with LangGraph's msgpack type registry, or switch the checkpoint write path to `model_dump(mode='json')` before handoff to the serializer). Not T05's scope to fix.

**Severity:** 🟢 LOW — pre-existing warning, future compatibility risk only.

---

## Additions beyond spec — audited and justified

- **`_resolve_node_scope` + `_node_exists_anywhere` in `ai_workflows/evals/runner.py`** ([runner.py:432-494](../../../../ai_workflows/evals/runner.py#L432-L494)). Not in the T05 spec directly but load-bearing for AC-2: T03's flat-node lookup missed LLM nodes wired inside compiled sub-graphs (`slice_worker` lives in `slice_branch`). Fix walks each top-level runnable's `.builder` attribute (present on `CompiledStateGraph`) to find the enclosing `StateGraph`, and uses that sub-graph's `state_schema` for the replay — critical because `_hydrate_state` uses the schema to reverse-hydrate pydantic leaves, and `SliceBranchState` ≠ `SliceRefactorState`. **Accepted** — the alternative (spec-literal) path would hard-block `slice_refactor` seed coverage. Propagated as M7-T03-ISS-02 RESOLVED in the T03 issue file.

- **`slice_refactor_eval_node_schemas()` in `ai_workflows/workflows/slice_refactor.py`** ([slice_refactor.py:1257-1281](../../../../ai_workflows/workflows/slice_refactor.py#L1257-L1281)). The T04 `aiw eval capture` helper requires every workflow with eval coverage to expose a `<workflow_id>_eval_node_schemas()` callable. T04 shipped the planner's; T05's `slice_refactor` coverage requires adding this one. Docstring explicitly names the sub-graph caveat (capture helper cannot walk top-level snapshot for sub-graph LLM nodes → live `CaptureCallback` is the authoritative path for this workflow). **Accepted** — prerequisite for the T05 fixture-capture procedure.

- **`_ensure_workflows_registered` autouse fixture in `tests/evals/test_seed_fixtures_deterministic.py`** ([test_seed_fixtures_deterministic.py:39-62](../../../../tests/evals/test_seed_fixtures_deterministic.py#L39-L62)). Band-aid for M7-T05-ISS-01 (T04 fixture pollution). Idempotent via `contextlib.suppress(ValueError)` — a different-builder conflict still raises, preventing silent divergence. **Accepted** — the test file cannot land without it or AC-4 fails under the full-suite run. MEDIUM recommendation above names the T04 side as the real fix-owner.

- **Subgraph-docstring paragraph in the runner module docstring** ([runner.py:23-47](../../../../ai_workflows/evals/runner.py#L23-L47)). Points at `_resolve_node_scope` and names the M7-T03-ISS-02 retrofit inline — maintains audit traceability from the runner to the issue log. **Accepted** — audit-trail hygiene.

None of these additions pulls in external dependencies, crosses layer boundaries, or introduces coupling not already implied by the spec.

---

## Gate summary

| Gate | Result |
| --- | --- |
| `uv run pytest` | 538 passed, 4 skipped, 2 warnings |
| `uv run pytest tests/evals/` | 49 passed, 1 skipped |
| `uv run aiw eval run planner` | `2 passed, 0 failed` |
| `uv run aiw eval run slice_refactor` | `1 passed, 0 failed` |
| `uv run lint-imports` | 4 kept, 0 broken |
| `uv run ruff check` | All checks passed |

---

## Issue log

| ID | Severity | Summary | Owner / next touch point |
| --- | --- | --- | --- |
| M7-T05-ISS-01 | 🟡 MEDIUM | T04 `test_eval_commands.py` autouse fixture pollutes session-wide workflow registry | Propagate to T06 milestone close-out — add post-yield teardown to the T04 fixture |
| M7-T05-ISS-02 | 🟢 LOW | `dorny/paths-filter@v3` not enumerated in architecture.md §6 | Flag-only; CI-infra, out of §6 scope |
| M7-T05-ISS-03 | 🟢 LOW | CI job uses `uv sync --all-extras` vs spec's `uv sync --dev` | Flag-only; behaviourally identical under current `pyproject.toml` |
| M7-T05-ISS-04 | 🟢 LOW | Explorer fixture tolerance swapped `notes → summary` — `notes` field does not exist | Documented in CHANGELOG; update spec text at T06 if desired |
| M7-T05-ISS-05 | 🟢 LOW | Only one `slice_refactor` fixture; spec allows "optionally a full-trajectory case" | Add more cases when an incident motivates them |
| M7-T05-ISS-06 | 🟢 LOW | LangGraph msgpack "unregistered type" warnings during capture | Track as pre-existing; future LangGraph blocker |
| M7-T03-ISS-02 | 🟡 MEDIUM | Replay runner flat-node lookup missed sub-graph-wrapped LLM nodes | **RESOLVED** in T05 working tree via `_resolve_node_scope`; retrofit traced in [../issues/task_03_issue.md](task_03_issue.md) |

---

## Deferred to nice_to_have

None. (M7-T05-ISS-06 — LangGraph msgpack warnings — is a candidate only if a concrete release blocks on it; not a feature-wish.)

---

## Propagation status

- **M7-T03-ISS-02 (sub-graph resolution in replay runner)** — RESOLVED in this task's working tree; retrofit documented in [../issues/task_03_issue.md](task_03_issue.md) under the new MEDIUM section + issue-log row. T03 status line carries an addendum noting the 2026-04-21 retrofit.
- **M7-T05-ISS-01 (T04 fixture pollution)** — propagated to [../task_06_milestone_closeout.md](../task_06_milestone_closeout.md) as carry-over so T06 Builder grows the post-yield teardown (see carry-over section on that task file).
- No other new carry-over into T06 beyond what the milestone close-out already references.
