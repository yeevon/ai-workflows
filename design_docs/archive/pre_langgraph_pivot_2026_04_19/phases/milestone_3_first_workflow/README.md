# Milestone 3 — First Workflow + Evals + Observability

## Goal

Port Pipeline 1 using `Pipeline` + Worker + Validator + Fanout from M2. Add `pydantic-evals`-based evaluation harness alongside the first workflow. Wire OTel observability via logfire.

**Exit criteria:** `aiw run test_coverage_gap_fill --repo /path --slice Auth` produces characterization tests. `aiw eval test_coverage_gap_fill` runs 10 cases against known-good outputs and reports pass/fail. `aiw inspect --task <task_id>` shows full prompt+output for debugging.

## Scope Changes from Original M3

- **Cloud-default workflow** — test_coverage_gap_fill uses Haiku for exploration and generation. Ollama wiring deferred to M4.
- **Added `pydantic-evals` harness** — the single biggest unforced error in the original plan was no evals layer. `Case`, `Dataset`, `LLMJudge`, `aiw eval` command.
- **Added OTel via logfire** — `logfire.instrument_anthropic()` + `logfire.instrument_openai()` in one place; every LLM call emits OTel GenAI spans automatically.
- **Added debug commands** — `aiw inspect --task`, `aiw rerun-task` for prompt iteration.

## Key Decisions In Effect

| Decision | Value |
| --- | --- |
| YAML loader | `pyyaml` + Pydantic validation |
| Workflow dir hash | Computed + stored in SQLite at run start (CRIT-02) |
| Step data flow | Typed outputs referenced via `input_from:` in YAML (CRIT-01) |
| Type checking | At workflow load time — reject plans where step inputs/outputs don't match |
| Default tier for exploration | `haiku` (not `local_coder` — Ollama deferred) |
| Evals | `pydantic-evals` alongside workflow dir |
| Observability | `logfire.instrument_*()` wires OTel GenAI spans |
| Prompt iteration | `aiw rerun-task` replays a single step with current prompts |

## Task Order

1. `task_01_workflow_loader.md` — YAML loader with type-checking across step boundaries
2. `task_02_aiw_run.md` — full `aiw run` command
3. `task_03_test_coverage_gap_fill.md` — the workflow
4. `task_04_evals_layer.md` — NEW — `pydantic-evals` integration + `aiw eval`
5. `task_05_otel_observability.md` — NEW — `logfire.instrument_*()` wiring
6. `task_06_debug_commands.md` — NEW — `aiw inspect --task`, `aiw rerun-task`

## What to Expect (Forcing Function)

This is where component APIs get tightened. Expect to:

- Loosen or tighten some Pydantic schemas after the first LLM hits them
- Improve `failure_reason` content after the first real mitigation cycle
- Add `max_output_chars` defaults after context runs hot
- Discover missing pieces (a tool you didn't plan for, a step that needs checkpointing)

Document all revisions to M1/M2 in the original task files as amendments.
