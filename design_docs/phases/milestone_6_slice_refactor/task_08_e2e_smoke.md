# Task 08 — End-to-End Smoke on Fixture Slice List

**Status:** 📝 Planned.

## What to Build

Exercise the full `slice_refactor` pipeline — `START → planner sub-graph → slice_list_normalize → slice_worker (fan-out) → slice_worker_validator → aggregate → strict-review gate → apply → END` — as one hermetic smoke test plus one `AIW_E2E=1`-gated live variant against real providers. Mirrors the M3 / M5 E2E pattern at [`tests/e2e/test_planner_smoke.py`](../../../tests/e2e/test_planner_smoke.py) and [`tests/e2e/test_tier_override_smoke.py`](../../../tests/e2e/test_tier_override_smoke.py).

Aligns with [architecture.md §11 Testing strategy](../../architecture.md), KDR-003 (OAuth-only Claude access), KDR-008 (FastMCP as the live MCP surface).

## Deliverables

### `tests/workflows/test_slice_refactor_e2e.py` (new, hermetic — always run)

End-to-end against stubbed providers:

- Fixture `goal` string that deterministically drives the planner stub to return a 3-slice `PlannerPlan`.
- Stubbed `slice-worker` tier returns a valid `SliceResult` for each slice on the first call.
- Run `build_slice_refactor()` through the shared `_dispatch.run_workflow(...)` path (same entry the CLI + MCP use).
- Assert the run pauses at the **planner's** plan-review gate (`strict_review=False`, inherited from the sub-graph).
- Resume with `--approve`; run continues through fan-out → validator → aggregate → strict-review gate.
- Assert run pauses at **`slice_refactor`'s** strict-review gate with a `SliceAggregate` payload.
- Resume with `gate_response="approve"`; run runs `apply`; asserts (a) 3 artefacts in `Storage`, (b) `runs.status == "completed"`, (c) `runs.total_cost_usd` is non-negative (stub adapters report 0, real adapters report real numbers).
- Reject-at-outer-gate variant: same shape but resume the outer gate with `reject`; assert 0 artefacts, `runs.status == "gate_rejected"`.
- No `anthropic` import or `ANTHROPIC_API_KEY` read (KDR-003 regression grep).

### `tests/e2e/test_slice_refactor_smoke.py` (new, `AIW_E2E=1`-gated live)

Mirrors `tests/e2e/test_planner_smoke.py`'s prerequisite + skip pattern:

- Prerequisite: `shutil.which("ollama")` + Ollama daemon at `http://localhost:11434` + `qwen2.5-coder:32b` pulled + `shutil.which("claude")` + authenticated Claude Code CLI. Either missing → `pytest.skip(...)` with readable reason.
- Goal: a short, cheap real goal that produces a small planner plan (e.g. `"Write three one-line unit tests for an add(a, b) function."`).
- Run through the same fan-out → aggregate → gate → apply path, resuming both gates via the `_dispatch.resume_workflow` shim (same helper the M5 T06 smoke uses).
- Asserts:
  - `aiw run slice_refactor …` completes to the planner's gate.
  - First resume continues to the outer gate with a `SliceAggregate`.
  - Second resume completes to `completed`.
  - `runs.total_cost_usd` is non-negative and stamped ([project memory](../../../../.claude/projects/-home-papa-jochy-prj-ai-workflows/memory/project_provider_strategy.md): Claude Code Opus reports notional 0 on the Max subscription — the absolute dollar figure is informational, not billable; match the M5 T06 posture).
  - Artefact count in `Storage` equals the number of approved slices.
  - `TokenUsage.sub_models` populated if the Claude Code `modelUsage` JSON returned sub-models (skip-assertion-if-empty, same as M5 T06).
  - No `anthropic` env var read, no `anthropic` SDK import reachable (grep).

### `design_docs/phases/milestone_6_slice_refactor/manual_smoke.md` (new)

Short walkthrough for the manual verification recorded in [T09](task_09_milestone_closeout.md)'s close-out CHANGELOG entry: a fresh Claude Code session registering `aiw-mcp`, calling `run_workflow(workflow_id="slice_refactor", inputs={"goal": "..."})`, capturing the two-gate payload (planner review + slice_refactor strict review), approving both, and observing the artefact count in `Storage`. Mirror [M5's manual_smoke.md](../milestone_5_multitier_planner/manual_smoke.md) shape.

## Acceptance Criteria

- [ ] Hermetic `tests/workflows/test_slice_refactor_e2e.py` green: full pipeline runs, both gates fire in order, approve path writes artefacts, reject path writes none.
- [ ] `AIW_E2E=1 uv run pytest tests/e2e/test_slice_refactor_smoke.py` green once against real Qwen + real Claude Code (record in the T09 close-out CHANGELOG entry).
- [ ] Default `uv run pytest` (no `AIW_E2E`) skips the live test cleanly; hermetic suite remains green.
- [ ] Prerequisite checks produce readable skip reasons when dependencies missing.
- [ ] KDR-003 regression: grep for `anthropic` / `ANTHROPIC_API_KEY` in production code returns zero hits.
- [ ] `uv run lint-imports` 3 / 3 kept.
- [ ] `uv run ruff check` clean.

## Dependencies

- [Task 01](task_01_slice_discovery.md) through [Task 07](task_07_concurrency_hard_stop.md) landed.
- Live verification requires `ollama` daemon + `qwen2.5-coder:32b` + `claude` CLI authenticated. Builder records the environment in the T09 CHANGELOG entry.
