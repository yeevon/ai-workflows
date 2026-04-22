---
name: ai-workflows
description: Invoke ai-workflows planner / slice_refactor workflows through the MCP server (primary) or the aiw CLI (fallback). Use when the user asks for a plan from a goal, or to refactor a slice of code across parallel branches.
---

# ai-workflows

Packaging-only skill (KDR-002). All orchestration lives in
`ai_workflows.workflows.*`; this file is a recipe card that routes
invocations to the already-registered MCP server or the `aiw` CLI.

## When to use

- The user asks for a plan from a goal (e.g. "draft a plan for
  adding rate limiting", "plan the auth migration") →
  `run_workflow` with `workflow_id="planner"`.
- The user asks to refactor a code slice across multiple files in
  parallel (e.g. "rename X across these packages", "migrate these
  modules to the new API") → `run_workflow` with
  `workflow_id="slice_refactor"`.
- The user asks for the status or cost of prior runs →
  `list_runs`.
- A run is paused at a gate and the user approves or rejects →
  `resume_run`.
- The user cancels a pending run → `cancel_run`.

## Primary surface — MCP

The `ai-workflows` MCP server is registered via `claude mcp add`
(see `design_docs/phases/milestone_4_mcp/mcp_setup.md`). Four
tools are exposed:

### `run_workflow(workflow_id, inputs, budget_cap_usd?, run_id?, tier_overrides?)`

```json
{
  "workflow_id": "planner",
  "inputs": {"goal": "Write a release checklist"},
  "budget_cap_usd": 0.50
}
```

Response when the run pauses at a `HumanGate`:

```json
{
  "run_id": "<ulid>",
  "status": "pending",
  "awaiting": "gate",
  "plan": null,
  "total_cost_usd": 0.0012,
  "error": null
}
```

Surface the pending status to the user and ask how to resume.

### `resume_run(run_id, gate_response)`

```json
{"run_id": "<ulid>", "gate_response": "approved"}
```

`gate_response` is `"approved"` or `"rejected"`. On `"approved"`
the workflow continues to its terminal artifact; on `"rejected"`
the run ends in `status="gate_rejected"`.

### `list_runs(workflow?, status?, limit?)`

```json
{"workflow": "planner", "status": "completed", "limit": 20}
```

Returns newest-first `RunSummary` rows with `total_cost_usd` per
row. This is the single cost surface the MCP server exposes.

### `cancel_run(run_id)`

```json
{"run_id": "<ulid>"}
```

Returns `status="cancelled"` if the row was pending, or
`status="already_terminal"` if the run had already finished.

## Fallback surface — `aiw` CLI

Use only if the MCP server is not registered in the current host.

- `uv run aiw run <workflow> --goal '<goal>' [--budget-cap-usd N] [--run-id ID]`
- `uv run aiw resume <run_id> [--gate-response approved|rejected]`
- `uv run aiw list-runs [--workflow W] [--status S] [--limit N]`

## Gate pauses

- The `planner` workflow pauses once at the plan-review
  `HumanGate`.
- `slice_refactor` pauses at the strict-review gate before
  applying slice outputs.
- The Ollama fallback gate (M8) may also fire mid-run when the
  Qwen/Ollama tier's circuit breaker trips. The signal is the
  `run_workflow` (or `resume_run`) response itself: `status="pending"`
  + `awaiting="gate"`, same shape as the regular plan-review pause.
  `list_runs` will show the row as `status="pending"` but does *not*
  project the failing-tier detail — the reason
  (`_ollama_fallback_reason`, `_ollama_fallback_count`) lives in the
  LangGraph checkpointer state, not in the `runs` registry. Resuming
  with `"approved"` triggers the configured fallback tier; resuming
  with `"rejected"` aborts. Note: a RETRY-equivalent resume requires
  waiting at least the circuit breaker's `cooldown_s` before
  resuming — resuming sooner re-trips the gate immediately because
  the breaker is still OPEN.

## What this skill does NOT do

- **No orchestration logic.** All branching, retries, and
  validator wiring live in `ai_workflows.workflows.*`. This
  skill only routes invocations.
- **No direct LLM calls.** The skill never reads provider API
  keys; the MCP subprocess inherits them from its parent
  environment at `claude mcp add` time.
- **No Anthropic API.** KDR-003 — Claude access is OAuth-only
  via the `claude` CLI subprocess inside the `planner-synth`
  tier. Never instruct the host to set any
  key that targets the Anthropic public HTTP API.
