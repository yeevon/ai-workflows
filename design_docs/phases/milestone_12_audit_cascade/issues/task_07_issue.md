# Task 07 — Milestone Close-out — Audit Issues

**Source task:** `design_docs/phases/milestone_12_audit_cascade/task_07_milestone_closeout.md`
**Audited on:** 2026-04-29 (cycle 1)
**Audit scope:** Doc-only milestone close-out. CO-1 through CO-5 + status surfaces + CHANGELOG promote + roadmap + root README. Zero `ai_workflows/` diff invariant.
**Status:** ✅ PASS

---

## Design-drift check

- **Zero `ai_workflows/` diff confirmed.** `git diff --stat e8f43c9..HEAD -- ai_workflows/` returns empty. T06 landing SHA `e8f43c9` matches the spec's pre-flight baseline; no drift since.
- **Seven load-bearing KDRs:** docs-only diff; no production code surface touched. KDR-002 / KDR-003 / KDR-004 / KDR-006 / KDR-008 / KDR-009 / KDR-013 invariants all preserved by absence of code change.
- **Layer discipline:** N/A (no source files touched). `lint-imports` re-runs clean: 5 contracts kept (KDR-011 cascade contract preserved from T02).
- **Architecture drift:** none. ADR-0004 amendments + architecture.md §4.4 framing fix correct three pre-existing stale-framing items; no new architectural claim introduced. CO-3 explicitly names Option A (H1 locked 2026-04-27) and credits the four `_build_standalone_*` helpers in `mcp/server.py` — matches `git grep`-able reality.

**Verdict:** no drift detected.

---

## AC grading

| AC | Status | Notes |
| --- | --- | --- |
| ADR-0004 §Decision item 1 no longer references `primitives/tiers.py` (CO-1) | met | Line 25 now reads "Both were placed in **workflow-scoped registries** at T01 (`planner.py`, `summarize_tiers.py`; `slice_refactor.py` inherits via composition) — not in `primitives/tiers.py`." Cites T01 explicitly. |
| ADR-0004 §Consequences "New primitive" bullet — accurate import-linter statement (CO-2) | met | Line 54 now reads "T02 added a fifth `lint-imports` contract to pin `audit_cascade.py` as a graph-layer module, bringing the contract count from 4 to 5 — an import-linter edit was needed." Matches `lint-imports` re-run output (5 contracts kept). |
| ADR-0004 §Decision item 7 — Option A bypass description (CO-3) | met | Line 40 now reads "T05 chose Option A (H1 locked 2026-04-27): `run_audit_cascade` bypasses `AuditCascadeNode` entirely and invokes the auditor `TieredNode` directly via four private `_build_standalone_*` helpers in `mcp/server.py` — the tool is a standalone re-implementation, not a thin surface wrapper over the sub-graph primitive. `AuditCascadeNode` remains the inline-workflow composition surface…" Both stale clauses replaced; H1 locked-date cited; inline-workflow composition surface acknowledged. |
| architecture.md §4.4 `run_audit_cascade` bullet — accurate T05 Option A framing (CO-4) | met | Line 105 now reads "invokes the auditor `TieredNode` directly, bypassing `AuditCascadeNode` per T05 Option A." Tool signature, M12 T05 note, KDR-011, ADR-0004 link intact. |
| `nice_to_have.md` §25 EvalRunner cascade-fixture replay entry (CO-5) | met | Lines 585-605: all five canonical fields present (What this would add, Why deferred, Trigger to adopt, Integration sketch, Related). Both extension options (a) `_resolve_node_scope` by-suffix override and (b) `CascadeEvalRunner` subclass documented per spec. Appears immediately before §Revisit cadence (line 609). |
| Milestone README `**Status:**` flipped to `✅ Complete (2026-04-29)`; Outcome section covers all 8 tasks | met | Line 3: `**Status:** ✅ Complete (2026-04-29).` Outcome section appended (lines 149-162) with chronological-ordering parenthetical (TA-T07-LOW-01 honoured), all 8 tasks + commit SHAs + KDR additions + green-gate snapshot. |
| Milestone README §"Task order" row 07 flipped | met | Line 70: "07 \| Milestone close-out \| doc \| ✅ Complete (2026-04-29)". |
| Milestone README §"Exit criteria" item 10 marked `✅ (T02/T03 complete 2026-04-27)` | met | Line 35: "✅ (T02/T03 complete 2026-04-27) `tests/graph/test_audit_cascade.py` + `tests/workflows/test_audit_cascade_wiring.py`…". |
| Milestone README §"Cumulative carry-over" backfilled with CO-5 | met | Line 136: "**`nice_to_have.md` §25** EvalRunner cascade-fixture replay — from T06 spec / KDR-004 carve-out (T07 bundled)." CO-5 added as fifth bullet. |
| `roadmap.md` M12 row reflects complete | met | Line 25: "M12 \| Tiered audit cascade \| … \| ✅ complete (2026-04-29)". |
| `CHANGELOG.md` dated `[M12 Tiered Audit Cascade]` section + T07 entry on top; `[Unreleased]` empty | met | Line 8 `## [Unreleased]` immediately followed by line 10 `## [M12 Tiered Audit Cascade] - 2026-04-29` (no entries between). T07 close-out entry leads the new dated section (lines 12-24). T06/T05/T04/etc. entries follow below. |
| Root `README.md` M12 table row + narrative updated | met | Line 22: `\| **M12 — Tiered audit cascade** \| Complete (2026-04-29) \|`. §Next narrative (line 148) honoured TA-T07-LOW-04 — unchanged, M21 still pointed at M22. |
| Zero `ai_workflows/` diff at T07 (docs-only invariant) | met | `git diff --stat e8f43c9..HEAD -- ai_workflows/` empty. |
| `uv run pytest` + `uv run lint-imports` (5 contracts) + `uv run ruff check` clean | met | See Gate summary below. |

**Carry-over from spec-hardening (Round-3 LOWs):**

| ID | Status | Notes |
| --- | --- | --- |
| TA-T07-LOW-01 | met | Outcome section opens with "(Bullets ordered chronologically per landing date — T08 amends T02 and ships before T03 per §"Task order" sequencing exception above.)". |
| TA-T07-LOW-02 | met | CO-5 §Integration sketch landed verbatim (both options (a) and (b) documented as in spec). |
| TA-T07-LOW-03 | met | T06 landing SHA `e8f43c9` confirmed at audit time as the pre-T07 baseline; no later commit on `design_branch` shifts the SHA. |
| TA-T07-LOW-04 | met | Root README §Next unchanged (still pointing at M22 from M21 close-out). |

All 14 ACs + 4 spec-hardening carry-overs satisfied.

---

## 🟢 LOW

### M12-T07-LOW-01 — ADR-0004 §Consequences "New TierConfigs" bullet still claims `primitives/tiers.py` landing site

**Where:** [`design_docs/adr/0004_tiered_audit_cascade.md:55`](../../../adr/0004_tiered_audit_cascade.md).

**What's wrong:** Line 55 still reads "**New TierConfigs.** `auditor-sonnet` + `auditor-opus` land in `ai_workflows/primitives/tiers.py` (M12 T01) with matching pricing entries." This is the same factual error CO-1 corrected at §Decision item 1 (line 25): the auditor TierConfigs landed in workflow-scoped registries, not in `primitives/tiers.py`. The two sentences in the same ADR now disagree about where T01 placed the auditors.

**Why this is LOW (not MEDIUM/HIGH):** the spec explicitly scoped CO-1 to §Decision item 1 only. The §Consequences "New TierConfigs" bullet was **not** in CO-1's scope, so the Builder correctly did not touch it. The audit context above flagged this as a forward-looking observation, not a deferral that should block T07. Severity is LOW because the inaccuracy is read-only documentation and was cleanly identified by the spec author as out-of-scope; nothing downstream depends on the §Consequences bullet for correctness.

**Action / Recommendation:** add a single sentence-level fix as carry-over to a future milestone task that touches ADR-0004 (e.g. M15 T?? if M15's tier overlay touches the cascade tiers, or as an opportunistic fix the next time anyone edits `0004_tiered_audit_cascade.md`). Suggested replacement text: "**New TierConfigs.** `auditor-sonnet` + `auditor-opus` were landed in **workflow-scoped registries** at M12 T01 (`planner.py`, `summarize_tiers.py`; `slice_refactor.py` inherits via composition) with matching pricing entries — not in `ai_workflows/primitives/tiers.py` (per CO-1 framing fix at §Decision item 1)." Single-sentence rewrite; matches the CO-1 pattern.

**Trade-off:** filing a one-sentence fix as its own task is overhead; opportunistic fix at next ADR-0004 touch is the lighter-weight path. No action required at T07 close-out — this would have required scope expansion the spec explicitly forbade.

---

## Additions beyond spec — audited and justified

None. Builder report is accurate; deliverables match spec exactly.

- CHANGELOG entry mentions "Files touched" inventory — informational, not a deliverable expansion.
- Outcome section's chronological-ordering parenthetical is exactly what TA-T07-LOW-01 asked for; not scope creep.
- `nice_to_have.md` §25 wording follows the existing entry-format convention (matches §24's tone) — not a spec-deviating decision.

---

## Gate summary

| Gate | Command | Result |
| --- | --- | --- |
| pytest | `uv run pytest` | PASS — 1478 passed, 11 skipped, 22 warnings in 42.89s. |
| lint-imports | `uv run lint-imports` | PASS — 5 contracts kept, 0 broken (matches T02-set count). |
| ruff | `uv run ruff check` | PASS — All checks passed. |
| ai_workflows zero-diff | `git diff --stat e8f43c9..HEAD -- ai_workflows/` | PASS — empty (no ai_workflows/ delta since T06). |

---

## Issue log — cross-task follow-up

| ID | Severity | Owner | Status |
| --- | --- | --- | --- |
| M12-T07-LOW-01 | LOW | Opportunistic — next editor of `design_docs/adr/0004_tiered_audit_cascade.md` | OPEN (out-of-scope at T07 by spec design; no propagation target — see Deferred section below) |

---

## Deferred to nice_to_have

None. M12-T07-LOW-01 is a one-sentence ADR fix, not a tracked candidate; it does not match any `nice_to_have.md` entry's shape and is too small to warrant its own §N entry. Tracked here as an opportunistic fix; no `nice_to_have.md` promotion needed.

---

## Propagation status

No code-touching findings; no forward-deferral required. M12-T07-LOW-01 is documentation-only and out-of-scope for T07 per the spec's explicit CO-1 framing; left for opportunistic fix at next ADR-0004 touch (no specific target task — ADR-0004 may not be touched again until M15+ if at all).

T07 closes M12 cleanly. All carry-over from T01–T06 + T08 either landed at T07 (CO-1 through CO-5) or was forward-deferred to its own future-task trigger (`_DynamicState["slice"]` workflow-name leak — unchanged at T07 per spec §Out-of-scope).

---

## Security review (2026-04-29)

**Scope:** Docs-only milestone close-out. Files changed: `design_docs/adr/0004_tiered_audit_cascade.md`, `design_docs/architecture.md`, `design_docs/nice_to_have.md`, `design_docs/phases/milestone_12_audit_cascade/README.md`, `design_docs/phases/milestone_12_audit_cascade/task_07_milestone_closeout.md`, `design_docs/roadmap.md`, `CHANGELOG.md`, `README.md`. Zero `ai_workflows/` diff confirmed (`git diff e8f43c9..HEAD -- ai_workflows/` returns empty).

### Threat model items checked

**1. Secrets discipline (wheel + docs).** Scanned all changed doc files for `ANTHROPIC_API_KEY`, `GEMINI_API_KEY=<real>`, `token=`, `password=`, `Bearer`, `Authorization`. All `ANTHROPIC_API_KEY` mentions are KDR-003 compliance assertions ("zero reads", "no SDK import") — no real value. `GEMINI_API_KEY` appears in `README.md` only as `export GEMINI_API_KEY=...` (placeholder). No credentials introduced. PASS.

**2. Wheel-contents.** No files added under `ai_workflows/` (zero diff). No new root-level files that would land in the wheel. The `pyproject.toml` and `uv.lock` are untouched. Wheel-contents invariant preserved. PASS.

**3. Executable / supply-chain content in docs.** Scanned all `+` lines in the doc diff for shell-injection patterns (`curl | sh`, `eval $()`, `exec()`, `subprocess`, `os.system`). None found. The `nice_to_have.md` §25 entry contains only prose + Python method references in backtick notation — no executable content. PASS.

**4. KDR-003 (no Anthropic API key).** `grep -rn "ANTHROPIC_API_KEY" ai_workflows/` returns zero hits (confirmed). All doc mentions are negating assertions. PASS.

**5. No `pyproject.toml` / `uv.lock` change.** Dependency audit gate not triggered. PASS.

### Findings

### No findings — all checked items clean.

**Verdict:** SHIP

---

## Sr. Dev review (2026-04-29)

**Files reviewed:** `design_docs/adr/0004_tiered_audit_cascade.md`, `design_docs/architecture.md` (§4.4), `design_docs/nice_to_have.md` (§25), `design_docs/phases/milestone_12_audit_cascade/README.md`, `design_docs/roadmap.md`, `CHANGELOG.md`, `README.md` | **Skipped:** none | **Verdict:** SHIP

### BLOCK

None.

### FIX

None.

### Advisory

**A1 — ADR-0004 §Consequences lines 57-58: two additional stale-framing bullets (Lens 1 / doc consistency)**

`design_docs/adr/0004_tiered_audit_cascade.md:57` — "Workflow opt-in field. Each existing workflow's config model grows an `audit_cascade_enabled: bool = False` field" contradicts the T03 H1-locked decision (KDR-014 / ADR-0009): the opt-in mechanism is a module-level constant + env-var override, not a field on the `*Input` model. This is the same out-of-scope pattern as Auditor finding M12-T07-LOW-01 (line 55 stale `primitives/tiers.py` claim) — not in CO-1/CO-2/CO-3 scope for T07, docs-only.

`design_docs/adr/0004_tiered_audit_cascade.md:58` — "cascade's author + auditor nodes capture independently under `evals/<workflow>/<node>/` with role-tagged filenames (`author_<case_id>.json` / `auditor_<case_id>.json`)" is wrong on two counts: T06's actual convention is a directory split (`<cascade_name>_primary/<case_id>.json` / `<cascade_name>_auditor/<case_id>.json`), not role-tagged filenames; and the path shape includes a `<dataset>` segment (`evals/<dataset>/<workflow>/...`), not `evals/<workflow>/<node>/`. Confirmed against `evals/README.md:31-34`.

**Recommendation:** Bundle both as addenda to the existing M12-T07-LOW-01 "opportunistic fix at next ADR-0004 touch" recommendation. Suggested replacement text:

Line 57: "**Workflow opt-in constant.** Each existing workflow gets a module-level `_AUDIT_CASCADE_ENABLED: bool = False` constant (M12 T03) overridable via `AIW_AUDIT_CASCADE*` env vars (KDR-014 / ADR-0009). No field on `*Input` models."

Line 58: "**Eval harness gains cascade fixtures.** Under `evals/<dataset>/<workflow>/`, the cascade pair writes two independent fixtures split by directory: `<cascade_name>_primary/<case_id>.json` (role='author') and `<cascade_name>_auditor/<case_id>.json` (role='auditor'). See `evals/README.md §Cascade fixture convention (M12 T06)`. No M7 engine change required; fixture-naming convention only."

No new tracking entry needed — subsumed by M12-T07-LOW-01's action.

---

### What passed review

- **Hidden bugs:** No production code was changed. All CO-1/CO-2/CO-3 sentence rewrites are factually accurate against the source modules (`mcp/server.py`, `graph/audit_cascade.py`, workflow registries). The CO-4 architecture.md §4.4 fix is consistent with ADR-0004 CO-3. No introduced inconsistency.
- **Defensive-code creep:** Doc-only diff contains exactly the carry-over items specified by the spec. No scope additions, no defensive additions.
- **Idiom alignment:** nice_to_have.md §25 matches the established five-field entry format (What/Why/Trigger/Sketch/Related). Trigger is concrete (two named conditions with a logical AND). Milestone README Outcome section follows the M11 T02 close-out pattern. CHANGELOG promotion follows the existing milestone-section convention (confirmed against M21 entry).
- **Premature abstraction:** N/A (doc-only task).
- **Comment/docstring drift:** CHANGELOG T07 entry is informative and accurate. Outcome section chronological-ordering parenthetical is clean. ADR-0004 CO-3 replacement names Option A, the H1 lock date, the four `_build_standalone_*` helpers, and the inline-workflow surface distinction — all verifiable against `mcp/server.py`.
- **Simplification:** Milestone README Outcome bullets are appropriately concise per-task summaries. No verbosity issues.

---

## Sr. SDET review (2026-04-29)

**Test files reviewed:** none modified (docs-only task) | **Skipped:** n/a | **Verdict:** SHIP

### BLOCK

None.

### FIX

None.

### Advisory

**A1 — Historical "State on design_branch at pause" snapshot in milestone README is internally inconsistent with close-out status (doc consistency)**

`design_docs/phases/milestone_12_audit_cascade/README.md:110-111` — The "State on design_branch at pause" table still shows T06 and T07 as "📝 Planned (spec missing)" after T07 has shipped. This section was frozen at the mid-run pause point (after T05 shipped) and intentionally not updated; it is a historical checkpoint, not a live status surface. The authoritative close-out record is the Outcome section (lines 149-162) which correctly lists all 8 tasks. No spec AC required this section to be updated, so this is not a compliance failure. A reader skimming the README chronologically could reasonably confuse the freeze-frame for current status.

**Recommendation:** At the next touch to this README (or opportunistically), add a one-line note directly above the "State on design_branch at pause" heading indicating it reflects the mid-run state only, e.g., "(Snapshot — M12 is now ✅ Complete; see §Outcome for close-out summary.)" No AC impact; no tracking entry needed.

### What passed review (one line per lens)

- **Wrong-reason (Lens 1):** T07 is docs-only; no production code changed; zero ai_workflows/ diff verified against e8f43c9. No test assertions to evaluate for correctness.
- **Coverage gaps (Lens 2):** No new tests were added or expected. Existing 1478-test suite is unaffected. All M12 ACs that required code were already covered in T01-T06+T08; no residual gap introduced by close-out docs.
- **Mock overuse (Lens 3):** N/A — no test code modified.
- **Fixture hygiene (Lens 4):** N/A — no fixture changes.
- **Hermetic gating (Lens 5):** No new tests added; gating posture unchanged. All three gate commands confirmed clean: pytest 1478 passed / 11 skipped / 22 warnings, lint-imports 5 contracts kept 0 broken, ruff all checks passed.
- **Naming/assertion hygiene (Lens 6):** N/A — no test code touched.
