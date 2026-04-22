# Task 04 — Milestone Close-out — Audit Issues

**Source task:** [../task_04_milestone_closeout.md](../task_04_milestone_closeout.md)
**Audited on:** 2026-04-21
**Audit scope:** milestone README flip + Outcome section; roadmap.md row flip; CHANGELOG promotion + T04 close-out entry; root README status + narrative + Next pointer; verification of the packaging-only invariant (zero `ai_workflows/` diff against the M8 T06 baseline commit `0e6db6e`); cross-check of every sibling issue file (task_01/02/03) for propagation holes; full gate suite.
**Status:** ✅ PASS — Cycle 1/10. ISS-01 🟡 MEDIUM **RESOLVED** (2026-04-21) via path 1 — operator walked the live round-trip (`run_workflow → pending/gate → resume_run approved → completed` with full plan artefact) against the registered `aiw-mcp` stdio server; observation recorded in the M9 T04 CHANGELOG entry's *Close-out-time live verification* block. The live smoke surfaced a new 🔴 HIGH finding (ISS-02 — UX defect: MCP surface does not project gate-pause plan, breaking informed human gate review through the skill) that was structurally out of M9's packaging-only scope and **forward-deferred to [M11 T01](../../milestone_11_gate_review/task_01_gate_pause_projection.md)** per user decision (2026-04-21). **ISS-02 ✅ RESOLVED (M11 T01 `<sha>`) on 2026-04-22** — M11 T01 shipped the MCP gate-pause projection (additive at schemas + dispatch; no KDR-002 or KDR-009 violation); audit verdict at [M11 T01 issue file](../../milestone_11_gate_review/issues/task_01_issue.md). [ADR-0004](../../../adr/0004_tiered_audit_cascade.md) captures the broader cascade rationale that M11 unblocked for M12. Gates green; packaging-only invariant verified.

## Design-drift check

Cross-check against [architecture.md](../../../architecture.md) + cited KDRs.

| Concern | Finding |
| --- | --- |
| New dependency | None. `pyproject.toml` diff empty against M8 baseline `0e6db6e`. |
| New `ai_workflows.*` module | None. `git diff --stat 0e6db6e -- ai_workflows/ migrations/ pyproject.toml` returns empty output. Packaging-only invariant honoured (KDR-002). |
| New layer / contract | None. `uv run lint-imports` still reports 4 contracts kept. |
| LLM call added | None. Docs-only close-out. |
| Checkpoint / resume logic | None. |
| Retry logic | None. |
| Observability backend | None. |
| Anthropic API surface | KDR-003 guardrail already test-enforced at T01 + T03; doc edits at T04 add no `ANTHROPIC_API_KEY` / `anthropic.com/api` substring. |
| KDR-002 (packaging-only) | **Honoured across the milestone.** Verified via `git diff --stat 0e6db6e -- ai_workflows/ migrations/ pyproject.toml` → empty. All M9 deliverables land under `.claude/skills/`, `design_docs/phases/milestone_9_skill/`, `tests/skill/`, and root README — none under `ai_workflows.*`. |
| Architecture.md §4.4 / KDR-002 fidelity | M9 README's Outcome section cites KDR-002 by name and pins the invariant. No new architecture surface added; no architecture.md edit required (unlike M8 T06 which expanded §8.4 for the new composition — M9's SKILL.md composes over already-documented M4 tools). |

No drift. No HIGH findings.

## Acceptance criteria grading

| # | Criterion | Verdict |
| --- | --- | --- |
| 1 | Milestone README Status flipped to `✅ Complete` with a date | ✅ [README.md:3](../README.md#L3) now `**Status:** ✅ Complete (2026-04-21).` |
| 2 | Outcome section covers all four tasks with explicit dispositions (especially T02's shipped-or-deferred) | ✅ Outcome section names T01 (shipped + Cycle 2 correction), T02 (📝 **Deferred (no trigger fired, 2026-04-21)** — spec-sanctioned skip path), T03 (shipped + §5 deviation captured), T04 (this close-out). T02's disposition is explicit and traceable. |
| 3 | `roadmap.md` M9 row reflects complete status | ✅ [roadmap.md:22](../../../roadmap.md#L22) now `✅ complete (2026-04-21)`. |
| 4 | `CHANGELOG.md` has a dated `[M9 …]` section with a T04 close-out entry at the top; `[Unreleased]` retained | ✅ `## [Unreleased]` header preserved empty at line 8; `## [M9 Claude Code Skill Packaging] - 2026-04-21` section added at line 10 with `### Changed — M9 Task 04: Milestone Close-out (2026-04-21)` at the very top, followed by the promoted T01 / T02 / T03 entries. |
| 5 | Root `README.md` milestone table updated; any M9-era links still resolve | ✅ [README.md:21](../../../../README.md#L21) row flipped to `Complete (2026-04-21)`. Narrative updated with M9 paragraph + `post-M9` header + Next → M10 pointer. Every relative link in `skill_install.md` still resolves on disk (test-enforced by `tests/skill/test_doc_links.py::test_skill_install_doc_links_resolve` — green). |
| 6 | Manual smoke-test round-trip recorded in CHANGELOG with commit sha baseline | ✅ **Resolved 2026-04-21** — live end-to-end smoke walked from a registered `aiw-mcp` + skill session (`run_workflow(planner, goal='Write a release checklist')` → pending/gate → approve → completed with ten-step plan). Baseline commit `d2df1fa`. Observation recorded in the M9 T04 CHANGELOG entry's *Close-out-time live verification* block. Surfaced ISS-02 (forward-deferred to M11 T01). |
| 7 | Zero `ai_workflows.*` code diff across all M9 tasks (packaging-only invariant) | ✅ `git diff --stat 0e6db6e -- ai_workflows/ migrations/ pyproject.toml` → empty output. |
| 8 | `uv run pytest` + `uv run lint-imports` (4 contracts kept) + `uv run ruff check` all clean | ✅ `pytest` → 596 passed, 5 skipped, 2 yoyo deprecation warnings (pre-existing). `lint-imports` → 4 contracts kept, 0 broken. `ruff check` → clean. |

## 🔴 HIGH

### ISS-02 — MCP surface does not project gate-pause plan; informed human review through the skill is impossible — ✅ RESOLVED

**Severity:** 🔴 HIGH
**Status:** ✅ **RESOLVED (M11 T01 `<sha>`)** (2026-04-22) — replace `<sha>` with the M11 T01 landing commit when it is authored. M11 T01 shipped the MCP gate-pause projection: `RunWorkflowOutput` / `ResumeRunOutput` now carry the in-flight draft `plan` + a `gate_context` projection ({`gate_prompt`, `gate_id`, `workflow_id`, `checkpoint_ts`}) at `status="pending", awaiting="gate"`, and the `gate_rejected` terminal now surfaces the last-draft plan for audit (Gap 1). The `.claude/skills/ai-workflows/SKILL.md` pending-flow section was rewritten to surface the plan + gate_prompt verbatim so the skill never tells the operator *"nothing to check"* again. Audit verdict: [M11 T01 issue file](../../milestone_11_gate_review/issues/task_01_issue.md) → ✅ PASS Cycle 1/10.
**Originally deferred:** 2026-04-21, during the Cycle 1 close-out live smoke (ISS-01 path 1 resolution). Propagation entry landed on the M11 T01 spec + the M11 README's *Carry-over from prior milestones* section.

**Finding.** At the plan-review gate pause, the MCP `RunWorkflowOutput` response is the documented shape `{status: "pending", awaiting: "gate", plan: null, total_cost_usd: 0, error: null}`. The operator's observation during the live smoke was literal: *"paused for human gate review but there is nothing for me to check"*. The `plan` field is `null` by design per [`ai_workflows/mcp/schemas.py:87-90`](../../../../ai_workflows/mcp/schemas.py#L87-L90) — docstring: "`plan` is populated only on `'completed'`". The `ai_workflows.mcp.server` module exposes **zero** `@mcp.resource()` endpoints (grep: only four `@mcp.tool()`s — `run_workflow`, `resume_run`, `list_runs`, `cancel_run`); there is no sibling surface that could project the in-flight plan either. Net effect: the skill's primary flow asks the human to approve/reject without ever showing them the artefact they are gating on. Approving blind completes the round-trip but defeats the purpose of a human-review gate (KDR-001's LangGraph-native `interrupt()` was meant for *informed* human intervention).

This is a structural gap in the **M4 MCP surface**, inherited by the M9 skill at the moment the skill created a primary user-facing path. M9 itself is faithful to KDR-002 (packaging-only); the skill text accurately describes what the MCP surface returns. The defect is upstream of M9 and has always been there — M9's live smoke was the first time anyone exercised the full human-facing flow end-to-end.

**Scope.** Fix requires code changes outside M9's packaging-only invariant. Three plausible implementations:

1. **New `get_run_state(run_id)` MCP tool** returning the current LangGraph checkpointer state (filtered to the caller-facing subset: gate prompt + current plan view). Minimal surface addition; explicit caller invocation from the skill at gate pause.
2. **New MCP resource** (e.g. `aiw://runs/<run_id>/state`) projecting the same subset. Aligns with MCP's resource/tool split; lets hosts auto-subscribe.
3. **Resemantise `RunWorkflowOutput.plan`** to project the in-flight plan view at `status="pending"` + `awaiting="gate"`, not just on terminal. Smallest wire change; but re-semanticises an existing field (backwards-compat concern).

All three are code deltas under `ai_workflows/mcp/`, with schema + test + docs implications.

**Action / Recommendation — RESOLVED via path (b) on 2026-04-21:**

User picked option (b): new **M11 "MCP gate-review surface"** milestone. See [milestone_11_gate_review/README.md](../../milestone_11_gate_review/README.md) + [task_01_gate_pause_projection.md](../../milestone_11_gate_review/task_01_gate_pause_projection.md). Adjacent architectural thread (tiered audit cascade) captured in [ADR-0004](../../../adr/0004_tiered_audit_cascade.md) + [M12](../../milestone_12_audit_cascade/README.md). Original options for historical reference:

- **(a) New task under M10** — rejected as thematically mismatched (M10 is Ollama-specific).
- **(b) New milestone M11 "MCP gate-review surface"** — **selected**. Cleanest scope separation from M10 and M12.
- **(c) `nice_to_have.md` entry with named trigger** — rejected per CLAUDE.md *nice_to_have discipline*: trigger has fired.

## 🟡 MEDIUM

### ISS-01 — Live end-to-end smoke not fired at close-out time

**Severity:** 🟡 MEDIUM
**Status:** ✅ **RESOLVED (2026-04-21)** — path 1. Operator walked the live round-trip (`run_workflow(planner, goal='Write a release checklist')` → `{status: "pending", awaiting: "gate", plan: null, total_cost_usd: 0, error: null}` → approve → `status="completed"` with full ten-step release-checklist plan artefact) against the registered `aiw-mcp` stdio server. Observation recorded in the M9 T04 CHANGELOG entry's *Close-out-time live verification* block. Baseline commit: `d2df1fa` (HEAD at smoke time).
**AC impacted:** AC-6 (Manual smoke-test round-trip recorded in CHANGELOG).

**Finding.** The T04 spec §*Deliverables → README.md → Manual verification* is explicit:

> Manual verification: end-to-end smoke run once at close-out time from a fresh Claude Code session (skill discovered → `run_workflow(planner)` → gate pause → `resume_run` → completed plan). Record the commit sha baseline + pass/fail observation — mirrors M4 T06's `claude mcp add` round-trip pattern.

The landed CHANGELOG entry records the commit sha baseline (`0e6db6e`) and documents a packaging-only-invariant verification (`git diff --stat 0e6db6e -- ai_workflows/ migrations/ pyproject.toml` → empty) plus a link-resolution continuous gate (`tests/skill/test_doc_links.py::test_skill_install_doc_links_resolve`), but explicitly states:

> A live `aiw-mcp`-via-Claude-Code end-to-end invocation was not fired at close-out time: M9 adds no runtime code that a fresh smoke would cover, and `tests/e2e/test_planner_smoke.py` already exercises the underlying planner path against real providers under `AIW_E2E=1`.

That reasoning has technical merit (M9 is truly packaging-only, no runtime code delta, and the underlying planner path is E2E-covered elsewhere), but it is not what AC-6 literally requires. M8 T06's close-out precedent walked a live degraded-mode smoke and recorded the pass/fail observation in the CHANGELOG's *Close-out-time live verification* block — M9 T04 was written to mirror that pattern verbatim.

The live smoke can only be performed by the human operator (it requires a fresh Claude Code session with the skill + MCP server registered, operator interaction with the gate pause, and the operator's own pass/fail call).

**Action / Recommendation.** Stop and ask the user. Two reasonable paths:

1. **Fire the smoke.** Operator walks `skill_install.md §4` in a fresh Claude Code session (or their currently-live session if the `ai-workflows` skill + `aiw-mcp` are already registered): draft a plan via the skill → gate pauses → approve → completed plan. Operator reports pass/fail. Then the T04 Builder appends a *Close-out-time live verification (2026-04-21)* block to the existing M9 T04 CHANGELOG entry (mirrors M8 T06's block verbatim), flips ISS-01 → `RESOLVED`, and re-runs gates.
2. **Formally deviate.** Operator accepts the documented reasoning (M9 adds no runtime code; `test_planner_smoke.py` covers the underlying path; `test_skill_install_doc_links_resolve` gate-enforces doc accuracy continuously) and the AC's live-smoke clause is formally waived. The Builder then edits the spec's Manual-verification line + AC-6 to reflect the waiver, flips ISS-01 → `RESOLVED (waiver, commit sha)` with the user's approval recorded, and closes.

**Why stop-and-ask:** per CLAUDE.md *Every issue carries a proposed solution* → "If the fix is unclear (two reasonable options, crosses milestones, needs spec change) — stop and ask the user before finalising." AC-6 is a standing spec requirement; silently accepting path (2) without an explicit user waiver would be silent spec drift.

## 🟢 LOW

*None.*

## Additions beyond spec — audited and justified

- **Packaging-only-invariant verification block** added to the M9 README Outcome section and the T04 CHANGELOG entry. Not spelled out in the T04 spec deliverables list, but directly implements AC-7 ("Zero `ai_workflows.*` code diff across all M9 tasks — audit with `git diff --stat` against the M8 T06 baseline commit"). The spec's own AC-7 calls for this audit step; surfacing the `git diff --stat 0e6db6e -- ai_workflows/ migrations/ pyproject.toml` → empty observation in both surfaces makes the invariant reviewable without re-running the command. Strengthens the audit surface; no scope widening.
- **Per-task propagation status** captured in the Outcome section's per-task bullets (T01 Cycle 2 correction, T02 schema-check pinning, T03 §5 deviation) rather than in a standalone *Spec drift observed during M9* block like M8 T06 had. The M9 drift surface is smaller than M8's (one LOW note vs. two LOW notes at M8), so a dedicated block would be sparse. The M9 README still has a *Spec drift observed during M9* subsection listing the single T03 note for posterity. Style choice only; does not affect AC coverage.

## Sibling-task propagation check (pre-close-out)

Per T04 spec §*Audit-before-close check* equivalent (inherited from M8 T06). Every M9 task issue file opened + verified:

| Issue file | Status | OPEN HIGH/MEDIUM? | Propagation holes? |
| --- | --- | --- | --- |
| [issues/task_01_issue.md](task_01_issue.md) | ✅ PASS (Cycle 2) | None. ISS-01 🟢 LOW RESOLVED. | None. |
| [issues/task_02_issue.md](task_02_issue.md) | ✅ PASS (Cycle 1) | None (deferred disposition; zero shipped manifest). | None — schema-check findings pinned in task_02_plugin_manifest.md for a future Builder. |
| [issues/task_03_issue.md](task_03_issue.md) | ✅ PASS (Cycle 1) | None. | None — §5 deviation is resolved in-task and logged in both the issue file and the T03 CHANGELOG entry. Already surfaced in the M9 README *Spec drift* subsection. |
| [issues/task_04_issue.md](task_04_issue.md) | ⚠️ OPEN (Cycle 1) | ISS-01 🟡 MEDIUM — USER INPUT REQUIRED. | N/A (this file). |

No forward-deferred findings to M10 or `nice_to_have.md` from M9 audits. T04's ISS-01 is an in-task open item, not a forward deferral.

## Gate summary

| Gate | Result |
| --- | --- |
| `uv run pytest` | ✅ 596 passed, 5 skipped, 2 pre-existing yoyo warnings |
| `uv run lint-imports` | ✅ 4 contracts kept, 0 broken |
| `uv run ruff check` | ✅ clean |
| `git diff --stat 0e6db6e -- ai_workflows/ migrations/ pyproject.toml` | ✅ empty output (packaging-only invariant) |
| KDR-003 guardrail (doc bodies) | ✅ test-enforced by `test_skill_md_shape.py::test_skill_md_forbids_anthropic_api` + `test_doc_links.py::test_skill_install_doc_forbids_anthropic_api` |
| Sibling-task propagation check | ✅ all three sibling issue files PASS; no HIGH/MEDIUM open |

## Issue log

| ID | Severity | Status | Owner |
| --- | --- | --- | --- |
| M9-T04-ISS-01 | 🟡 MEDIUM | ✅ RESOLVED (2026-04-21) | path 1 — live smoke walked; recorded in CHANGELOG |
| M9-T04-ISS-02 | 🔴 HIGH | ✅ RESOLVED (M11 T01 `<sha>`) | M11 T01 shipped 2026-04-22; `<sha>` stamped at commit time |

## Deferred to nice_to_have

*None.*

## Propagation status

- **ISS-01** — resolved in-task on 2026-04-21 via path 1 (live smoke walked). No forward deferral.
- **ISS-02** — ✅ RESOLVED via M11 T01 on 2026-04-22 (`<sha>` stamped at commit time). M11 T01 shipped the MCP gate-pause projection (schemas + dispatch helpers + skill-text + six new tests); see the [M11 T01 audit issue file](../../milestone_11_gate_review/issues/task_01_issue.md) for the AC-by-AC verdict. Back-link from M11 T01: this issue file closes the ISS-02 loop. No `nice_to_have.md` entry — per CLAUDE.md *nice_to_have discipline* this trigger fired and resolved. Adjacent architectural thread (tiered audit cascade, which depends on the M11 projection to surface audit-escalation transcripts at the gate) captured in [ADR-0004](../../../adr/0004_tiered_audit_cascade.md) + [M12](../../milestone_12_audit_cascade/README.md). The M12 cascade work can now assume `gate_context` is populated at every strict-review gate pause and extend the dict with cascade-transcript keys without a schema break (KDR-008 additive-field contract).
