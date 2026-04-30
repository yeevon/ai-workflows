# Task 01 — `TierConfig.fallback` schema

**Status:** ✅ Built (cycle 1, 2026-04-30).
**Grounding:** [milestone README](README.md) · [architecture.md §4.1 + §9](../../architecture.md) · [ai_workflows/primitives/tiers.py](../../../ai_workflows/primitives/tiers.py) · [KDR-014](../../architecture.md) (framework owns tier policy; env-var is the only operator override path).

## What to Build

Add a `fallback: list[Route]` field to `TierConfig` with pydantic validation that rejects nested fallbacks at schema-check time. This is the schema foundation for M15 — the dispatch cascade that walks the list lives in T02 (`TieredNode`). T01 ships the schema field + hermetic tests only.

No overlay loader, no `_dispatch.py` integration, no provider calls. Schema + tests.

## Deliverables

### 1. `ai_workflows/primitives/tiers.py` — `TierConfig.fallback` schema field

Extend the existing `TierConfig` pydantic model using the existing `Route` alias (`tiers.py:80`):

```python
class TierConfig(BaseModel):
    name: str
    route: Route
    max_concurrency: int = 1
    per_call_timeout_s: int = 120
    # Added in M15 T01 (fallback cascade).
    fallback: list[Route] = Field(
        default_factory=list,
        description=(
            "Ordered fallback routes tried after this tier's retry budget "
            "exhausts (M15). Flat only — routes in this list cannot themselves "
            "carry a `fallback` field. Cascade logic lives in TieredNode (T02)."
        ),
    )

    @field_validator("fallback", mode="before")
    @classmethod
    def _reject_nested_fallback(cls, v: Any) -> Any:
        """Nested fallback is architecturally forbidden (ADR-0006)."""
        if isinstance(v, list):
            for i, item in enumerate(v):
                if isinstance(item, dict) and "fallback" in item:
                    raise ValueError(
                        f"nested fallback is not allowed: fallback[{i}] "
                        "declares its own fallback field."
                    )
        return v
```

The `Route` alias on `tiers.py:80` is `Annotated[LiteLLMRoute | ClaudeCodeRoute, Field(discriminator="kind")]`. Reuse it directly — do not re-declare the discriminator union.

### 2. Tests — `tests/primitives/test_tierconfig_fallback.py` (new)

Hermetic — no disk I/O outside `tmp_path`, no provider calls.

- `test_tierconfig_fallback_field_accepts_flat_list` — construct a `TierConfig` with a two-entry `fallback` list (one `LiteLLMRoute`, one `ClaudeCodeRoute`); assert it parses and `len(tier.fallback) == 2`.
- `test_tierconfig_fallback_field_rejects_nested_fallback` — attempt to construct a `TierConfig` where a `fallback` entry carries its own `fallback` key; assert pydantic `ValidationError` with `"nested fallback is not allowed"` in the error message; assert the error message includes the index (`fallback[0]`).
- `test_tierconfig_fallback_defaults_to_empty_list` — construct a `TierConfig` without the `fallback` field; assert `tier.fallback == []`.
- `test_tierconfig_fallback_roundtrip_via_model_dump` — construct a `TierConfig` with a one-entry fallback; `model_dump(mode="json")` and re-parse via `TypeAdapter(TierConfig).validate_python(...)`; assert round-trip produces identical object.

### 3. `tests/primitives/test_tiers_loader.py` — no edits required

Existing loader tests stay green without modification. AC-4 verifies this passively (gates run).

## Acceptance Criteria

- [ ] **AC-1: `TierConfig.fallback` schema.** Field exists on `TierConfig`, defaults to `[]`, accepts flat lists of `Route` (both `LiteLLMRoute` and `ClaudeCodeRoute` entries), and rejects nested fallbacks at pydantic validation time with an error message naming the offending index.
- [ ] **AC-2: Hermetic tests green.** `tests/primitives/test_tierconfig_fallback.py` — 4 new tests covering flat acceptance, nested rejection, empty default, and round-trip. All pass; no provider calls.
- [ ] **AC-3: Existing tests unchanged.** `tests/primitives/test_tiers_loader.py` and the rest of `tests/` pass without edits. Verified by full `uv run pytest` run.
- [ ] **AC-4: Schema round-trip preserved.** Existing `TierConfig` instances without `fallback` (from `TierRegistry.load()` with the repo's `tiers.yaml`) parse and validate unchanged. Covered passively by AC-3.
- [ ] **AC-5: Layer contract preserved.** `uv run lint-imports` reports 5 contracts kept, 0 broken. No `ai_workflows.graph` / `ai_workflows.workflows` / surface imports in `primitives`.
- [ ] **AC-6: Gates green.** `uv run pytest` + `uv run lint-imports` + `uv run ruff check` all pass.
- [ ] **AC-7: CHANGELOG entry.** `CHANGELOG.md` under `[Unreleased]` — `### Added — M15 Task 01: TierConfig.fallback schema + hermetic tests (YYYY-MM-DD)` entry naming files touched, ACs satisfied, deviations (if any).

## Dependencies

- Ships against 0.4.0 baseline (M17 closed 2026-04-30). M15 will ship as the next minor (≥0.5.0). M16 + M17 already shipped — M15 composes over both. No runtime dependencies on earlier milestones beyond the `TierConfig` primitive itself.

## Out of scope

- **Dispatch-layer cascade logic.** T02. T01 ships the schema field + tests only; no `TieredNode` changes, no `_dispatch.py` changes.
- **Cost-attribution changes.** T02 + T03 territory. `CostTracker` API unchanged at T01.
- **`aiw list-tiers` CLI command.** T03 deliverable.
- **ADR-0006.** T04 deliverable.
- **`tiers.yaml` relocation → `docs/tiers.example.yaml`.** T04 deliverable.
- **Documentation rewrites in `docs/writing-a-workflow.md`.** T04 deliverable. T01 only adds the field + tests.
- **`_mid_run_tier_overrides` (M8 T04 post-gate fallback).** M15's declarative fallback and M8's reactive override coexist; T01 does not touch the M8 surface.
- **YAML overlay / persistent user tier config.** Dropped on 2026-04-30 rescoping — conflicts with KDR-014. Requires a KDR-014 amendment if ever revisited.
- **MCP schema change.** No input/output models gain a `fallback` field. Per README non-goals.

## Risks

1. **Pydantic error messages on nested-fallback rejection.** Must be clear enough that a user reading the error knows *which* entry tripped the check. The `@field_validator` message includes the index (`fallback[{i}]`) to name the offending entry. AC-2's nested-rejection test asserts the index appears in the error message.

## Carry-over from task analysis

- [x] **TA-LOW-01 — Spec filename retains dropped concept** (severity: LOW, source: task_analysis.md round 1)
      Satisfied at orchestrator-rename time (2026-04-30): old file `task_01_overlay_and_fallback_schema.md` removed; README line 83 updated to `task_01_fallback_schema.md`. No Builder action needed.

- [x] **TA-LOW-02 — Reuse `Route` alias (not re-declare discriminator union)** (severity: LOW, source: task_analysis.md round 1)
      `fallback` field type **must** reuse the existing `Route = Annotated[…]` alias on `tiers.py:80` — do not re-declare `Annotated[LiteLLMRoute | ClaudeCodeRoute, Field(discriminator="kind")]` inline. Already enforced in §1 above.
      **Recommendation:** Builder verifies it uses `list[Route]`, not a freshly declared union. Ruff/mypy catch any inline drift.
      **Verified at task-analyzer round 1, 2026-04-30:** `tiers.py:81` confirms `list[Route]` is used. ✓

- [x] **TA-LOW-03 — Nested-fallback error message index** (severity: LOW, source: task_analysis.md round 1)
      `_reject_nested_fallback` validator error message must include the offending entry's index. Already addressed in §1 above (`f'nested fallback is not allowed: fallback[{i}] declares its own fallback field.'`).
      **Recommendation:** AC-2's nested-rejection test must assert the index appears. Already specified in §2.
      **Verified at task-analyzer round 1, 2026-04-30:** `tiers.py:119` emits `fallback[{i}]`; `test_tierconfig_fallback.py:76` asserts `"fallback[0]"` in error text. ✓

- [x] **TA-LOW-04 — `field_validator` import not in `tiers.py`** (severity: LOW, source: task_analysis.md round 2)
      `ai_workflows/primitives/tiers.py:47` currently imports `from pydantic import BaseModel, Field` only. `field_validator` is not imported. The `_reject_nested_fallback` validator requires it.
      **Recommendation:** Builder extends the import line to `from pydantic import BaseModel, Field, field_validator` when adding the `fallback` field.
      **Verified at task-analyzer round 1, 2026-04-30:** `tiers.py:48` imports `field_validator`. ✓
