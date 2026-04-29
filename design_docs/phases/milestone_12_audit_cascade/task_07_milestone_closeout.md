# Task 07 — Milestone Close-out

**Status:** 📝 Planned.
**Grounding:** [milestone README](README.md) · [CLAUDE.md](../../../CLAUDE.md) close-out conventions · [M11 T02](../milestone_11_gate_review/task_02_milestone_closeout.md) (pattern mirrored).

## What to Build

Close M12. Confirm every exit criterion from the [milestone README](README.md) landed across T01–T06 + T08. Bundle four stale-framing amendments to [ADR-0004](../../adr/0004_tiered_audit_cascade.md) and one framing fix to [architecture.md](../../architecture.md) §4.4 in a single commit. Add an [EvalRunner cascade-fixture replay](../../nice_to_have.md) entry to `nice_to_have.md`. Update [CHANGELOG.md](../../../CHANGELOG.md), flip M12 complete in [roadmap.md](../../roadmap.md), and refresh the root [README.md](../../../README.md). No production code change — any finding becomes a forward-deferred carry-over on a future task or a new `nice_to_have.md` entry, never a drive-by fix.

Mirrors [M11 Task 02](../milestone_11_gate_review/task_02_milestone_closeout.md) so reviewers get identical close-out muscle memory.

---

## Carry-over items (mandatory — must all land in this task)

These were explicitly forward-deferred to T07 from the tasks that produced them.

### CO-1 — ADR-0004 §Decision item 1: stale landing-site framing

**Source:** T01 TA-LOW-03 / M12-T01-ISS-02.

**Current text (ADR-0004 §Decision, item 1, final sentence):**

> Both sit in the `TierRegistry` (`ai_workflows/primitives/tiers.py`) next to `planner-synth`. No new driver, no new LiteLLM route, no new env var.

**What actually landed (T01):** Auditor tier entries live in the **workflow-scoped registries** (`planner.py`, `summarize_tiers.py`; `slice_refactor.py` inherits via composition), not in `primitives/tiers.py`.

**Required fix:** Replace the stale sentence with the accurate landing site, preserving surrounding context. Exact replacement text is at Builder discretion; must cite T01 explicitly.

---

### CO-2 — ADR-0004 §Consequences: stale "No import-linter edit needed"

**Source:** T02 M12-T02-MED-01.

**Current text (ADR-0004 §Consequences, "New primitive" bullet, last sentence on line 54):**

> Fits the existing four-layer contract (graph imports only primitives; workflows / surfaces import graph). No import-linter edit needed.

**What actually landed (T02):** T02 added a new `lint-imports` contract to pin `audit_cascade.py` as a graph-layer module, so an import-linter edit **was** needed. `uv run lint-imports` now runs **5 contracts** (up from 4).

**Required fix:** Replace "No import-linter edit needed." with an accurate statement noting that T02 added a fifth lint-imports contract for the cascade primitive.

---

### CO-3 — ADR-0004 §Decision item 7: stale AuditCascadeNode reuse claim

**Source:** T05 spec §Propagation status.

**Current text (ADR-0004 §Decision, item 7):**

> Internal routing reuses the same `AuditCascadeNode`; the MCP tool is a thin surface wrapper.

**What actually landed (T05 Option A, H1-locked 2026-04-27):** `run_audit_cascade` **bypasses** `AuditCascadeNode` entirely and invokes the auditor `TieredNode` directly (four private `_build_standalone_*` helpers in `mcp/server.py`). The tool is not a thin wrapper over the sub-graph primitive — it is a standalone re-implementation.

**Required fix:** Replace **both clauses** of the stale sentence:
- Clause 1 ("Internal routing reuses the same `AuditCascadeNode`") — false; tool bypasses the cascade primitive entirely.
- Clause 2 ("the MCP tool is a thin surface wrapper") — false; tool is a standalone re-implementation (see `mcp/server.py`'s `_build_standalone_audit_config`, `_build_audit_configurable`, `_make_standalone_auditor_prompt_fn` and the fourth build helper).

Accurate replacement must: name Option A (H1 locked 2026-04-27), explain that `run_audit_cascade` invokes the auditor `TieredNode` directly with caller-supplied `artefact_kind` (H2 Option A), and acknowledge that `AuditCascadeNode` remains the inline-workflow surface (workflow sub-graph composition is unchanged). Exact wording at Builder discretion within those constraints.

---

### CO-4 — architecture.md §4.4: stale cascade-reuse framing

**Source:** T05 round-2 TA-T05-LOW-02.

**Current text (architecture.md line 105, the `run_audit_cascade` bullet):**

> `run_audit_cascade(artefact_ref, tier_ceiling?) → AuditReport` *(lands at M12 T05 — standalone invocation of the tiered audit cascade over an existing artefact; reuses the `AuditCascadeNode` primitive the workflows consume inline. See KDR-011 + [ADR-0004](adr/0004_tiered_audit_cascade.md).)*

**Required fix:** Replace "reuses the `AuditCascadeNode` primitive the workflows consume inline" with accurate framing that T05 Option A invokes the auditor `TieredNode` directly, bypassing `AuditCascadeNode`. Surrounding text (tool signature, M12 T05 note, KDR/ADR links) must remain intact.

---

### CO-5 — nice_to_have.md: EvalRunner cascade-fixture replay entry

**Source:** M12 T06 spec / T06 KDR-004 carve-out note.

T06 establishes the cascade fixture-capture convention (`evals/<dataset>/<workflow>/<cascade_name>_primary/` + `<cascade_name>_auditor/`) but explicitly **does not** enable `EvalRunner` replay for cascade nodes because `EvalRunner._resolve_node_scope` requires a `<node>_validator` pair (KDR-004), which cascade nodes do not provide.

**Required addition:** Append a new numbered entry (§25) to `nice_to_have.md` covering all five canonical fields:
- **What it would add:** `EvalRunner` replay mode for cascade author/auditor nodes (either by extending `_resolve_node_scope` to recognise `_primary`/`_auditor` suffixes and skip the `<node>_validator` pair-lookup on the auditor side, or by a new `CascadeEvalRunner` subclass that overrides `_resolve_node_scope` while leaving the base `EvalRunner` untouched).
- **Why deferred:** KDR-004 validator-pairing requirement is architecturally load-bearing (`EvalRunner._resolve_node_scope` requires `<node>_validator`); a by-suffix override needs design work and a new ADR recording the carve-out before it lands.
- **Trigger to adopt:** A workflow flips `audit_cascade_enabled` to `True` as a production default AND the team wants CI-gated regression coverage of the auditor's verdict quality (not just the primary node's output shape).
- **Integration sketch:** Either (a) extend `EvalRunner._resolve_node_scope` to recognise `_primary` / `_auditor` suffixes as cascade-internal conventions and skip the validator-pair lookup for the `_auditor` side (the cascade's validator node is `<cascade_name>_validator`, not `<cascade_name>_auditor_validator`), or (b) introduce a `CascadeEvalRunner` subclass that overrides `_resolve_node_scope` for cascade fixtures while leaving the base `EvalRunner` untouched. Touchpoints: `ai_workflows/evals/runner.py` (`_resolve_node_scope` + `_invoke_replay`), `tests/evals/test_runner.py` (new test cases for the cascade-replay path). New ADR required to record the validator-pairing carve-out per KDR-004.
- **Related:** M12 T06 (fixture convention), KDR-004, `EvalRunner._resolve_node_scope`.

---

## Deliverables

### [ADR-0004](../../adr/0004_tiered_audit_cascade.md)

Apply CO-1, CO-2, CO-3 in-place (three sentence-level edits across two sections). Land as part of the ADR-amendment commit.

### [architecture.md](../../architecture.md) §4.4

Apply CO-4 in-place (one sentence-level edit to the `run_audit_cascade` bullet). Land in the same ADR-amendment commit.

### [nice_to_have.md](../../nice_to_have.md)

Apply CO-5 (new §25 entry, following the established entry format: **What this would add**, **Why deferred**, **Trigger to adopt**, **Integration sketch**, **Related**). Land in the same commit as CO-1–CO-4.

### [README.md](README.md) (milestone)

- Flip **Status** from `📝 Planned` to `✅ Complete (2026-04-29)`.
- Flip row 07 in §"Task order" table from `📝 Planned` to `✅ Complete (2026-04-29)` (matches the format of every other already-shipped row).
- Flip §"Exit criteria" item 10 (`tests/graph/test_audit_cascade.py + tests/workflows/test_audit_cascade_wiring.py — hermetic coverage…`) to `✅ (T02/T03 complete 2026-04-27)` — coverage shipped at T02/T03; T07 close-out is the natural moment to mark it.
- Update §"Cumulative carry-over forward-deferred to M12 T07 close-out" to add CO-5 as the fifth item: "**`nice_to_have.md` §25** EvalRunner cascade-fixture replay — from T06 spec / KDR-004 carve-out." (Current list has only CO-1–CO-4.)
- Append an **Outcome** section summarising all 8 tasks:
  - T01 — Auditor TierConfigs (`auditor-sonnet` + `auditor-opus`) in workflow-scoped registries; KDR-003 hermetic grep extended.
  - T02 — `AuditCascadeNode` graph primitive + `AuditFailure` exception + re-prompt template + `AuditVerdictNode`; `RetryingEdge` integration; HumanGate escalation path; lint-imports contract count 4 → 5.
  - T08 — T02 amendment: `audit_cascade_node(skip_terminal_gate=True)` parameter for non-interruptible fan-out contexts (slice_refactor parallel branches).
  - T03 — Workflow wiring: module-constant cascade enable + `AIW_AUDIT_CASCADE*` env-var overrides for `planner` + `slice_refactor`; KDR-014 / ADR-0009 locked decision.
  - T04 — `TokenUsage.role` tag + `CostTracker.by_role(run_id)` aggregation; role-tagged records in existing ledger; KDR-009 preserved.
  - T05 — `run_audit_cascade` MCP tool + SKILL.md ad-hoc-audit section; Option A standalone path (bypasses `AuditCascadeNode`); `_strip_code_fence` helper (closes latent T02 bug).
  - T06 — Eval harness: author/auditor fixture split (`<cascade_name>_primary/` / `<cascade_name>_auditor/`); `evals/README.md`; golden tests for planner + slice_refactor; KDR-004 EvalRunner carve-out.
  - T07 — ADR-0004 amendment (CO-1/CO-2/CO-3) + architecture.md framing fix (CO-4) + nice_to_have.md §25 entry (CO-5) + status flip.
  - KDR additions: KDR-011 (tiered audit cascade), KDR-014 (framework owns quality policy), per ADR-0004 + ADR-0009.
  - Green-gate snapshot: `uv run pytest` + `uv run lint-imports` (5 contracts) + `uv run ruff check`.

### [roadmap.md](../../roadmap.md)

Flip M12 row `Status` from `planned` to `✅ complete (2026-04-29)`.

### [CHANGELOG.md](../../../CHANGELOG.md)

Promote the accumulated `[Unreleased]` M12 entries into a dated section `## [M12 Tiered Audit Cascade] - 2026-04-29`. Keep the top-of-file `[Unreleased]` section as a fresh empty skeleton. Add a T07 close-out entry at the top of the new dated section. Record:

- CO-1/CO-2/CO-3 ADR-0004 amendments and CO-4 architecture.md framing fix.
- CO-5 nice_to_have.md §25 entry (EvalRunner cascade-fixture replay).
- The 5-contract lint-imports snapshot confirming the cascade contract added at T02.
- Docs-only scope honoured at T07: zero `ai_workflows/` diff.

### Root [README.md](../../../README.md)

- Flip the M12 row in the milestone status table to `Complete (2026-04-29)`.
- Update the narrative paragraph: replace any "Planned" or "in progress" wording with M12 complete.
- **No change to the §Next section.** M21 is the newest shipped milestone and its §Next pointer at M22 is unaffected by M12 close-out — M12 is closed retroactively. Do not add M12-mentioning prose to the §Next narrative.

---

## Acceptance Criteria

- [ ] ADR-0004 §Decision item 1 no longer references `primitives/tiers.py` as landing site (CO-1).
- [ ] ADR-0004 §Consequences "New primitive" bullet no longer says "No import-linter edit needed"; accurate statement present (CO-2).
- [ ] ADR-0004 §Decision item 7 no longer claims internal routing reuses `AuditCascadeNode`; Option A bypass accurately described (CO-3).
- [ ] architecture.md §4.4 `run_audit_cascade` bullet no longer says "reuses the `AuditCascadeNode` primitive … inline"; accurate T05 Option A framing present (CO-4).
- [ ] `nice_to_have.md` §25 EvalRunner cascade-fixture replay entry added with trigger + integration sketch (CO-5).
- [ ] Milestone README `**Status:**` line flipped to `✅ Complete (2026-04-29)`; Outcome section covers all 8 tasks.
- [ ] Milestone README §"Task order" row 07 Status column flipped from `📝 Planned` to `✅ Complete (2026-04-29)`.
- [ ] Milestone README §"Exit criteria" item 10 marked `✅ (T02/T03 complete 2026-04-27)`.
- [ ] Milestone README §"Cumulative carry-over" backfilled with CO-5 (currently lists only CO-1–CO-4).
- [ ] `roadmap.md` M12 row reflects complete status.
- [ ] `CHANGELOG.md` has a dated `[M12 Tiered Audit Cascade]` section with a T07 close-out entry at the top; `[Unreleased]` retained as an empty skeleton.
- [ ] Root `README.md` M12 table row + narrative updated.
- [ ] Zero `ai_workflows/` diff at T07 (docs-only invariant — verify with `git diff --stat e8f43c9..HEAD -- ai_workflows/` against T06 landing commit `e8f43c9`; update SHA at Builder pre-flight if a later commit has since landed on `design_branch`).
- [ ] `uv run pytest` + `uv run lint-imports` (5 contracts) + `uv run ruff check` all clean.

---

## Dependencies

- T01–T06 + T08 all landed and gates green.

## Out of scope (explicit)

- Any code change in `ai_workflows/`. T07 is docs-only; code deltas forbidden here.
- The `_DynamicState["slice"]` workflow-name leak (T03 audit `M12-T03-LOW-05`) — its own future task triggered by "first non-`slice` embedding workflow"; explicitly NOT bundled here per M12 README §Cumulative carry-over.
- Cascade-depth tuning, shared-quota circuit breaker, cross-workflow telemetry dashboard — all deferred per M12 README §Propagation status.

## Carry-over from spec-hardening (task-analyzer Round 3 LOWs — push to Builder)

These are spec-level guidance items surfaced by the Round-3 task-analyzer; they are not ACs but should be followed during implementation:

- **TA-T07-LOW-01:** When writing the Outcome section in the milestone README, prepend a one-line parenthetical explaining the chronological-not-numeric ordering of T08 in the bullet list (T08 amends T02 and ships before T03 per the milestone README §"Task order" sequencing exception), so readers don't mistake it for an editorial typo.
- **TA-T07-LOW-02:** CO-5's nice_to_have.md §25 "Integration sketch" field is already specified in the CO-5 §Required addition above (the five-bullet form). Builder should use that sketch verbatim — do not derive a new one from scratch.
- **TA-T07-LOW-03:** The T06 landing commit SHA is `e8f43c9` at spec-drafting time. If a later commit has since landed on `design_branch` before T07 Builder pre-flight, update the SHA in the zero-diff AC to the actual T07 pre-task baseline commit.
- **TA-T07-LOW-04:** Root README §Next section ("M21 is complete; next planned is M22…") is unaffected by M12 close-out. Do not rewrite §Next — M12 is retroactively closed after M21 already shipped; the linear-narrative-by-newest-milestone surface stays as-is.

## Propagation status

Filled in at audit time. Any finding from T07 audits that requires code lands as a forward-deferred carry-over on the appropriate future milestone task (M13+) or as a new `nice_to_have.md` entry — same discipline as M11 T02.
