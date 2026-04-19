# Milestone 6 — `slice_refactor` DAG

**Status:** 📝 Planned. Starts once [M5](../milestone_5_multitier_planner/README.md) closes clean.
**Grounding:** [architecture.md §4.3](../../architecture.md) · [roadmap.md](../../roadmap.md).

## Goal

Ship the canonical use-case workflow: `planner` sub-graph → parallel per-slice workers → per-slice validator → aggregate → strict-review `HumanGate` → apply. Proves LangGraph parallelism, strict-review semantics, and the full artefact lifecycle.

## Exit criteria

1. `ai_workflows.workflows.slice_refactor` exports a `StateGraph` with the shape above.
2. Per-slice worker fan-out runs bounded by the per-provider semaphore from `TierConfig` ([architecture.md §8.6](../../architecture.md)).
3. Strict-review gate holds the run indefinitely; only `aiw resume --gate-response approve|reject` clears it.
4. Double-failure hard-stop works: two distinct per-slice failures abort the run regardless of sibling independence ([architecture.md §8.2](../../architecture.md)).
5. Apply node writes artefacts to `Storage` and the run is marked complete.
6. End-to-end smoke test on a fixture slice list.
7. Gates green.

## Non-goals

- Applying artefacts to a real repo via subprocess (post-M6; treat the `apply` node as writing to `Storage` only here).
- Advanced concurrency tuning beyond the existing `TierConfig` semaphore.

## Key decisions in effect

| Decision | Reference |
| --- | --- |
| Validator after every LLM node | KDR-004 |
| 3-bucket retry taxonomy, graph-level routing | KDR-006 |
| Double-failure hard-stop | [architecture.md §8.2](../../architecture.md) |
| Strict-review no-timeout | [architecture.md §8.3](../../architecture.md) |

## Task order

| # | Task |
| --- | --- |
| 01 | Slice-discovery phase (reuses `planner` sub-graph output as slice list) |
| 02 | Parallel slice-worker node pattern (fan-out + merge) |
| 03 | Per-slice validator wiring |
| 04 | Aggregator node |
| 05 | Strict-review `HumanGate` wiring |
| 06 | `apply` node (writes artefacts to `Storage`) |
| 07 | Concurrency semaphore wiring + double-failure hard-stop test |
| 08 | End-to-end smoke test on fixture slice list |
| 09 | Milestone close-out |

Per-task files generated once M5 closes.

## Issues

Land under [issues/](issues/).
