# Task 06 — End-to-End Smoke (Hermetic + `AIW_E2E=1` Live)

**Status:** 📝 Planned.

## What to Build

Extend the M3 `AIW_E2E=1`-gated smoke test at [`tests/e2e/test_planner_smoke.py`](../../../tests/e2e/test_planner_smoke.py) so it drives the M5 multi-tier path end-to-end against **real** providers: Qwen via Ollama + Claude Code CLI. Also add a second `AIW_E2E=1`-gated test that exercises the tier-override surface ([T04](task_04_tier_override_cli.md) / [T05](task_05_tier_override_mcp.md)) by overriding `planner-synth` back to Gemini Flash and confirming the override actually routes a cheaper tier.

Aligns with [architecture.md §11 Testing strategy](../../architecture.md), KDR-003 (OAuth-only Claude access).

## Deliverables

### `tests/e2e/test_planner_smoke.py` — multi-tier mode

Update the existing e2e so, when both prerequisites are present, it runs against the full multi-tier planner (Qwen + Claude Code):

- Prerequisite check: `shutil.which("ollama")` → an Ollama daemon reachable at `http://localhost:11434`; `shutil.which("claude")` → OAuth-authenticated Claude Code CLI. Either missing → `pytest.skip(...)` with a readable reason (not a fail).
- Goal: a short, cheap real goal (e.g. `"Write a three-bullet release checklist."`).
- Asserts:
  - `aiw run planner …` completes to the gate.
  - `aiw resume <run_id> --approve` completes to `completed`.
  - `runs.total_cost_usd` is strictly positive (Claude Code + any Haiku sub-model); Qwen contributes 0.
  - `TokenUsage.sub_models` on the Claude Code row is non-empty if the `modelUsage` JSON the CLI returned contained sub-models (skip the assertion if not — some Opus calls do not auto-spawn).
  - No `anthropic` env var read, no `anthropic` SDK import reachable (grep).

### `tests/e2e/test_tier_override_smoke.py` (new, `AIW_E2E=1`-gated)

- Prerequisite: Gemini `GEMINI_API_KEY` (sufficient on its own — the override target runs cheaper than Claude Code + faster than Qwen, making this the fast-path e2e).
- Invokes the MCP `run_workflow` tool in-process (mirrors [`tests/mcp/test_server_smoke.py`](../../../tests/mcp/test_server_smoke.py)) with `tier_overrides={"planner-synth": "planner-explorer"}` — forcing the synth call onto Gemini Flash rather than Claude Code Opus.
- Asserts: run completes to the gate; `aiw resume` completes; both `TokenUsage` rows are LiteLLM-provider rows (no `ClaudeCodeSubprocess` call recorded).

### `design_docs/phases/milestone_5_multitier_planner/manual_smoke.md` (new)

Short walkthrough for the manual verification recorded in [T07](task_07_milestone_closeout.md)'s close-out CHANGELOG entry: a fresh Claude Code session registering `aiw-mcp`, calling `run_workflow(workflow_id="planner", inputs={"goal": "..."})`, capturing the multi-tier payload. Mirrors [mcp_setup.md](../milestone_4_mcp/mcp_setup.md) shape.

## Acceptance Criteria

- [ ] `AIW_E2E=1 uv run pytest tests/e2e/test_planner_smoke.py` green once against real Qwen + real Claude Code (record the run in the T07 close-out CHANGELOG entry — gate-approved plan + positive cost + zero Anthropic SDK surface).
- [ ] `AIW_E2E=1 uv run pytest tests/e2e/test_tier_override_smoke.py` green once against real Gemini — override forces cheaper path.
- [ ] Default `uv run pytest` (no `AIW_E2E`) skips both live tests cleanly; hermetic suite remains 332 + M5 new-test-count passed.
- [ ] Prerequisite checks produce readable skip reasons when `ollama` / `claude` / `GEMINI_API_KEY` missing — no misleading failures.
- [ ] KDR-003 regression: the e2e `grep` for `anthropic` / `ANTHROPIC_API_KEY` in production code returns zero hits.
- [ ] `uv run lint-imports` 3 / 3 kept.
- [ ] `uv run ruff check` clean.

## Dependencies

- [Task 01](task_01_qwen_explorer.md) through [Task 05](task_05_tier_override_mcp.md) landed.
- Live verification requires `ollama` daemon + `qwen2.5-coder:32b` pulled + `claude` CLI authenticated + `GEMINI_API_KEY`. Builder records the environment used in the T07 CHANGELOG entry.
