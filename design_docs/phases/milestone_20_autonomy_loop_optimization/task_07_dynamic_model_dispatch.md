# Task 07 — Dynamic model dispatch (`get_model_for_agent_role` helper; default-Sonnet + flags)

**Status:** 📝 Planned. **Gated on T06's GO verdict.**
**Kind:** Model-tier / code.
**Grounding:** [milestone README](README.md) · [research brief `research_analysis` §Lens 3.2 / §Lens 3.4](research_analysis) · memory `project_autonomy_optimization_followups.md` thread #6 · sibling [task_06](task_06_shadow_audit_study.md) (gates T07) · sibling [task_21](task_21_adaptive_thinking_migration.md) (provides per-role effort assignments) · sibling [task_22](task_22_per_cycle_telemetry.md) (defaults calibrated against this telemetry).

## What to Build

A **dispatch helper** that picks the model + effort for each agent invocation based on:
- The agent's role (Builder / Auditor / sr-dev / sr-sdet / security-reviewer / dependency-auditor / task-analyzer / architect / roadmap-selector).
- The task's complexity signal (default-routine vs `--expert` vs `--cheap`).
- The autopilot flag (`--expert` pins Opus everywhere applicable; `--cheap` pins Haiku for mechanical roles).

T07's defaults come **from T06's empirical study**, not from priors. T07 ships only when T06's verdict is GO; if T06 is NO-GO or DEFER, T07 ships nothing or ships only the helper-shape with today's per-agent model frontmatter unchanged.

**Critical rule (research brief §Lens 2.2):** never switch model mid-context. The helper resolves the model at spawn time; the resolved model is passed as the spawn's `model:` field; the agent runs to completion at that model. Mid-spawn escalation is achieved by *spawning a fresh sub-agent* in a heavier model with the prior spawn's findings as input — not by switching the running spawn.

## Helper shape

```python
# scripts/orchestration/dispatch.py (NEW)
"""Resolve (model, effort) for an agent spawn.

Per M20 T07. Defaults sourced from T06 study verdict.
Operator flags: --expert → Opus, --cheap → Haiku for mechanical roles.
"""

from typing import Literal

AgentRole = Literal[
    "builder", "auditor", "sr-dev", "sr-sdet", "security-reviewer",
    "dependency-auditor", "task-analyzer", "architect", "roadmap-selector",
]
Flag = Literal["default", "expert", "cheap"]

def get_model_for_agent_role(role: AgentRole, flag: Flag = "default") -> tuple[str, str]:
    """Return (model_name, effort) for the given (role, flag) pair.

    Defaults populated post-T06. Pre-T06 placeholder shown below
    for spec-shape only — actual defaults are TBD per T06 verdict.
    """
    ...
```

Default table (placeholder — T06 may revise):

| Role | `default` | `--expert` | `--cheap` |
|---|---|---|---|
| builder | sonnet-4-6, high | opus-4-6, high | sonnet-4-6, medium |
| auditor (routine) | sonnet-4-6, high | opus-4-6, high | (reject — auditor doesn't downgrade) |
| auditor (hostile-spec / multi-file) | opus-4-6, max | opus-4-7, max | (reject) |
| sr-dev / sr-sdet / security-reviewer | sonnet-4-6, high | sonnet-4-6, high | sonnet-4-6, medium |
| dependency-auditor | sonnet-4-6, medium | sonnet-4-6, medium | haiku-4-5, n/a |
| task-analyzer | opus-4-6, high | opus-4-6, max | (reject) |
| architect | opus-4-6, high | opus-4-6, max | (reject) |
| roadmap-selector | opus-4-6, medium | opus-4-6, high | (reject) |

(Reject cases mean the helper raises `ValueError("--cheap is not applicable for role <role>")`.)

## Deliverables

### `scripts/orchestration/dispatch.py` — the helper module

Pure-function helper. No state. Reads from a config table that T06's study output populates.

### `.claude/commands/auto-implement.md` — invoke the helper at each spawn

Update each Task-spawn prompt template to invoke the helper:

```markdown
At each agent spawn, resolve the model + effort via:
    python scripts/orchestration/dispatch.py <role> --flag <default|expert|cheap>
Pass the resolved (model, effort) into the Task call's model + effort fields.
```

Same pattern in `clean-tasks.md`, `clean-implement.md`, `queue-pick.md`, `autopilot.md`.

### `--expert` and `--cheap` flag wiring

`/auto-implement` and `/autopilot` accept `--expert` / `--cheap` as args. The flag value threads through to every helper invocation in the run. If neither flag is passed, default applies.

### `.claude/commands/_common/dispatch_table.md` (NEW)

Markdown table mirroring the helper's resolution logic. Single source of truth for human-readable defaults; Python helper enforces them programmatically.

### Backward-compat: agent frontmatter `model:` line

Each agent file's frontmatter still carries a `model:` line as a fallback if the dispatch helper isn't invoked (e.g. a developer calling the agent directly). The fallback is the `default` flag's resolved model. Spawn-time invocation via the helper overrides the frontmatter.

### Reverter-friendly commit isolation for the default-tier flip (analogy to autonomy decision 2)

The shift from "Opus 4.6 default everywhere" to "Sonnet 4.6 default for Builder + reviewers" is a configuration-policy change with measurable cost / quality implications. **Land the default-table change on a separate isolated commit** in the spirit of autonomy decision 2 (CLAUDE.md non-negotiable, applied analogically — the default-table flip is **not a new KDR**, but the same independent-revertability rationale applies given the change's impact + uncertain quality implications). Other T07 work (helper module, slash-command integration, flag wiring, tests) can land on a single commit; the default-table flip lands separately so it can be reverted independently if production observation surfaces a quality regression T06 missed.

## Tests

### `tests/orchestrator/test_dispatch_helper.py` (NEW)

- Each (role, flag) pair returns the expected (model, effort).
- Reject cases raise `ValueError`.
- Unknown role raises `ValueError`.
- Unknown flag raises `ValueError`.

### `tests/orchestrator/test_dispatch_table_consistency.py` (NEW)

- `_common/dispatch_table.md`'s table rows match the helper's resolution logic.
- Each agent file's frontmatter `model:` matches the helper's `default` flag.

### `tests/orchestrator/test_no_mid_context_switch.py` (NEW)

Hermetic: simulate a multi-cycle Builder→Auditor loop and assert the model name passed to each agent at each cycle is consistent within the agent (Builder runs at Sonnet 4.6 in cycle 1 stays at Sonnet 4.6 in cycle 2, even if the loop escalates — escalation spawns a fresh agent at Opus, doesn't switch the running Builder).

## Acceptance criteria

1. `scripts/orchestration/dispatch.py` exists with the `get_model_for_agent_role` helper.
2. The helper's default table is populated per T06's GO verdict (or, if T06 is NO-GO, T07 ships only the helper *shape* with today's per-agent frontmatter as the default).
3. The 5 spawning slash commands invoke the helper at each spawn.
4. `--expert` / `--cheap` flags wire through `/auto-implement` and `/autopilot` to every helper invocation in the run.
5. `.claude/commands/_common/dispatch_table.md` matches the helper.
6. Each agent's frontmatter `model:` matches the helper's `default` flag (backward-compat for direct agent invocation).
7. The default-table commit is **isolated** per autonomy decision 2.
8. `tests/orchestrator/test_dispatch_helper.py` passes.
9. `tests/orchestrator/test_dispatch_table_consistency.py` passes.
10. `tests/orchestrator/test_no_mid_context_switch.py` passes.
11. CHANGELOG.md updated under `[Unreleased]` with `### Changed — M20 Task 07: Dynamic model dispatch (get_model_for_agent_role helper; default-Sonnet for Builder + reviewers; --expert / --cheap flag wiring; default-tier flip on isolated commit per autonomy decision 2; gated on T06 verdict)`.
12. Status surfaces flip together.

## Smoke test (Auditor runs)

```bash
# Helper resolves correctly
python scripts/orchestration/dispatch.py builder --flag default
python scripts/orchestration/dispatch.py auditor --flag expert
python scripts/orchestration/dispatch.py dependency-auditor --flag cheap

# Reject cases surface clean errors
python scripts/orchestration/dispatch.py auditor --flag cheap 2>&1 | grep -q "not applicable" && echo "reject OK"

# Verify slash commands invoke the helper
for cmd in auto-implement clean-tasks clean-implement queue-pick autopilot; do
  grep -q "scripts/orchestration/dispatch.py" .claude/commands/$cmd.md \
    && echo "$cmd OK" \
    || { echo "$cmd FAIL"; exit 1; }
done

# Run dispatch tests
uv run pytest tests/orchestrator/test_dispatch_helper.py tests/orchestrator/test_dispatch_table_consistency.py tests/orchestrator/test_no_mid_context_switch.py -v
```

## Out of scope

- **Per-task model overrides** — T07 dispatches by role + flag, not by task. A future task could add per-task-kind override (e.g. "this M-something task is doc-only, downgrade further to Haiku"), but that's a future optimization not load-bearing for M20.
- **Mid-spawn escalation that switches model** — explicitly rejected per research brief §Lens 2.2 cache-invalidation footgun. Escalation is achieved by *fresh sub-agent in heavier model*, not by switching mid-context.
- **Agent Teams adoption** — out of scope per M20 README §Non-goals.
- **Quota-aware dispatch** ("if quota is at 80% of weekly limit, downgrade everywhere") — sketched as a future option in T22's out-of-scope. Not for M20.
- **Pre-T06 implementation** — if T06 is DEFER, T07 ships only the *helper shape* (function signature + `_common/dispatch_table.md`) with today's per-agent model frontmatter as the default. The default-table flip waits for T06's GO.

## Dependencies

- **T06** (study) — **blocking-on-verdict**. T07's defaults come from T06's recommendation. If T06 is NO-GO, T07 ships the shape only.
- **T21** (adaptive-thinking migration) — **blocking**. T07 sets per-role `effort:` values per T21's per-role table.
- **T22** (telemetry) — strongly precedent. T07's `--cheap` Haiku scope and `--expert` Opus threshold should be calibrated against T22's data, which is what T06 produces.

## Carry-over from prior milestones

*None.*

## Carry-over from task analysis

- **L7 (round 1, 2026-04-27):** Add a one-line clarification that `scripts/orchestration/dispatch.py` is invoked by the slash-command orchestrator via Bash at each spawn boundary (mirrors T22's framing: "the orchestrator runs in Claude Code, has Bash + Read access, can do this in a single follow-up turn after each Task return"). Avoids reader confusion about how a Python helper integrates with markdown procedure documents.

## Carry-over from prior audits

(populated by `/clean-implement` audit cycles)
