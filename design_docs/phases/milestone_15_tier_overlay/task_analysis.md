# M15 Tier Fallback Chains — Task Analysis

**Round:** 2 | **Analyzed on:** 2026-04-30 | **Analyst:** task-analyzer agent
**Specs analyzed:** `task_01_fallback_schema.md` (rewrite of round-1 `task_01_overlay_and_fallback_schema.md`)

## Summary

| Severity | Count |
| --- | --- |
| 🔴 HIGH | 0 |
| 🟡 MEDIUM | 0 |
| 🟢 LOW | 2 |

**Stop verdict:** LOW-ONLY — round-1 H1–H6 + M1–M5 all resolved; spec is implementable as written. Two cosmetic LOWs left for spec carry-over.

---

## Round-1 fixes verified

Walked the round-1 finding list against the rewritten spec and the live tree:

| Round-1 finding | Round-2 status |
| --- | --- |
| **H1** — overlay-loader scope contradicts rescoped README | ✅ Resolved. Deliverables §1–§2 now ship `TierConfig.fallback` field + 4 hermetic tests only; no `load_overlay`, `merge_overlay`, `OverlayParseError`, `_resolve_overlay_path`, `$AIW_TIERS_PATH`, `~/.ai-workflows/tiers.yaml`. Out-of-scope §86 explicitly excludes "YAML overlay / persistent user tier config" with KDR-014 rationale. |
| **H2** — KDR-014 violation via overlay loader | ✅ Resolved. No persistent-config-override path remains in the spec. |
| **H3** — stale "0.2.0" version annotation | ✅ Resolved. Spec line 24: `# Added in M15 T01 (fallback cascade).` — no version pin, no `__version__` claim. CHANGELOG framing at AC-7 uses `[Unreleased]` correctly. |
| **H4** — `_LOG.warning(...)` symbol not defined in `tiers.py` | ✅ Resolved (overlay-only code path was deleted; no logging call remains). |
| **H5** — wrong line numbers for `_resolve_tier_registry` | ✅ Resolved (no `_dispatch.py` reference in T01 anymore — Out-of-scope §79 confirms "no `_dispatch.py` changes"). |
| **H6** — re-declared discriminator union | ✅ Resolved. Spec §1 now uses `fallback: list[Route] = Field(default_factory=list, …)` (line 25) and explicitly says "Reuse it directly — do not re-declare the discriminator union" (line 48). Verified `Route` alias exists at `ai_workflows/primitives/tiers.py:80`. |
| **M1** — filename retains "overlay_and_" | ✅ Resolved. `ls design_docs/phases/milestone_15_tier_overlay/` shows `task_01_fallback_schema.md` only; old file removed. README line 83 already points to the new filename. |
| **M2** — moot Risks §1 + §2 | ✅ Resolved. Risks section (lines 89–91) keeps only the nested-fallback error-message risk. |
| **M3** — Out-of-scope framing referenced overlay | ✅ Resolved. Out-of-scope (lines 77–87) is rewritten cleanly: T02 cascade, T02/T03 cost, T03 list-tiers, T04 ADR + relocation, T04 docs, M8 reactive-override coexistence, no MCP schema change, YAML overlay explicitly dropped with KDR-014 trigger named. |
| **M4** — AC-9 wire-smoke too heavy for schema-only | ✅ Resolved. New AC-4 ("Schema round-trip preserved") is hermetic-equivalent — no `aiw run planner` invocation. |
| **M5** — Dependencies referenced "0.1.3 patch" | ✅ Resolved. Dependencies §75 now reads "Ships against 0.4.0 baseline. M15 will ship as the next minor (≥0.5.0). M16 + M17 already shipped." Verified `__version__ = "0.4.0"` at `ai_workflows/__init__.py:33`. |
| **L1/L2/L3** | ✅ Pushed to spec carry-over (lines 95–105) as TA-LOW-01/02/03. |

## Live-codebase claims verified

- `Route` alias at `ai_workflows/primitives/tiers.py:80` → `Annotated[LiteLLMRoute | ClaudeCodeRoute, Field(discriminator="kind")]`. Spec line 48 cites this verbatim. ✓
- `TierConfig` at `ai_workflows/primitives/tiers.py:83-94` has fields `name`, `route`, `max_concurrency=1`, `per_call_timeout_s=120` — matches spec §1 base shape exactly. ✓
- `from typing import Annotated, Any, Literal` at `tiers.py:44` — `Any` already imported, so the validator's `v: Any` annotation is fine. ✓
- `tests/primitives/test_tiers_loader.py` exists; spec AC-3/AC-4 reference it correctly. ✓
- `pyproject.toml` defines exactly 5 `[[tool.importlinter.contracts]]` blocks. AC-5's "5 contracts kept, 0 broken" matches. ✓
- `__version__ = "0.4.0"` at `ai_workflows/__init__.py:33`. Spec dependencies framing (≥0.5.0 next minor) is consistent. ✓
- `CHANGELOG.md:8` → `## [Unreleased]` block exists and is currently empty; AC-7's framing is sound. ✓
- README link at line 83 is already `[\`TierConfig.fallback\` schema + hermetic tests](task_01_fallback_schema.md)` — link target matches the renamed spec file. ✓
- `AllFallbacksExhaustedError` / `TierAttempt` confirmed absent from current tree (`grep -rn` returns 0) — correctly out-of-scope for T01 (T02 territory). ✓

## Findings (round 2)

### 🟢 LOW

#### L1 — Spec doesn't list the new `pydantic.field_validator` import the Builder must add

**Target spec:** `task_01_fallback_schema.md` §1 (lines 14–46).
**Issue:** The validator block at line 34 uses `@field_validator("fallback", mode="before")`, but `ai_workflows/primitives/tiers.py:47` currently reads `from pydantic import BaseModel, Field` only. `field_validator` is not imported anywhere in the file. The spec doesn't tell the Builder to add the import. A competent Builder will catch the `NameError` at first test run and add `field_validator` to the import line, but the spec could pre-empt the round-trip by naming it.
**Recommendation:** Push to spec carry-over.
**Push to spec carry-over:** *"§1 import update: extend `tiers.py` line 47 from `from pydantic import BaseModel, Field` to `from pydantic import BaseModel, Field, field_validator`. Pydantic v2 `field_validator` is not currently imported in this file."*

#### L2 — Round-1 carry-over TA-LOW-01 is now moot

**Target spec:** `task_01_fallback_schema.md` carry-over §95–97 (TA-LOW-01).
**Issue:** TA-LOW-01 says *"the README link at line 83 should be updated from `task_01_overlay_and_fallback_schema.md` to `task_01_fallback_schema.md` if the old file is removed."* Verified both: old file is gone (`ls` confirms only `task_01_fallback_schema.md` remains); README line 83 already points to the new filename. The carry-over item is satisfied at spec-rewrite time and shouldn't ride along into implementation as an open AC.
**Recommendation:** Push to spec carry-over (delete TA-LOW-01 from the carry-over block, or mark it satisfied with a strikethrough so the audit trail is preserved). Builder shouldn't see an open checkbox for already-completed work.
**Push to spec carry-over:** *"TA-LOW-01 is satisfied at orchestrator-rename time (file `task_01_overlay_and_fallback_schema.md` removed; README line 83 points to `task_01_fallback_schema.md`). Mark `[x]` or remove from carry-over so the Builder doesn't re-process."*

---

## What's structurally sound

- **Scope alignment with rescoped README.** Spec body matches README exit-criterion #1 verbatim and only that criterion. Cascade dispatch (#2), cost attribution (#3), validator interaction (#4), CircuitOpen test (#5), `aiw list-tiers` (#6), `tiers.yaml` relocation (#7), ADR-0006 (#8) are all explicitly carved out as T02–T04 work in §77–§87.
- **KDR-014 respected.** No persistent-config-override path; per-call rebinding via `--tier-override`/`tier_overrides` is acknowledged as the only operator path.
- **Layer rule preserved.** Schema lives in `primitives/`; cascade logic explicitly deferred to `graph/` at T02. AC-5 verifies `lint-imports` stays at 5 contracts kept.
- **Hermetic-test discipline.** §50–57 names 4 tests — flat acceptance, nested rejection, empty default, `model_dump`/`TypeAdapter` round-trip — all hermetic, no `tmp_path` even needed (pure pydantic), no provider calls.
- **No SEMVER break.** Optional field defaulting to `[]`; existing `TierConfig` instances round-trip unchanged. Next-minor target (≥0.5.0) is correct.
- **Status surfaces correctly aligned.** Spec `**Status:** 📝 Planned` matches README task-order table (line 83) "Kind: code + test"; no `tasks/README.md` for M15; README "Done when" checkboxes all unticked. No drift.
- **AC mapping to README exit criteria.** AC-1 ↔ exit-criterion #1 (schema + nested rejection); AC-3/AC-4 ↔ exit-criterion #1 round-trip; AC-5/AC-6 ↔ exit-criterion #10 (gates green). All other exit criteria are explicitly out-of-scope.
- **`Route` alias reuse.** §1 line 25 (`fallback: list[Route]`) and §1 line 48 ("Reuse it directly — do not re-declare the discriminator union") both pin the H6 fix. Carry-over TA-LOW-02 reinforces.
- **Nested-fallback error message names the offending index.** §1 line 41–43 (`f"nested fallback is not allowed: fallback[{i}] declares its own fallback field."`); AC-1 + AC-2 + Risks §1 + carry-over TA-LOW-03 all reinforce. Builder cannot accidentally drop the index.

## Cross-cutting context

- **`nice_to_have.md` slots.** T01 doesn't claim a slot. README line 113–115 names three forward-options (immediate-fail-over, tier-name-reference fallback, YAML overlay) as `nice_to_have.md` candidates with explicit triggers — none claimed at T01. No slot-drift risk.
- **ADR slot 0006.** Free; T04 territory. T01 doesn't add an ADR, so no ADR-numbering conflict here.
- **Project memory.** `project_m10_specs_clean_pending_implement.md` references the prior /clean-implement deferral pattern but doesn't flag M15 specifically. Nothing in memory marks M15 on-hold beyond the "implement after M17" note already in README line 3 — informational, not a finding. M17 closed 2026-04-30 per memory, so M15 is now eligible.
- **Sibling task specs T02–T05.** Don't exist yet (incremental-spec convention, README line 89). Cross-spec consistency cannot be verified for unwritten siblings; T01's narrow scope leaves T02–T05 with what the README assigns.
- **CHANGELOG.** `[Unreleased]` block at line 8 is empty; T01 entry will land cleanly under `### Added — M15 Task 01: …`. AC-7 framing is sound.
- **Pydantic v2 `field_validator` semantics.** `mode="before"` is the right choice here — the validator inspects raw dicts/lists before pydantic coerces them into `Route` discriminated-union instances, which is exactly when the `"fallback"` key on a child item is still a dict key (after coercion it would be a `TierConfig` model attribute). Builder doesn't need a hint on `mode="before"` vs. `mode="after"` — the spec gets this right.
