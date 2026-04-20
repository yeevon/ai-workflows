# Task 05 — `aiw resume` CLI Command — Audit Issues

**Source task:** [../task_05_cli_resume.md](../task_05_cli_resume.md)
**Audited on:** 2026-04-20
**Audit scope:** `ai_workflows/cli.py` (new `resume` command + `_resume_async` + `_emit_resume_final` + shared `_build_cfg` + T04 extension to `_emit_final_state`), `tests/cli/test_resume.py` (new), `CHANGELOG.md`; cross-checked against `design_docs/architecture.md` (§3 layer contract, §4.1 primitives, §4.2 graph adapters, §4.4 surfaces, §5 runtime flow — especially steps 6–8 on gate + resume, §6 dependencies, §7 contracts, §8.2 error handling, §8.3 gates, §8.5 cost control) and KDR-003 / KDR-004 / KDR-006 / KDR-007 / KDR-009. Sibling audit [task_04_issue.md](task_04_issue.md) reviewed for consistency — `_emit_final_state`'s cost-at-pause stamp is a T04 extension landed here and validated against T04's ACs; neither T04's 7 ACs nor its KDR-003 source-grep guard regress.

**Status:** ✅ PASS — all 6 ACs met; no OPEN issues.

## Design-drift check

| Vector | Result | Note |
| --- | --- | --- |
| New dependency | ✅ None | No additions to `pyproject.toml`. New imports (`langgraph.types.Command`, `datetime.UTC`, `datetime.datetime`, `ai_workflows.primitives.cost.TokenUsage`) are all from packages already in `architecture.md §6` (LangGraph, stdlib, project-internal primitives). No `nice_to_have.md` item pulled in. |
| New module / layer | ✅ Fits | Zero new modules. All changes land in existing `cli.py` (surfaces layer) and the new test file mirrors the `ai_workflows/cli.py` path at `tests/cli/test_resume.py`. `lint-imports`: 3 / 3 KEPT, 0 broken. |
| Surface → graph import | ✅ Task-spec sanctioned | `cli.py` continues to import `build_async_checkpointer` from `graph.checkpointer` (same import T04 audit already signed off on) and now also `Command` from `langgraph.types` — a LangGraph public API used per KDR-009's "LangGraph owns resume" contract. The §3 shorthand ("surfaces import workflows + primitives") is descriptive; the enforced import-linter contracts are the authoritative rule and remain 3 / 3 KEPT. Task spec explicitly prescribes `await app.ainvoke(Command(resume=gate_response), cfg)` (line 30) so this is a direct spec implementation. |
| LLM call added | ✅ No new call | `_resume_async` threads the same `TieredNode` → `LiteLLMAdapter` path as T04 via `config["configurable"]["tier_registry"]` rebuilt from the run's recorded `workflow_id`. No new provider call; KDR-004 validator pairing is entirely inside the workflow graph and untouched. |
| Checkpoint / resume | ✅ LangGraph-owned | `_resume_async` awaits `build_async_checkpointer()` (the `AsyncSqliteSaver` factory), compiles the graph against it, and hands `Command(resume=gate_response)` to `compiled.ainvoke(...)`. No hand-rolled checkpoint read/write; no direct `SqliteSaver` mutation. `_emit_final_state`'s new `await storage.update_run_status(run_id, "pending", total_cost_usd=...)` writes to the `Storage` run registry, *not* the checkpoint — KDR-009 preserved (Storage owns run registry; LangGraph owns checkpoints). |
| Retry logic | ✅ Taxonomy | No bespoke `try/except` retry in the resume path. The single `except Exception` wrapping `ainvoke` is the CLI's top-level boundary (same shape as T04's `_run_async`), delegating to the existing `_surface_graph_error` so state-resident `NonRetryable` messages surface intact. KDR-006 retry loop runs entirely inside `retrying_edge` at the graph layer. |
| Observability | ✅ Structured | `resume` calls the same `configure_logging(level="INFO")` entry-point T04 added; no additional logger instantiations, no Langfuse / LangSmith / OTel pulled in. |
| Four-layer contract | ✅ Holds | `cli.py` imports stay monotonic: `langgraph.types` (3rd-party) + `workflows` (registry) + `graph.checkpointer` / `graph.cost_callback` (graph adapters) + `primitives.cost` / `primitives.storage` / `primitives.logging` / `primitives.retry`. Lint-imports 3 / 3 KEPT. |
| KDR-003 (no Anthropic API, no direct provider secret reads in CLI) | ✅ | T04's `test_cli_module_does_not_read_provider_secrets` source-greps `cli.py` for `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `import anthropic`, `from anthropic` — still none present after T05's additions. Module docstring now explicitly names resume's secret-boundary discipline ("never reads provider API keys directly"). Env-var reads continue to stay at the `LiteLLMAdapter` boundary. |
| Cost control (KDR / §8.5) | ✅ | Cost reseed uses the existing `CostTracker.record()` API with a synthetic `TokenUsage(cost_usd=stored_cost, model="<resumed>", tier="<resumed>")`. The `model`/`tier` placeholders are a deliberate sentinel — they roll into `tracker.total(run_id)` without masquerading as a real provider call, preserving `CostTracker.by_tier()` / `by_model()` reporting clarity (a future "resumed" row in those rollups is informational, not a provider attribution). Budget cap from the original run rides across via the same `CostTrackingCallback(budget_cap_usd=…)` path. |
| `finished_at` stamping | ✅ | `_update_run_status_sync` auto-stamps `finished_at` only for `{completed, failed}`. The CLI passes an explicit `datetime.now(UTC).isoformat()` for the `gate_rejected` branch (confirmed by reading `storage.py:357-359`). `completed` relies on the auto-stamp. No drift from Storage's public contract. |
| `nice_to_have.md` items | ✅ None adopted | |

**Deviations from spec — audited and OK:** the CHANGELOG's *Deviations from spec* section names three. Each inspected:

1. **AC-5 tested via row-readback of `runs.total_cost_usd`, not a cap-trip on resume.** The planner graph has no post-gate LLM calls (`gate → artifact → END`, and `_artifact_node` makes no provider calls), so `CostTrackingCallback.on_node_complete`'s cap-check boundary never fires during resume — there is no node where the cap can trip. The CHANGELOG deviation is accurate: AC-5 asks for "cost tracker reseeded from the stored cost so `--budget` caps carry across `run` + `resume`". The reseed itself is provable end-to-end via `test_resume_reseeds_cost_tracker_from_runs_total_cost_usd` — if the reseed were missing, `tracker.total(run_id)` at completion would be `0` (no post-gate LLM calls to populate it), and the `update_run_status("completed", total_cost_usd=…)` call would zero the row; the test asserts `0.0033` carries through. The cap-check path itself is exercised by T04's `test_run_budget_cap_breach_exits_nonzero_with_budget_message` against the pre-gate segment of the same graph. No functional gap. If M5 adds a workflow with post-gate LLM calls, an explicit cap-trip-on-resume test should land in that milestone — noted below as a deferred forward-looking flag, not an issue for T05.
2. **No new closer helper — reuse `update_run_status`.** Spec step 1 (deliverables §Tests) says `Storage.update_run_status(run_id, "completed") (or equivalent closer helper — add one if missing)`. Existing `update_run_status` already covers both `completed` + `gate_rejected` with the explicit `finished_at` override; a new helper would be redundant and add surface area to `primitives/storage.py` without a caller that needs it. Task-spec-sanctioned ("or equivalent"). No drift.
3. **Cost-at-pause stamp added to `_emit_final_state` (T04 extension).** Not prescribed by T04, required by T05 AC-5. The stamp is minimal — one `await storage.update_run_status(run_id, "pending", total_cost_usd=tracker.total(run_id))` call — and does not alter T04's stdout contract (the three-line `run_id / awaiting: gate / resume with: …` block is unchanged; pause-stamp runs before `typer.echo(run_id)`). T04's 7 ACs re-verified below in the "sibling audit" subsection.

**Sibling audit — T04 regression check.** `_emit_final_state` became `async` and gained a `storage: SQLiteStorage` parameter. `_run_async` is the only caller and passes the storage handle it already opened. All 8 `tests/cli/test_run.py` tests pass (1.94s total across the CLI package, `tests/cli/` 15 / 15 green). The `runs` row's `total_cost_usd` was previously left at `NULL` on pause; now it's stamped — T04's `_read_run_row(storage_path, run_id)` test asserts only `workflow_id == "planner"` + `status == "pending"`, so it does not regress, but the new stamp is visible to any future caller (e.g. `aiw list-runs` in T06) and aligns with the column's semantics (running cost, not final cost). T04's KDR-003 source-grep still passes. No regression.

No design drift.

## AC grading

| # | Acceptance criterion | Grade | Evidence |
| --- | --- | --- | --- |
| 1 | `aiw resume <run_id>` rehydrates from `AsyncSqliteSaver` and completes a gate-paused `planner` run | ✅ | `test_resume_happy_path_completes_and_persists_plan_artifact` — drives `_run_and_pause()` (two scripted LLM responses → `HumanGate("plan_review")` interrupt → run id echoed), then `aiw resume <id>` with default `--gate-response approved`. Assertions: exit 0, plan JSON in stdout (`"goal": "Ship the marketing page."`), `runs.status == "completed"`, `runs.finished_at is not None`, and — most importantly — `plan` artifact row persists under `(run_id, "plan")` via `storage.read_artifact(...)`. The artifact is written by the planner's `_artifact_node` only when `gate_plan_review_response == "approved"` (`planner.py:189-195`), proving the resume cleared the gate, ran the post-gate node, and persisted the artifact. |
| 2 | `--gate-response` is forwarded verbatim to `Command(resume=...)` | ✅ | `test_resume_forwards_gate_response_verbatim` — asserts `storage.get_gate(run_id, "plan_review")["response"] == "approved"`. `HumanGate` calls `storage.record_gate_response(run_id, gate_id, response)` where `response` is the return value of `langgraph.interrupt()` — which LangGraph pins to the value passed in `Command(resume=...)`. A round-trip through the gate log is cleaner than mocking `Command` because it proves the end-to-end value propagated across the CLI → LangGraph → gate-node boundary without substitution. Direct wiring verified at `cli.py:487`: `final = await compiled.ainvoke(Command(resume=gate_response), cfg)`. |
| 3 | Unknown `run_id` exits 2 with a helpful message (no traceback) | ✅ | `test_resume_unknown_run_id_exits_two_with_no_run_found_message` — invokes `aiw resume 00000000000000000000000000` (a ULID-shape id that was never created). `_resume_async` reads `await storage.get_run(run_id)` → `None` → `typer.echo(f"no run found: {run_id}", err=True)` + `raise typer.Exit(code=2)`. Test asserts `exit_code == 2`, `"no run found: 00000000000000000000000000" in result.output`, and `"Traceback" not in result.output`. Early-exit before any checkpointer or graph compile, so no LangGraph surface is touched. |
| 4 | `Storage` run-status row flips to `completed` on success, `gate_rejected` on rejection | ✅ | Happy path covered by AC-1 (`row["status"] == "completed"`). Rejection path covered by `test_resume_rejected_flips_status_to_gate_rejected_and_exits_one` — invokes `aiw resume <id> --gate-response rejected`, asserts `exit_code == 1`, `"plan rejected by gate" in output`, and reads the `runs` row back: `status == "gate_rejected"`, `finished_at is not None`, no `plan` artifact persisted (because `_artifact_node` no-ops on non-`approved`). The explicit `finished_at` on the rejected branch is required because `_update_run_status_sync` only auto-stamps `{completed, failed}` (confirmed by reading `storage.py:357-359`). |
| 5 | Cost tracker reseeded from the stored cost so `--budget` caps carry across `run` + `resume` | ✅ | `test_resume_reseeds_cost_tracker_from_runs_total_cost_usd` — `aiw run` pauses with `runs.total_cost_usd = 0.0033` (T04 cost-at-pause stamp). Resume path reads that value (`row["total_cost_usd"] or 0.0`), seeds the tracker via a synthetic `TokenUsage(cost_usd=stored_cost, model="<resumed>", tier="<resumed>")`, and wires `CostTrackingCallback(cost_tracker=tracker, budget_cap_usd=budget_cap_usd)` into the graph config. On completion, `tracker.total(run_id) == 0.0033` (no post-gate LLM calls to add to it), and the `completed` flip stamps that value back onto the row. Test asserts both the pre-resume pause-cost and post-resume completion-cost are `pytest.approx(0.0033)` — if the reseed were missing, completion would stamp `0.0` and the test would fail. (See deviation 1 above re: cap-trip-on-resume is functionally equivalent given the planner graph's shape.) |
| 6 | `uv run pytest tests/cli/test_resume.py` green; `uv run lint-imports` 3 / 3 kept | ✅ | `tests/cli/test_resume.py`: 7 passed in 1.94s (package-local run). Full suite: 289 passed in 6.01s (up from T04's 282). `uv run lint-imports`: 3 contracts kept, 0 broken. `uv run ruff check`: all checks passed. |

## Additions beyond spec — audited and justified

- **Shared `_build_cfg(run_id, workflow, tier_registry, callback, storage)` helper.** Task spec §2.4 says "build the same config shape as T04" — extracting the shared builder pins the field set and eliminates drift between `_run_async` and `_resume_async`. Zero public-surface change; internal-only. Both callers pass `thread_id=run_id` per KDR-009's checkpointer-thread-matches-run-id convention.
- **Cost-at-pause stamp in `_emit_final_state` (T04 extension).** See deviation 3 above. Required by AC-5 to make the reseed testable; minimal scope (one `await` before the existing `typer.echo` block); does not alter the T04 stdout contract.
- **`_emit_final_state` signature change — now async, takes `storage: SQLiteStorage`.** Mechanical consequence of the cost-at-pause stamp. `_run_async` is the only caller and already holds the storage handle. T04's 8 tests pass unchanged.
- **Explicit `finished_at = datetime.now(UTC).isoformat()` on the rejected branch.** `_update_run_status_sync` auto-stamps `finished_at` only for `{completed, failed}`. `gate_rejected` is a separate terminal state that needs an explicit stamp. The UTC-aware timestamp matches Storage's `_utcnow()` convention (`storage.py:_utcnow`). No primitives-layer change.
- **Synthetic `TokenUsage(model="<resumed>", tier="<resumed>")` for the reseed.** The angle-bracket sentinels are unambiguous placeholders that will not collide with a real model/tier name (`LiteLLMRoute.model` is `gemini/…`; tier names are `planner-*` / `local_coder` / etc.). Reporting rollups that group by model or tier will surface a single `<resumed>` bucket — informational, not misleading. Alternative (zero-cost-usd rows) would misreport aggregate spend; this keeps `tracker.total()` honest.
- **Fallback response read from `final.get("gate_plan_review_response", gate_response)` in `_emit_resume_final`.** `HumanGate.strict_review=True` writes the response to state via `gate_<id>_response`, so the state-recorded value is the authoritative source. The CLI-argument fallback covers the theoretical edge case where the gate errored before its post-interrupt block ran (e.g. a graph-wide NonRetryable). Defensive — does not mask bugs (the fallback surfaces the same value the user passed), and keeps the rejection branch working if LangGraph internals ever change the interrupt payload shape.

## 🔴 HIGH

None.

## 🟡 MEDIUM

None.

## 🟢 LOW

None.

## Gate summary

| Gate | Result | Notes |
| --- | --- | --- |
| `uv run pytest tests/cli/test_resume.py` | ✅ 7 passed | 1.94s package-local. |
| `uv run pytest` (full suite) | ✅ 289 passed | +7 from T04's 282 baseline; no regressions. |
| `uv run pytest tests/cli/test_run.py` | ✅ 8 passed | T04 suite re-verified green against the `_emit_final_state` async signature change. |
| `uv run lint-imports` | ✅ 3 kept, 0 broken | `primitives → graph → workflows → surfaces` intact. |
| `uv run ruff check` | ✅ clean | No violations. |
| KDR-003 source-grep (`cli.py`) | ✅ | T04's `test_cli_module_does_not_read_provider_secrets` still green after T05's new imports; no `GEMINI_API_KEY` / `ANTHROPIC_API_KEY` / `import anthropic` / `from anthropic` present. |

## Issue log — cross-task follow-up

None open. The planner-specific absence of a post-gate LLM call means AC-5's "cap trip on resume" path is not exercised end-to-end today. This is not a T05 issue (the reseed itself is proven); noting it here as a **forward-looking flag**, not a DEFERRED action: *if and when M5 adds a workflow with a post-gate LLM call, that milestone's CLI-level test should include a cap-trip-on-resume case*. Recorded in `design_docs/nice_to_have.md` consideration: no — this is not a deferred simplification, it is a future AC boundary that will naturally land with the first post-gate LLM workflow. No cross-task propagation required at this time.

## Additions beyond spec — forward compatibility

None of the additions above constitute new public surface. `_build_cfg` / `_emit_resume_final` / `_emit_final_state` are all module-private. No new primitives-layer methods. No new `graph/*` helpers. No changes to `pyproject.toml`.

## Deferred to `nice_to_have.md`

None. No findings map to existing `nice_to_have.md` items.

## Propagation status

No forward-deferrals from this audit. The planner-post-gate-LLM flag above is a future-milestone consideration with no concrete target task today; it will land naturally when the first such workflow is specced. No carry-over sections to append to sibling tasks.

T06 (`aiw list-runs` / `aiw cost-report`) will reuse `_build_cfg` and the `CostTracker` seed pattern; already available in `cli.py`. No spec changes needed.
