---
name: ai-workflows
description: Invoke ai-workflows planner / slice_refactor workflows through the MCP server (primary) or the aiw CLI (fallback). Use when the user asks for a plan from a goal, or to refactor a slice of code across parallel branches.
allowed-tools: Bash
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
  "plan": {"goal": "...", "steps": [{"index": 1, "title": "...", "...": "..."}]},
  "total_cost_usd": 0.0012,
  "error": null,
  "gate_context": {
    "gate_prompt": "Approve plan for: 'Write a release checklist'? 4 steps.",
    "gate_id": "plan_review",
    "workflow_id": "planner",
    "checkpoint_ts": "2026-04-22T14:03:11.240515+00:00"
  }
}
```

Read the `plan` and `gate_context.gate_prompt` from the response.
Surface the **plan body** to the user verbatim, quote the gate
prompt, and ask for `approved` or `rejected`. Pass their choice as
`gate_response` to `resume_run`.

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

- **Cascade fixture layout** (M12 T06) — when capturing fixtures from a
  cascade-enabled run (`AIW_CAPTURE_EVALS=<dataset>` + cascade env-var
  flipped on), authors land under `evals/<dataset>/<workflow>/<cascade_name>_primary/`
  and auditors under `<cascade_name>_auditor/`. See `evals/README.md` for
  the full convention (planner: `<cascade_name>=planner_explorer_audit`;
  slice_refactor: `<cascade_name>=slice_worker_audit`).

### `run_audit_cascade(run_id_ref?, artefact_kind?, inline_artefact_ref?, tier_ceiling?)`

Audit a completed run's artefact (or an inline dict you pass directly) via an `auditor-{sonnet,opus}` tier. Useful for:

- **Spot-checking a plan** before committing to executing it.
- **Auditing a draft artefact** without kicking off a full workflow run.
- **Confidence-checking an artefact** from a completed run when you want a higher-tier opinion than the run's own cascade produced.

Exactly one of `run_id_ref` / `inline_artefact_ref` must be set. When `run_id_ref` is set, `artefact_kind` is also required (caller picks the kind — planner uses `"plan"`, slice_refactor uses `"applied_artifacts"`; external workflows declare their own kinds in their workflow code per KDR-013). `tier_ceiling` defaults to `"opus"` (highest auditor tier — Max flat-rate $0). Use `"sonnet"` for cheaper audits when the artefact is short or pre-vetted.

Returns `{passed, verdicts_by_tier, suggested_approach, total_cost_usd, by_role}`. On `passed=False`, surface the `suggested_approach` to the user verbatim — that's the auditor's recommendation. Standalone audit is single-pass (no retry, no HumanGate); the verdict comes back in the function return.

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
