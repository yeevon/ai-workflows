# Task 03 — ADR-0010 + skill-install §Generating-your-own-workflow + docs §Scaffolding

**Status:** 📝 Planned.
**Grounding:** [milestone README](README.md) · [design_docs/adr/](../../../design_docs/adr/) (ADR slot 0010 reserved for M17) · [design_docs/phases/milestone_9_skill/skill_install.md](../milestone_9_skill/skill_install.md) (skill-install doc to extend) · [docs/writing-a-workflow.md](../../../docs/writing-a-workflow.md) (§Scaffolding section to append) · [M16 task_01](../milestone_16_external_workflows/task_01_external_workflow_modules.md) (KDR-013 + ADR-0007 — user-owned code framing this ADR extends).

## What to Build

Three documentation deliverables, doc-only task (zero `ai_workflows/` source changes):

1. **ADR-0010** (`design_docs/adr/0010_user_owned_generated_code.md`) — records the risk-ownership framing, validator-scope decision, write-target safety rules, and rejected alternatives for M17's scaffold_workflow.
2. **`design_docs/phases/milestone_9_skill/skill_install.md` §Generating your own workflow** — end-to-end walkthrough from scaffold invocation to loading the generated file.
3. **`docs/writing-a-workflow.md` §Scaffolding** — explains the scaffold-assisted authoring approach as an alternative to writing a `WorkflowSpec` by hand.

## Deliverables

### 1. `design_docs/adr/0010_user_owned_generated_code.md`

Follows the ADR format already established in `design_docs/adr/`. Must cover:

- **Status:** Accepted (M17, 2026-04-30).
- **Context:** `scaffold_workflow` generates `.py` files on the user's behalf. From the moment a file is written to disk, it is user-owned. The scaffold validates "parseable Python + `register_workflow(spec)` call" only (KDR-004 validator scope). No `lint`, no `pytest`, no `import-linter` is run on the generated artefact before handing it to the user.
- **Decision:** Four binding rules:
  1. Validator scope = schema only (parseable Python + `register_workflow(...)` call shape). Anything beyond that is user territory.
  2. Write-target safety rules: no writes inside `ai_workflows/` (package-safety guard); parent directory must exist + be writable; existing files require `--force`; writes are atomic (`tempfile.mkstemp` + `os.replace`).
  3. Generated code loaded via `AIW_EXTRA_WORKFLOW_MODULES` (M16 load path, KDR-013). ai-workflows surfaces import errors at startup but does not lint, test, or sandbox user code.
  4. No auto-registration. The user restarts `aiw` / `aiw-mcp` to pick up new modules.
- **Alternatives rejected:**
  - *Lint the generated code before handing it over* — increases latency, mismatches the operator-owns-risk framing, imposes ai-workflows' style preferences on the user.
  - *Sandbox the scaffold runtime* — over-engineering for single-user local-only deployment (see CLAUDE.md threat model); no untrusted network consumer.
  - *Keep generated code inside the package* — contradicts KDR-013 (user-owned external workflow code) and the write-safety rules.
- **Consequences:** Users must verify generated code quality themselves. Scaffold prompt engineering (T02) is the primary quality lever. The risk-ownership boundary is clear and mirrors M16's ADR-0007 framing.
- **Related KDRs/ADRs:** KDR-004 (validator pairing), KDR-013 (user-owned external workflow code), ADR-0007 (M16 external workflow load path).

### 2. `design_docs/phases/milestone_9_skill/skill_install.md` — §Generating your own workflow

New section appended after the existing content. Covers the end-to-end scaffold flow:

- **Invocation:** `aiw run scaffold_workflow --goal "..." --target ~/path/workflow.py [--force]` (or `aiw run-scaffold --goal ...`).
- **Review at the gate:** The HumanGate surfaces the full `spec_python` (the generated `.py` content) and a structured summary showing the write target. Displayed in the CLI or surfaced in `RunWorkflowOutput.gate_context` for MCP consumers.
- **Approve or reject:** `aiw resume <run-id> --gate-response approved` writes the file atomically; `--gate-response rejected` aborts without writing. A rejected run can be retried with a refined goal (start a new run).
- **Write path:** On approval, the file is written to `target_path`. The workflow returns `WriteOutcome(target_path, sha256)` confirming the atomic write.
- **`AIW_EXTRA_WORKFLOW_MODULES` handoff:** `PYTHONPATH=~/path AIW_EXTRA_WORKFLOW_MODULES=<dotted_module_name> aiw run <workflow_name> ...` loads the generated file at startup. The module name is the file stem (no `.py`).
- **Where to iterate:** Edit the generated file directly (it is plain Python), then restart `aiw` or `aiw-mcp` to re-register. To regenerate from scratch, run `aiw run scaffold_workflow` with `--force` to overwrite.

### 3. `docs/writing-a-workflow.md` §Scaffolding

Append a new section (e.g. `## Scaffolding a workflow`) to `docs/writing-a-workflow.md`. Explains:
- The scaffold as an alternative starting point for authors who prefer to describe a workflow in plain English rather than writing a `WorkflowSpec` by hand.
- The scaffold produces a `WorkflowSpec` + `register_workflow(spec)` file that the user then loads via `AIW_EXTRA_WORKFLOW_MODULES`.
- Cross-references the skill_install.md §Generating-your-own-workflow walkthrough for the full CLI invocation.
- Notes the scope of the validator (schema only — "parseable Python + `register_workflow()` call") and that the user owns the generated code.

### 4. Status surfaces and CHANGELOG

- Flip task spec `**Status:**` to `✅ Done (<date>)`.
- Flip milestone README task row 03 to `✅ Done`.
- Tick `[ ] ADR-0010 added` and `[ ] Skill-install doc extension` checkboxes in the milestone README exit criteria.
- CHANGELOG: `### Added — M17 Task 03: ADR-0010 + skill-install doc + docs/writing-a-workflow.md §Scaffolding`.

## Acceptance Criteria

- **AC-1 — ADR-0010 created.** `design_docs/adr/0010_user_owned_generated_code.md` exists; covers Status, Context, Decision (four rules), Alternatives rejected (three), Consequences. Cites KDR-004, KDR-013, ADR-0007.
- **AC-2 — skill_install.md extended.** §Generating-your-own-workflow section present; covers invocation, gate review, approve/reject, write path, `AIW_EXTRA_WORKFLOW_MODULES` handoff, iteration.
- **AC-3 — docs/writing-a-workflow.md extended.** §Scaffolding section added (file confirmed to exist at spec-generation time).
- **AC-4 — Status surfaces flipped.** Per-task spec ✅, milestone README task row 03 ✅, milestone README exit criteria for ADR-0010 + skill-install ✅.
- **AC-5 — CHANGELOG updated.**
- **AC-6 — Gates green.** `uv run pytest` + `uv run lint-imports` + `uv run ruff check` all pass (doc-only task — no source changes; gates confirm no regressions from T02 code changes).

## Dependencies

- T01 ✅ (scaffold_workflow implementation provides the context for ADR-0010 and the doc walkthrough).
- T02 ✅ (CS300 dogfood smoke provides the real-world example to reference in skill_install.md; prompt iteration confirms the generated code shape).
- M16 T01 ✅ (ADR-0007 + KDR-013 framing that ADR-0010 extends).

## Out of scope

- Source code changes to `ai_workflows/` (doc-only task).
- Prompt template changes. T02.
- Version bump to 0.4.0. T04.
- Milestone close-out. T04.

## Carry-over from task analysis

- [ ] **TA-LOW-01 — ADR-0007 attribution** (severity: LOW, source: task_analysis.md round 1)
      When updating the M17 milestone README, replace the two `(M16 T03)` references for ADR-0007 with `(M16 T01)`. M16 only shipped T01; ADR-0007 landed there (the milestone had no T03).
      **Recommendation:** Fix as part of T03's doc edits. Specifically: §What M17 ships item 8 and §Risk-ownership-boundary first paragraph in `design_docs/phases/milestone_17_scaffold_workflow/README.md`.

- [ ] **TA-LOW-03 — §Scaffolding placement hint** (severity: LOW, source: task_analysis.md round 1)
      When appending §Scaffolding to `docs/writing-a-workflow.md`, place it after the existing §Minimum viable spec section (around line 68) since both teach the `WorkflowSpec` + `register_workflow(spec)` shape. The §Scaffolding section frames the meta-workflow as an alternative entry point for the same target API.
      **Recommendation:** Builder places the new section immediately after §Minimum viable spec.

## Carry-over to T04

- Version bump: `pyproject.toml` `version` → `"0.4.0"`.
- CHANGELOG promotion: `[Unreleased]` → `## [0.4.0] - <date>`.
- Milestone status flip in `design_docs/roadmap.md`.
