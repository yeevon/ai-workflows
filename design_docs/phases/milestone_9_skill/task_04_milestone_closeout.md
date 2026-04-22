# Task 04 — Milestone Close-out

**Status:** 📝 Planned.
**Grounding:** [milestone README](README.md) · [CLAUDE.md](../../../CLAUDE.md) close-out conventions · [M8 T06](../milestone_8_ollama/task_06_milestone_closeout.md) (pattern to mirror).

## What to Build

Close M9. Confirm every exit criterion from the
[milestone README](README.md). Update
[CHANGELOG.md](../../../CHANGELOG.md), flip M9 complete in
[roadmap.md](../../roadmap.md), and refresh the root
[README.md](../../../README.md). No code change beyond docs — any
finding surfaced during close-out becomes a forward-deferred
carry-over on an M10 task or a new `nice_to_have.md` entry, never
a drive-by fix.

Mirrors [M8 Task 06](../milestone_8_ollama/task_06_milestone_closeout.md)
so reviewers get identical close-out muscle memory.

## Deliverables

### [README.md](README.md) (milestone)

- Flip **Status** from `📝 Optional` (or `📝 Planned` if promoted)
  to `✅ Complete (<YYYY-MM-DD>)`.
- Append an **Outcome** section summarising:
  - Skill file ([task 01](task_01_skill_md.md)) —
    `.claude/skills/ai-workflows/SKILL.md` landed with YAML
    frontmatter + five body sections; packaging-only per KDR-002.
  - Plugin manifest ([task 02](task_02_plugin_manifest.md)) —
    one of: *shipped at `.claude/plugins/ai-workflows/plugin.json`*
    / *deferred (no trigger fired)* / *deferred (schema unstable)*.
    Record the exact disposition.
  - Distribution doc ([task 03](task_03_distribution_docs.md)) —
    `design_docs/phases/milestone_9_skill/skill_install.md` with
    five sections (Prerequisites → Install MCP → Install skill →
    Smoke → Troubleshooting); root `README.md` links in.
  - Manual verification: end-to-end smoke run once at close-out
    time from a fresh Claude Code session (skill discovered →
    `run_workflow(planner)` → gate pause → `resume_run` →
    completed plan). Record the commit sha baseline + pass/fail
    observation — mirrors M4 T06's `claude mcp add` round-trip
    pattern.
  - Green-gate snapshot: `uv run pytest`, `uv run lint-imports`
    (**4 contracts kept** — no new layer contract added at M9;
    packaging-only milestone touches no `ai_workflows.*` module),
    `uv run ruff check`.
- Keep the **Carry-over from prior milestones** section intact
  (currently: *None* — M8 T06 closed clean).

### [roadmap.md](../../roadmap.md)

Flip M9 row `Status` from `optional` (or `planned` if promoted)
to `✅ complete (<YYYY-MM-DD>)`.

### [CHANGELOG.md](../../../CHANGELOG.md)

Promote accumulated `[Unreleased]` entries from M9 tasks into a
dated section `## [M9 Claude Code Skill Packaging] - <YYYY-MM-DD>`.
Keep the top-of-file `[Unreleased]` section intact. Add a T04
close-out entry at the top of the new dated section — mirror M8
T06's shape. Record:

- The skill-install manual smoke rerun at close-out time — commit
  sha baseline + the operator's pass/fail observation.
- The `uv run lint-imports` 4-contract snapshot confirming no new
  contracts landed at M9.
- The T02 disposition (shipped / deferred) with the named reason
  if deferred.
- The packaging-only scope honoured: zero `ai_workflows.*` diff.

### Root [README.md](../../../README.md)

- Flip the M9 row in the milestone status table to "Complete
  (<YYYY-MM-DD>)".
- If T03 landed a link to `skill_install.md`, verify it still
  resolves after the close-out edits.

## Acceptance Criteria

- [ ] Milestone README Status flipped to `✅ Complete` with a date.
- [ ] Outcome section covers all four tasks (T01 / T02 / T03 / T04)
      with explicit dispositions (especially T02's
      shipped-or-deferred).
- [ ] `roadmap.md` M9 row reflects the complete status.
- [ ] `CHANGELOG.md` has a dated `[M9 …]` section with a T04
      close-out entry at the top; `[Unreleased]` retained.
- [ ] Root `README.md` milestone table updated; any M9-era links
      still resolve.
- [ ] Manual smoke-test round-trip recorded in CHANGELOG with
      commit sha baseline.
- [ ] Zero `ai_workflows.*` code diff across all M9 tasks
      (packaging-only invariant — audit with `git diff --stat`
      against the M8 T06 baseline commit).
- [ ] `uv run pytest` + `uv run lint-imports` (4 contracts kept) +
      `uv run ruff check` all clean.

## Dependencies

- T01, T02 (shipped or explicitly deferred), T03 all complete.

## Out of scope (explicit)

- Any code change in `ai_workflows/`. M9 is packaging-only; code
  deltas forbidden here. If a finding requires code, it forks to
  M10 or a nice_to_have.md entry.
- Plugin marketplace publishing. That's a distribution event, not
  a close-out event — captured in the release checklist, not M9.
- New workflow registrations. The skill documents whatever is in
  `workflows.list_workflows()` at close-out; new workflows land
  under their own milestones.

## Propagation status

Filled in at audit time. Any deferred finding from M9 audits
propagates either to M10 (carry-over section appended to the
target M10 task spec) or to `nice_to_have.md` with a named
trigger — same discipline as M8 T06.
