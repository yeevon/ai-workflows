# M15 Tier Fallback Chains — Task Analysis

**Round:** 3 | **Analyzed on:** 2026-04-30 | **Analyst:** task-analyzer agent
**Specs analyzed:** `task_01_fallback_schema.md` (✅ Built — re-confirmed clean), `task_02_tierednode_cascade_dispatch.md` (round 3 re-check after M4 fix)

## Summary

| Severity | Count |
| --- | --- |
| 🔴 HIGH | 0 |
| 🟡 MEDIUM | 0 |
| 🟢 LOW | 0 |

**Stop verdict:** CLEAN

Round 2's sole MEDIUM (M4 — module docstring "exactly-once invariant" not flagged for update) is resolved. Round 3 surfaces no new findings. T02 is ready for `/clean-implement` (or `/auto-implement`) Builder kickoff.

## Findings

*None.*

## What's structurally sound

- **M4 fix verified.** T02 spec now contains an explicit §1.6 "Module docstring update" sub-section (lines 110–117) instructing the Builder to amend `tiered_node.py:39–44`'s "Exactly-once invariants" bullet. The new wording is fully written out in the spec — the Builder does not have to interpret intent. The bullet's three sub-claims are each correctly relaxed:
  - "one provider call per *attempted route*" (matches §1.5 cascade walk)
  - "one `CostTracker.record` per *successful attempt* (cost callback fires on success only)" (matches §1's cost-attribution paragraph at line 103-108)
  - "one structured log record per *attempt* (success or failure)" (matches §1.5 record-count contract)
  - The closing degenerate-case sentence ("For tiers with `fallback=[]` … the new contract degenerates to the old invariant") preserves backward compat reasoning and aligns with AC-6.
- **AC-13 extended.** Lines 189–195 now explicitly bind the per-attempt log records *and* the docstring update into a single AC with a citation to §1.6. The two surfaces flip together at task close — no risk of the Builder shipping behaviour without the doc, or vice versa. Status-surface hygiene: code + doc edits in the same commit.
- **Live-codebase docstring location verified.** `grep -n "Exactly-once invariants" tiered_node.py` returns line 39, and the bullet runs through line 44 (verified with `sed -n '39,44p'`). The spec's line citation is accurate and stable; the Builder's `Edit` tool call against the cited text will be unambiguous.
- **Cited helpers still resolve.** `_provider_from_route` at `tiered_node.py:509`, `_model_from_route` at `:518`, `CircuitOpen` guard region at `:238–247`, semaphore acquisition pattern at `:255–273` — all confirmed present, exactly where the spec claims. The round-2 fixes (M1/M2/M3) remain wired correctly.
- **Carry-over LOWs unchanged and load-bearing.** TA-LOW-01 through TA-LOW-04 (lines 241–275) survive unchanged. L2 (`TierAttempt.usage` always-None) is the most consequential — it tells the Builder to drop the field unless a consumer materialises during implementation. Builder retains discretion; no ambiguity.
- **T01 ✅ Built — no further findings.** All T01 carry-over checkboxes ticked. Re-read confirms no regression.
- **Layer + KDR discipline.** Round 3's deltas are docstring + AC text only. No new imports, no new types, no layer movement. KDR-004 (validator pairing), KDR-006 (three-bucket retry — `AllFallbacksExhaustedError(NonRetryable)` preserves the bucket contract via `RetryingEdge → on_terminal`), KDR-009, KDR-013 all unchanged. No cross-cutting drift.
- **Smoke command surface.** `tests/graph/test_tiered_node_fallback.py` is a new file (matches Builder convention); the four cited test names are well-formed. The fixture pattern (`_FakeLiteLLMAdapter` + `_RaisingLiteLLMAdapter`, `_build_config` helper) mirrors the existing `tests/graph/test_tiered_node.py` per spec § 2 — verified the sibling test file convention exists in-tree. Auditor smoke will be `uv run pytest tests/graph/test_tiered_node_fallback.py -v` against the four named tests.

## Cross-cutting context

- **`nice_to_have.md` slot drift** (round 1's standing note) — still applies for T05 milestone close-out, not T02. No M15-task spec currently hardcodes a slot number; the two anticipated deferrals (immediate-fail-over fast-path, tier-name reference variant) will land at T05 against whichever slots are free at close time.
- **ADR-0006** still reserved for T04. Slot free.
- **CHANGELOG entry** under `[Unreleased] → ### Added` is correctly scoped (M15 Task 02 line); the date placeholder `YYYY-MM-DD` is a Builder substitution.
- **SEMVER posture.** T02 is purely additive at the public surface (two new exports: `TierAttempt`, `AllFallbacksExhaustedError`). M15 ships ≥ 0.5.0 (minor bump from 0.4.0 baseline), spec-stated at line 217. No backward-incompatible change; AC-6 + AC-8 hold the empty-fallback default path.
- **Memory:** M15 is the active "deferred-after-M17" milestone returning to play; T01 shipped 2026-04-30 (cycle 1). T02 ready to Build.
- **Stop verdict CLEAN** — Builder can proceed without further spec edits. Orchestrator advances to `/clean-implement` (or `/auto-implement`) M15 T02.
