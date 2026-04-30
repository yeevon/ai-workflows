# Task 03 issue file — ADR-0010 + skill-install doc + docs/writing-a-workflow.md §Scaffolding

## Cycle 1 build report

**Date:** 2026-04-30
**Builder:** Claude Sonnet 4.6
**Task:** M17 T03 — ADR-0010 + skill-install §Generating-your-own-workflow + docs §Scaffolding
**Verdict:** BUILT

---

### Files written / modified

| File | Action |
|---|---|
| `design_docs/adr/0010_user_owned_generated_code.md` | NEW — ADR-0010 full text |
| `design_docs/phases/milestone_9_skill/skill_install.md` | EXTENDED — §7 Generating your own workflow appended |
| `docs/writing-a-workflow.md` | EXTENDED — `## Scaffolding a workflow` section inserted after `### Minimum viable spec` |
| `design_docs/phases/milestone_17_scaffold_workflow/README.md` | UPDATED — task row 03 ✅, exit-criteria ADR-0010 + skill-install ticked, `(M16 T03)` → `(M16 T01)` |
| `design_docs/phases/milestone_17_scaffold_workflow/task_03_adr_and_docs.md` | UPDATED — Status ✅, TA-LOW-01 + TA-LOW-03 carry-over ticked |
| `CHANGELOG.md` | UPDATED — M17 T03 entry under [Unreleased] |

---

### AC satisfaction

| AC | Description | Status |
|---|---|---|
| AC-1 | `design_docs/adr/0010_user_owned_generated_code.md` exists; Status/Context/Decision (4 rules)/Alternatives rejected (3)/Consequences; cites KDR-004, KDR-013, ADR-0007 | ✅ |
| AC-2 | skill_install.md §7 Generating-your-own-workflow present; covers invocation, gate, approve/reject, write path, AIW_EXTRA_WORKFLOW_MODULES, iteration | ✅ |
| AC-3 | docs/writing-a-workflow.md §Scaffolding a workflow present; placed after §Minimum viable spec (TA-LOW-03) | ✅ |
| AC-4 | Status surfaces: spec ✅, README row 03 ✅, README exit-criteria ADR-0010 + skill-install ✅ | ✅ |
| AC-5 | CHANGELOG updated | ✅ |
| AC-6 | Gates green: `uv run pytest` 1510 passed / 12 skipped; `uv run lint-imports` 5 kept / 0 broken; `uv run ruff check` all checks passed | ✅ |

### Carry-over satisfied

- **TA-LOW-01** — Corrected single remaining `(M16 T03)` reference for ADR-0007 in `README.md` §Risk-ownership-boundary to `(M16 T01)`. Note: the task spec said "two `(M16 T03)` references" but only one remained at build time — the §What M17 ships item 8 reference had already been cleared by prior T01/T02 work (item 8 contains only "ADR-0010" without attribution). The single remaining instance was corrected.
- **TA-LOW-03** — `## Scaffolding a workflow` placed immediately after `### Minimum viable spec` in `docs/writing-a-workflow.md`, not appended at the end of the file.

---

### Deviations from spec

1. **builder-only link markers required.** The docs link checker (`tests/docs/test_docs_links.py`) enforced that every relative link to `design_docs/` in `docs/` carries a `(builder-only, on design branch)` marker on the same line. The task spec did not mention this convention. Two links in the new `§Scaffolding a workflow` section were caught by the gate on first run and fixed before handoff:
   - `[ADR-0010](../design_docs/adr/0010_user_owned_generated_code.md)` — marker added.
   - `[skill_install.md §Generating your own workflow](../design_docs/phases/milestone_9_skill/skill_install.md#7-generating-your-own-workflow)` — marker added.
   This is not a spec deviation per se — it is the project's existing docs-link convention applied consistently.

2. **Only one `(M16 T03)` reference found.** The carry-over TA-LOW-01 said "two references." At build time only one remained (§Risk-ownership-boundary line 36). The §What M17 ships item 8 had no `(M16 T03)` attribution at all. Both the existing reference and any absence are now consistent with `(M16 T01)`.

---

### Planned commit message

```
M17 Task 03: ADR-0010 + skill-install doc + docs/writing-a-workflow.md §Scaffolding (KDR-004, KDR-013)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

---

## Cycle 1 audit

**Source task:** `design_docs/phases/milestone_17_scaffold_workflow/task_03_adr_and_docs.md`
**Audited on:** 2026-04-30
**Audit scope:** doc-only deliverables (ADR-0010, skill_install §Generating-your-own-workflow, docs/writing-a-workflow.md §Scaffolding, status surfaces, CHANGELOG, TA-LOW-01 + TA-LOW-03 carry-overs).
**Status:** ✅ PASS

### Design-drift check

No drift detected. ADR-0010 cites and reinforces KDR-004 (validator pairing — schema-only scope) and KDR-013 (user-owned external workflow code) and extends ADR-0007's hands-off framing. No new dependencies. No new module/layer. No LLM-call additions. No checkpoint or retry logic touched. No MCP-tool surface change. No `anthropic` SDK or `ANTHROPIC_API_KEY` references introduced. Doc-only task — no `ai_workflows/` source changed (verified: zero diff under `ai_workflows/`).

### AC grading

| AC | Status | Notes |
|---|---|---|
| AC-1 ADR-0010 | ✅ met | `design_docs/adr/0010_user_owned_generated_code.md` exists; Status (Accepted, M17, 2026-04-30); Context (validator scope / write-target safety / post-write lifecycle); Decision with four binding rules (validator scope; write-target safety; AIW_EXTRA_WORKFLOW_MODULES handoff per KDR-013; no auto-registration); three Rejected alternatives (lint generated code; sandbox scaffold runtime; keep generated code inside package); Consequences; Related cites KDR-004, KDR-013, ADR-0007. |
| AC-2 skill_install §Generating-your-own-workflow | ✅ met | §7 covers invocation (both `aiw run scaffold_workflow` and `aiw run-scaffold` aliases), gate review (CLI + MCP `gate_context`), approve/reject (with atomic write semantics), write path (four safety guards mirrored from ADR-0010 Rule 2), `AIW_EXTRA_WORKFLOW_MODULES` handoff (PYTHONPATH + module-stem guidance + editable-install variant), iteration (edit-direct / regenerate-with-force / docs cross-ref). |
| AC-3 docs/writing-a-workflow.md §Scaffolding | ✅ met | `## Scaffolding a workflow` at line 96, immediately after `### Minimum viable spec` at line 68 (TA-LOW-03 satisfied). Sub-sections cover what the scaffold produces, validator scope/ownership (cites KDR-004 + ADR-0010), full CLI walkthrough cross-ref to skill_install, plus a `(builder-only, on design branch)` marker on each `design_docs/` link per docs link-checker convention. |
| AC-4 Status surfaces | ✅ met | (a) spec `**Status:** ✅ Done (2026-04-30).`; (b) milestone README task table row 03 = `✅ Done`; (c) `tasks/README.md` not present for M17 (n/a); (d) milestone README exit criteria `[x] Skill-install doc extension` + `[x] ADR-0010 added` ticked. Four surfaces consistent. |
| AC-5 CHANGELOG | ✅ met | `### Added — M17 Task 03: ADR-0010 + skill-install doc + docs/writing-a-workflow.md §Scaffolding (2026-04-30)` under `[Unreleased]` with file-list bullets covering all six modified paths. |
| AC-6 Gates | ✅ met | Re-ran from scratch: `uv run pytest` → 1510 passed / 12 skipped (matches Builder); `uv run lint-imports` → 5 kept / 0 broken; `uv run ruff check` → All checks passed. |
| TA-LOW-01 ADR-0007 attribution | ✅ met | §Risk-ownership-boundary line 36 reads `ADR-0007 (M16 T01)`. Spec called out "two `(M16 T03)` references"; Builder correctly noted only one existed at build time (item 8 of §What-M17-ships had no attribution suffix). Audited line 47 (item 8): contains `**ADR-0010 — user-owned generated code.**` with no stale attribution; nothing to fix. Builder's deviation note is accurate. |
| TA-LOW-03 §Scaffolding placement | ✅ met | §Scaffolding at line 96, immediately after §Minimum viable spec (line 68). No content interposed between them other than the §Minimum viable spec example code block. Placement matches spec recommendation. |

### Phase 4 critical sweep

- **Diff-vs-checkbox.** Both `[x]` carry-overs (TA-LOW-01, TA-LOW-03) have corresponding diff hunks in this cycle (README line-36 edit; new `## Scaffolding a workflow` section in `docs/writing-a-workflow.md`). No cargo-cult ticking.
- **Cycle-overlap detection.** No cycle-0 issue file exists for T03 (this is the first audit cycle). Loop-spinning check N/A.
- **Rubber-stamp detection.** Diff exceeds 50 lines (~530 lines added across ADR + skill_install §7 + writing-a-workflow §Scaffolding + README/spec/CHANGELOG edits) and verdict is PASS with zero HIGH+MEDIUM findings — so the trigger fires. Justification for PASS: every AC has a verifiable artefact on disk; gate re-runs reproduced Builder's results exactly; ADR text was line-by-line cross-checked against the four-rule spec; placement / cross-references / `(builder-only, on design branch)` markers were grep-verified; no source code touched (lowest possible regression surface). Doc-only tasks are inherently low-risk for rubber-stamping.
- **Status-surface drift.** None — four surfaces aligned (spec, milestone README task row, exit criteria, no `tasks/README.md` for M17).
- **Doc drift.** Cross-references between writing-a-workflow.md → skill_install.md §7 and writing-a-workflow.md → ADR-0010 verified to resolve (paths exist; anchors `#7-generating-your-own-workflow` consistent with the H2 `## 7. Generating your own workflow` heading slugification).
- **Scope creep.** None. ADR-0010 stays within risk-ownership framing; no nice_to_have.md item promoted; explicit non-goals respected (no lint/test/sandbox of generated code).
- **Test gaps.** Doc-only task; AC-6 confirms regression suite still green. T01 + T02 already shipped behavioural tests for the scaffold itself.
- **Secrets shortcuts.** None — no API keys, no `.env` references, no provider-credential surfaces.
- **Builder schema conformance.** Builder return text + issue file Cycle 1 build report follow expected format. Two declared deviations are minor and correctly characterised (link-checker markers were already-existing project convention; one-vs-two `(M16 T03)` references reconciled by inspection).

### Additions beyond spec — audited and justified

- `(builder-only, on design branch)` markers on the two `design_docs/` cross-references in `docs/writing-a-workflow.md` §Scaffolding. Justified: enforced by `tests/docs/test_docs_links.py` link-checker; consistent with existing convention applied to all other ADR cross-references in the same file (lines 567-568, 658). Not a spec deviation.

### Gate summary

| Gate | Command | Result |
|---|---|---|
| pytest | `uv run pytest` | PASS — 1510 passed / 12 skipped |
| lint-imports | `uv run lint-imports` | PASS — 5 kept / 0 broken |
| ruff | `uv run ruff check` | PASS — all checks passed |

### Issue log — cross-task follow-up

None this cycle. No HIGH / MEDIUM / LOW findings raised.

### Deferred to nice_to_have

None this cycle.

### Propagation status

T04 spec does not yet exist (per "Per-task specs land as each predecessor closes" convention in milestone README). T03's existing `## Carry-over to T04` section (version bump → 0.4.0; CHANGELOG promotion `[Unreleased]` → `## [0.4.0] - <date>`; roadmap milestone status flip) is the carry-over channel; it will be folded into T04's spec at task-analysis time. No additional forward-deferrals from this audit.

---

## Sr. SDET review (2026-04-30)
**Test files reviewed:** `tests/workflows/test_scaffold_workflow.py`, `tests/docs/test_writing_workflow_snippets.py`, `tests/docs/test_docs_links.py`, `tests/test_scaffolding.py` | **Skipped:** none | **Verdict:** SHIP

### What passed review (one line per lens)

- **Wrong-reason (Lens 1):** No trivial assertions, tautologies, or mock-driven tautologies found. All test assertions in `tests/workflows/test_scaffold_workflow.py` exercise real code paths — `validate_scaffold_output`, `atomic_write`, `validate_target_path`, and the full graph stub-adapter integration. No concern.
- **Coverage gaps (Lens 2):** Doc-only task; T01+T02 shipped the behavioural test suite. The new §Scaffolding a workflow section in `docs/writing-a-workflow.md` is covered by `tests/docs/test_docs_links.py` (link-resolution + builder-only markers) and `tests/docs/test_writing_workflow_snippets.py::test_all_python_blocks_compile` (all ```python blocks compile). No new code path was added — coverage gap is not applicable.
- **Mock overuse (Lens 3):** `_StubLiteLLMAdapter` correctly targets `tiered_node_module.LiteLLMAdapter` (the import site, not the source module). `SQLiteStorage.open(tmp_path / "storage.sqlite")` used in-process — no `aiosqlite` mock. Pattern is correct.
- **Fixture hygiene (Lens 4):** Three `autouse=True` fixtures (`_reset_stub`, `_reensure_scaffold_registered`, `_redirect_default_paths`) correctly scope to the test function. No ordering dependency, no monkeypatch leak. `_StubLiteLLMAdapter.reset()` called both before and after the yield — no bleed.
- **Hermetic gating (Lens 5):** No network calls without `AIW_E2E=1` / `AIW_EVAL_LIVE=1` gate. All scaffold tests stub `LiteLLMAdapter`. `tests/release/test_scaffold_live_smoke.py` exists but is in `tests/release/` (runs by default only for release smoke — acceptable). No subprocess calls to real providers in hermetic suite.
- **Naming + assertion hygiene (Lens 6):** Test names are descriptive (`test_validator_rejects_syntactically_invalid_python`, `test_atomic_write_overwrites_only_on_replace`, etc.). Complex dict assertions include `result.output` in context. No bare `pytest.skip()` without reason.

### Advisory

**Advisory 1 — `test_doc_section_order` does not pin `## Scaffolding a workflow`**
File: `tests/docs/test_writing_workflow_snippets.py:732`
The `_EXPECTED_SECTIONS` list hardcodes the 9 sections from the M19 rewrite. The new `## Scaffolding a workflow` section added by M17 T03 is a `##`-level heading between `## The WorkflowSpec shape` and `## Worked example` but is not listed in `_EXPECTED_SECTIONS`. A future edit could silently reorder or remove it without a test catching the regression.
Action: add `"## Scaffolding a workflow"` to `_EXPECTED_SECTIONS` between `"## The \`WorkflowSpec\` shape"` and `"## Worked example"`. Advisory (Lens 6).

**Advisory 2 — No hermetic pin that `docs/writing-a-workflow.md §Scaffolding` mentions `ADR-0010` by name**
File: `tests/docs/test_writing_workflow_snippets.py` (no such test)
`test_docs_links.py` verifies the `ADR-0010` link resolves; `test_all_python_blocks_compile` verifies the bash block compiles. But no test pins the text-presence of `KDR-004` or `ADR-0010` by name in the section — a future edit stripping the citations would not be caught.
Action: add `assert "ADR-0010" in doc_text` and `assert "KDR-004" in doc_text` in `test_writing_workflow_snippets.py`. Low priority; advisory (Lens 2 in-scope advisory only).

### Findings

- **BLOCK:** none
- **FIX:** none
- **Advisory:** 2 (section-order pin gap, ADR citation text-presence gap)

---

## Sr. Dev review (2026-04-30)

**Files reviewed:** `design_docs/adr/0010_user_owned_generated_code.md`, `design_docs/phases/milestone_9_skill/skill_install.md` (§7 only), `docs/writing-a-workflow.md` (§Scaffolding only), `design_docs/phases/milestone_17_scaffold_workflow/README.md`, `design_docs/phases/milestone_17_scaffold_workflow/task_03_adr_and_docs.md`, `CHANGELOG.md` | **Skipped:** none | **Verdict:** FIX-THEN-SHIP

---

### 🔴 BLOCK

None.

---

### 🟠 FIX

**FIX-1 — Inaccurate CLI command: `aiw list-runs --run-id` does not exist**

`design_docs/phases/milestone_9_skill/skill_install.md` lines 274–275:

> Via CLI, the gate response appears in `aiw list-runs --run-id scaffold-qg-1`.

`aiw list-runs` (cli.py:683–704) accepts `--workflow`, `--status`, and `--limit` only. There is no `--run-id` parameter on this command. A user copying this command will get a Typer "No such option: --run-id" error.

The gate content during a paused run is shown by `aiw run` itself via its stdout print (cli.py:423: `resume with: aiw resume {run_id} --gate-response <approved|rejected>`) — the gate state is not separately queryable per run-id via `list-runs`. The accurate statement is that the gate pause is visible in the stdout of the original `aiw run` invocation; the user can also call `aiw list-runs --workflow scaffold_workflow --status gate` to find paused runs, but not filter by run-id.

**Lens:** Lens 1 (hidden bug that passes tests — doc accuracy).
**Action:** Replace the inaccurate prose. Suggested replacement:

> Via CLI, the gate pause is reported in the `aiw run` stdout (which prints the `run_id` and the `spec_python` preview). Paused runs can also be found with `aiw list-runs --workflow scaffold_workflow --status gate`.

---

### 🟡 Advisory

**ADV-1 — ADR-0010 Context §3 tension label ("Post-write lifecycle") slightly overstates the framework's scope**

`design_docs/adr/0010_user_owned_generated_code.md` lines 27–29 frame "Post-write lifecycle" as one of three tensions the ADR resolves. The decision (Rule 3 + Rule 4) is correct. The tension label implies the framework is choosing how much of the lifecycle to own — but the Rules are pure hands-off. Advisory only: the text is coherent as written; a one-word change ("Post-write handoff framing") would sharpen the intent.

**Lens:** Lens 5 (comment/docstring drift — label imprecision).

**ADV-2 — `docs/writing-a-workflow.md` §Scaffolding example omits `--run-id`**

Lines 108–118: the `aiw run-scaffold` block does not include `--run-id`. The approve/resume step is shown in §Full CLI walkthrough via cross-reference to skill_install.md, so the omission is not wrong — but a reader who copies only the §What the scaffold produces snippet cannot subsequently call `aiw resume <run-id>` without knowing what run-id was assigned. Contrast with skill_install.md §7 which always passes `--run-id scaffold-qg-1`. Advisory because the cross-reference is explicit and present.

**Lens:** Lens 5 (doc drift).

---

### What passed review

- **Lens 1 (bugs):** ADR-0010 four rules are internally consistent; write-safety guard descriptions in both docs match the CLI source; `AIW_EXTRA_WORKFLOW_MODULES` handoff examples use correct env-var name and module-stem convention. One FIX found (`list-runs --run-id`).
- **Lens 2 (defensive creep):** None. Docs describe a real shipped feature with no phantom branches or fallback shims.
- **Lens 3 (idiom alignment):** Doc-only task; no source idioms to check. Cross-references resolve to existing files with correct slugified anchors.
- **Lens 4 (premature abstraction):** Not applicable to doc-only task.
- **Lens 5 (comment/docstring drift):** Two minor advisories raised. ADR-0010 module docstring cites task + relationship correctly. `skill_install.md` §7 heading matches anchor slug `#7-generating-your-own-workflow` used in cross-references.
- **Lens 6 (simplification):** Not applicable to doc-only task.

## Security review (2026-04-30)

**Reviewer:** security-reviewer agent
**Task:** M17 T03 — ADR-0010 + skill-install §Generating-your-own-workflow + docs §Scaffolding
**Scope:** doc-only task; primary concerns are whether ADR-0010 and user-facing docs accurately describe security boundaries and do not introduce misleading guidance.

### 🔴 Critical — must fix before publish/ship

None.

### 🟠 High — should fix before publish/ship

None.

### 🟡 Advisory — track; not blocking

**ADV-01 — Wheel contents: design_docs/ exclusion gate**
- Threat model item: Item 1 (wheel contents). The new `design_docs/adr/0010_user_owned_generated_code.md` must not appear in the published wheel. The non-skippable pre-publish wheel-contents check at T04 is the gate. No action required for T03.
- Action: T04 builder runs `uv build && unzip -l dist/*.whl` before publish; verify `design_docs/` absent.

**ADV-02 — Env var inheritance note missing from AIW_EXTRA_WORKFLOW_MODULES handoff examples**
- File: `design_docs/phases/milestone_9_skill/skill_install.md` line 319; `docs/writing-a-workflow.md` line 114. Threat model item: Item 6 (subprocess env leakage). Current examples are safe (no sensitive vars injected). Advisory only — if subprocess examples are extended in a future revision, re-check.
- Action: No immediate action.

### Positive findings

ADR-0010 write-safety rules (Rule 2: no writes inside `ai_workflows/`, atomic `mkstemp`+`os.replace`, `--force` guard) are accurately stated in the ADR and mirrored in docs. Validator scope is correctly bounded to `ast.parse()` + `register_workflow()` call-shape only; HumanGate is correctly described as a user-review gate, not a certification gate. No `ANTHROPIC_API_KEY` or raw API-key references introduced. No `shell=True` guidance. `--host 0.0.0.0` foot-gun documentation unchanged and intact. KDR-013 user-owned risk boundary clearly stated in ADR-0010 §Consequences and docs.

**Verdict:** SHIP
