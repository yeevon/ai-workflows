# Milestone 7 — Eval Harness

**Status:** 📝 Planned. Starts once [M6](../milestone_6_slice_refactor/README.md) closes clean.
**Grounding:** [architecture.md §4.3 / §10](../../architecture.md) · [analysis/langgraph_mcp_pivot.md §E](../../analysis/langgraph_mcp_pivot.md) · [roadmap.md](../../roadmap.md).

## Goal

Build the prompt-regression guard promised by KDR-004 ("prompting is a contract"). Capture input/expected pairs from real runs, replay them against the current graph, and surface regressions in CI. Fulfils the concern flagged in the pivot analysis §E.

## Exit criteria

1. A versioned eval dataset schema (pydantic) stored under `evals/` per workflow.
2. `aiw eval capture <run_id>` snapshots a real run into the dataset.
3. `aiw eval run <workflow>` replays the dataset against the current graph and reports pass/fail per case.
4. CI step runs a smoke-sized eval subset on every PR that touches `workflows/` or `graph/`.
5. Gates green.

## Non-goals

- LLM-as-judge scoring (out of scope; deferred to a later milestone).
- Langfuse integration — see [nice_to_have.md §1](../../nice_to_have.md).

## Key decisions in effect

| Decision | Reference |
| --- | --- |
| Prompting is a contract | KDR-004 |
| Schema-first contracts | [architecture.md §7](../../architecture.md) |

## Task order

| # | Task |
| --- | --- |
| 01 | Eval dataset schema (`EvalCase`, `EvalSuite` pydantic models) |
| 02 | Capture helper: real run → dataset entry |
| 03 | Replay runner: dataset + graph → pass/fail report |
| 04 | CLI `aiw eval capture` + `aiw eval run` |
| 05 | CI hookup (GitHub Actions step or equivalent) |
| 06 | Milestone close-out |

Per-task files generated once M6 closes.

## Issues

Land under [issues/](issues/).
