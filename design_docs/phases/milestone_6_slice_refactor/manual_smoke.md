# Manual Smoke — M6 `slice_refactor` via Claude Code

This walkthrough mirrors [milestone_5_multitier_planner/manual_smoke.md](../milestone_5_multitier_planner/manual_smoke.md) but focuses on the M6 `slice_refactor` payload: a fresh Claude Code session calls `ai-workflows.run_workflow` against the new parallel-fan-out workflow (planner sub-graph → slice fan-out → aggregator → strict-review gate → apply) and captures the two-gate round-trip that T09's close-out CHANGELOG cites.

Complements the automated tests:

- Hermetic sibling — [tests/workflows/test_slice_refactor_e2e.py](../../../tests/workflows/test_slice_refactor_e2e.py) (always run, stubbed providers).
- Live sibling — [tests/e2e/test_slice_refactor_smoke.py](../../../tests/e2e/test_slice_refactor_smoke.py) (runs under `AIW_E2E=1 uv run pytest`).

This doc is the **human-in-the-loop** verification that the same payload lands correctly when Claude Code is the MCP host.

---

## 1. Prerequisites

- **M4 MCP registration** is live. `claude mcp list` shows `ai-workflows → uv run aiw-mcp (stdio)` — if not, run through [milestone_4_mcp/mcp_setup.md §2](../milestone_4_mcp/mcp_setup.md).
- `ollama` daemon reachable at `http://localhost:11434` with `qwen2.5-coder:32b` pulled (`ollama list` shows the model). The default `slice_refactor` tier registry routes both the `planner-explorer` tier and the new M6 `slice-worker` tier through local Qwen.
- `claude` CLI authenticated (`claude setup-token` completed in the same shell that launches Claude Code). `planner-synth` still fires against Claude Code Opus.
- `GEMINI_API_KEY` is **not** required for the default path — Qwen + Claude Code cover every tier. It becomes required only when the tier-override path (step 5) reroutes a tier onto LiteLLM's Gemini Flash model.

No Anthropic API key is required or consulted — runtime never touches the Anthropic API ([KDR-003](../../architecture.md)).

## 2. Baseline — default `slice_refactor` run

From a fresh Claude Code session registered against `aiw-mcp`:

> "Using the `ai-workflows` MCP server, call `run_workflow` with `workflow_id='slice_refactor'`, `inputs={'goal': 'Write three one-line unit tests for an add(a, b) function.', 'max_steps': 3}`, and `run_id='manual-m6-1'`."

Expected response shape (the planner sub-graph pauses at its own `HumanGate` first):

```json
{
  "run_id": "manual-m6-1",
  "status": "pending",
  "awaiting": "gate",
  "plan": null,
  "total_cost_usd": 0.0XX,
  "error": null
}
```

`total_cost_usd` reflects the planner sub-graph's explorer + synth calls so far (Qwen contributes `0`; Claude Code Opus reports a notional `modelUsage` figure on the Max subscription — informational, not billable).

## 3. Approve the planner gate — fan out across slice workers

> "Call `resume_run` with `run_id='manual-m6-1'` and `gate_response='approved'`."

Expected: the run fans out across one `slice-worker` call per planner step (three parallel branches under the default three-step goal), aggregates, and pauses at the **strict-review** gate. The response shape matches the first pause (`status="pending"`, `awaiting="gate"`), but the interrupt payload carries `gate_id="slice_refactor_review"` and a `SliceAggregate` summary with per-slice successes + failures the reviewer can inspect before approving.

Capture the aggregate payload for the T09 CHANGELOG entry — the two-gate shape is the artefact that distinguishes `slice_refactor` from the single-gate planner.

## 4. Approve the strict-review gate — observe artefact count

> "Call `resume_run` with `run_id='manual-m6-1'` and `gate_response='approved'`."

Expected: the `apply` node writes one `artifacts` row per succeeded slice (keyed `slice_result:<slice_id>`) and the run reaches `status="completed"`. The response dict returns `plan=null` (slice_refactor's terminal state is `applied_artifact_count`, not a `PlannerPlan`) and a rolled-up `total_cost_usd`.

Verify the artefact count from Claude Code:

> "Call `list_runs` with `workflow='slice_refactor'` and `limit=1`."

Confirm the row shows `status: completed` and a stamped `total_cost_usd`. If the M4 `get_artifact` MCP tool is registered, `get_artifact(run_id='manual-m6-1', kind='slice_result:1')` returns the first slice's `SliceResult` JSON; repeat for slices `2` and `3`.

## 5. Tier-override — route `slice-worker` through Claude Code Opus

This step requires `claude` CLI authenticated in the shell that launched Claude Code (same rule as [mcp_setup.md §5(a)](../milestone_4_mcp/mcp_setup.md) — the MCP subprocess inherits the parent environment).

> "Call `run_workflow` with `workflow_id='slice_refactor'`, `inputs={'goal': 'Write three one-line unit tests for an add(a, b) function.', 'max_steps': 3}`, `run_id='manual-m6-2'`, and `tier_overrides={'slice-worker': 'planner-synth'}`."

The default `slice_refactor` tier registry has `slice-worker` on Qwen and `planner-synth` on Claude Code Opus; this override repoints the worker calls onto Opus. Approve both gates as in steps 3–4 and capture the resulting `total_cost_usd` — it should land higher than the baseline since every slice now fires against Opus instead of local Qwen.

Round-trip verified — the slice_refactor + override surface is live.

## 6. Double-failure hard-stop — smoke the abort path (optional)

The [architecture.md §8.2](../../architecture.md) double-failure hard-stop is covered by the hermetic suite at [tests/workflows/test_slice_refactor_hard_stop.py](../../../tests/workflows/test_slice_refactor_hard_stop.py). Reproducing it against real providers requires two slices to exhaust their semantic retry budgets on output the validator rejects — not reliably reproducible from a plain-English goal. Skip by default; reach for the hermetic suite when the abort wiring needs re-verification.

## 7. Troubleshooting

### (a) `slice-worker` call times out

Ollama daemon unreachable or `qwen2.5-coder:32b` not pulled. Same diagnosis as the M5 troubleshooting §5(a):

```bash
curl -s http://localhost:11434/api/tags
ollama list | grep qwen2.5-coder
```

### (b) Fan-out fails with `UnknownTierError: unknown replacement tier 'slice-worker'`

The workflow being overridden does not declare `slice-worker`. Confirm the workflow id is `slice_refactor` (not `planner`) — the planner's tier registry has no `slice-worker` entry.

### (c) Strict-review gate pauses with zero succeeded slices

Every slice's validator raised `NonRetryable` on the first attempt but the hard-stop threshold did not fire (only one slice failed non-retryably). This is a valid outcome — the reviewer can still approve to record the audit trail, and `apply` will return `applied_artifact_count=0`. The run will reach `status="completed"`.

---

## Scope boundary (what this walkthrough does **not** cover)

- **Subprocess / `git apply` invocation.** M6's `apply` node writes to `Storage` only; invoking `git apply` or any filesystem write lands post-M6. The [milestone README](README.md) lists this under non-goals.
- **Double-failure abort walkthrough.** See step 6 — the hermetic suite owns that path.
- **CI automation.** The `AIW_E2E=1`-gated test at [tests/e2e/test_slice_refactor_smoke.py](../../../tests/e2e/test_slice_refactor_smoke.py) covers this path without a human. Use it for regression detection; use this doc for a milestone-closing human verification.
