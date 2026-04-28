# Task 02 — Sub-agent input prune (orchestrator-side scope discipline + per-spawn output budget)

**Status:** 📝 Planned.
**Kind:** Compaction / doc + code.
**Grounding:** [milestone README](README.md) · [research brief `research_analysis` §Lens 2.3 / §Lens 2.4](research_analysis) · memory `project_autonomy_optimization_followups.md` thread #8 · [`.claude/commands/auto-implement.md`](../../../.claude/commands/auto-implement.md) · [`.claude/commands/clean-tasks.md`](../../../.claude/commands/clean-tasks.md) · [`.claude/agents/auditor.md`](../../../.claude/agents/auditor.md) (the Auditor's "load full task scope" invariant — preserved at-the-agent, pruned at-the-orchestrator).

## What to Build

Orchestrator-side **scope discipline** for every sub-agent spawn: the spawning slash command (`auto-implement`, `clean-tasks`, `clean-implement`, `queue-pick`, `autopilot`) passes **only what the agent will certainly use** — task spec + KDR-relevant architecture sections + current diff (where applicable) — and lets the agent pull the rest on demand via its own `Read` tool. Whole-milestone READMEs, unrelated-sibling issue files, and full architecture.md pre-loads are removed from the orchestrator's `Task` invocation prompt.

Pair this with a **per-spawn output token budget** mandated in the spawn prompt: 1–2 K tokens for read-only sub-agents (auditor, sr-dev, sr-sdet, security-reviewer, dependency-auditor, task-analyzer, architect, roadmap-selector), 4 K for code-writing sub-agents (builder). The output budget is a soft directive in the prompt, not a runtime cap (Claude Code's `Task` tool doesn't expose hard output limits) — but combined with T01's hard 3-line return schema, the agent has explicit cost-of-prose pressure.

**Critical preservation:** the Auditor's "load full task scope, not the diff" invariant (CLAUDE.md non-negotiable) is *agent-internal*, not *orchestrator-input*. T02 prunes only the orchestrator's pre-load; the Auditor still pulls architecture.md + sibling issue files + every cited KDR via its own Read tool inside its run. The asymmetry per the research brief: **the cost of an under-pre-fed sub-agent is one extra Read call; the cost of an over-pre-fed sub-agent is token waste + attention dilution. Asymmetry favours under-pre-feeding.**

## Deliverables

### `.claude/commands/auto-implement.md` — pruned spawn-prompt template

Locate the Builder + Auditor + reviewer Task-spawn invocations. Replace bulk pre-loads with scoped references:

- **Builder spawn:** task spec path + parent milestone README path + project context brief. **Remove:** sibling task issue files, pre-loaded architecture.md, pre-loaded CHANGELOG.
- **Auditor spawn:** task spec path + issue file path + parent milestone README path + project context brief + current `git diff` + the **specific KDR sections** the task spec cites (parsed at spawn time, not the whole §9 table). **Remove from inline content:** whole-milestone-README *content* (path stays; Auditor reads on-demand), pre-loaded architecture.md *content*, pre-loaded sibling issue file *content*. The Auditor pulls all of these via its own Read tool when its phases need them. **Path references stay; content inlining goes.** The Auditor's "load full task scope" invariant (CLAUDE.md non-negotiable) is preserved — it just does the loading itself, on-demand, instead of receiving everything pre-stuffed into the spawn prompt.
- **Reviewer spawns** (sr-dev, sr-sdet, security-reviewer): task spec + issue file + project context brief + current `git diff` + list of files touched (aggregated from Builder reports). **Remove:** pre-loaded full source files, full test files, full architecture.md.

Each spawn prompt includes the per-agent output budget directive:

```
Output budget: <1-2K|4K> tokens. Combine with T01's 3-line schema —
your durable findings live in the file you write; the return is the schema only.
```

### `.claude/commands/clean-tasks.md` — task-analyzer spawn prune

Same scope-discipline rule for `task-analyzer` Task spawn:
- Pass: milestone directory path + analysis-output file path + project context brief + round number + list of task spec filenames.
- Remove: pre-loaded full task spec contents (analyzer reads them via its own Read tool), pre-loaded architecture.md, pre-loaded sibling milestone READMEs.

### `.claude/commands/clean-implement.md`, `queue-pick.md`, `autopilot.md` — same pattern

Apply the scope-discipline rule consistently across all 5 spawning commands. Each command's spawn-prompt section names the minimal pre-load set + the output budget directive.

### `.claude/commands/_common/spawn_prompt_template.md` (NEW)

Canonical spawn-prompt scaffolding referenced by each slash command. Single source of truth for: minimal pre-load set, output budget directive, schema reminder linking to T01's `_common/agent_return_schema.md`, agent-specific context-brief substitution.

### Orchestrator measurement instrumentation (lightweight)

Each Task spawn captures the spawn-prompt size (in tokens, via the **regex-based proxy** `len(re.findall(r"\S+", text)) * 1.3` — token-counting accuracy is not load-bearing here, magnitude is; same proxy used by T01, T22, T23 for consistency; no `tiktoken` test-only dep added per round-1 L8 carry-over) into `runs/<task>/cycle_<N>/spawn_<agent>.tokens.txt` (per audit M11 — nested directory; drop `_<cycle>` suffix from filename since the directory provides the namespace). Aggregated by T22 (per-cycle telemetry). T02 only emits the per-spawn measurement; T22 builds the aggregation surface.

## Tests

### `tests/orchestrator/test_spawn_prompt_size.py` (NEW)

Hermetic test that constructs a synthetic spawn prompt for each slash command's Task invocation against a fixture task and asserts:
- Spawn-prompt token count ≤ a per-agent ceiling (Builder: 8 K; Auditor: 6 K; reviewers: 4 K; task-analyzer: 6 K; roadmap-selector: 4 K). Ceilings are calibrated against the M12 T01 audit baseline (T22 produces the empirical measurement once it lands; for T02 these are the audit-time baselines).
- The minimal pre-load set is present (task spec, issue file, project context brief).
- Whole-milestone-README and unrelated-sibling-issue pre-loads are absent.

### `tests/orchestrator/test_kdr_section_extractor.py` (NEW)

Test the KDR-section parsing logic that extracts only the cited KDRs from architecture.md §9 for the Auditor's spawn:
- Task spec citing "KDR-003, KDR-013" → spawn prompt includes only those two KDR sections.
- Task spec citing no KDRs → spawn prompt includes the §9 grid header only (compact pointer for the Auditor to expand on-demand).

## Acceptance criteria

1. The 5 spawning slash commands (`auto-implement`, `clean-tasks`, `clean-implement`, `queue-pick`, `autopilot`) describe the pruned spawn-prompt convention with a per-agent minimal pre-load set and an output budget directive.
2. `.claude/commands/_common/spawn_prompt_template.md` exists as the canonical reference; each slash command links to it.
3. `tests/orchestrator/test_spawn_prompt_size.py` passes with the per-agent ceilings.
4. `tests/orchestrator/test_kdr_section_extractor.py` passes with positive + edge cases.
5. Per-spawn token-count instrumentation lands at `runs/<task>/cycle_<N>/spawn_<agent>.tokens.txt` (T22 consumes these aggregates; nested per-cycle directory per audit M11).
6. **Validation re-run:** re-run the M12 T01 audit cycle 1 spawn (against a frozen fixture of M12 T01's pre-T02 spawn-prompt input) and assert the post-T02 input-token count is ≥ 30 % smaller than the pre-T02 baseline.
7. CHANGELOG.md updated under `[Unreleased]` with `### Changed — M20 Task 02: Sub-agent input prune (orchestrator-side scope discipline + per-spawn output budget; research brief §Lens 2.3)`.
8. Status surfaces flip together at task close.

## Smoke test (Auditor runs)

```bash
# Verify _common/spawn_prompt_template.md exists
test -f .claude/commands/_common/spawn_prompt_template.md && echo "common template OK"

# Verify each slash command links to it
for cmd in auto-implement clean-tasks clean-implement queue-pick autopilot; do
  grep -q "_common/spawn_prompt_template.md" .claude/commands/$cmd.md \
    && echo "$cmd OK" \
    || { echo "$cmd FAIL"; exit 1; }
done

# Verify each slash command names the output budget directive
for cmd in auto-implement clean-tasks clean-implement queue-pick autopilot; do
  grep -q "Output budget:" .claude/commands/$cmd.md \
    && echo "$cmd budget OK" \
    || { echo "$cmd FAIL — missing output budget directive"; exit 1; }
done

# Run prune + KDR-extractor tests
uv run pytest tests/orchestrator/test_spawn_prompt_size.py tests/orchestrator/test_kdr_section_extractor.py -v

# Validation re-run (the 30% reduction claim)
uv run pytest tests/orchestrator/test_spawn_prompt_size.py::test_m12_t01_audit_spawn_30pct_reduction -v
```

## Out of scope

- **Auditor's internal scope discipline** — the Auditor still loads the full task scope per its agent definition. T02 prunes only the *orchestrator's pre-load*, not the *agent's own reads*. Confusing the two would break the Auditor's KDR-drift-check invariant.
- **Per-cycle context decay across cycles** — that's T03's scope (in-task cycle compaction). T02 prunes the pre-load *into* a single spawn; T03 prunes the carry-forward *across* cycles.
- **Cross-task context decay** — that's T04's scope.
- **Hard runtime output cap** — Claude Code's `Task` tool doesn't expose this. The output budget is a prompt-level directive paired with T01's 3-line schema; combined they exert prose-suppression pressure without a hard runtime cap.
- **Adoption of server-side `compact_20260112`** — that's T28's evaluation scope. T02 is purely client-side input scoping.
- **Builder spawn-prompt diet beyond what's named here** — the Builder still needs the full task spec, parent milestone README, and project context brief. Pruning further would compromise the Builder's spec-grounded implementation.

## Dependencies

- **T01** (return-value schema) is **strongly precedent**, not strictly blocking. T02's output budget directive references the T01 schema; ideally T01 lands first so the budget directive can link to a real schema reference. If T01 is delayed, T02 can land with a placeholder reference and link-fix on T01's land.

## Carry-over from prior milestones

*None.*

## Carry-over from task analysis

(populated by `/clean-tasks m20`)

## Carry-over from prior audits

(populated by `/clean-implement` audit cycles)
