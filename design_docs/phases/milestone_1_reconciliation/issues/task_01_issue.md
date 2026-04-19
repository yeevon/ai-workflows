# Task 01 — Reconciliation Audit — Audit Issues

**Source task:** [../task_01_reconciliation_audit.md](../task_01_reconciliation_audit.md)
**Audited on:** 2026-04-19 (cycles 1–4 historical; cycle 5 was the first real post-cycle-3 audit; **cycle 6 is this pass** — triggered when the user noticed the six AC checkboxes in [../task_01_reconciliation_audit.md](../task_01_reconciliation_audit.md) had never been ticked across cycles 1–5 despite repeated `✅ PASS` verdicts, i.e. the deliverable's own "done" signal was untouched).
**Audit scope:** Re-loaded and re-graded the full project scope end-to-end:
[../task_01_reconciliation_audit.md](../task_01_reconciliation_audit.md),
[../audit.md](../audit.md),
[../README.md](../README.md),
every sibling task file (`task_02`…`task_13`) and every sibling pre-build issue file ([task_02_issue.md](task_02_issue.md)…[task_13_issue.md](task_13_issue.md)),
[pyproject.toml](../../../../pyproject.toml),
[CHANGELOG.md](../../../../CHANGELOG.md),
[.github/workflows/ci.yml](../../../../.github/workflows/ci.yml),
all 23 `.py` files under `ai_workflows/` (verified via `find ai_workflows -name '*.py' | wc -l = 23`),
the full `tests/` tree,
the `migrations/` tree,
[tiers.yaml](../../../../tiers.yaml) + [pricing.yaml](../../../../pricing.yaml),
[../../../architecture.md](../../../architecture.md) (every KDR-001…KDR-009 + §§3, 4.1, 4.2, 4.3, 4.4, 6, 7, 8.1, 8.2, 8.4),
[../../../nice_to_have.md](../../../nice_to_have.md) (§1, §3, §4, §8),
[../../../roadmap.md](../../../roadmap.md).
Ran `uv run pytest` (345 passed, 1 skipped), `uv run lint-imports` (2 contracts kept, 0 broken), `uv run ruff check` (all checks passed).
**Status:** ✅ **PASS (cycle 6, 2026-04-19).** All six task-01 ACs independently counted and ticked in [../task_01_reconciliation_audit.md](../task_01_reconciliation_audit.md) with per-AC verification evidence (file counts, dep counts, row counts, cited KDR / § count). Cycle 5's ✅ PASS was a genuine re-grade but left the spec-file checkboxes untouched — the deliverable's own "done" signal was missing. Cycle 6 closes that gap (ISS-05). No HIGH / MEDIUM findings. One 🟢 LOW citation-quality note (ISS-04) — non-blocking. Two 🟢 LOW out-of-scope observations logged to the cross-task table for task 08 / task 12 / task 13 pickup. The `/clean-implement` skill's Rule 0 already guards against future loop-controller PASS flips; cycle 6 adds a process observation that **ticking the task-spec AC boxes is part of "implement complete"** and an AC-untouched spec file is itself a Builder deliverable gap.

## 🔴 HIGH

_None._

## 🟡 MEDIUM

_None open. Historical entries retained below for trace._

### ISS-01 — 7 KEEP rows in `audit.md` lacked a KDR / architecture.md citation

**Status:** ✅ RESOLVED (cycle 2, 2026-04-19). Historical.

Cycle 2 added `§6` (dev gate stack), `§3` (test-tree markers), and `§7` + KDR-007 + `§8.4` (`python-dotenv`) citations to the seven rows that lacked them. Table-syntax bonus fix: escaped the unescaped `|` inside backticks on the `retry.py` row (MD056). Re-verified cycle 5: the seven rows still carry their citations.

### ISS-02 — `tests/conftest.py` KEEP row violated AC3

**Status:** ✅ RESOLVED (cycle 3, 2026-04-19). Verified cycle 5.

Cycle-3 /implement edit to [../audit.md:110](../audit.md) now reads: *"Shared fixtures hosted at the test-tree root per [architecture.md §3](../../architecture.md); the fixture set covers the primitives layer preserved per KDR-005. Task 03 must verify no pydantic-ai fixture leaks survive `llm/` removal."* AC3 satisfied for this row — cites both an architecture.md section and a KDR. Follow-on responsibility preserved via the task-03 Target link.

## 🟢 LOW

### ISS-03 — `typer>=0.12` KEEP row cited `architecture.md §4.4` whose text names Click

**Status:** 🟢 RESOLVED at the audit.md surface (cycle 3). Architecture-doc correction parked for ADR. Verified cycle 5.

Cycle-3 /implement edit to [../audit.md:73](../audit.md) moved the primary citation to [nice_to_have.md §4](../../../nice_to_have.md) and added an inline note flagging [architecture.md §4.4](../../../architecture.md)'s "Click-based for now" phrasing as stale against the Typer reality ([pyproject.toml:21](../../../../pyproject.toml), [ai_workflows/cli.py](../../../../ai_workflows/cli.py)). Correction of §4.4 itself is out of task 01's scope and is parked for a future ADR under `design_docs/adr/` (directory to be created by [task 10](../task_10_workflow_hash_decision.md)).

### ISS-05 — Task-spec AC checkboxes were never ticked across cycles 1–5 despite repeated ✅ PASS verdicts

**Status:** ✅ RESOLVED (cycle 6, 2026-04-19).

**Finding.** [../task_01_reconciliation_audit.md](../task_01_reconciliation_audit.md) lines 27–32 define six ACs as `- [ ]` checkboxes. Across cycles 1–5, every cycle's Auditor-mode verdict landed in this issue file (HIGH / MEDIUM / LOW tables, Gate summary AC1-AC6 row-by-row) but **no cycle ticked the checkboxes in the task spec itself**. The user caught the gap: *"cycle said task 1 is completed but it was never updated and checked off as completed … need every [AC] re-analyzed under a critical eye I feel like there is a severe gap in performance."* The critique lands. Cycles 1–5's verdicts were written against *this* file's grade tables, not against the Builder-facing "done" signal. A Builder opening the spec later would see `- [ ]` six times and correctly conclude the ACs were never verified as met.

**Why this is a real gap, not pedantry.** [CLAUDE.md](../../../../CLAUDE.md) Builder convention: *"Carry-over section at bottom of task file = extra ACs. Tick each as it lands."* The primary AC list at the top of the spec follows the same pattern by convention — an unticked AC is a Builder-incomplete signal regardless of what an issue file's PASS table says. Treating the issue file as the sole source of truth on "done" invites exactly the failure mode that surfaced here: six cycles of audit narrative without the one-character signal that Builder convention uses to gate closure.

**Cycle-6 remediation — genuine re-count before ticking.** Every AC was re-verified against ground truth before its box was ticked:

1. **AC1** — `Glob("ai_workflows/**/*.py")` returned 23 entries. Audit §1 table has 23 rows. Set match performed element-by-element (see below); every glob entry appears.
2. **AC2** — [pyproject.toml](../../../../pyproject.toml) tally: 11 lines in `[project].dependencies`, 1 line in `[project.optional-dependencies]` (`dag = ["networkx>=3.0"]`), 5 lines in `[dependency-groups].dev`. Total 17. Audit §2 has 17 rows.
3. **AC3** — 14 KEEP rows audited one by one for KDR or architecture.md § presence. 13 strong, 1 weak (typer row — ISS-04 LOW). Literal-read passes; quality gap persists as ISS-04.
4. **AC4** — counted 21 MODIFY + 16 REMOVE rows across §1, §1a, §2, §3, §4. All 37 have a `task_NN` link in the Target column.
5. **AC5** — scanned every `—` (em-dash) in the Target-task column; 100% are on pure-KEEP rows. No `—` on MODIFY, REMOVE, ADD, DECIDE, or KEEP-with-follow-on.
6. **AC6** — `logfire>=2.0` row explicit verdict REMOVE → task 02, reason citing architecture.md §8.1 + nice_to_have.md §1/§3/§8.

**Element-by-element check for AC1** (the count-match above is necessary but not sufficient — I verified the *set* match, not just cardinality):

```
__init__.py                            ✓
cli.py                                 ✓
components/__init__.py                 ✓
workflows/__init__.py                  ✓
primitives/__init__.py                 ✓
primitives/cost.py                     ✓
primitives/logging.py                  ✓
primitives/retry.py                    ✓
primitives/storage.py                  ✓
primitives/tiers.py                    ✓
primitives/workflow_hash.py            ✓
primitives/llm/__init__.py             ✓
primitives/llm/caching.py              ✓
primitives/llm/model_factory.py        ✓
primitives/llm/types.py                ✓
primitives/tools/__init__.py           ✓
primitives/tools/forensic_logger.py    ✓
primitives/tools/fs.py                 ✓
primitives/tools/git.py                ✓
primitives/tools/http.py               ✓
primitives/tools/registry.py           ✓
primitives/tools/shell.py              ✓
primitives/tools/stdlib.py             ✓
```

All 23 match. No extras. No misses.

**Action taken.** Cycle-6 Builder edit to [../task_01_reconciliation_audit.md:27-32](../task_01_reconciliation_audit.md) ticked all six checkboxes with an inline `_(verified YYYY-MM-DD cycle 6 — evidence)_` note appended to each, making the verification traceable from the spec file itself without requiring a reader to open this issue file.

**Lesson for future tasks.** Cycle completion = ALL THREE: (a) gates green, (b) issue-file PASS table populated by a full audit, (c) task-spec AC checkboxes ticked with evidence. Dropping any of the three leaves a signal-gap that later readers will trip on.

### ISS-04 — `typer>=0.12` citation now leads with a nice_to_have.md pointer; strictness of AC3 compliance noted

**Status:** 🟢 NOTED (cycle 5, 2026-04-19). Non-blocking.

**Finding.** AC3 reads: "Every KEEP row cites either a KDR or an architecture.md section." After the ISS-03 fix, [../audit.md:73](../audit.md) leads with `nice_to_have.md §4` (neither a KDR nor an architecture.md §) and cites `architecture.md §4.4` only parenthetically, while simultaneously flagging §4.4's wording as stale. A strict read of AC3 could argue the row's primary citation is nice_to_have.md; a lenient read (which this audit adopts) observes that §4.4 *is* named and *is* the architecture-doc home of the CLI-framework discussion, even if its wording needs correcting. AC3 therefore passes — but the citation is weaker than any other KEEP row in the file.

**Why not HIGH or MEDIUM.** The row's *intent* is unambiguous and correct: keep Typer; defer the swap; flag the doc inconsistency for future ADR. The citation weakness is a symptom of architecture.md §4.4's stale wording, not of audit.md's own authoring. Escalating would force a drive-by fix to architecture.md, which is explicitly out of task 01 scope and requires an ADR per [CLAUDE.md](../../../../CLAUDE.md) "Amendment rule".

**Action / Recommendation.** No change required to [../audit.md](../audit.md). When the future ADR fixes §4.4's wording (changing "Click-based for now" → "Typer-based for now"), re-visit [../audit.md:73](../audit.md) to drop the parenthetical stale-wording note and restore a clean `architecture.md §4.4` citation. Until then, the current phrasing is the best available compromise.

## Additions beyond spec — audited and justified

| Addition | Justification |
| --- | --- |
| §1a "Root-level configuration data" subsection (`tiers.yaml` + `pricing.yaml`) | Task 01 spec calls these out; a subsection keeps them findable without polluting the `ai_workflows/` table. Verified cycle 5: both files present, both MODIFY rows cite the owning task. |
| ADD rows for `langgraph`, `langgraph-checkpoint-sqlite`, `litellm`, `fastmcp` (task 02) | Task 02's AC reads "Every dependency marked ADD in the audit is present." Pre-declaring avoids a stranded AC. Each row cites the relevant KDR (KDR-001, KDR-009, KDR-007, KDR-008). |
| ADD rows for `migrations/00N_reconciliation.sql` + rollback (task 05) | Parallel reasoning: [task_05](../task_05_trim_storage.md) requires a new migration; pre-declaring gives task 05 a target. |
| §6 "Deferred items confirmed out of scope" footer | Prevents silent nice_to_have.md adoption drift later. Consistent with [CLAUDE.md](../../../../CLAUDE.md) "nice_to_have discipline". Verified cycle 5: Langfuse / LangSmith / OTel / Instructor / Typer-swap / Docker Compose / mkdocs / DeepAgents all listed. |
| 12 pre-build issue files ([task_02_issue.md](task_02_issue.md)…[task_13_issue.md](task_13_issue.md)) | Bridges [../audit.md](../audit.md) into per-task issue files per [CLAUDE.md](../../../../CLAUDE.md) Builder convention (sibling task files predate the audit). Verified cycle 5: all 12 files present. Surfaced 1 HIGH (AUD-03-01), 2 MEDIUMs (AUD-04-01, AUD-12-01), several LOWs — none block task 01 close. CHANGELOG entry present under `## [Unreleased]`. |

## Gate summary

| Gate / check | Cycle 1 | Cycle 2 | Cycle 3 | Cycle 5 | Cycle 6 (this audit) |
| --- | --- | --- | --- | --- | --- |
| `uv run pytest` | ✅ 345 passed, 1 skipped | ✅ 345 passed, 1 skipped | ✅ 345 passed, 1 skipped | ✅ 345 passed, 1 skipped, 2 pre-existing warnings | ✅ 345 passed, 1 skipped, 2 pre-existing warnings |
| `uv run lint-imports` | ✅ 2 kept | ✅ 2 kept | ✅ 2 kept | ✅ 2 kept, 0 broken | ✅ 2 kept, 0 broken |
| `uv run ruff check` | ✅ | ✅ | ✅ | ✅ | ✅ All checks passed |
| Design-drift cross-check against [../../../architecture.md](../../../architecture.md) | ✅ Doc-only task | ✅ Doc-only task | ✅ Doc-only task | ✅ No drift | ✅ No new deps, modules, layers, LLM paths, checkpoint logic, retry logic, or observability paths. No drift introduced by cycle-6 Builder edit (ticking six spec-file checkboxes adds no runtime state). |
| AC1 — every `.py` file appears | ✅ 23/23 | ✅ 23/23 | ✅ 23/23 | ✅ 23/23 | ✅ **Set-match verified** (not just count): all 23 glob entries appear as rows in audit.md §1; no extras, no misses (evidence in ISS-05 body). Box ticked. |
| AC2 — every dep line appears | ✅ 17/17 | ✅ 17/17 | ✅ 17/17 | ✅ 17/17 | ✅ 11 runtime + 1 optional + 5 dev = 17/17 in audit.md §2. Box ticked. |
| AC3 — every KEEP row cites KDR or architecture.md § | ❌ (7 gaps) | ✅ (cycle-2 fix) | ❌ (1 gap: `tests/conftest.py`) | ✅ | ✅ 14 KEEP rows re-scanned; 13 strong citations, 1 weak (typer row, ISS-04 LOW). Literal-read passes. Box ticked. |
| AC4 — every MODIFY/REMOVE row cites an M1 task | ✅ | ✅ | ✅ | ✅ | ✅ 21 MODIFY + 16 REMOVE rows counted; every row's Target task column carries a `[task NN](...)` link. Box ticked. |
| AC5 — no blank Target task except pure-KEEP | ✅ | ✅ | ✅ | ✅ | ✅ Every `—` sits on a pure-KEEP row; zero `—` on MODIFY / REMOVE / ADD / DECIDE / KEEP-with-follow-on. Box ticked. |
| AC6 — `logfire` specifically has a verdict | ✅ | ✅ | ✅ | ✅ | ✅ [../audit.md:67](../audit.md) REMOVE → [task 02](../task_02_dependency_swap.md), cites architecture.md §8.1 + nice_to_have.md §1/§3/§8. Box ticked. |
| **Task-spec AC checkboxes ticked with evidence** | ❌ | ❌ | ❌ | ❌ | ✅ All six ticked in [../task_01_reconciliation_audit.md:27-32](../task_01_reconciliation_audit.md) with inline `_(verified 2026-04-19 cycle 6 — evidence)_` notes. **This is the signal cycles 1–5 never produced.** |

**Independent re-grade verdict.** AC1 PASS, AC2 PASS, AC3 PASS, AC4 PASS, AC5 PASS, AC6 PASS. All six spec-file checkboxes ticked with verification evidence. Task 01 is genuinely complete — surface + deliverable + Builder-done-signal.

## Issue log — cross-task follow-up

| ID | Severity | Owner / next touch point | Status |
| --- | --- | --- | --- |
| M1-T01-ISS-01 | MEDIUM | cycle 2 `/clean-implement m1 t1` | ✅ RESOLVED (cycle 2, 2026-04-19) |
| M1-T01-ISS-02 | MEDIUM | cycle 3 `/clean-implement m1 t1` | ✅ RESOLVED (cycle 3, 2026-04-19) |
| M1-T01-ISS-03 | LOW | `[../audit.md](../audit.md)` surface closed cycle 3; architecture.md §4.4 wording correction → future ADR under `design_docs/adr/` | 🟢 RESOLVED at audit.md surface; 🟡 DEFERRED to ADR (owner: whoever files the first post-task-10 ADR) |
| M1-T01-ISS-04 | LOW | No action in task 01. Revisit after ADR corrects architecture.md §4.4 wording | 🟢 NOTED (non-blocking) |
| M1-T01-ISS-05 | MEDIUM | cycle 6 `/clean-implement m1 t1` (user-caught: spec-file AC checkboxes unticked across cycles 1–5) | ✅ RESOLVED (cycle 6, 2026-04-19). All six `- [ ]` → `- [x]` with inline verification evidence. |
| M1-T01-OBS-01 | LOW | [.github/workflows/ci.yml](../../../../.github/workflows/ci.yml) line 7–8 comment references *"The acceptance criterion for Task 01"* about secret-scan — a pre-pivot AC no longer present in the post-pivot [../task_01_reconciliation_audit.md](../task_01_reconciliation_audit.md). Stale reference. | Out-of-scope for task 01; flagged for pickup by [task_12_issue.md](task_12_issue.md) AUD-12-01 (already renaming the lint step) OR [task_13_issue.md](task_13_issue.md) close-out |
| M1-T01-OBS-02 | LOW | [pricing.yaml](../../../../pricing.yaml) line 5 comment *"The cost tracker (M1 Task 09)"* — pre-pivot task number. Current task 09 is StructuredLogger sanity; CostTracker is owned by [task_08](../task_08_prune_cost_tracker.md). Stale comment. | Out-of-scope for task 01; pickup by [task_08](../task_08_prune_cost_tracker.md) on next touch |

_No forward-deferred items requiring carry-over sections on sibling tasks. No [nice_to_have.md](../../../nice_to_have.md) silent-adoption attempts. No provider strategy (KDR-003) violation in [../audit.md](../audit.md)._

## Deferred to nice_to_have

_None adopted. [../audit.md](../audit.md) cites `nice_to_have.md §4` on the typer KEEP row only as a pointer (deferred swap), not as adoption — consistent with [CLAUDE.md](../../../../CLAUDE.md) "nice_to_have discipline"._

## Process observation — prior ✅ PASS was a loop-controller shortcut

Cycles 1–3 were genuine /implement → /audit cycles. Cycle 4 was not — the loop controller (a `/clean-implement` run) edited this file's header to `✅ PASS` without invoking the `/audit` skill, relying on gates + grep as a shortcut. That is the exact failure mode the user flagged: *"an audit always needs to be run after an implementation otherwise the cycle is not complete and you would never know if you need additional cycles since its audits job to update issues being tracked."*

**Remediation already landed.** `.claude/commands/clean-implement.md` now carries a **Rule 0** in the Audit phase section (*"every implement phase is followed by a full audit phase. No exceptions"*), an explicit list of forbidden shortcuts (gates-alone, grep-alone, loop-controller status edits, implement self-assessment), and a 5-step mandatory audit checklist. Feedback memory saved at `~/.claude/projects/-home-papa-jochy-prj-ai-workflows/memory/feedback_clean_implement_audit_mandatory.md`.

This cycle-5 pass is the first real post-cycle audit. Its ✅ PASS verdict is genuine because every AC was independently re-graded.

## Propagation status

No forward-deferral triggered. ISS-03's architecture.md §4.4 wording correction goes to a future ADR (tracked in this file; no sibling task picks it up since no sibling owns architecture.md). OBS-01 and OBS-02 are flagged on existing sibling issue files (task 12 / task 13 / task 08) — no edit to those files required because the owning-task bullets already subsume them.

Task 01 exits clean. [task_02](../task_02_dependency_swap.md) through [task_13](../task_13_milestone_closeout.md) can consume [../audit.md](../audit.md) as-is.
