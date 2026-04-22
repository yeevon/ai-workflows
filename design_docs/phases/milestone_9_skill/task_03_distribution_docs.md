# Task 03 — Distribution / Install Docs

**Status:** 📝 Planned.
**Grounding:** [milestone README §Exit criteria 3–4](README.md) · [M4 mcp_setup.md](../milestone_4_mcp/mcp_setup.md) · [KDR-002](../../architecture.md).

## What to Build

A short user-facing document that walks a fresh user from zero to
invoking `planner` through the skill inside Claude Code. This task
lands **documentation only** — no code, no new tests beyond a doc
link-check, no new dependencies.

The existing [M4 mcp_setup.md](../milestone_4_mcp/mcp_setup.md) already
covers MCP server registration. T03's doc does **not** duplicate it —
it links to it. The new doc's contribution is the skill-install step
plus the end-to-end smoke check (skill + MCP composed).

## Deliverables

### [design_docs/phases/milestone_9_skill/skill_install.md](../../phases/milestone_9_skill/skill_install.md)

Sections:

1. **Prerequisites.** `uv sync` run; `GEMINI_API_KEY` exported;
   `claude` CLI available (for the `planner-synth` / Claude Code
   Opus tier, and for `claude mcp add`). One-line per prereq.
2. **Install the MCP server** — one-line link to
   [M4 mcp_setup.md](../milestone_4_mcp/mcp_setup.md). Do not
   duplicate the walk-through.
3. **Install the skill.**
   - **Option A: in-repo.** The skill travels with the repo —
     `.claude/skills/ai-workflows/SKILL.md` is already under source
     control. Claude Code discovers it automatically when launched
     from the repo root (or any subdirectory).
   - **Option B: user-level.** Symlink or copy
     `.claude/skills/ai-workflows/` into `~/.claude/skills/` so
     every Claude Code session picks it up, regardless of cwd.
     Example symlink command (`ln -s …`) with absolute paths.
   - **Option C (if T02 shipped): plugin.** Link to the plugin
     manifest at `.claude/plugins/ai-workflows/plugin.json` and
     describe the install command Claude Code exposes. Mark
     "Available only if T02 shipped" inline so the doc is honest
     when T02 is deferred.
4. **End-to-end smoke.** From a fresh Claude Code session, ask:
   > "Use the ai-workflows skill to draft a plan for writing a
   > release checklist."

   Expected chain:
   - Claude Code reads `SKILL.md`.
   - Calls `run_workflow(workflow_id="planner", inputs={"goal": "..."})`
     on the MCP server.
   - Pauses at the plan-review gate; Claude Code surfaces the
     draft plan to the user.
   - User approves; Claude Code calls `resume_run(run_id, "approved")`.
   - Final plan returned.

   Record the expected response shapes inline (same JSON shape
   pattern as M4 mcp_setup.md §4).
5. **Troubleshooting.** Three entries:
   - Skill not discovered → check `.claude/skills/ai-workflows/`
     path + `claude --version` + frontmatter shape.
   - MCP server not responding → punt to M4 mcp_setup.md §5.
   - Fallback gate fires mid-run (M8) → link to the M8 outcome
     section; the skill surfaces `gate_reason` to the user; RETRY
     requires waiting the `CircuitBreaker.cooldown_s` interval.

### [README.md](../../../README.md) root-level linkage

Add a single line to the "How to use" section (or equivalent) of the
root README pointing at `skill_install.md`. One line, not a re-copy.

### Tests

[tests/skill/test_doc_links.py](../../../tests/skill/test_doc_links.py):

- `test_skill_install_doc_exists` —
  `design_docs/phases/milestone_9_skill/skill_install.md` resolves.
- `test_skill_install_doc_links_resolve` — every relative link in
  the doc body resolves to an existing file on disk (guards
  against renamed paths in M4 / M8 silently rotting the doc).
- `test_root_readme_links_skill_install` — the root `README.md`
  contains a substring linking to `skill_install.md`.

No live Claude Code round-trip test — that's a manual verification
recorded in T04's CHANGELOG entry (same pattern as M4 T06's
`claude mcp add` verification).

## Acceptance Criteria

- [ ] `design_docs/phases/milestone_9_skill/skill_install.md` exists
      with the five sections above.
- [ ] Root `README.md` links to `skill_install.md` from a single
      contextually appropriate line (not a re-copy of the install
      steps).
- [ ] Every relative link in `skill_install.md` resolves on disk.
- [ ] `skill_install.md` does **not** contain `ANTHROPIC_API_KEY`
      or `anthropic.com/api` — KDR-003 guardrail.
- [ ] No new runtime or dev dependency. No new import-linter
      contract. Four-contract count preserved.
- [ ] `uv run pytest` + `uv run lint-imports` + `uv run ruff check`
      all clean.

## Dependencies

- T01 complete (the doc tells users how to install *something*).
- T02 either complete or explicitly deferred (§3 Option C is
  conditional on T02's shipping).

## Out of scope (explicit)

- A tutorial covering workflow *design*. `skill_install.md` is the
  user's *install* surface; the workflows layer's behaviour is
  documented per-workflow in `ai_workflows/workflows/<name>.py`
  docstrings and milestone READMEs.
- Video walkthroughs, screenshots. Text-only for now.
- Host-specific install variants beyond Claude Code. KDR-002 —
  other hosts read the MCP schema directly; a per-host install
  doc lands only if a user asks.
- Distribution via PyPI / Homebrew / Docker. Deferred. If demand
  appears, lands as a nice_to_have.md trigger, not here.
