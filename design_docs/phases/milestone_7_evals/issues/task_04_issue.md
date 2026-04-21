# Task 04 — CLI Surface (`aiw eval capture` + `aiw eval run`) — Audit Issues

**Source task:** [../task_04_cli_surface.md](../task_04_cli_surface.md)
**Audited on:** 2026-04-21
**Audit scope:** `ai_workflows/cli.py`, `ai_workflows/evals/_capture_cli.py`, `ai_workflows/workflows/planner.py` (`planner_eval_node_schemas` addition), `tests/cli/test_eval_commands.py`, `tests/cli/conftest.py`, `CHANGELOG.md`, `pyproject.toml` importlinter block, cross-check against [architecture.md](../../../architecture.md) §3 / §4.4 / §6 / §7, KDR-002, KDR-003, KDR-004, KDR-006, KDR-007, KDR-009, KDR-010, and the T01/T02/T03 issue files for carry-over.
**Status:** ✅ PASS — no OPEN issues.

---

## Design-drift check

| Axis | Finding |
| --- | --- |
| New dependency | None. Only stdlib (`importlib`, `uuid`, `datetime`, `pathlib`, `asyncio`, `typing`) + existing deps (`typer`, `pydantic`, `aiosqlite` via `AsyncSqliteSaver`). No `pydantic-ai`, no `instructor`, no external observability backend. |
| New module / layer | One new module: `ai_workflows/evals/_capture_cli.py` — sits inside the existing `evals` layer from T01. CLI imports it through `ai_workflows.evals._capture_cli`; `evals → surfaces` contract unaffected. The module does a runtime `importlib.import_module(f"ai_workflows.workflows.{workflow_id}")` to resolve the per-workflow schema registry — the same pattern T03's `EvalRunner._resolve_builder` uses, and permitted by the narrowed `evals cannot import surfaces` contract T03 shipped (M7-T01-ISS-03 retrofit). No fifth contract needed. |
| LLM call added | None. Capture path is checkpoint-read-only (`saver.aget(cfg).channel_values`). Replay path inherits T03's `EvalRunner`, which itself honours KDR-004 (the replay graph pairs `<node> → <node>_validator`). Deterministic mode monkey-patches `LiteLLMAdapter` → `StubLLMAdapter`; live mode inherits the `AIW_EVAL_LIVE=1` + `AIW_E2E=1` double-gate from T03. |
| KDR-003 no Anthropic API | Confirmed. `grep -n 'anthropic\|ANTHROPIC_API_KEY'` on the four files touched returns zero matches. No provider key is read anywhere in the capture path — it never fires a completion. |
| Checkpoint / resume | Capture reads state via `AsyncSqliteSaver.aget(cfg).channel_values` — LangGraph-owned API. No hand-rolled checkpoint writes, no migration, no serializer. KDR-009 honoured. |
| Retry logic | None. Capture is a single-SELECT read; replay inherits T03's retry passthrough via `target_spec.runnable`. |
| Observability | `configure_logging(level="INFO")` at the command entry point (mirrors `run` / `resume` / `list-runs`). No Langfuse / OTel / LangSmith imports. `nice_to_have.md` §1/§3/§8 triggers untouched. |
| KDR-004 validator-after-every-LLM | Inherited from T03's replay shape. Capture never fires an LLM node, so this axis applies only via the runner wired on the `run` subcommand — unchanged from T03. |
| KDR-010 bare-typed | N/A. No new `response_format` schemas introduced. The `planner_eval_node_schemas` registry simply re-exports `ExplorerReport` and `PlannerPlan` (both already bare-typed per T07b). |
| Four-layer contract | `uv run lint-imports` → 4 kept, 0 broken. The T03 amendment (`evals cannot import surfaces`) is the contract that permits this task's `evals → workflows` dynamic resolution. The CLI's new `eval_app` sub-app imports `ai_workflows.evals` — `surfaces → evals` has always been permitted (architecture.md §3: surfaces imports from everything below it). |
| Typer sub-app pattern | `eval_app = typer.Typer(...)` + `app.add_typer(eval_app, name="eval")` matches the existing `run` / `resume` / `list-runs` Typer conventions. Help surfacing confirmed manually: `aiw --help` lists `eval`; `aiw eval --help` lists `capture` + `run`. |

**Verdict:** no HIGH drift. All architectural rules held.

---

## AC grading

| # | Criterion | Status | Evidence |
| --- | --- | --- | --- |
| 1 | `aiw eval capture --run-id <id> --dataset foo` writes fixture JSON for every LLM-node call; exits 2 on unknown / non-completed run_id | ✅ PASS | Happy path: [test_eval_commands.py:306-363](../../../../tests/cli/test_eval_commands.py#L306-L363) (runs the full `aiw run` → `aiw resume` → `aiw eval capture` chain, verifies two fixtures at `captured-seed/planner/{explorer,planner}/*.json`, asserts `expected_output` matches the stubbed JSON, provenance carries `captured_from_run_id`). Non-completed: [test_eval_commands.py:272-298](../../../../tests/cli/test_eval_commands.py#L272-L298) (pending run → exit 2). Unknown run_id: [test_eval_commands.py:300-314](../../../../tests/cli/test_eval_commands.py#L300-L314) (no matching row → exit 2). |
| 2 | `aiw eval run planner` runs deterministic replay, prints summary, exits 0 all-pass / 1 any-fail | ✅ PASS | All-pass: [test_eval_commands.py:193-205](../../../../tests/cli/test_eval_commands.py#L193-L205) (single passing fixture → exit 0, `1 passed 0 failed` in stdout). Any-fail: [test_eval_commands.py:208-234](../../../../tests/cli/test_eval_commands.py#L208-L234) (fixture with unknown node → exit 1, `[FAIL]` in output). |
| 3 | `--live` refuses unless BOTH `AIW_EVAL_LIVE=1` and `AIW_E2E=1` are set | ✅ PASS | [test_eval_commands.py:247-262](../../../../tests/cli/test_eval_commands.py#L247-L262) — tests both permutations: (a) neither set → exit 2 with `AIW_EVAL_LIVE` in message; (b) only `AIW_EVAL_LIVE` set → exit 2 with `AIW_E2E` in message. Inherits T03's `EvalRunner.__init__` double-gate. |
| 4 | `aiw eval` sub-group surfaces under `aiw --help` | ✅ PASS | [test_eval_commands.py:173-181](../../../../tests/cli/test_eval_commands.py#L173-L181) (`aiw eval --help` lists both subcommands) + [test_eval_commands.py:184-189](../../../../tests/cli/test_eval_commands.py#L184-L189) (`aiw --help` lists `eval`). Manually verified: `uv run aiw --help` shows the `eval` sub-group. |
| 5 | Shared-dispatch discipline kept; import-linter 4/4 kept | ✅ PASS | `ai_workflows/cli.py` imports `EvalRunner`, `load_suite` from `ai_workflows.evals` — no replay logic reimplemented. `uv run lint-imports` → 4 kept, 0 broken. |
| 6 | `uv run pytest && uv run lint-imports && uv run ruff check` green | ✅ PASS | 533 passed / 4 skipped / 2 warnings; 4 kept 0 broken; `All checks passed!`. |

All six spec ACs PASS. No carry-over items from T01/T02/T03 issues targeted T04.

---

## 🔴 HIGH

None.

## 🟡 MEDIUM

None.

## 🟢 LOW

### M7-T04-ISS-01 — `_run_fail_fast` accesses `EvalRunner._mode` via private attribute

[`cli.py:560-580`](../../../../ai_workflows/cli.py#L560-L580) — the `--fail-fast` helper rebuilds an `EvalReport` from a list of per-case partial reports and needs the runner's mode to stamp into the aggregate. It reads `runner._mode` with a `# noqa: SLF001` exemption. The attribute is private-by-convention on `EvalRunner`. Two clean fixes exist: (a) expose a public `EvalRunner.mode` property, or (b) take the mode from the first `partial.mode` returned by `runner.run(one)` so the aggregate is assembled entirely from public surface.

**Action / Recommendation:** T05 / T06 touch point — if either needs to construct aggregate reports the same way, land one of the two fixes above. Zero functional risk today; the noqa makes the access audit-visible and the helper is only used under `--fail-fast`, which the tests don't exercise (the flag is validation-only in M7, not a CI entry point). Leaving as LOW rather than forcing a fix this cycle keeps the T04 scope tight.

**Severity:** 🟢 LOW — cosmetic / API-hygiene, no functional impact.

### M7-T04-ISS-02 — `_capture_cli` imports module-private helpers from `capture_callback`

[`_capture_cli.py:59-62`](../../../../ai_workflows/evals/_capture_cli.py#L59-L62) imports `_normalize`, `_normalize_output`, and `output_schema_fqn` from `capture_callback.py`. The first two are underscore-prefixed module-private helpers. Same-package import is within Python's convention but a hygiene improvement would be to extract the three helpers into a shared `_helpers.py` in `evals/` (or rename them without the underscore prefix if they are truly part of the evals-internal surface).

**Action / Recommendation:** Not a T04 fix. Land during T06 close-out if the file count stays reasonable; otherwise defer. Zero behavioural risk; `_normalize` / `_normalize_output` semantics are already pinned by T02's unit tests.

**Severity:** 🟢 LOW — within-package convention, no layer violation.

### M7-T04-ISS-03 — `test_eval_run_empty_suite_exits_one` pins beyond-spec behaviour

The spec's AC-2 calls out "exits 0 on all-pass, 1 on any-fail" but says nothing about an *empty* suite. The implementation chose "empty suite → exit 1 with `no eval cases found` message" as the safer default (silent pass on an unpopulated directory would be the same class of drift AC-5 catches in T03). The test [test_eval_commands.py:265-269](../../../../tests/cli/test_eval_commands.py#L265-L269) codifies this choice. Flag for visibility — if a future CI orchestrator disagrees (e.g. wants empty suite → exit 0 so bootstrap doesn't fail), the branch is a two-line change.

**Action / Recommendation:** No action. Document the choice in the T06 close-out exit-criteria section if anyone revisits.

**Severity:** 🟢 LOW — implementation-defined behaviour, consistent with "fail loud on absence" M7 spirit.

---

## Additions beyond spec — audited and justified

- **`planner_eval_node_schemas()` registry on `planner.py`** ([planner.py:429-449](../../../../ai_workflows/workflows/planner.py#L429-L449)). The T04 spec's preferred capture path is "replay against the checkpointed state" but doesn't spell out how to resolve the per-node output schema needed for `EvalCase.output_schema_fqn`. LangGraph's `StateNodeSpec` exposes the `runnable` but not the `output_schema=` binding passed to `tiered_node(...)`. The Builder added a small workflow-exposed callable returning `{node_name: pydantic_cls}` so capture can stamp the FQN without introspecting the TieredNode closure. **Accepted** — a closed-world per-workflow registry is less fragile than runtime reflection; a workflow without a registry raises `WorkflowCaptureUnsupportedError` at the CLI surface (exit 2) so the missing case is audit-visible.
- **`CaptureNotCompletedError` / `UnknownRunError` / `WorkflowCaptureUnsupportedError` typed exceptions** ([_capture_cli.py:90-99](../../../../ai_workflows/evals/_capture_cli.py#L90-L99)). Three distinct precondition failures, three distinct CLI exit-2 messages. Pattern mirrors `_dispatch.UnknownWorkflowError` / `UnknownTierError` / `ResumePreconditionError`. **Accepted** — standard surface-boundary error taxonomy.
- **`_filter_inputs` drops downstream-node outputs from reconstructed inputs** ([_capture_cli.py:211-241](../../../../ai_workflows/evals/_capture_cli.py#L211-L241)). When capturing the `explorer` node, the final state still contains `planner_output` (written after `explorer` completed). A naïve replay with the full state would seed the `explorer`'s prompt_fn with the planner's answer, corrupting the replay. The filter walks the registry and drops every `<other_node>_output` + `<other_node>_output_revision_hint` key so each captured case's inputs only contain the state keys the target node's `prompt_fn` could have read at capture time. **Accepted** — correctness-critical invariant; the alternative (full-state capture) would produce silently-wrong replays.
- **Suffix-on-collision via `EvalCase.model_copy(update=...)`** ([_capture_cli.py:262-280](../../../../ai_workflows/evals/_capture_cli.py#L262-L280)). Mirrors `CaptureCallback._resolve_unique_path`. Uses `model_copy` because `EvalCase` is `frozen=True`; pydantic v2 supports `model_copy(update=...)` on frozen models. **Accepted** — behavioural parity with the live-run capture path.
- **`_isolate_evals_root` autouse fixture in tests** ([test_eval_commands.py:104-109](../../../../tests/cli/test_eval_commands.py#L104-L109)). Sets `AIW_EVALS_ROOT` per-test so `default_evals_root()` lands under `tmp_path`, matching how the T02 integration tests isolate the fixture root. **Accepted** — required test hygiene; without it tests would pollute the repo's real `evals/` directory.
- **Two extra tests beyond the six in spec** — `test_eval_run_dataset_scopes_suite_load`, `test_eval_run_empty_suite_exits_one`, `test_eval_capture_unknown_run_exits_two`, `test_root_help_lists_eval_sub_group`. Each closes a gap the spec enumerates implicitly (dataset-scoping, empty-suite handling, unknown-run, help-surfacing completeness). **Accepted** — additional coverage, no scope creep. Total test count: 11.

None of these additions pulls in an external dependency, adds a new surface, or introduces coupling the spec did not already imply.

---

## Gate summary

| Gate | Result |
| --- | --- |
| `uv run pytest` | 533 passed, 4 skipped, 2 warnings |
| `uv run pytest tests/cli/test_eval_commands.py` | 11 passed |
| `uv run lint-imports` | 4 kept, 0 broken |
| `uv run ruff check` | All checks passed |
| Manual: `uv run aiw --help` | `eval` sub-group present |
| Manual: `uv run aiw eval --help` | `capture` + `run` both listed |

---

## Issue log

| ID | Severity | Summary | Owner / next touch point |
| --- | --- | --- | --- |
| M7-T04-ISS-01 | 🟢 LOW | `_run_fail_fast` reads `runner._mode` via private access | Flag-only; land a public `EvalRunner.mode` property if T05/T06 touches the helper |
| M7-T04-ISS-02 | 🟢 LOW | `_capture_cli` imports module-private `_normalize` / `_normalize_output` | Flag-only; consider extracting to `evals/_helpers.py` at T06 close-out |
| M7-T04-ISS-03 | 🟢 LOW | Empty-suite exits 1 — beyond-spec behaviour | Flag-only; document in T06 exit-criteria if CI prefers exit 0 |

---

## Deferred to nice_to_have

None. The `--json` output format the spec explicitly leaves out is already parked in nice_to_have territory per the T04 task file's "Out of scope" section.

---

## Propagation status

No forward-deferrals. All three LOWs are self-contained flag-only entries the T05/T06 Builders will pick up opportunistically; none gates those tasks. No new carry-over added to T05 / T06 from this audit.
