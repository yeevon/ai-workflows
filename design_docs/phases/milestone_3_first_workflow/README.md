# Milestone 3 — First Workflow: test_coverage_gap_fill

## Goal

Port Pipeline 1 to use the components built in Milestones 1 and 2. This is the forcing function — real use will reveal what the component APIs actually need to be. Expect to refactor Worker, Validator, and Fanout here. That's the point.

**Exit criteria:** `aiw run test_coverage_gap_fill --repo /path/to/repo --slice AuthModule` produces characterization tests for the target slice, with cost logged and visible in `aiw inspect`.

## Scope

- Workflow YAML loader + Pydantic validation (used by all future workflows)
- `aiw run` command (full implementation)
- `test_coverage_gap_fill` workflow: YAML, prompts, run.py

## Key Decisions In Effect

| Decision | Value |
|---|---|
| YAML loader | `pyyaml` + Pydantic validation |
| `flow:` precedence | `flow:` = top-level sequence; `after:`/`before:` = within-component deps; DAG merge at load |
| Workflow YAML snapshot | Copied into `runs/<run_id>/` at run start |
| `run.py` thickness | CLI arg parsing only — no workflow-specific pre/post logic |
| Tool registration | `custom_tools.py` auto-discovered and imported at workflow load |

## Task Order

1. `task_01_workflow_loader.md` — build this first; all future workflows depend on it
2. `task_02_aiw_run.md` — wire the CLI to the loader and runner
3. `task_03_test_coverage_gap_fill.md` — the workflow itself

## What to Expect

The workflow will reveal friction in the component APIs. Common findings from first-workflow integration:
- Prompt variable names don't match what the template expects → fix `render_prompt()` contract
- Worker output schema is too strict for what the LLM produces → loosen or add retry
- Fanout failure messages aren't specific enough to act on → improve `failure_reason` content
- Cost tracking misses some calls → verify every `generate()` is tagged

Document all API changes in the component tasks from Milestone 2 as amendments. Don't paper over friction — fix it at the source.
