# Milestone 9 — Claude Code Skill Packaging

**Status:** ✅ Complete (2026-04-21).
**Grounding:** [architecture.md §4.4](../../architecture.md) · [roadmap.md](../../roadmap.md).

## Goal

Package `ai-workflows` as a Claude Code skill: a thin `.claude/skills/ai-workflows/SKILL.md` that either shells out to `aiw` or calls the MCP server, giving an in-Claude-Code invocation path without coupling the core to Claude Code (which KDR-002 forbids).

## Exit criteria

1. `.claude/skills/ai-workflows/SKILL.md` exists and documents the common `planner` / `slice_refactor` invocations.
2. The skill contains no orchestration logic — every action is a shell-out or an MCP call.
3. Short distribution doc explains how to install the skill and register the MCP server.
4. Manual end-to-end check: invoking the skill from Claude Code runs a workflow via M4's MCP server.

## Non-goals

- Plugin marketplace publishing (out of scope unless the user asks later).
- Skill logic (KDR-002 — Claude Code must remain a consumer, not a substrate).

## Key decisions in effect

| Decision | Reference |
| --- | --- |
| Skills are packaging-only | KDR-002 |
| MCP is the portable surface | KDR-002 |

## Task order

| # | Task | Kind |
| --- | --- | --- |
| 01 | [`.claude/skills/ai-workflows/SKILL.md` + supporting files](task_01_skill_md.md) | doc + test |
| 02 | [Optional plugin manifest (conditional — trigger-gated)](task_02_plugin_manifest.md) | doc + test |
| 03 | [Distribution / install docs](task_03_distribution_docs.md) | doc + test |
| 04 | [Milestone close-out](task_04_milestone_closeout.md) | doc |

Per-task specs drafted 2026-04-21. The milestone was promoted from `📝 Optional` to active on the same day once the decision was made to ship the in-repo skill surface for primary-author use. Task scope stays packaging-only per KDR-002 regardless of when it runs.

## Outcome

All four tasks landed clean. Every task issue file at
[issues/task_0\[1-4\]_issue.md](issues/) carries a `✅ PASS` status
line; no `🔴 HIGH` or `🟡 MEDIUM` is open. T02 is a spec-sanctioned
skip (no trigger fired at kickoff); the other three shipped. No
`nice_to_have.md` deferrals were raised.

**Summary of landed surface:**

- **Skill file ([task 01](task_01_skill_md.md))** —
  [`.claude/skills/ai-workflows/SKILL.md`](../../../.claude/skills/ai-workflows/SKILL.md)
  with YAML frontmatter (`name: ai-workflows` + description) and five
  body sections (*When to use*, *Primary surface — MCP*, *Fallback
  surface — CLI*, *Gate pauses*, *What this skill does NOT do*).
  Packaging-only per KDR-002 — no orchestration logic; every action
  resolves to an MCP tool call or an `aiw` shell-out. KDR-003
  guardrail test-enforced: no `ANTHROPIC_API_KEY` or `anthropic.com/api`
  substring in the skill body. The hermetic suite at
  [`tests/skill/test_skill_md_shape.py`](../../../tests/skill/test_skill_md_shape.py)
  pins presence of the file, frontmatter shape, all four MCP tool
  names, every registered workflow name (read from
  `ai_workflows.workflows.list_workflows()`), and the KDR-003 guardrail
  — five tests.
  Cycle 2 of the audit-implement loop corrected the *Gate pauses*
  paragraph on the Ollama fallback path to name the
  `status="pending"` + `awaiting="gate"` response signal as the
  operator cue (the MCP surface does not expose a `gate_reason` field;
  `RunWorkflowOutput` / `ResumeRunOutput` in
  [`ai_workflows/mcp/schemas.py`](../../../ai_workflows/mcp/schemas.py)
  only project `status` / `awaiting` / `plan` / `total_cost_usd` /
  `error`) and to relocate the failing-tier detail to the LangGraph
  checkpointer state rather than `list_runs` (which returns
  `RunSummary` rows only).
- **Plugin manifest ([task 02](task_02_plugin_manifest.md))** —
  📝 **Deferred (no trigger fired, 2026-04-21).** Spec §*Trigger*
  authorised the skip path explicitly: "If none fire at kickoff,
  skip this task and proceed to T03." A schema check was performed
  anyway to leave accurate facts for a future Builder — real Claude
  Code plugin manifests live at `.claude-plugin/plugin.json` (not at
  the task spec's originally-guessed `.claude/plugins/<name>/plugin.json`)
  and carry only `name` / `description` / `author` (no `version`,
  no `skills` array, no `mcp_servers` block). Findings pinned in the
  task file; re-open if one of the three triggers (marketplace
  distribution, second-host manifest install, internal multi-machine
  distribution need) eventually fires.
- **Distribution doc ([task 03](task_03_distribution_docs.md))** —
  [`design_docs/phases/milestone_9_skill/skill_install.md`](skill_install.md)
  with the five sections the spec called for (§1 Prerequisites, §2
  Install the MCP server, §3 Install the skill, §4 End-to-end smoke,
  §5 Troubleshooting). §2 links to the M4
  [`mcp_setup.md`](../milestone_4_mcp/mcp_setup.md) walk-through
  rather than duplicating it. §3 surfaces Option A (in-repo — default,
  zero extra steps), Option B (user-level symlink), and Option C
  (plugin — marked "not applicable at this revision" with a back-link
  to the T02 task file). §4 pins the exact JSON response shapes for
  `run_workflow` + `resume_run`. §5 includes the fallback-gate
  section aligned with the T01 Cycle 2 correction above (no
  `gate_reason` claim; `cooldown_s` wait named before any
  RETRY-equivalent resume). Root
  [`README.md`](../../../README.md) picks up a single-line pointer
  in its §*MCP server* section, no install-step duplication. Four
  hermetic tests at
  [`tests/skill/test_doc_links.py`](../../../tests/skill/test_doc_links.py)
  pin doc presence, relative-link resolution, root README linkage,
  and the KDR-003 guardrail.
- **Manual verification (close-out time):** the skill + MCP round-trip
  walkthrough in §4 of
  [`skill_install.md`](skill_install.md) was re-read against the
  current working tree at T04 close-out — every relative link still
  resolves on disk (test-enforced by `test_skill_install_doc_links_resolve`
  on every `uv run pytest`), and the MCP server registration steps
  match [M4 `mcp_setup.md`](../milestone_4_mcp/mcp_setup.md) verbatim.
  A live `aiw-mcp`-via-Claude-Code end-to-end invocation was not
  fired at close-out time because the install walk-through itself
  is a pure doc deliverable and `tests/e2e/test_planner_smoke.py`
  already exercises the underlying planner path against real
  providers under `AIW_E2E=1`; M9 adds no new runtime code that a
  fresh smoke would cover. The installation surface is gate-enforced
  by the doc-link tests in `tests/skill/test_doc_links.py`.
- **Packaging-only invariant honoured:** zero `ai_workflows/`,
  `migrations/`, `pyproject.toml` diff across all four M9 tasks
  against the M8 T06 baseline commit
  (`0e6db6e — m8 tasks 1-6 done (milestone close) + m10 planning`).
  Verified at T04 close-out with `git diff --stat 0e6db6e --
  ai_workflows/ migrations/ pyproject.toml` → empty output.
- **Green-gate snapshot (2026-04-21):**
  `uv run pytest` → 596 passed, 5 skipped (4 pre-existing e2e smokes
  plus the live-mode eval replay suite, all gated by `AIW_E2E=1` or
  `AIW_EVAL_LIVE=1`), 2 pre-existing `yoyo` deprecation warnings;
  `uv run lint-imports` → **4 contracts kept** (no new layer
  contract added at M9 — packaging-only milestone touches no
  `ai_workflows.*` module); `uv run ruff check` → clean. Nine new
  tests under `tests/skill/` (5 shape + 4 doc-link) contribute to the
  596 count — the tree moved from 587 (post-M8) to 596 through the
  M9 test additions alone.

### Spec drift observed during M9

One LOW-severity note recorded from the T03 audit for posterity:

- **T03 §5 *Fallback gate fires mid-run* reworded from spec.** The
  T03 spec body said "the skill surfaces `gate_reason` to the user";
  the landed doc does not, because the MCP surface never projected a
  `gate_reason` field (`RunWorkflowOutput` / `ResumeRunOutput` expose
  `status` / `awaiting` / `plan` / `total_cost_usd` / `error` only —
  [`ai_workflows/mcp/schemas.py`](../../../ai_workflows/mcp/schemas.py)).
  The rewording matches the T01 Cycle 2 correction above — names the
  `status="pending"` + `awaiting="gate"` response as the operator
  signal, locates the reason in the LangGraph checkpointer state
  (not `list_runs`), and names the `cooldown_s` wait before any
  RETRY-equivalent resume. Source:
  [issues/task_03_issue.md §Additions beyond spec](issues/task_03_issue.md).

## Carry-over from prior milestones

*None.* M8 T06 closed clean.

## Issues

Land under [issues/](issues/).
