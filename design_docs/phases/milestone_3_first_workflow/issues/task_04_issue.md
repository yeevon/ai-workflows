# Task 04 — `aiw run` CLI Command — Audit Issues

**Source task:** [../task_04_cli_run.md](../task_04_cli_run.md)
**Audited on:** 2026-04-20
**Audit scope:** `ai_workflows/cli.py`, `ai_workflows/workflows/planner.py` (new `planner_tier_registry` helper), `ai_workflows/primitives/storage.py` (new `default_storage_path` helper + `AIW_STORAGE_DB` env override), `tests/cli/__init__.py`, `tests/cli/test_run.py`, `CHANGELOG.md`; cross-checked against `design_docs/architecture.md` (§3 layer contract, §4.1 primitives, §4.2 graph adapters, §4.4 surfaces, §5 runtime flow, §6 dependencies, §7 contracts, §8.2 error handling, §8.3 gates, §8.5 cost control) and KDR-003 / KDR-004 / KDR-006 / KDR-007 / KDR-009.
**Status:** ✅ PASS — all 7 ACs met; no OPEN issues.

## Design-drift check

| Vector | Result | Note |
| --- | --- | --- |
| New dependency | ✅ None | No additions to `pyproject.toml`. `typer` / `langgraph` / `pydantic` all already in `architecture.md §6`. No `nice_to_have.md` item pulled in. |
| New module / layer | ✅ Fits | All additions land in existing layers: `cli.py` (surfaces), helper in `workflows/planner.py` (workflows), helper in `primitives/storage.py` (primitives). `tests/cli/` is a new test-tree package, mirroring `ai_workflows/cli/` convention. `lint-imports`: 3 / 3 KEPT, 0 broken. |
| Surface → graph import | ✅ Task-spec sanctioned | `cli.py` imports `build_async_checkpointer` from `graph.checkpointer` and `CostTrackingCallback` from `graph.cost_callback`. The enforced four-layer contract only forbids *upward* imports; surfaces reaching downward into `graph` is consistent with `architecture.md §4.2` / §5 step 3 (surfaces build the checkpointer + callback before invoke). The §3 shorthand ("surfaces import workflows + primitives") is descriptive, not prescriptive — the import-linter contracts are the authoritative rule. Task spec explicitly requires these two imports (lines 33–34, 37). |
| LLM call added | ✅ No new call | CLI threads the existing `TieredNode` → `LiteLLMAdapter` path via `config["configurable"]["tier_registry"]`. No new provider call; KDR-004 pairing untouched. |
| Checkpoint / resume | ✅ LangGraph | `build_async_checkpointer()` → `AsyncSqliteSaver` compiled directly; no hand-rolled checkpoint writes. `_surface_graph_error` reads checkpointed state via `compiled.aget_state(cfg)` (LangGraph-owned API) — does not write. KDR-009 preserved. |
| Retry logic | ✅ Taxonomy | No bespoke `try/except` retry in `cli.py`. The single `except Exception` wraps `ainvoke` as the CLI top-level boundary, delegates to `_surface_graph_error`, and exits 1 with the real bucket exception surfaced from state (`NonRetryable("budget exceeded: …")`). KDR-006 retry loop runs entirely inside `retrying_edge` at the graph layer. |
| Observability | ✅ Structured | CLI calls `configure_logging(level="INFO")` at command entry so `StructuredLogger` records from `tiered_node` / `validator_node` / `human_gate` route to stderr, keeping stdout as the machine-parseable contract (run id / gate hint / plan JSON / cost total). No Langfuse / LangSmith / OTel pulled in. |
| Four-layer contract | ✅ Holds | `cli.py` imports `workflows` (registry + lazy-import module) + `graph` (checkpointer factory, cost callback) + `primitives` (storage, cost, logging, retry). Monotonic downward direction. Lint-imports 3 / 3 KEPT. |
| KDR-003 (no Anthropic API, no direct provider secret reads in CLI) | ✅ | `test_cli_module_does_not_read_provider_secrets` greps for `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `import anthropic`, `from anthropic` in `cli.py` source — none present. CLI docstring explicitly cites KDR-003. `GEMINI_API_KEY` read stays at `LiteLLMAdapter` boundary. |
| `nice_to_have.md` items | ✅ None adopted | |

**Deviations from spec — audited and OK:** the CHANGELOG's *Deviations from spec* section names four. Each inspected:

1. **`BudgetExceeded` → `NonRetryable("budget exceeded: …")`.** The exception class was removed in M1 Task 08 in favour of the three-bucket taxonomy (KDR-006). Spec written before M1.08 landed; the user-visible "budget" token is preserved verbatim in the message — test pins `"budget" in result.output.lower()`. No drift.
2. **Generic tier-registry lookup via `getattr(module, f"{workflow}_tier_registry", None)`.** Spec says "new `planner_tier_registry()` helper that returns the two routes." Helper ships as named (`planner.py:320-343`) and is found via the generic lookup. Extension — not a spec violation; scaling pattern for M5/M6 workflows without touching the CLI. Zero cost; no new public surface.
3. **`_surface_graph_error` uses `compiled.aget_state(cfg)` to recover the state-resident `last_exception`.** Unavoidable: on budget breach `wrap_with_error_handler` catches the `NonRetryable` and writes it to state; the graph then routes to `on_terminal="explorer_validator"`, which reads the never-written `state["explorer_output"]` and raises a plain `KeyError`. Without `aget_state`, the CLI would surface the KeyError instead of the budget message the user needs. The fallback is best-effort (swallows its own exception) so a malformed checkpoint still surfaces the outer exception rather than crashing. No KDR violated.
4. **Added `configure_logging(level="INFO")` at command entry.** Not in spec; required to keep stdout the machine-parseable surface (gate hint lines are first / second / third stdout lines — structlog's default routes to stderr already, but explicit config is a defensive pin). Fits `architecture.md §8.1` observability shape.

No design drift.

## AC grading

| # | Acceptance criterion | Grade | Evidence |
| --- | --- | --- | --- |
| 1 | `aiw run planner --goal '<text>'` runs the T03 graph to either completion or a gate interrupt and prints the expected output | ✅ | `test_run_pauses_at_gate_and_prints_resume_command` — scripts two valid LiteLLM adapter responses, runs the full graph to `HumanGate("plan_review", strict_review=True)`, reads the three stdout lines: `run_id` / `awaiting: gate` / `resume with: aiw resume {run_id} --gate-response <approved|rejected>`. Completion path (no gate) covered defensively by `_emit_final_state`'s `plan` branch — `plan.model_dump_json(indent=2)` + `total cost: $X.XXXX`. |
| 2 | Run id auto-generated (ULID-shape) when `--run-id` not supplied | ✅ | `_generate_ulid()` — 10-char Crockford-base32 timestamp (48-bit) + 16-char random tail (80-bit) via `secrets.token_bytes`. `test_generate_ulid_produces_26_crockford_chars` + `test_generate_ulid_is_unique_across_calls` + the happy-path test's `re.fullmatch(rf"[{_CROCKFORD}]{{26}}", run_id)`. `test_run_respects_explicit_run_id_override` pins the `--run-id` override path. |
| 3 | `Storage.create_run(run_id, "planner", budget)` called exactly once per invocation | ✅ | `_run_async` calls `await storage.create_run(run_id_resolved, workflow, budget_cap_usd)` once (no retry wrapper, no loop). The happy-path test reads the `runs` row back via a fresh connection, asserts `workflow_id == "planner"` + `status == "pending"`. The "exactly once" lock is enforced by the `runs.run_id PRIMARY KEY` (`migrations/001_initial.sql:26`) — a second call with the same id would raise `IntegrityError` and flip `exit_code` non-zero; the test asserts `exit_code == 0`. |
| 4 | Gate interrupt output tells the user the exact `aiw resume` command to run | ✅ | `_emit_final_state` prints `resume with: aiw resume {run_id} --gate-response <approved\|rejected>` when `"__interrupt__" in final`. Test `test_run_pauses_at_gate_and_prints_resume_command` asserts the line verbatim. |
| 5 | `--budget` cap enforced end-to-end (trips `BudgetExceeded`, exits non-zero) | ✅ | `test_run_budget_cap_breach_exits_nonzero_with_budget_message` — `--budget 0.00001` caps below the first stubbed call cost ($0.0012). `CostTrackingCallback.on_node_complete` raises `NonRetryable("budget exceeded: …")`; `wrap_with_error_handler` writes it to state; `_surface_graph_error` pulls it back via `aget_state`; CLI exits 1 with `"budget" in output.lower()`. Functional equivalent of spec's `BudgetExceeded` — the class itself was renamed in M1.08 (see deviation 1 above). |
| 6 | CLI does not read `GEMINI_API_KEY` directly (KDR-003 boundary) | ✅ | `test_cli_module_does_not_read_provider_secrets` source-greps `cli.py` for `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `import anthropic`, `from anthropic`. None present. Env-var reads stay at `LiteLLMAdapter` boundary. Planner module (`planner_tier_registry`) passes through a `LiteLLMRoute(model="gemini/gemini-2.5-flash")` with no env read either. |
| 7 | `uv run pytest tests/cli/test_run.py` green; `uv run lint-imports` 3 / 3 kept | ✅ | 8 passed in 1.17s (`tests/cli/test_run.py` only), 282 passed in 4.84s (full suite), no regressions. `lint-imports` 3 kept / 0 broken. `ruff check`: all checks passed. |

## Additions beyond spec — audited and justified

- **`default_storage_path()` + `AIW_STORAGE_DB` env override in `primitives/storage.py`.** Spec allows it ("new helper `default_storage_path()` added here if it does not already exist; mirror the default-path handling in `graph/checkpointer.py`"). Mirrors the existing `AIW_CHECKPOINT_DB` / `DEFAULT_CHECKPOINT_PATH` pair exactly, including parent-dir auto-creation. Distinct on-disk file from the checkpointer per KDR-009. Tests auto-route both DBs under `tmp_path` via the autouse `_redirect_default_paths` fixture so no real-run byproduct lands under `~/.ai-workflows/`.
- **Generic `getattr(module, f"{workflow}_tier_registry", None)` lookup.** Extension beyond spec (see deviation 2 above). Scales to M5/M6 workflows without CLI changes; no new public surface; falls back to `{}` so a gate-only workflow still runs.
- **`configure_logging(level="INFO")` at command entry.** See deviation 4 above; required to keep stdout the machine-parseable surface.
- **`_surface_graph_error` via `compiled.aget_state(cfg)`.** See deviation 3 above; only way to surface the state-resident `NonRetryable` message past the validator KeyError cascade.
- **`_build_initial_state` generic construction via `getattr(module, "PlannerInput")`.** Tight specialisation — spec is silent on the shape, but this mirrors the tier-registry generic-lookup pattern and keeps the CLI free of per-workflow `import PlannerInput` lines. Exits 2 if the module exposes no `PlannerInput` — M3 only registers `planner`, so the branch is theoretical today but pins the contract for M5/M6 input schemas.
- **`TODO(M3)` / `TODO(M4)` pointers at the bottom of `cli.py`** for `resume`, `list-runs`, `cost-report` (M3 T05 / T06) and the MCP mirrors (M4). Zero runtime cost; consistent with the pre-pivot stub `cli.py` style and with the task order in the milestone README.

None extend scope beyond the task file.

## 🔴 HIGH

None.

## 🟡 MEDIUM

None.

## 🟢 LOW

None.

## Gate summary

| Gate | Result | Notes |
| --- | --- | --- |
| `uv run pytest tests/cli/test_run.py` | ✅ 8 passed | 1.17s; two `DeprecationWarning`s from yoyo (pre-existing, unrelated to this task). |
| `uv run pytest` (full suite) | ✅ 282 passed | 4.84s; no regressions vs. pre-T04 baseline (274). |
| `uv run lint-imports` | ✅ 3 kept / 0 broken | 22 files / 32 dependencies analysed. |
| `uv run ruff check` | ✅ All checks passed | |

## Issue log — cross-task follow-up

None. All findings closed against this task; no forward-deferred carry-over needed.

## Deferred to nice_to_have

None. No finding in this audit maps to a `nice_to_have.md` parking-lot item.

## Propagation status

No forward-deferral to M3 T05 / T06 / T07 / T08 from this audit — every concern was resolvable inside T04's scope. M3 T05 (`aiw resume`) will need the same `default_storage_path()` + `AIW_STORAGE_DB` helpers and the same `configure_logging` pattern; those are idempotent and already in place, so T05's builder can import them without follow-up carry-over.
