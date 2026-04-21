# Milestone 7 — Eval Harness

**Status:** ✅ Complete (2026-04-21).
**Grounding:** [architecture.md §4 / §7 / §10](../../architecture.md) · [analysis/langgraph_mcp_pivot.md §E](../../analysis/langgraph_mcp_pivot.md) · [roadmap.md](../../roadmap.md).

## Goal

Build the prompt-regression guard promised by **KDR-004** ("prompting is a contract"). Capture input + expected output pairs from real workflow runs, commit them as JSON fixtures under `evals/`, and replay them against the current graph on every PR. Catch the failure modes determinism does not: prompt-template drift, validator-schema drift, tier-wiring drift, provider-output drift.

Two replay modes:

- **Deterministic** (default, runs on every PR): stub adapter returns the captured output verbatim; the run exercises prompt-template rendering, `ValidatorNode` schema parsing, and graph-wiring. Fails if any contract downstream of the model's raw output regressed.
- **Live** (opt-in via `AIW_EVAL_LIVE=1`, manual or nightly): re-fires the captured inputs against the real provider and compares the fresh output against the pinned expected output with a per-case tolerance. Fails if model-side behaviour drifted.

## Exit criteria

1. `ai_workflows.evals` package exports `EvalCase`, `EvalSuite`, `EvalRunner`, `CaptureCallback` — layer-discipline kept (`evals` imports `graph` + `primitives` only; not imported *by* `graph` / `workflows`; import-linter contract updated).
2. `aiw eval capture --run-id <run_id> --dataset <name>` snapshots every LLM-node input+output from a completed `runs.status=completed` row into `evals/<workflow>/<node>/<case_id>.json` fixtures.
3. `aiw eval run <workflow> [--live]` replays the dataset against the current graph; deterministic-mode always available, live-mode gated by `AIW_EVAL_LIVE=1` or `--live` flag with prerequisite check.
4. CI job runs the deterministic replay on every PR that touches `ai_workflows/workflows/**`, `ai_workflows/graph/**`, or `evals/**`; fails the PR on any case regression.
5. Seed fixtures committed for both shipped workflows: `planner` (≥2 cases covering explorer + synth nodes) and `slice_refactor` (≥1 case covering the slice_worker node; optionally a full-trajectory case).
6. `uv run pytest && uv run lint-imports && uv run ruff check` green.

## Non-goals

- **LLM-as-judge scoring.** Deferred to a future milestone (or a `nice_to_have.md` entry if the need becomes real).
- **Semantic similarity beyond schema-exact + substring matching.** Live-mode comparison uses strict JSON equality on `output_schema`-bound fields plus per-field regex/substring tolerance; fuzzy embedding comparisons are out.
- **Langfuse / LangSmith integration.** See [nice_to_have.md §1](../../nice_to_have.md) + [§3](../../nice_to_have.md). M7 is deliberately a **native pytest + JSON fixtures** harness so the adoption bar for Langfuse stays at its stated trigger (prompt-regression incident that log inspection could not diagnose).
- **Prompt versioning / diffing UI.** Git diff over `evals/` fixtures serves as the audit trail.
- **Cross-run eval aggregation / dashboards.** Out of scope.

## Key decisions in effect

| Decision | Reference |
| --- | --- |
| Prompting is a contract | KDR-004 |
| Schema-first contracts | [architecture.md §7](../../architecture.md) |
| Bare-typed response_format schemas | KDR-010 / [ADR-0002](../../adr/0002_bare_typed_response_format_schemas.md) |
| Native pytest harness, not Langfuse | [nice_to_have.md §1](../../nice_to_have.md) trigger guard |
| Validator after every LLM node | KDR-004 |

## Task order

| # | Task |
| --- | --- |
| 01 | Eval dataset schema + storage layout (`EvalCase`, `EvalSuite`, JSON fixture convention) |
| 02 | Capture helper (`CaptureCallback` — production graph-layer callback emitting fixtures during live runs) |
| 03 | Replay runner (deterministic stub-adapter mode + gated live-mode) |
| 04 | CLI `aiw eval capture` + `aiw eval run` surface |
| 05 | CI hookup (`.github/workflows/ci.yml` + seed fixtures for `planner` + `slice_refactor`) |
| 06 | Milestone close-out |

Per-task spec files generated at M7 kickoff (2026-04-20).

## Scope boundary vs. future milestones

- **M8 Ollama infrastructure** will need eval coverage for the health-check + fallback-to-Gemini gate; those cases get captured under M8 T0x, not retrofitted into M7.
- **M9 Claude Code skill packaging** is packaging-only and does not introduce new LLM nodes; no eval work.
- **LLM-as-judge** and **embedding-based tolerance** are deferred; if ever promoted, require a new KDR + ADR per the amendment rule.

## Carry-over from prior milestones

None. M6 close-out audit (T09) verified zero forward-deferred items targeting M7.

## Outcome (2026-04-21)

The six-task M7 sweep landed the prompt-regression harness promised by KDR-004. Deterministic replay runs on every PR touching `ai_workflows/workflows/**`, `ai_workflows/graph/**`, or `evals/**`; live replay stays manual / close-out-only.

- **Schema substrate** ([task 01](task_01_dataset_schema.md), audited [issues/task_01_issue.md](issues/task_01_issue.md)) — `ai_workflows.evals` package exports `EvalCase`, `EvalSuite`, `EvalTolerance` as pydantic v2 bare-typed (KDR-010, `extra="forbid"`, `frozen=True`) models plus the on-disk JSON fixture helpers (`save_case` / `load_case` / `load_suite` / `fixture_path` / `default_evals_root`). Layout: `evals/<workflow>/<node>/<case_id>.json`. Fourth import-linter contract added (`evals cannot import surfaces`); the paired `graph → evals` prohibition is enforced by [`tests/evals/test_layer_contract.py`](../../../tests/evals/test_layer_contract.py).
- **Capture callback** ([task 02](task_02_capture_callback.md), audited [issues/task_02_issue.md](issues/task_02_issue.md)) — `CaptureCallback` in `ai_workflows/evals/capture_callback.py` emits one fixture per successful LLM-node call when `AIW_CAPTURE_EVALS=<dataset>` is set (or the explicit `capture_evals` kwarg is threaded). `TieredNode` fires it duck-typed after `CostTrackingCallback` via `config.configurable["eval_capture_callback"]`, keeping `graph` evals-unaware. Default path is byte-identical with the env var unset (verified by [`tests/workflows/test_dispatch_capture_opt_in.py`](../../../tests/workflows/test_dispatch_capture_opt_in.py)). Exceptions are logged + swallowed so capture cannot break a live run.
- **Replay runner** ([task 03](task_03_replay_runner.md), audited [issues/task_03_issue.md](issues/task_03_issue.md)) — `EvalRunner(mode="deterministic" | "live")` with hermetic `StubLLMAdapter` for deterministic mode and double-env-gated (`AIW_EVAL_LIVE=1` + `AIW_E2E=1`) live mode. Tolerance engine supports `strict_json` (schema-parsed equality + unified diff), `substring`, `regex`, and per-field `field_overrides`. Subgraph node resolution via `_resolve_node_scope` + `_node_exists_anywhere` (retrofit landed in T05 for `slice_refactor.slice_worker` which lives inside the `slice_branch` compiled sub-graph).
- **CLI surface** ([task 04](task_04_cli_surface.md), audited [issues/task_04_issue.md](issues/task_04_issue.md)) — `aiw eval capture --run-id <id> --dataset <name>` reconstructs fixtures from `AsyncSqliteSaver.aget(cfg).channel_values` on a completed run (zero provider calls). `aiw eval run <workflow> [--live] [--dataset …] [--fail-fast]` dispatches into `EvalRunner` and exits 0 all-pass / 1 any-fail / 2 on wiring errors. Per-workflow schema registry pattern (`<workflow_id>_eval_node_schemas()`) in both `planner` and `slice_refactor`.
- **CI wiring + seed fixtures** ([task 05](task_05_ci_hookup_seed_fixtures.md), audited [issues/task_05_issue.md](issues/task_05_issue.md)) — `eval-replay` job in [`.github/workflows/ci.yml`](../../../.github/workflows/ci.yml) gated by `dorny/paths-filter@v3` on `ai_workflows/workflows/**`, `ai_workflows/graph/**`, `evals/**`. Three seed fixtures committed: [`evals/planner/explorer/happy-path-01.json`](../../../evals/planner/explorer/happy-path-01.json), [`evals/planner/planner/happy-path-01.json`](../../../evals/planner/planner/happy-path-01.json), [`evals/slice_refactor/slice_worker/happy-path-01.json`](../../../evals/slice_refactor/slice_worker/happy-path-01.json). Captured from live runs `eval-seed-planner` + `eval-seed-slice2`. [`tests/evals/test_seed_fixtures_deterministic.py`](../../../tests/evals/test_seed_fixtures_deterministic.py) is always-on under `uv run pytest` (no env gate).
- **Capture-mechanism choice locked at T04:** `aiw eval capture` uses **checkpoint-channel reconstruction** (reads `AsyncSqliteSaver.aget(cfg).channel_values` on a completed run). Chosen over the re-run-with-`AIW_CAPTURE_EVALS` fallback because it is free, deterministic, and does not fire new provider calls — the reconstructed bytes are the bytes the run actually exchanged.
- **Close-out-time live replay baseline (2026-04-21):**
  - `AIW_E2E=1 AIW_EVAL_LIVE=1 uv run aiw eval run planner --live` → **0 passed, 2 failed**. Both failures are model-phrasing drift in the `summary` free-text field (e.g. expected `"This report outlines considerations and assumptions…"` / got `"This report outlines the considerations and assumptions…"`).
  - `AIW_E2E=1 AIW_EVAL_LIVE=1 uv run aiw eval run slice_refactor --live` → **0 passed, 1 failed**. Failure is model-phrasing + structural drift in the `diff` field (no tolerance override, so strict-JSON applies).
  - **Tolerance decision:** deferred to [nice_to_have.md §14](../../nice_to_have.md). Current substring-on-captured-full-sentence tolerance is too strict for live replay to be signal-producing; shortening substrings to distinctive keywords (`"release checklist"`, `"v1.2.0"`, `"def add"`) would fix it, but tolerance tuning without a forcing incident is premature. The deterministic CI gate (2/2 + 1/1 pass) is the load-bearing check; live mode remains a diagnostic ritual at close-out.
- **Green-gate snapshot:** `uv run pytest` → **538 passed, 4 skipped**. `uv run lint-imports` → **4 contracts kept, 0 broken** (the new `evals cannot import surfaces` contract sits alongside the three pre-existing layer contracts). `uv run ruff check` → **All checks passed**.

## Issues

Per-task audit files land under [issues/](issues/) after each task's first audit.
