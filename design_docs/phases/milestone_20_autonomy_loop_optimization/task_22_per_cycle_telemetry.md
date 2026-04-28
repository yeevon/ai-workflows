# Task 22 — Per-cycle token telemetry per agent

**Status:** 📝 Planned.
**Kind:** Model-tier / code.
**Grounding:** [milestone README](README.md) · [research brief `research_analysis` §Lens 3.4 (anthropics/claude-code #52502 — metering opacity)](research_analysis) · memory `project_autonomy_optimization_followups.md` thread #22 · sibling [task_06](task_06_shadow_audit_study.md) (study consumes T22's measurements + owns the per-cell proxy aggregation) · [task_07](task_07_dynamic_model_dispatch.md) (defaults calibrated against T22's data) · [task_23](task_23_cache_breakpoint_discipline.md) (verification reads T22's `cache_read_input_tokens`) · [task_27](task_27_tool_result_clearing.md) (rotation trigger reads T22's `input_tokens`).

## What to Build

A small **telemetry wrapper** around every sub-agent invocation that captures token-counts + cost-proxy + model + effort + cache-hit metrics, and persists each invocation's record to `runs/<task>/cycle_<N>/<agent>.usage.json`. T22 is the **measurement substrate** for T06 (the model-dispatch study cannot produce per-cell deltas without it), T07 (default-tier picks should be empirically calibrated), and T23 (cache-breakpoint verification depends on `cache_read_input_tokens` measurements).

Per the research brief §Lens 3.4: anthropics/claude-code issue #52502 (Apr 23, 2026) documents that even Anthropic's own usage dashboard is opaque about which model in a multi-agent stack consumed what. T22 gives ai-workflows local visibility independent of upstream dashboard fixes.

## Surface-check pre-step (per audit M7)

Before any production capture: run `python scripts/orchestration/check_task_response_fields.py` (a single Task spawn dump) to confirm whether Claude Code's Task tool returns `cache_creation_input_tokens`, `cache_read_input_tokens`, `input_tokens`, and `output_tokens` in its response payload. The result lands at `runs/m20_t22_surface_check.txt` for the audit trail.

- **If cache-* fields ARE exposed:** T22 ships full per the §Captured fields below. T23 (cache-breakpoint verification) ships normally.
- **If cache-* fields are NOT exposed:** T22 ships with the available subset only — `input_tokens` + `output_tokens` (computed from prompt + return text via the regex proxy if not exposed by the API), `model` + `effort` (from spawn args), `wall_clock_seconds` (from timestamps), `verdict` (from the T01 schema return). Fields `cache_creation_input_tokens` + `cache_read_input_tokens` are recorded as `null`. T23 downgrades to STOP-AND-ASK at its land time (not T22's concern).
- **If the surface is partial** (some fields exposed, others not): T22 captures whichever subset is available; null-fills the rest; documents the partial surface in `runs/m20_t22_surface_check.txt`.

## Captured fields

```json
{
  "task": "m20_t01",
  "cycle": 1,
  "agent": "auditor",
  "spawn_ts": "2026-04-27T15:30:42Z",
  "complete_ts": "2026-04-27T15:33:18Z",
  "wall_clock_seconds": 156,
  "model": "claude-opus-4-7",
  "effort": "high",
  "input_tokens": 12450,
  "output_tokens": 387,
  "cache_creation_input_tokens": 8200,
  "cache_read_input_tokens": 4250,
  "verdict": "PASS",
  "fragment_path": "runs/m20_t01/cycle_1/audit_issue.md",
  "section": "—"
}
```

T22 captures **raw token counts only** — no per-model coefficient computed at capture time. Per audit M9: per-cell quota-proxy aggregations are computed by **T06's analysis script** using the appropriate ratio model (API-price ratio, observed Max-quota consumption from the T06 runs themselves, or both). T22 is the measurement substrate; T06 owns the proxy / aggregation layer.

The model + effort fields come from spawn arguments (orchestrator-side, no Task-tool dependency). The cache-* + input/output token fields come from the Task tool's response payload IF the surface check confirms they're exposed; otherwise null per the surface-check pre-step above.

## Deliverables

### Telemetry wrapper script — `scripts/orchestration/telemetry.py` (NEW)

A CLI utility the orchestrator invokes via Bash at each Task-spawn boundary. The slash commands are markdown procedure documents, not Python — telemetry capture is shell-out, not in-process import. (No new code lands under `ai_workflows/`; M20 preserves the runtime-vs-orchestration-infra boundary per README §Scope note.) Per audit M10, M20 helpers nest under `scripts/orchestration/` for namespace clarity.

```bash
# At spawn time, capture spawn metadata
python scripts/orchestration/telemetry.py spawn \
    --task m20_t01 --cycle 1 --agent auditor \
    --model claude-opus-4-7 --effort high

# At completion time (after Task return), capture the metrics
python scripts/orchestration/telemetry.py complete \
    --task m20_t01 --cycle 1 --agent auditor \
    --input-tokens 12450 --output-tokens 387 \
    --cache-creation 8200 --cache-read 4250 \
    --verdict PASS --fragment-path '...'
```

The script appends to `runs/<task>/cycle_<N>/<agent>.usage.json` and ensures atomic write (lock file or write-temp-then-rename). Path convention matches T03's directory layout per audit M11. Task shorthand follows the zero-padded `m<MM>_t<NN>` convention per audit M12.

### Slash-command integration

Each of the 5 spawning slash commands (`auto-implement`, `clean-tasks`, `clean-implement`, `queue-pick`, `autopilot`) describes the telemetry-record convention in its spawn block:

```markdown
At spawn time, run `python scripts/orchestration/telemetry.py spawn ...`
in the same orchestrator turn as the Task call. At Task return,
read the Task's metadata fields and run
`python scripts/orchestration/telemetry.py complete ...` to persist the record.
```

This is non-mechanical for the orchestrator (it has to read Task metadata fields and pass them to the script). Acceptable — the orchestrator runs in Claude Code, has Bash + Read access, can do this in a single follow-up turn after each Task return.

### Aggregation hook for T04 — retrofitted by T22

Per audit M15: T22 ships in Phase C (after T04 in Phase A). T04's `iter_<N>_shipped.md` template at T04 land time has no Telemetry summary section. T22's Builder uses Edit to **insert** the section into pre-existing `iter_<N>_shipped.md` files generated by T04 in the interim. The contract is: T22 owns the aggregation script + retrofit; T04 owns the iteration-shipped artifact's other sections.

T22's aggregation script reads all `runs/<task>/cycle_<N>/*.usage.json` files for the iteration's task and appends a Telemetry summary section to T04's `iter_<N>_shipped.md`:

```markdown
## Telemetry summary
| Cycle | Agent | Model | Effort | Input tokens | Output tokens | Cache hit % | Quota proxy | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
```

T22 produces the per-record JSONs; T04 produces the per-iteration aggregation. Both layers exist; neither replaces the other.

### `.cycle/` directory cleanup

Verify `runs/` is in `.gitignore` (already is per existing project state). Telemetry records are local-only, never committed.

## Tests

### `tests/orchestrator/test_telemetry_record.py` (NEW)

Hermetic test of `scripts/orchestration/telemetry.py`:
- `spawn` subcommand creates the per-cycle directory + writes the spawn record.
- `complete` subcommand updates the record with completion metrics.
- Atomic-write semantics: simulated concurrent invocations don't lose records.
- Bad input (missing required field) raises a clean error message.

### `tests/orchestrator/test_telemetry_aggregation.py` (NEW)

Hermetic test of the T04-side aggregation:
- 3-cycle task with 5 agent invocations per cycle (15 records total) → aggregation table has 15 rows.
- Quota-proxy column computes correctly per-model.
- Cache-hit % computes correctly: `cache_read / (cache_read + cache_creation)`.

## Acceptance criteria

1. `scripts/orchestration/telemetry.py` exists with `spawn` + `complete` subcommands.
2. Per-cycle JSON records land at `runs/<task>/cycle_<N>/<agent>.usage.json` with all captured fields.
3. The 5 spawning slash commands describe the telemetry-record convention.
4. T04's aggregation hook reads telemetry records into `iter_<N>_shipped.md`.
5. `tests/orchestrator/test_telemetry_record.py` passes.
6. `tests/orchestrator/test_telemetry_aggregation.py` passes.
7. `runs/` is in `.gitignore`; telemetry records are local-only.
8. CHANGELOG.md updated under `[Unreleased]` with `### Added — M20 Task 22: Per-cycle agent telemetry wrapper (raw token capture + model + effort + wall-clock + verdict; cache-* fields conditional on Task tool surface check; quota-proxy aggregation owned by T06; basis for T06 study + T07 dispatch defaults + T23 cache verification + T27 rotation trigger; mitigates anthropics/claude-code #52502 metering opacity)`.
9. Status surfaces flip together.

## Smoke test (Auditor runs)

```bash
# Run a synthetic spawn-then-complete flow
mkdir -p runs/m20_t22_smoke/1
python scripts/orchestration/telemetry.py spawn \
  --task m20_t22_smoke --cycle 1 --agent auditor \
  --model claude-opus-4-7 --effort high
python scripts/orchestration/telemetry.py complete \
  --task m20_t22_smoke --cycle 1 --agent auditor \
  --input-tokens 100 --output-tokens 50 \
  --cache-creation 80 --cache-read 20 \
  --verdict PASS --fragment-path '/tmp/x'

# Verify the record landed
test -f runs/m20_t22_smoke/1/auditor.usage.json && echo "record landed"

# Verify all expected fields
python -c "import json; d=json.load(open('runs/m20_t22_smoke/1/auditor.usage.json')); \
  assert d['agent']=='auditor' and d['quota_consumption_proxy']>0 and d['verdict']=='PASS'"

# Run tests
uv run pytest tests/orchestrator/test_telemetry_record.py tests/orchestrator/test_telemetry_aggregation.py -v
```

## Out of scope

- **Cost reconciliation against the upstream Anthropic dashboard** — out of scope by design. Per #52502, the dashboard is opaque about per-model breakdown in multi-agent stacks. T22's quota proxy is the local-best-estimate; reconciliation would require Anthropic API surface that doesn't exist.
- **Real-time alerting on quota thresholds** — out of scope for M20. A future task in M21 or beyond could add a "halt if projected quota for this autopilot run exceeds X" surface, but that's a productivity feature not load-bearing for the optimization work.
- **Persistence beyond the run** — telemetry records live under `runs/` (gitignored). They survive across sessions on the same machine but aren't shipped or aggregated cross-machine. Acceptable for solo-use ai-workflows per KDR-013 and the deployment-shape memory.
- **Cross-session aggregation surface** — out of scope. Future tasks could add a `/telemetry` command that summarises across recent runs, but that's productivity not optimization.

## Dependencies

- **T21** (adaptive-thinking migration) — strongly precedent. T22 captures `effort` per spawn; T21 ensures every agent has an explicit `effort` value to capture.
- **T01** (return-value schema) — non-blocking. T22's `verdict` field is the T01 verdict line, parsed at completion time.

## Carry-over from prior milestones

*None.*

## Carry-over from task analysis

(populated by `/clean-tasks m20`)

## Carry-over from prior audits

(populated by `/clean-implement` audit cycles)
