# M15 Task 05 Issue File — Milestone Close-out

## Cycle 1 — Builder notes (2026-04-30)

### Deliverables landed

| Deliverable | File | AC |
|---|---|---|
| CO-1: architecture.md §4.1 TierConfig row | `design_docs/architecture.md:67` | AC-1 |
| Milestone README Status flipped | `design_docs/phases/milestone_15_tier_overlay/README.md` | AC-2, AC-3, AC-4, AC-5 |
| roadmap.md M15 row + Deferred narrative | `design_docs/roadmap.md` | AC-6 |
| Root README.md M15 row | `README.md` | AC-7 |
| CHANGELOG.md T05 entry | `CHANGELOG.md` | AC-8 |
| Spec Status flipped | `design_docs/phases/milestone_15_tier_overlay/task_05_milestone_closeout.md` | AC-2 (spec surface) |
| Issue file created | `design_docs/phases/milestone_15_tier_overlay/issues/task_05_issue.md` | — |

### CO-1 implementation choice

Option chosen: drop the bare `tiers.yaml` reference from the cell heading; keep `pricing.yaml`; add note that authoritative tier definitions live in per-workflow Python registries (KDR-014) and that `docs/tiers.example.yaml` is a schema-reference example only, not loaded at dispatch time. This reads more clearly than retaining a `docs/tiers.example.yaml` half-reference alongside `pricing.yaml`.

### Carry-over items resolved

- TA-LOW-01: live pytest count (1532 passed) used in Outcome section gate snapshot.
- TA-LOW-02: ADR-0006 hyperlinked inline in the Outcome section KDR note.
- TA-LOW-03: T04 carry-over checkboxes were already all `[x]` — no action needed.
- TA-LOW-04: `pricing.yaml` reference preserved in CO-1; only `tiers.yaml` half removed.

### Gate results

- `uv run pytest` — **1532 passed**, 12 skipped, 22 warnings — PASS
- `uv run lint-imports` — **5 contracts kept, 0 broken** — PASS
- `uv run ruff check` — **all checks passed** — PASS

### Docs-only invariant

No files under `ai_workflows/` were touched. This is a docs-only task.

### Planned commit message

```
M15 Task 05: milestone close-out (KDR-014)

- CO-1: architecture.md §4.1 TierConfig row — stale tiers.yaml reference
  removed; pricing.yaml preserved; per-workflow Python registries noted
  as authoritative tier source per KDR-014
- Milestone README: Status flipped to Complete; task-05 row updated;
  exit criterion #10 lint-imports count corrected to 5; all 10 exit
  criteria annotated with satisfying task; Outcome section added
- roadmap.md: M15 row flipped to complete; Deferred narrative rewritten
  to past tense with Shipped prefix
- README.md: M15 row updated to Complete (2026-04-30)
- CHANGELOG.md: T05 close-out entry added
- task_05 spec: Status flipped to Complete; carry-over checkboxes ticked

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

### Deviations from spec

None.

---

## Cycle 1 — Auditor findings (2026-04-30)

**Source task:** `design_docs/phases/milestone_15_tier_overlay/task_05_milestone_closeout.md`
**Audited on:** 2026-04-30
**Audit scope:** docs-only milestone close-out; CO-1 architecture.md fix; status-surface flips on four surfaces; 4 carry-over items.
**Status:** ✅ PASS

### Design-drift check (KDR-002/003/004/006/008/009/013/014)

No drift detected. T05 is docs-only — zero `ai_workflows/` changes. KDR-014 (framework owns tier policy) is reinforced by:
- architecture.md §4.1 cell now states "Authoritative tier definitions live in per-workflow Python registries (KDR-014); `docs/tiers.example.yaml` is a schema-reference example only, not loaded at dispatch time."
- roadmap.md `## Deferred` narrative preserves the KDR-014 YAML-overlay-rejection rationale.
- Outcome section explicitly cross-links ADR-0006 as the YAML-overlay-rejection record.

No new dependencies, no new modules, no LLM calls added, no checkpoint or retry surface change. Layer contract count remains `5 contracts kept, 0 broken` (M12 T02's audit_cascade contract remains in effect).

### AC grading

| AC | Status | Notes |
|---|---|---|
| AC-1 | ✅ met | architecture.md:67 TierConfig row: `tiers.yaml` reference removed; `pricing.yaml` preserved (TA-LOW-04 honoured); per-workflow Python registry framing added with KDR-014 citation; `docs/tiers.example.yaml` correctly framed as example-only. |
| AC-2 | ✅ met | Milestone README `**Status:**` line: `📝 Planned (rescoped 2026-04-30; deferred — implement after M17 close-out).` → `✅ Complete (2026-04-30).` |
| AC-3 | ✅ met | §"Task order" row 05: column shows `✅ Complete (2026-04-30)` and link target updated. |
| AC-4 | ✅ met | Exit criterion #10 corrected from `(4 contracts kept …)` to `(5 contracts kept … audit_cascade contract was added at M12 T02 and remains in effect)`; all 10 exit criteria annotated with the satisfying task (T01/T02/T03/T04/T05 mapping per spec). |
| AC-5 | ✅ met | Outcome section appended at README:122-143 covering T01–T05 + KDR additions + gate snapshot. ADR-0006 hyperlinked twice (TA-LOW-02). |
| AC-6 | ✅ met | roadmap.md:28 row flipped to `✅ complete (2026-04-30)`; `## Deferred` paragraph at line 56 prefixed with `✅ Shipped 2026-04-30 — ` and verb phrase rewritten from "Implement after M17." to "Implemented." Rescoping rationale preserved. |
| AC-7 | ✅ met | Root README.md:25 row `\| **M15 — Tier overlay + fallback chains** \| Complete (2026-04-30) \|` (boldface applied per shipped-row convention). |
| AC-8 | ✅ met | CHANGELOG.md `[Unreleased] → ### Added` has T05 close-out entry covering files-touched, ACs satisfied, deviations. M15 T01–T04 entries preserved above. No version bump (already at 0.4.0). |
| AC-9 | ✅ met | `git diff --stat HEAD~1..HEAD -- ai_workflows/` empty; working-tree diff also has zero `ai_workflows/` files. Docs-only invariant holds. |
| AC-10 | ✅ met | `uv run pytest` — **1532 passed**, 12 skipped, 22 warnings, 69.21s. Matches Builder's claim and the Outcome §gate-snapshot. |
| AC-11 | ✅ met | `uv run lint-imports` — **5 contracts kept, 0 broken**. |
| AC-12 | ✅ met | `uv run ruff check` — all checks passed. |

### Carry-over grading

| ID | Status | Notes |
|---|---|---|
| M15-T04-LOW-02 (CO-1) | ✅ resolved | architecture.md:67 TierConfig row diff matches the spec's CO-1 second option (drop `tiers.yaml` reference; cite per-workflow registries per KDR-014). |
| TA-LOW-01 | ✅ resolved | Outcome §gate-snapshot pytest count = 1532, matches re-run. |
| TA-LOW-02 | ✅ resolved | ADR-0006 hyperlinked twice in Outcome section (T04 summary + KDR-additions paragraph). |
| TA-LOW-03 | ✅ resolved | Cross-checked T04 spec — all four carry-over checkboxes already `[x]` (lines 204-215). Builder's claim is accurate; no action was needed. |
| TA-LOW-04 | ✅ resolved | architecture.md diff preserves `pricing.yaml`; only `/ tiers.yaml` was excised. |

Diff-vs-checkbox cross-reference: every `[x]` in the spec's `## Carry-over from prior audits` and `## Carry-over from task analysis` sections is matched by a corresponding hunk (architecture.md, README.md outcome section + ADR hyperlink, T04 spec inspection, architecture.md preserved-string).

### Gate summary

| Gate | Command | Result |
|---|---|---|
| pytest | `uv run pytest` | PASS — 1532 passed, 12 skipped |
| lint-imports | `uv run lint-imports` | PASS — 5 contracts kept, 0 broken |
| ruff | `uv run ruff check` | PASS — all checks passed |
| docs-only invariant | `git diff --stat HEAD~1..HEAD -- ai_workflows/` | PASS — empty |
| AC-1 grep | `grep "tiers.yaml" design_docs/architecture.md` | PASS — 0 hits |
| milestone status | `grep "Complete (2026-04-30)" .../README.md` | PASS — 2 hits (Status line + task-05 row) |
| roadmap status | `grep "complete (2026-04-30)" design_docs/roadmap.md` | PASS — M15 row present |
| root README | `grep "Complete (2026-04-30)" README.md` | PASS — M15 row present |
| AC-4 contract count | `grep "5 contracts" .../README.md` | PASS — 2 hits (exit criterion + Outcome) |

### Critical sweep

Verified explicitly:
- **Status-surface alignment.** Four surfaces all flipped together: (a) spec `**Status:**` line, (b) milestone README task-order row + Status line, (c) root README.md table row, (d) roadmap.md M15 row + `## Deferred` narrative. No surface left stale. (Note: M15 milestone has no `tasks/README.md`, so the four-surface rule reduces to these four.)
- **Carry-over checkbox cargo-cult.** All five `[x]` items in the spec backed by visible diff hunks. TA-LOW-03 (claim "no action needed") cross-checked against T04 spec at lines 204-215 — claim is accurate.
- **Cycle-overlap / loop-spinning.** No prior cycle exists for T05 (cycle 1 is the first). N/A.
- **Rubber-stamp detection.** Diff is ~63 lines insertion / 22 deletion — under the 50-line MEDIUM threshold for the rubber-stamp heuristic, and zero HIGH/MEDIUM findings raised. No rubber-stamp signal — verdict reasoning has been documented gate-by-gate and AC-by-AC above.
- **Docs-only invariant.** No `ai_workflows/` file in working tree or in `HEAD~1..HEAD`.
- **Optional cosmetic deferral.** Spec's "Out of scope" allows the `TierRegistry.load()` docstring tweak; Builder did not include it. Acceptable — explicitly non-AC.
- **Builder return-text schema.** Issue file Builder section is well-formed; no schema drift findings.

### Additions beyond spec — audited and justified

None. Builder confined the change to the spec's enumerated deliverables. `pricing.yaml` reference preservation (TA-LOW-04) honoured.

### 🔴 HIGH

*(none)*

### 🟡 MEDIUM

*(none)*

### 🟢 LOW

*(none)*

### Deferred to nice_to_have

*(none — T05 deliverables fully scoped within the milestone close-out)*

### Propagation status

No forward-deferrals from this audit. M15 closes cleanly with all carry-overs resolved in-task.

### Verdict

✅ **PASS.** All 12 ACs met, all 4 carry-over items resolved (one shown to require no action by cross-reference), four status surfaces aligned, three gates green, docs-only invariant preserved. The orchestrator may commit the working-tree changes per autonomous-mode rules.

---

## Terminal gate — cycle 1 (2026-04-30)

**Verdicts:** sr-dev=SHIP · sr-sdet=FIX-THEN-SHIP · security=SHIP

### Locked terminal decision (loop-controller + sr-sdet concur, 2026-04-30)

**FIX-1 (sr-sdet Lens 2 — filename mismatch):**
M15 README exit criterion #9 and Outcome §T01 named `tests/primitives/test_tiered_node_fallback_schema.py` but the actual file on disk is `tests/primitives/test_tierconfig_fallback.py` (verified via `ls tests/primitives/test_tier*.py`). Applied: `replace_all` edit to README corrected both occurrences. Single clear recommendation; no KDR conflict; pure doc fix; all gates still green. Decision: apply.

**Advisory items (sr-dev Advisories, sr-sdet ADV-1/2, security):** non-blocking; no action required for terminal clean.

### Gate results after FIX-1 applied

| Gate | Result |
|---|---|
| `uv run pytest` | ✅ 1532 passed, 12 skipped |
| `uv run lint-imports` | ✅ 5 contracts kept, 0 broken |
| `uv run ruff check` | ✅ all checks passed |

**Status: ✅ TERMINAL CLEAN (cycle 1 — terminal-gate bypass applied; sr-sdet FIX-THEN-SHIP resolved; sr-dev SHIP; security SHIP; all gates green)**
