# Task 28 — Evaluate server-side `compact_20260112` strategy — Audit Issues

**Source task:** [../task_28_evaluate_server_side_compaction.md](../task_28_evaluate_server_side_compaction.md)
**Audited on:** 2026-04-28
**Audit scope:** Analysis-only deliverable — `design_docs/analysis/server_side_compaction_evaluation.md` (203 lines, 5 sections); `design_docs/nice_to_have.md` §24 entry; CHANGELOG `[Unreleased]` entry; status surfaces (spec line 3, milestone README task pool row line 110, suggested phasing line 148). Cycle 1 of /auto-implement.
**Status:** ✅ PASS

## Design-drift check

No drift detected. T28 is analysis-only — produces one new analysis document plus a `nice_to_have.md` entry plus CHANGELOG. No `ai_workflows/` source code changed, no tests touched, no `pyproject.toml` / `uv.lock` movement, no new module / layer / boundary crossing, no LLM call added, no checkpoint or retry logic, no observability backend, no MCP tool surface change. Layer rule (`primitives → graph → workflows → surfaces`) untouched.

KDR-003 explicitly considered in §4 R5 of the evaluation as a "MEDIUM proximity" risk and is one of the four cited rationales for the DEFER verdict. The verdict therefore actively *protects* KDR-003 rather than threatening it.

## AC grading

| AC | Status | Notes |
| -- | ------ | ----- |
| 1 — Document exists with all 5 sections populated | ✅ Met | `server_side_compaction_evaluation.md` (203 lines). §1 Mechanism, §2 ai-workflows fit (split into §2.1 Surface Fit + §2.2 Loop-Semantics), §3 Composition with T03/T04, §4 Risk Catalogue (5 risks R1–R5), §5 Verdict + Integration Sketch. Each section is substantively populated with multi-paragraph analysis, not stub placeholders. |
| 2 — Verdict (GO / NO-GO / DEFER) surfaced in title or first paragraph | ✅ Met | Line 6 (the deck immediately under the title): `**Verdict: DEFER** — surface mismatch blocks adoption…`. Repeated at §5 (line 143) and the summary table (line 202). |
| 3 — If GO: integration sketch names consuming command(s), threshold, follow-up task | n/a (DEFER) | Verdict is DEFER, so AC-3 does not apply. The document still includes a conditional integration sketch (§5 lines 165–188) — names `auto-implement.md` Auditor spawn block + `clean-implement.md` Auditor spawn block, threshold `trigger.value = 80000 input_tokens`, follow-up task ID T29 (M20 if open, M21 otherwise), MEDIUM 1–2 day effort. This is "nice to have" beyond AC-3 but does no harm. |
| 4 — If DEFER: `nice_to_have.md` has new entry with reopen trigger | ✅ Met | `nice_to_have.md §24` (lines 557–581). Trigger is conjunctive: Claude Code `Task` tool exposes `context_management.edits` in stable release **AND** (T22 telemetry shows >80K Auditor sessions OR Anthropic GA-promotes the strategy). Both conditions must hold. Entry cross-references the evaluation document. |
| 5 — CHANGELOG `[Unreleased]` updated with the prescribed `### Added — M20 Task 28: …` heading and verdict | ✅ Met | `CHANGELOG.md` lines 8–39. Heading exactly matches spec wording (`### Added — M20 Task 28: Server-side compaction evaluation document (design_docs/analysis/server_side_compaction_evaluation.md; verdict DEFER)`). Body cites the surface-mismatch + T03/T04-already-O(1) + beta-stability rationales and lists files touched. |
| 6 — Status surfaces flip together | ✅ Met | (a) spec line 3: `**Status:** ✅ Done (2026-04-28). Verdict: DEFER. See …`; (b) milestone README line 110 task pool row: `✅ Done (DEFER — 2026-04-28)`; (c) milestone README line 148 suggested-phasing prose updated to surface T28 verdict. No `tasks/README.md` exists for this repo so (c)/(d) are n/a; milestone README "Done when" / exit criteria do not list T28 individually so no checkbox flip needed (T28 is an additive Phase A row, not a numbered exit criterion). All four applicable surfaces agree. |

All ACs met. Verdict-quality (Phase 4 sweep below) confirms the document is substantive, not a stub.

## Verdict-quality review

The evaluation's load-bearing factual claim — "Claude Code's `Task` tool does not expose `context_management.edits`" — was independently verified during the audit. The orchestrator surface in `.claude/commands/auto-implement.md` (line 12) is `Task`-tool dispatch (`All substantive work runs in dedicated subagents via Task spawns`). Repo-wide `grep -rn "context_management"` returns only the new T28 documents and an autopilot run-log reference; there is no existing usage anywhere in `ai_workflows/` or `.claude/`. The surface-mismatch claim therefore stands.

The DEFER rationale chain is internally consistent:
- Surface fit fails (factual, verified).
- KDR-003 proximity risk is correctly identified as semantic-coupling concern even if the surface were available.
- T01–T04 already shipped 2026-04-28 (verified — milestone README lines 50–53 all show `[T<NN> Done — 2026-04-28]`); marginal-benefit-low claim is structurally sound.
- Beta stability + untested pause-resume add risk without proportionate gain.

Section 3's "compose-alongside, not replace-some" decision is well-argued and reflects the project's audit-trail-as-first-class invariant. Section 5's reopen trigger is concrete (conjunctive, named-and-measurable on both sides) — exactly what AC-4 calls for.

The evaluation cites specific line ranges in `auto-implement.md` (lines 106–140) and `clean-implement.md` (lines 129–164) for the conditional integration sketch. The actual Auditor spawn block in `auto-implement.md` starts at line 105; the cited range (106–140) is approximate but plausible as future-implementer guidance — minor imprecision, not a defect.

## 🔴 HIGH — none

## 🟡 MEDIUM — none

## 🟢 LOW

### LOW-1 — Section 5 line-number references are approximate

Section 5 of the evaluation document cites `auto-implement.md` "lines 106–140" and `clean-implement.md` "lines 129–164" as the Auditor spawn blocks targeted for any future integration. The actual Auditor-spawn section in `auto-implement.md` starts at line 105 (per `grep -n "Auditor spawn"`); the line ranges are approximate guidance rather than exact pointers. Given that any future T29 implementation will re-locate these blocks anyway (line numbers drift across cycles), the imprecision is harmless.

**Action / Recommendation:** No fix required. Note for any future implementer: re-grep for the Auditor spawn header at integration time rather than trusting the cited line ranges.

## Additions beyond spec — audited and justified

- **§5 conditional integration sketch.** AC-3 explicitly applies only on GO; the spec (line 68) only requires "the trigger that would justify reopening the question" on DEFER. The Builder produced the integration sketch anyway under DEFER. This is additive and non-load-bearing — gives the future implementer a starting point if the trigger fires. No coupling, no complexity added to the codebase. Justified.
- **Summary table at end of evaluation.** Not required by spec but reinforces the verdict at the foot. Harmless.

No drive-by refactors, no `nice_to_have.md` adoption, no scope creep.

## Gate summary

| Gate | Command | Result |
| ---- | ------- | ------ |
| pytest | `AIW_BRANCH=design uv run pytest -q` | PASS — 1021 passed, 7 skipped, 22 warnings (46.18s) |
| lint-imports | `uv run lint-imports` | PASS — Contracts: 5 kept, 0 broken |
| ruff check | `uv run ruff check` | PASS — All checks passed |
| Spec smoke test (lines 88–96) | `test -f … && wc -l … && grep -iE "verdict.*(GO\|NO-GO\|DEFER)"` | PASS — doc exists, 203 lines (≥80), verdict line present (3 hits) |
| Spec smoke test (lines 98–102) | conditional `nice_to_have` check on DEFER | PASS — `nice_to_have entry OK` |

Builder's gate-output is corroborated by re-run from scratch.

## Issue log — cross-task follow-up

None. T28 is analysis-only and self-contained. The DEFER reopen trigger is documented in `nice_to_have.md §24`; if the trigger fires post-M20, a new task T29 (M20 if open, M21 otherwise) is the right vehicle. No carry-over to propagate to a sibling task at this time.

## Deferred to nice_to_have

- **`compact_20260112` server-side compaction adoption.** Already filed by the Builder under `nice_to_have.md §24` (lines 557–581) per AC-4. Trigger: Claude Code `Task` tool exposes `context_management.edits` in stable release AND (T22 telemetry shows long Auditor sessions still hitting >80K tokens OR Anthropic GA-promotes the strategy with a stable parameter name). Both conditions must hold. The deferral is the *task deliverable* itself, not a finding from the audit.

## Propagation status

Not applicable. No forward-deferred items. T28 is analysis-only and the DEFER outcome is filed against `nice_to_have.md` rather than a future task.

## Security review (2026-04-28)

**Scope:** Analysis-only task. Files touched: `design_docs/analysis/server_side_compaction_evaluation.md`, `design_docs/nice_to_have.md` (§24 entry), `CHANGELOG.md`, milestone README, task spec. No `ai_workflows/` source changes. No `pyproject.toml` / `uv.lock` movement.

### Wheel contents (Threat model item 1)

`pyproject.toml` `[tool.hatch.build.targets.wheel]` restricts wheel contents to `packages = ["ai_workflows"]`. Verified against the existing `dist/jmdl_ai_workflows-0.3.1-py3-none-any.whl`: no `design_docs/`, no `analysis/`, no `nice_to_have.md`, no `.env*` present. The new evaluation document (`design_docs/analysis/server_side_compaction_evaluation.md`) and `nice_to_have.md §24` are design-time artifacts only; they cannot reach the published wheel under the current hatchling configuration. No issue.

### KDR-003 alignment (Threat model item 2)

`design_docs/analysis/server_side_compaction_evaluation.md` line 54 explicitly names importing the `anthropic` SDK as a KDR-003 violation and states the migration is "not on the roadmap." Line 135 (R5 — KDR-003 Proximity) cites the specific rule verbatim and uses it as one of four rationale pillars for the DEFER verdict. The DEFER verdict therefore actively enforces KDR-003 rather than creating a path toward violating it. The `nice_to_have.md §24` reopen trigger does not relax this — both trigger conditions require Claude Code to natively expose the surface, not direct Anthropic SDK consumption.

`grep -rn "ANTHROPIC_API_KEY" ai_workflows/` returns zero hits (confirmed). No new SDK import or key-read path introduced by T28 (no source code changed).

### Credentials / secrets in deliverable files (Threat model items 3, 7)

Both `server_side_compaction_evaluation.md` and `nice_to_have.md §24` contain zero real credentials, zero real API keys, and zero secret-bearing examples. The only API key name appearing in the evaluation document (`ANTHROPIC_API_KEY` at lines 54 and 135) appears inside a quoted prohibition statement from the KDR, not as an assignment or usage example. No `Bearer `, no `Authorization`, no key values. No logging or prompt-emission paths introduced (analysis-only, no code).

### `nice_to_have.md` entry readability and safety (Threat model item 4)

`nice_to_have.md §24` (lines 557–581): entry uses placeholder-style prose only, cross-references the evaluation document, states the conjunctive reopen trigger clearly, and contains no secrets or real values. Auditable by any future reviewer without risk.

### 🔴 Critical — must fix before publish/ship

None.

### 🟠 High — should fix before publish/ship

None.

### 🟡 Advisory — track; not blocking

None.

### Verdict: SHIP

## Dependency audit (2026-04-28)

Dependency audit: skipped — no manifest changes. T28 is analysis-only; `pyproject.toml` and `uv.lock` were not modified.

## Sr. SDET review (2026-04-28)

**Test files reviewed:** none — T28 is analysis-only; no test files exist in the diff.
**Skipped (out of scope):** all existing test files (no modifications to review).
**Verdict:** SHIP

## Sr. Dev review (2026-04-28)

**Files reviewed:** `design_docs/analysis/server_side_compaction_evaluation.md` (203 lines, NEW), `design_docs/nice_to_have.md` §24 (lines 557–581, modified), `design_docs/phases/milestone_20_autonomy_loop_optimization/task_28_evaluate_server_side_compaction.md` (spec, for verdict-quality check).
**Skipped (out of scope):** `.claude/commands/autopilot.md`, `.claude/commands/auto-implement.md`, `.claude/commands/clean-implement.md` — confirmed unmodified by T28 (not present in working-tree diff; no `context_management` / `compact_20260112` hits in any of the three files).
**Verdict:** SHIP

### BLOCK — must-fix before commit

None.

### FIX — fix-then-ship

None.

### Advisory — track but not blocking

**Advisory-1 — Surface-fit claim relies on absence-of-evidence, which is sound but could be more precisely grounded** (`design_docs/analysis/server_side_compaction_evaluation.md:46–52`)

The evaluation argues Claude Code's `Task` tool does not expose `context_management.edits` by quoting the orchestrator's description of the `Task` surface and by analogy with the T01 finding about `outputFormat: json_schema`. This is a structurally valid argument — the absence of any `context_management` usage anywhere in the repo, combined with the `Task` tool's documented call signature (spawn prompt + optional tool-list + model override), confirms the claim. However, the evaluation does not cite a primary source for the `Task` tool's public parameter schema (e.g. the Claude Code docs or the tool's introspection output). A future reader auditing the reopen trigger would benefit from knowing where to look to confirm the surface has changed. This is documentation hygiene on an analysis document — not a code bug and not a spec defect.

Action / Recommendation: No fix required before ship. If the evaluation is re-read in the context of the reopen trigger, a one-line note such as "check Claude Code Task tool parameter schema via `claude --help` or the Claude Code changelog" would make the verification path self-contained.

**Advisory-2 — Reopen trigger has a latent ambiguity: condition (b) can fire without condition (a)** (`design_docs/nice_to_have.md:576–577` and `design_docs/analysis/server_side_compaction_evaluation.md:161–163`)

The trigger is stated as conjunctive: condition (a) `Task` tool exposes `context_management.edits` AND condition (b)(i) T22 telemetry shows >80K tokens OR (b)(ii) Anthropic promotes to GA. But the evaluation's §5 prose says "Both conditions must hold: the surface must be accessible AND there must be a demonstrated need." However, sub-condition (b)(ii) — "Anthropic promotes the strategy to GA with a stable parameter name" — does not by itself prove a demonstrated need in ai-workflows; it is about API stability, not token pressure. A future reader could interpret (b)(ii) as a sufficient demonstration of need when it is actually a stability condition, not a need condition. The nice_to_have.md entry is cleaner on this than the evaluation itself (it separates "surface accessible" from "need demonstrated"), but the ambiguity is present in the evaluation's reopen-trigger prose.

Action / Recommendation: Advisory only. The nice_to_have.md entry is the actionable artifact (the evaluation is the supporting analysis). The slight ambiguity in the evaluation prose does not affect the trigger in nice_to_have.md, which is the authoritative deferral record.

**Advisory-3 — T22 not yet shipped; the trigger's (b)(i) condition is a forward reference to an unshipped task** (`design_docs/analysis/server_side_compaction_evaluation.md:161`)

The reopen trigger references "T22 telemetry shows long Auditor sessions still hitting >80K tokens despite T03/T04." T22 is currently at "Candidate" status in the milestone README (not yet implemented). Referencing T22 telemetry as a trigger condition is sound (the evaluation correctly notes T22 as "strongly precedent"), but a reader discovering this entry post-M20 who finds T22 still unshipped would need to know the trigger cannot be evaluated until T22 lands. The nice_to_have.md entry does not note this dependency.

Action / Recommendation: Advisory only. The dependency is implicit and any future reviewer will verify T22 status before evaluating the trigger. No fix required.

### What passed review (one-line per lens)

- Hidden bugs: none — analysis document, no executable code.
- Defensive-code creep: not applicable — no code produced.
- Idiom alignment: not applicable — analysis document uses no framework primitives; no module/class structure to check.
- Premature abstraction: not applicable — no abstractions introduced; the conditional integration sketch in §5 is explicitly conditioned on the DEFER trigger firing and is framed as a starting point, not a committed design.
- Comment / docstring drift: evaluation document structure is well-formed; section headers match the spec's prescribed sections; module-level header cites task and date. No restatement-style comments found.
- Simplification: no simplification opportunities in an analysis document. The summary table at the end is additive and aids skimming; the verdict is repeated in three places (lede, §5 header, summary table) which is appropriate for a decision document consulted at different entry points.

### Scope-creep verification (primary focus for analysis-only tasks)

`git diff HEAD --name-only -- tests/` returned empty. `git status --short -- tests/` returned empty. Zero test files were touched by T28. The working tree shows only design-doc and CHANGELOG modifications:

- `design_docs/analysis/server_side_compaction_evaluation.md` (new, untracked — 203 lines, matches Auditor claim)
- `design_docs/phases/milestone_20_autonomy_loop_optimization/issues/task_28_issue.md` (new, untracked — the issue file itself)
- `design_docs/phases/milestone_20_autonomy_loop_optimization/README.md` (modified)
- `design_docs/phases/milestone_20_autonomy_loop_optimization/task_28_evaluate_server_side_compaction.md` (modified)
- `design_docs/nice_to_have.md` (modified)
- `CHANGELOG.md` (modified)

No `ai_workflows/` source changes. No `pyproject.toml` / `uv.lock` movement. Scope discipline confirmed.

### Auditor gate-claim spot-check

The Auditor reported `pytest -q` → 1021 passed, 7 skipped, 22 warnings. Since no test files and no source files were modified by T28, the suite result is structurally independent of this task's deliverables. The Auditor's full-suite re-run is consistent: a purely analysis-only task cannot break existing tests, and none of the six lenses below surface any test-quality finding (there are no tests to review).

### What passed review (one line per lens)

- Tests-pass-for-wrong-reason: not applicable — no tests added or modified.
- Coverage gaps: not applicable — analysis-only task; no code paths added.
- Mock overuse: not applicable — no tests added or modified.
- Fixture / independence: not applicable — no tests added or modified.
- Hermetic-vs-E2E gating: not applicable — no tests added or modified.
- Naming / assertion-message hygiene: not applicable — no tests added or modified.
