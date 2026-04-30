# Task 05 — Milestone Close-out

**Status:** ✅ Complete (2026-04-30).
**Grounding:** [milestone README](README.md) · [CLAUDE.md](../../../CLAUDE.md) close-out conventions · [M12 T07](../milestone_12_audit_cascade/task_07_milestone_closeout.md) (pattern mirrored) · [KDR-014](../../architecture.md) (framework owns quality policy).

## What to Build

Close M15. Confirm every exit criterion from the [milestone README](README.md) landed across T01–T04. Apply CO-1 (the forward-deferred architecture.md stale-reference fix from M15-T04-LOW-02). Correct the stale "4 contracts kept" claim in milestone README exit criterion #10 to "5 contracts kept" (audit_cascade contract was added at M12 T02 and has been in effect since). Update [CHANGELOG.md](../../../CHANGELOG.md), flip M15 complete in [roadmap.md](../../roadmap.md), and refresh the root [README.md](../../../README.md). No production code change — any finding becomes a forward-deferred carry-over on a future task, never a drive-by fix.

Mirrors [M12 T07](../milestone_12_audit_cascade/task_07_milestone_closeout.md) so reviewers get identical close-out muscle memory.

---

## Carry-over items (mandatory — must all land in this task)

These were explicitly forward-deferred to T05 from the tasks that produced them.

### CO-1 — `design_docs/architecture.md` §4.1: stale `tiers.yaml` reference

**Source:** M15-T04-LOW-02 (T04 audit, 2026-04-30).

**Current text (`architecture.md:67`, TierConfig row):**

> `TierConfig` + `pricing.yaml` / `tiers.yaml` | Logical tier ("planner", "implementer", "local_coder") → concrete provider + model + limits. Tiers that route to LiteLLM-supported providers carry a LiteLLM model string; the `claude_code` tier carries a subprocess invocation spec.

**What actually landed (T04):** `tiers.yaml` was deleted from the repo root and relocated to `docs/tiers.example.yaml` as a schema-smoke fixture. Per KDR-014, the authoritative tier definitions live in per-workflow Python registries, not in any YAML file. The YAML file is an example only, not a dispatch-time input.

**Required fix:** Update the cell heading to reflect the post-T04 reality. Either:
- Replace `` `pricing.yaml` / `tiers.yaml` `` with `` `pricing.yaml` / `docs/tiers.example.yaml` `` (accurate filename) and add a note that `docs/tiers.example.yaml` is a schema-reference example only, not loaded at dispatch time; or
- Drop the `tiers.yaml` / `docs/tiers.example.yaml` reference entirely from the cell heading since the authoritative tier definitions are per-workflow Python registries per KDR-014, and the YAML is purely illustrative.

Either option is acceptable; Builder chooses whichever reads most clearly. The cell body may also note that `docs/tiers.example.yaml` is the schema-smoke fixture and that per-workflow registries (e.g. `planner.py`, `slice_refactor.py`) are the authoritative tier source.

---

## Deliverables

### 1. `design_docs/architecture.md` §4.1

Apply CO-1 in-place (one row-level edit to the TierConfig row). Exact wording at Builder discretion within the CO-1 constraints above. Land in the close-out commit.

### 2. Milestone README (`design_docs/phases/milestone_15_tier_overlay/README.md`)

- Flip **Status** from `📝 Planned (rescoped 2026-04-30; deferred — implement after M17 close-out).` to `✅ Complete (2026-04-30).`
- Flip row 05 in §"Task order" table from `Milestone close-out` (no status marker) to `✅ Complete (2026-04-30)`.
- Correct exit criterion #10 `uv run lint-imports` snapshot: replace `(4 contracts kept — no new layer; fallback schema in `primitives`, cascade logic in `graph`)` with `(5 contracts kept — no new layer; fallback schema in `primitives`, cascade logic in `graph`; audit_cascade contract was added at M12 T02 and remains in effect)`. The number was stale at spec-drafting time.
- Mark each exit criterion as satisfied with the task that landed it (inline annotation after each item). Specifically:
  - #1 (`TierConfig.fallback` schema): `✅ T01`
  - #2 (Fallback dispatch logic): `✅ T02`
  - #3 (Cost attribution): `✅ T02`
  - #4 (Validator interaction): `✅ T01/T02`
  - #5 (CircuitOpen cascade): `✅ T03`
  - #6 (`aiw list-tiers`): `✅ T03`
  - #7 (`docs/tiers.example.yaml`): `✅ T04`
  - #8 (ADR-0006): `✅ T04`
  - #9 (Hermetic tests): `✅ T01/T02/T03`
  - #10 (Gates green — 5 contracts): `✅ T01–T04`
- Append an **Outcome** section summarising all five tasks:
  - T01 — `TierConfig.fallback: list[Route]` schema field; `AllFallbacksExhaustedError(NonRetryable)` with `attempts: list[TierAttempt]`; flat-only nesting enforced at schema validation.
  - T02 — `TieredNode` cascade dispatch after retry-budget exhaustion; per-fallback retry counter; cost attribution accumulates across all attempts; `ValidatorNode` interaction unchanged (runs on successful route output).
  - T03 — `aiw list-tiers [--workflow <name>]` CLI command; HTTP CircuitOpen cascade test (`test_http_fallback_on_circuit_open.py`) pinning the MCP envelope shape when cascade fires under a tripped circuit breaker.
  - T04 — ADR-0006 (fallback cascade semantics — seven decision points + four rejected alternatives; KDR-014 YAML-overlay rejection recorded); `tiers.yaml` → `docs/tiers.example.yaml` relocation; `### Fallback chains` subsection in `docs/writing-a-workflow.md`.
  - T05 — `architecture.md` §4.1 stale `tiers.yaml` reference corrected (CO-1 / M15-T04-LOW-02); lint-imports contract count corrected to 5; status surfaces flipped.
  - KDR additions: none (KDR-014 strengthened by ADR-0006 YAML-overlay rejection, per T04).
  - Green-gate snapshot: `uv run pytest` (1532 passed) + `uv run lint-imports` (5 contracts kept) + `uv run ruff check` (all checks passed).

### 3. `design_docs/roadmap.md`

Two edits:
1. Flip the §Milestones table row at `roadmap.md:28` from `📝 planned (rescoped 2026-04-30 — YAML overlay dropped; deferred, implement after M17)` to `✅ complete (2026-04-30)`.
2. Update the `## Deferred` narrative entry at `roadmap.md:56` (the paragraph beginning `**M15 — Tier fallback chains (rescoped 2026-04-30; deferred).**`) in-place: prefix with `✅ Shipped 2026-04-30 — ` and rewrite the closing verb phrase ("Implement after M17.") to past tense ("Implemented.")  Do not delete the entry — it preserves the rescoping rationale.

### 4. Root `README.md`

- Flip the M15 row in the milestone status table from `| M15 — Tier overlay + fallback chains | Planned |` to `| **M15 — Tier overlay + fallback chains** | Complete (2026-04-30) |`.
- No change to the §Next section — M15 ships alongside the already-complete milestones; the §Next narrative focuses on whatever is the next planned milestone, not M15.

### 5. `CHANGELOG.md`

Add a T05 close-out entry under `## [Unreleased] → ### Added` noting: M15 milestone closed; CO-1 architecture.md stale reference corrected; lint-imports contract count corrected; status surfaces flipped. The accumulated M15 T01–T04 entries remain under `[Unreleased]` — they will be promoted to a dated version section when M15 publishes (`uv publish`). T05 does not bump the version (already at `0.4.0` per M17 T04 close-out; M15 was retroactively completed after M17 shipped).

### 6. Status surfaces (spec + issue files)

- Flip this spec's `**Status:**` from `📝 Planned.` to `✅ Complete (2026-04-30).` in the same commit.
- Create `design_docs/phases/milestone_15_tier_overlay/issues/task_05_issue.md` (audit file, created by the Auditor at audit time — Builder does not create this file).

---

## Acceptance Criteria

| AC | Description |
|---|---|
| AC-1 | `design_docs/architecture.md:67` TierConfig row no longer references `tiers.yaml` as a dispatch-time or repo-root file; accurate post-T04 framing present (either `docs/tiers.example.yaml` with example-only note, or YAML reference dropped in favour of per-workflow Python registry statement per KDR-014) |
| AC-2 | Milestone README `**Status:**` line flipped to `✅ Complete (2026-04-30)` |
| AC-3 | Milestone README §"Task order" row 05 Status column shows `✅ Complete (2026-04-30)` |
| AC-4 | Milestone README exit criterion #10 `uv run lint-imports` snapshot corrected from "4 contracts" to "5 contracts"; all 10 exit criteria annotated with satisfying task |
| AC-5 | Milestone README has **Outcome** section covering T01–T05 + gate snapshot |
| AC-6 | `design_docs/roadmap.md` M15 §Milestones table row (`roadmap.md:28`) reflects `✅ complete (2026-04-30)`; `## Deferred` narrative entry prefixed with `✅ Shipped 2026-04-30 — ` and rewritten to past tense |
| AC-7 | Root `README.md` M15 table row shows `Complete (2026-04-30)` |
| AC-8 | `CHANGELOG.md` has T05 close-out entry under `[Unreleased]` |
| AC-9 | Zero `ai_workflows/` diff at T05 (docs-only invariant — verify with `git diff --stat HEAD~1..HEAD -- ai_workflows/`; must return empty) |
| AC-10 | `uv run pytest` passes (full suite — no regressions) |
| AC-11 | `uv run lint-imports` passes — 5 contracts kept, 0 broken |
| AC-12 | `uv run ruff check` passes |

---

## Smoke test

```bash
# AC-1: architecture.md no longer says tiers.yaml as dispatch-time file
grep -n "tiers.yaml" design_docs/architecture.md  # should return 0 hits (or only docs/tiers.example.yaml)

# AC-2: milestone README status flipped
grep "Status" design_docs/phases/milestone_15_tier_overlay/README.md | head -1

# AC-4: exit criterion #10 corrected
grep "contracts kept" design_docs/phases/milestone_15_tier_overlay/README.md

# AC-9: docs-only invariant (run after the T05 commit)
git diff --stat HEAD~1..HEAD -- ai_workflows/  # must be empty
```

---

## Dependencies

- T01–T04 all landed and gates green. ✅ (all shipped as of 2026-04-30)

## Out of scope (explicit)

- Any code change in `ai_workflows/`. T05 is docs-only; code deltas forbidden here.
- `ai_workflows/primitives/tiers.py` docstring update for `TierRegistry.load()` — optional cosmetic deferred from M15-T04-LOW-02; Builder may include it if trivial and zero-risk, but it is non-AC and non-blocking.
- Version bump — already at `0.4.0` per M17 T04 close-out. No bump at T05.
- Publishing to PyPI — out of scope for the autonomous loop; requires explicit user action.
- Any new feature, any KDR change.

---

## Carry-over from prior milestones

*(none at T05 kickoff beyond the explicitly named CO-1 above)*

## Carry-over from prior audits

- [x] **M15-T04-LOW-02 — `architecture.md §4.1` stale `tiers.yaml` reference** (severity: LOW, source: M15 T04 audit, 2026-04-30)
      `design_docs/architecture.md:67` TierConfig row still references `tiers.yaml`. After M15 T04, `tiers.yaml` no longer exists at the repo root; the relocated file is `docs/tiers.example.yaml` (schema-smoke fixture, not loaded at dispatch time).
      **Recommendation:** Update the architecture.md §4.1 TierConfig row as described in CO-1 above. Also optionally refresh `TierRegistry.load()` docstrings in `ai_workflows/primitives/tiers.py` to clarify that the `root/tiers.yaml` lookup is dev-fixture only — non-blocking, cosmetic.

## Carry-over from task analysis

- [x] **TA-LOW-01 — Outcome §gate-snapshot pytest count pre-asserted as `1532 passed`** (severity: LOW, source: task_analysis.md round 1)
      The spec's Outcome section hard-codes `1532 passed` from the T04 gate run. T05 may inherit a different count.
      **Recommendation:** At close-out commit, run `uv run pytest` and update the Outcome §gate-snapshot count to the live value.

- [x] **TA-LOW-02 — Outcome §"KDR additions: none" missing cross-link to ADR-0006** (severity: LOW, source: task_analysis.md round 1)
      The "KDR-014 strengthened by ADR-0006 YAML-overlay rejection" note has no hyperlink to ADR-0006.
      **Recommendation:** Hyperlink `ADR-0006` inline in the Outcome section so reviewers can jump to the rejection rationale.

- [x] **TA-LOW-03 — T04 audit LOW-1 carry-over checkboxes unticked** (severity: LOW, source: task_analysis.md round 1)
      `task_04_issue.md:71-75` flags four `[ ]` carry-over checkboxes in `task_04_adr_0006_and_tiers_doc_relocation.md` that remain unticked despite resolved diffs. Auditor suggested rolling this into T05 close-out.
      **Recommendation:** Optionally tick the four carry-over checkboxes in `task_04_adr_0006_and_tiers_doc_relocation.md` to `[x]` during T05 (one-line bookkeeping fix; non-blocking).

- [x] **TA-LOW-04 — CO-1 does not clarify that `pricing.yaml` reference stays** (severity: LOW, source: task_analysis.md round 1)
      `architecture.md:67` cell reads `` `pricing.yaml` / `tiers.yaml` ``. CO-1 only directs the Builder to fix the `tiers.yaml` half. Builder should not accidentally remove the `pricing.yaml` reference.
      **Recommendation:** In CO-1 implementation, preserve the `pricing.yaml` reference — CO-1 only touches the `tiers.yaml` half of the cell heading.
