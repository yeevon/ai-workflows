# Milestone 7 — Eval Harness

**Status:** 📝 Planned. Starts after [M6](../milestone_6_slice_refactor/README.md) close-out (2026-04-20).
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

## Issues

Per-task audit files land under [issues/](issues/) after each task's first audit.
