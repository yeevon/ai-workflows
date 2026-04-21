# Manual Smoke — M5 Multi-Tier Planner via Claude Code

This walkthrough mirrors [milestone_4_mcp/mcp_setup.md](../milestone_4_mcp/mcp_setup.md) but focuses on the M5 multi-tier payload: a fresh Claude Code session calls `ai-workflows.run_workflow` against the upgraded planner (Qwen explorer → Claude Code Opus synth) and captures the round-trip that T07's close-out CHANGELOG cites.

Complements the automated e2e at [tests/e2e/test_planner_smoke.py](../../../tests/e2e/test_planner_smoke.py): that suite runs under `AIW_E2E=1 uv run pytest`; this doc is the **human-in-the-loop** verification that the same payload lands correctly when Claude Code is the MCP host.

---

## 1. Prerequisites

- **M4 MCP registration** is live. `claude mcp list` shows `ai-workflows → uv run aiw-mcp (stdio)` — if not, run through [milestone_4_mcp/mcp_setup.md §2](../milestone_4_mcp/mcp_setup.md).
- `ollama` daemon reachable at `http://localhost:11434` with `qwen2.5-coder:32b` pulled (`ollama list` shows the model).
- `claude` CLI authenticated (`claude setup-token` completed in the same shell that launches Claude Code).
- `GEMINI_API_KEY` is **not** required for the default multi-tier path — Qwen + Claude Code cover both calls. It becomes required only when you invoke the tier-override path (step 4).

No Anthropic API key is required or consulted — runtime never touches the Anthropic API ([KDR-003](../../architecture.md)).

## 2. Baseline — default multi-tier planner

From a fresh Claude Code session registered against `aiw-mcp`:

> "Using the `ai-workflows` MCP server, call `run_workflow` with `workflow_id='planner'`, `inputs={'goal': 'Write a three-bullet release checklist', 'max_steps': 3}`, and `run_id='manual-m5-1'`."

Expected response shape (the planner pauses at the `HumanGate`):

```json
{
  "run_id": "manual-m5-1",
  "status": "pending",
  "awaiting": "gate",
  "plan": null,
  "total_cost_usd": 0.0XX,
  "error": null
}
```

`total_cost_usd` is populated by Claude Code's `modelUsage` report (Qwen contributes `0` — local model). A value of `0.0` at this stage means the synth call has not yet fired — confirm the gate is `"gate"` rather than the explorer step.

Approve the gate:

> "Call `resume_run` with `run_id='manual-m5-1'` and `gate_response='approved'`."

Expected: `status="completed"` + populated `plan` + rolled-up `total_cost_usd`. Capture the final payload for the T07 CHANGELOG entry.

## 3. Inspect per-run cost

> "Call `list_runs` with `workflow='planner'` and `limit=1`."

Confirm the row shows `status: completed` and `total_cost_usd > 0`. This is the scalar the automated e2e asserts on — recording the value here pairs the manual run with the automated smoke.

## 4. Tier-override — route synth through Gemini Flash

This step requires `GEMINI_API_KEY` in the shell that launched Claude Code (same rule as [mcp_setup.md §5(b)](../milestone_4_mcp/mcp_setup.md) — the MCP subprocess inherits the parent environment).

> "Call `run_workflow` with `workflow_id='planner'`, `inputs={'goal': 'Write a three-bullet release checklist', 'max_steps': 3}`, `run_id='manual-m5-2'`, and `tier_overrides={'planner-synth': 'planner-explorer'}`."

Because the default registry has `planner-explorer` on Qwen and `planner-synth` on Claude Code, this override replaces the synth call's tier config with the explorer's — both calls now run on Qwen. To observe the _Gemini Flash_ override (the fast-path the automated `test_tier_override_smoke.py` covers), first register a `gemini_flash` tier in a workflow that declares one, then `tier_overrides={'planner-synth': 'gemini_flash'}`. Capture the response — `total_cost_usd` should be lower than the step-2 baseline since neither call hits Claude Code Opus.

Round-trip verified — the multi-tier + override surface is live.

## 5. Troubleshooting

### (a) Explorer call times out

Ollama daemon is unreachable or the Qwen model has not been pulled. Check:

```bash
curl -s http://localhost:11434/api/tags
ollama list | grep qwen2.5-coder
```

### (b) Synth call fails with "claude: command not found"

The MCP subprocess did not inherit the path to `claude`. Fix by passing the absolute path at registration — see [mcp_setup.md §5(a)](../milestone_4_mcp/mcp_setup.md).

### (c) Override raised `UnknownTierError`

Both sides of the override must name tiers the workflow declares. The planner declares `planner-explorer` and `planner-synth` — any other name on either side of the override surfaces as a `ToolError` with the sorted registered-tier list in the message.

---

## Scope boundary (what this walkthrough does **not** cover)

- **CI automation.** The `AIW_E2E=1`-gated tests in [tests/e2e/](../../../tests/e2e/) cover this path without a human. Use those for regression detection; use this doc for a milestone-closing human verification.
- **Subscription-cost calibration.** Claude Code Opus on the Max plan reports notional per-call costs in `modelUsage`; the absolute dollar figure is informational, not billable. The sibling [`tests/e2e/test_tier_override_smoke.py`](../../../tests/e2e/test_tier_override_smoke.py) asserts `total_cost_usd >= 0`, not a hard ceiling — the same posture applies here.
