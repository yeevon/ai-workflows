# milestone_10_ollama_hardening — Task Analysis

**Round:** 4
**Analyzed on:** 2026-04-25
**Specs analyzed:** task_01_fallback_tier_adr.md, task_02_retry_cooldown_prompt.md, task_03_single_gate_invariant.md, task_04_send_payload_invariant.md, task_05_doc_sweep.md, task_06_milestone_closeout.md
**Analyst:** task-analyzer agent

## Summary

| Severity | Count |
| --- | --- |
| 🔴 HIGH | 0 |
| 🟡 MEDIUM | 0 |
| 🟢 LOW | 6 |
| Total | 6 |

**Stop verdict:** LOW-ONLY

Convergence reached: zero HIGH, zero MEDIUM. Round-3 fixes M1+M2+M3 all held line-by-line and introduced no new drift. The five round-3 LOWs are still applicable (orchestrator has not yet pushed them to spec carry-over), and one new LOW surfaced in this pass (L6 — pre-existing publish-ceremony / order-of-operations duplicate-step ambiguity in T06 that earlier rounds did not flag). The orchestrator should push all six LOWs to each spec's `## Carry-over from task analysis` section and exit the loop.

## Round-3 fixes — verification

All three round-3 fixes verified held line-by-line:

- **Round-3 M1 fix** — task_05_doc_sweep.md:240–247 now reads *"Verify Exit criterion #3 reads 'three-branch' — the M10 task-analysis pass corrected this pre-emptively against the pre-revision 'two-branch' drift, so the working tree should already match T03's landed test name `test_three_branch_parallel_fanout_records_one_gate`. If the README has been reset to 'two-branch' since (e.g. via a botched merge), restore the 'three-branch' wording. T03's body explicitly fans out three parallel `Send(...)` payloads, so the 'three-branch' reading is canonical."* The double-application from round 3 is gone — sub-clause (b) is now a verify-step, not a pending edit.

- **Round-3 M2 fix** — task_05_doc_sweep.md:48–51 now reads *"…The mapping table in T05's *'slot mapping table + branch-count correction'* deliverable section (further down) is the canonical place to record the actual landing slots vs. the planned ones."* The cross-reference now matches the actual subsection title at task_05_doc_sweep.md:224 (*"### [README.md](README.md) (M10 milestone) — slot mapping table + branch-count correction"*). Verified `grep -nF "Update README" task_*.md` returns no hits — the round-2-era stale reference is fully cleaned.

- **Round-3 M3 fix** — both edits landed in task_06_milestone_closeout.md:
  - **Edit 1** (cross-reference + heading-shape) at lines 103–112: now reads *"Add a T06 close-out entry at the top of the new dated section under the canonical heading `### Changed — M10 Task 06: Milestone Close-out (<YYYY-MM-DD>)` — mirror M13 T08's shape (see `CHANGELOG.md:269` for the canonical close-out form), not M8 T06's (M8 T06 used a milestone-named section because no publish was run; M13 T08 is the M13-era close-out and is the right reference for a publish-bearing milestone close-out). `### Changed` is the right Keep-a-Changelog kind for a close-out because the close-out reframes existing landed surface rather than introducing new behavioural surface."* Verified at CHANGELOG.md:269 — `### Changed — M13 Task 08: Milestone Close-out (2026-04-22)` resolves.
  - **Edit 2** (new AC) at lines 295–297: *"Close-out CHANGELOG entry uses the canonical heading `### Changed — M10 Task 06: Milestone Close-out (<YYYY-MM-DD>)` (mirroring M13 T08's shape at `CHANGELOG.md:269`)."* AC is now present in the close-out checklist between the slot-drift AC and the milestone README/roadmap AC.

The user's specific concerns from the prompt are also clean:

- **"Did any round-3 edit introduce new drift in cross-references?"** — No. Verified every M13 T07 / M13 T08 reference across T06: lines 22 + 162 cite M13 T07 for the publish-ceremony runbook (correct — M13 T07 IS the publish task `task_07_changelog_publish.md`); lines 105 + 108 + 297 cite M13 T08 for the close-out *heading shape* (correct — M13 T08 is the close-out task with the canonical close-out heading at CHANGELOG.md:269). The two reference targets are different artefacts and the spec uses each correctly.
- **"Are there other 'stale subsection name' cross-references the M2 fix missed?"** — No. `grep -nF "Update README" task_*.md` returns no hits. T05's deliverable subsection is uniquely cross-referenced by the slot-drift defensive clause at line 48, and the round-3 M2 fix is the only place that needed updating.
- **"Are there other M13 T07/T08 confusions across T06?"** — No. Verified all four M13 T07 references (the runbook + procedure cross-references) and all three M13 T08 references (the heading-shape cross-references). Each reference points at the correct artefact.
- **"Are there *other* CHANGELOG references across the six specs the round-2 + round-3 M3 fixes didn't catch?"** — No. Verified every `### {Kind}` heading instruction across T01/T02/T03/T04/T05/T06 — all six tasks now use the canonical `### {Kind} — M10 Task NN: <title> (<YYYY-MM-DD>)` shape with a Keep-a-Changelog vocabulary kind. The off-vocabulary `### Docs` / `### Tests` text appears only inside justification blocks. T06's own close-out entry (the gap round-3 M3 caught) now also uses the canonical `### Changed — M10 Task 06: Milestone Close-out (<YYYY-MM-DD>)`.
- **"Look for any newly-introduced findings outside the round-3 scope."** — One LOW (L6) — a pre-existing structural duplicate between T06's order-of-operations step 3 and Pre-publish steps 1–2. Round-2 and round-3 did not flag this; surfacing it now so the orchestrator's loop-exit pushes it as carry-over rather than losing it.

The five LOWs from rounds 1–3 are still applicable — the orchestrator has not yet pushed them to spec carry-over (verified: `grep -n "Carry-over from task analysis"` finds no matches in the milestone task spec files). They re-surface here as L1–L5; L6 is new in round 4.

## Findings

### 🟢 LOW

(LOW findings from rounds 1–3 are still applicable — the orchestrator pushes them as carry-over text at loop-exit, which has not happened yet. Re-listed here so the orchestrator's subsequent close-out sweep absorbs them. L6 is new in round 4.)

#### L1 — T05 says "§17–§22 were filled" but nice_to_have.md skips §8 (numbering gap)

**Task:** task_05_doc_sweep.md
**Issue:** task_05_doc_sweep.md:30 says *"slots `§17`–`§22` were filled by entries landed during the 0.1.x release cycle and the M16 kickoff."* Verified via `grep -nE "^## [0-9]+\." design_docs/nice_to_have.md` — the file has 21 sections (§1–§7, §9–§22; §8 is a long-standing numbering gap inherited from a pre-M10 deletion). Practical conclusion (§23 is the next free slot) is correct, but the framing slightly mis-states the count of filled entries.
**Recommendation:** Either drop the "§17–§22 were filled" framing or add a footnote.
**Push to spec:** yes — append to task_05_doc_sweep.md `## Carry-over from task analysis` with: *"Footnote on §8: long-standing numbering gap in `nice_to_have.md` (jumps from §7 to §9). Not a free slot — file pre-existed M10. If the Builder enumerates filled slots, exclude §8 from the count to avoid implying it's available."*

#### L2 — T01 docstring suggested-wording uses markdown-link syntax that won't render in Python docstrings

**Task:** task_01_fallback_tier_adr.md
**Issue:** task_01_fallback_tier_adr.md:78–82 sketches the docstring as: *"The fallback choice is locked at [ADR-0003](../../../design_docs/adr/0003_ollama_fallback_tier_choice.md)…"* Markdown `[text](url)` is valid in Sphinx-style RST but produces ugly raw text inside a Python docstring rendered by `help()` / `pydoc`. Existing docstrings (e.g. slice_refactor.py:208–222) use plain `M8 T04`, `KDR-006`, `:func:` references — no markdown brackets.
**Recommendation:** Switch to plain `ADR-0003` (which the Auditor's grep at task_01_fallback_tier_adr.md:106–116 already expects literally).
**Push to spec:** yes — append to task_01_fallback_tier_adr.md `## Carry-over from task analysis`.

#### L3 — T04 names a fixture-pattern source by path but doesn't enumerate which fields the SliceSpec stub needs

**Task:** task_04_send_payload_invariant.md
**Issue:** task_04_send_payload_invariant.md:47–49 says *"Re-use the fixture pattern from `tests/workflows/test_slice_refactor_ollama_fallback.py` — copy the minimum needed to instantiate two specs."* `SliceSpec` has three required fields (`id: str`, `description: str`, `acceptance: list[str]`, with `extra="forbid"` per slice_refactor.py:430–452). The Builder will figure this out at first failing test, but a one-liner saves a cycle.
**Recommendation:** Append after line 49: *"Minimal SliceSpec instantiation: `SliceSpec(id='slice-0', description='', acceptance=[])` — only `id` is round-tripped through `_route_after_fallback_dispatch_slice`'s `slice_by_id` lookup; `description` + `acceptance` are required by `extra='forbid'` validation."*
**Push to spec:** yes — append to task_04_send_payload_invariant.md `## Carry-over from task analysis`.

#### L4 — T03's recipe step 4 mentions `cooldown_s` import but doesn't name the canonical source for a workflow author

**Task:** task_03_single_gate_invariant.md
**Issue:** task_03_single_gate_invariant.md:105–107 (recipe step 4): *"Compose `build_ollama_fallback_gate`. Build the gate with `tier_name`, `fallback_tier`, and `cooldown_s` (the M10 T02 kwarg)…"* — A future workflow author following the recipe needs to know the source of truth for `cooldown_s` (the per-tier `CircuitBreaker.cooldown_s` under T02 option (a), or a workflow-local constant under option (b)).
**Recommendation:** Append a half-sentence after "the M10 T02 kwarg": *"…wire it from the per-tier `CircuitBreaker.cooldown_s` so the rendered prompt names the breaker's actual cooldown — not a hard-coded literal."*
**Push to spec:** yes — append to task_03_single_gate_invariant.md `## Carry-over from task analysis`.

#### L5 — T02 cites planner.py:520 + slice_refactor.py:1508 line numbers but actual locations are 519 + 1507 (off-by-one)

**Task:** task_02_retry_cooldown_prompt.md
**Issue:** task_02_retry_cooldown_prompt.md:179–180 says *"…see `ai_workflows/workflows/planner.py:520` and `ai_workflows/workflows/slice_refactor.py:1508`)…"* — but `grep -n "build_ollama_fallback_gate"` resolves both to line 519 and 1507 respectively (verified at round 4 against the live working tree). Off-by-one in both citations. Builder will find the right line via grep, but a wrong line-number citation is exactly the kind of spec rot the analysis pass exists to catch.
**Recommendation:** Fix the literal line numbers to match what the live codebase reports.
**Push to spec:** yes — append to task_02_retry_cooldown_prompt.md `## Carry-over from task analysis` with: *"Line numbers in the workflow-wiring-sites paragraph (around line 179) cite planner.py:520 and slice_refactor.py:1508. Live grep at round-4 task-analysis time resolves them to planner.py:519 and slice_refactor.py:1507. Update the literals to match (or drop them in favor of the grep, which is more robust against future drift)."*

#### L6 — T06's order-of-operations step 3 and Pre-publish steps 1–2 specify the same CHANGELOG promotion at two different points

**Task:** task_06_milestone_closeout.md
**Issue:** task_06_milestone_closeout.md:149–151 (order-of-operations step 3): *"Land the close-out doc updates (milestone README outcome, roadmap, root README, CHANGELOG `## [0.2.1]` section with placeholder footer) — but **not** the `__version__` bump yet."* Then task_06_milestone_closeout.md:166–173 (Pre-publish steps 1–2): step 1 = bump `__version__`, step 2 = *"Promote the accumulated `[Unreleased]` block to a dated `## [0.2.1] - <YYYY-MM-DD>` section in [CHANGELOG.md](../../../CHANGELOG.md). Keep `[Unreleased]` empty above it. Add a `### Published` footer **with placeholder values** (`<filled-in-post-publish>`) — the post-publish amendment fills them in."*

The CHANGELOG `[0.2.1]` section + placeholder footer is described once in step 3 of the order-of-operations (close-out doc updates phase) and again in step 2 of Pre-publish (publish-ceremony phase). A Builder reading both will either (a) do it twice (the second pass is a no-op the first time it ran cleanly, but creates a confusing diff during code review), or (b) get confused about whether the `[0.2.1]` promotion is part of the close-out commit or part of the publish-ceremony commit.

This is structural ambiguity that pre-existed round-3 (rounds 1–3 didn't flag it). Round-3 M2's fix that re-anchored the cross-reference at line 133 (*"step 4 of the order-of-operations below; the `__version__` bump itself is step 1 of the Pre-publish sub-list further down"*) made the *ordering* of `__version__` bump-vs-CHANGELOG-promotion clearer, but did not resolve the duplication of the CHANGELOG-promotion description itself.

The Builder will figure it out at write time — likely by treating step 3's CHANGELOG instruction as the canonical one and reading Pre-publish step 2 as a verify-step. But this is exactly the kind of structural ambiguity `/clean-tasks` exists to catch.

**Recommendation:** Two possible cleanups (orchestrator picks one; either works):

- **Path (a) — collapse step 2 of Pre-publish into a verify.** Rewrite Pre-publish step 2 as: *"Verify the `## [0.2.1] - <YYYY-MM-DD>` section is in place from the close-out doc updates (order-of-operations step 3). The `### Published` footer should already carry placeholder values; the post-publish amendment fills them in."*
- **Path (b) — narrow step 3 of order-of-operations.** Drop the CHANGELOG `## [0.2.1]` reference from step 3 entirely; the CHANGELOG promotion lives only in Pre-publish step 2. Step 3 then reads: *"Land the close-out doc updates (milestone README outcome, roadmap, root README) — but **not** the CHANGELOG promotion or the `__version__` bump yet."*

Path (a) is the lower-coupling default — it preserves the existing close-out-first-then-publish ordering and matches the M13 T07/T08 muscle memory (M13 T08's close-out commit landed the dated CHANGELOG section; T07's earlier publish ceremony was version-bump + placeholder-footer-stamp).

**Push to spec:** yes — append to task_06_milestone_closeout.md `## Carry-over from task analysis` with: *"The CHANGELOG `## [0.2.1]` promotion is described twice — once in order-of-operations step 3 (close-out phase) and once in Pre-publish step 2 (publish-ceremony phase). At implement time, treat step 3 as canonical (the CHANGELOG promotion lands as part of the close-out commit, mirroring M13 T08); read Pre-publish step 2 as a verify-step that confirms the close-out commit's CHANGELOG block is intact before `uv build`. If a future revision of T06 is needed, collapse Pre-publish step 2 into an explicit verify-clause."*

## What's structurally sound

Round-1 + round-2 + round-3 fixes all hold line-by-line against the live spec text + working tree:

- **Round-3 M1 fix held.** task_05_doc_sweep.md:240–247 now reframes sub-clause (b) as a verify-step matching the round-2 working-tree edit at README.md:29 (verified via `git diff design_docs/phases/milestone_10_ollama_hardening/README.md` → working-tree edit confirmed; README:29 reads "three-branch"). The spec no longer describes a pending edit that already shipped.

- **Round-3 M2 fix held.** task_05_doc_sweep.md:48–51 cross-references the deliverable subsection by its actual title (*"slot mapping table + branch-count correction"*). `grep -nF "Update README" task_*.md` returns no hits — the stale subsection name is fully cleaned.

- **Round-3 M3 fix held.** task_06_milestone_closeout.md:103–112 carries the explicit canonical heading shape `### Changed — M10 Task 06: Milestone Close-out (<YYYY-MM-DD>)` plus the M13 T08 cross-reference. The matching AC at task_06_milestone_closeout.md:295–297 is in place. Verified `CHANGELOG.md:269` resolves to *"### Changed — M13 Task 08: Milestone Close-out (2026-04-22)"*.

- **Round-2 fixes still hold.** The H1 + M1 + M2 + M3 fixes from round 2 are intact; round-3 did not regress any of them.

- **All M13 T07 / M13 T08 references are correct.** Verified: T06:22 + T06:162 cite M13 T07 for the publish-ceremony runbook (correct — M13 T07 is the publish task `task_07_changelog_publish.md`). T06:106 + T06:108 + T06:297 cite M13 T08 for the close-out heading shape (correct — M13 T08 is the close-out task `task_08_milestone_closeout.md` with the canonical heading at CHANGELOG.md:269). The two reference targets are distinct artefacts and the spec uses each correctly.

- **All CHANGELOG heading instructions across T01/T02/T03/T04/T05/T06 use the canonical shape.** Verified each spec's CHANGELOG section: T01 (`### Changed — M10 Task 01: ADR-0003 + OllamaFallback docstring lock for fallback_tier`), T02 (three blocks: `### Added` / `### Changed` / `### Deprecated`, each with the `M10 Task 02: <title>` form), T03 (`### Added — M10 Task 03: cross-workflow single-gate invariant test + reducer promotion`), T04 (`### Added — M10 Task 04: Send-payload carry invariant test`), T05 (`### Changed — M10 Task 05: architecture.md §8.4 Limitations paragraph + five nice_to_have.md entries`), T06 (`### Changed — M10 Task 06: Milestone Close-out`). All six use Keep-a-Changelog vocabulary; off-vocabulary `### Docs` / `### Tests` appears only inside meta-justification blocks.

- **All cited line numbers (other than the L5 off-by-ones noted in round 3) verified against live working tree:** `PLANNER_OLLAMA_FALLBACK` at planner.py:114 with docstring at 118–127; `SLICE_REFACTOR_OLLAMA_FALLBACK` at slice_refactor.py:204; `_merge_ollama_fallback_fired` at slice_refactor.py:350; `_merge_mid_run_tier_overrides` at slice_refactor.py:366; `_ollama_fallback_dispatch_slice` at slice_refactor.py:1245; `_route_after_fallback_dispatch_slice` at slice_refactor.py:1298; the override-payload skip at slice_refactor.py:1359–1360; `build_planner` at planner.py:455; `build_slice_refactor` at slice_refactor.py:1457; `build_ollama_fallback_gate` call at slice_refactor.py:1507. T03's reducer-reference span 604–607 is correct (the `Annotated[..., _merge_*]` lines at 605 and 607 are bracketed by the typing block at 604–607). Architecture.md §8.4 starts at line 189; the inline "process-local `CircuitBreaker`" mention is at line 191. CHANGELOG.md:10 is the canonical heading-shape exemplar T02 cites; CHANGELOG.md:269 is the M13 T08 close-out exemplar T06 cites.

- **All `__all__` claims hold.** `ai_workflows/graph/__init__.py:26` exports `["FallbackChoice", "build_ollama_fallback_gate"]` only — T02's claim that `render_ollama_fallback_prompt`, `FALLBACK_DECISION_STATE_KEY`, `FALLBACK_GATE_ID` are NOT re-exported at package level (T02 lines 30–35; T04 lines 43–45) is correct. `ai_workflows/workflows/slice_refactor.py:182–201` exports the public surface T03 will extend with the two reducer-rename additions.

- **`build_ollama_fallback_gate` smoke command's function references resolve.** T02's `python -W error::DeprecationWarning -c` command imports `build_planner` from planner.py and `build_slice_refactor` from slice_refactor.py; both functions exist at planner.py:455 and slice_refactor.py:1457. The footnote at T02 lines 281–283 verifying the function names is accurate.

- **Seven load-bearing KDRs honored across all six specs.** No upward layer imports proposed; no `anthropic` SDK or `ANTHROPIC_API_KEY` reads; no LLM-without-validator additions; no bespoke try/except retry loops; no MCP tool schema changes; no hand-rolled checkpoint writes; no policing of external workflow code. T06's publish gate threads `dependency-auditor` on the wheel — KDR-013 wheel-contents discipline preserved. All four `import-linter` contracts unchanged at M10.

- **`nice_to_have.md` slot state matches T05's planned-range assumption.** Verified: 21 sections present (§1–§7, §9–§22); §22 is the highest-numbered. §23 is the next free slot — matching T05's planned range. T05's *"slot-drift defensive clause"* (lines 27–55) correctly anticipates a re-grep at thaw time. Cross-task slot references (T01 §25; T03 §26; T05 §23–§27 mapping table; T06 §23–§27) are mutually consistent.

- **Cross-spec dependency chain held.** T01 → T02 (T01 docstrings make T02's gate-factory edits less reviewer-noisy); T02 → T03 (T03 builds gates with the new `cooldown_s` kwarg); T03 → T04 (T04 reuses T03's `FakeStorage` + `StubLLMAdapter` patterns); T05 sequencing-only after T04; T06 close-out after T01–T05. No out-of-order dependencies. Task-order table in README.md:62–69 matches the spec dependencies.

- **`scripts/release_smoke.sh` exists.** T06's pre-publish step 3 reference verified.

- **M13 T07 + release_runbook.md exist.** T06's cross-references at lines 22–24 + 161–162 resolve.

- **Publish-ceremony step count is correct.** T06's "(steps 1–13 below)" cross-reference at line 153 matches the actual count: Pre-publish 6 + Publish 4 + Post-publish 3 = 13.

- **Working-tree state remains stable.** README.md is still the only modified file in the milestone directory per `git status` (the round-2 H1 edit). All six task specs + this analysis file are still untracked.

- **f-string format-spec for cooldown rendering is safe.** `f"{60.0:g}"` → `60`; `f"{12.5:g}"` → `12.5` — T02's `test_prompt_includes_cooldown_warning` assertion (literal `60` token, no decimal) is correct.

## Cross-cutting context

- **Milestone status:** still **paused**, pending CS300 thaw per project memory (`project_m13_shipped_cs300_next.md`). The findings here would only bite on M10 thaw; fixing them now is cheap and avoids thaw-time pressure.

- **0.2.0 ship status:** unchanged from rounds 1–3. CHANGELOG.md `[Unreleased]` block on `design_branch` still contains the M16 Task 01 entry that was never promoted to a dated `## [0.2.0] - 2026-04-24` section — T06's reconciliation step + AC catches this drift on thaw. Verified `[Unreleased]` block at CHANGELOG.md:8–66.

- **Convergence trajectory across rounds:** Round 1: 2 HIGH + several MEDIUM/LOW. Round 2: 1 HIGH + 3 MEDIUM + 4 LOW. Round 3: 0 HIGH + 3 MEDIUM + 5 LOW. Round 4: 0 HIGH + 0 MEDIUM + 6 LOW. The HIGH and MEDIUM count has hit zero; the LOW count is stable (5 from prior rounds + 1 new in round 4 surfacing a pre-existing structural ambiguity). The /clean-tasks loop should exit at LOW-ONLY this round.

- **Carry-over push outstanding.** Verified `grep -n "Carry-over from task analysis"` finds no instances anywhere in the milestone task spec files. The orchestrator's loop-exit step is responsible for pushing all six LOWs (L1 → task_05; L2 → task_01; L3 → task_04; L4 → task_03; L5 → task_02; L6 → task_06) to each spec's `## Carry-over from task analysis` section.
