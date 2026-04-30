# M15 Task 01 Issue File — `TierConfig.fallback` schema

**Task:** [task_01_fallback_schema.md](../task_01_fallback_schema.md)
**Status:** ✅ Built (cycle 1, 2026-04-30)

---

## Cycle 1 build report

### Pre-flight checks

- No prior issue file. No BLOCKED items.
- Spec and invoker brief consistent. No conflicts.
- Carry-over items from task analysis (TA-LOW-01 through TA-LOW-04) reviewed.

### Implementation summary

**`ai_workflows/primitives/tiers.py`**

- Extended pydantic import line 47 from `from pydantic import BaseModel, Field` to
  `from pydantic import BaseModel, Field, field_validator`. (`Any` was already imported at line 44
  via `from typing import Annotated, Any, Literal`.)
- Added `fallback: list[Route] = Field(default_factory=list, description=…)` to `TierConfig`
  after `per_call_timeout_s`.
- Added `_reject_nested_fallback` `@field_validator("fallback", mode="before")` class method that
  rejects dict entries in the fallback list carrying a `"fallback"` key; error message includes the
  index (`fallback[{i}]`).
- `Route` alias at line 80 (`Annotated[LiteLLMRoute | ClaudeCodeRoute, Field(discriminator="kind")]`)
  reused directly — no re-declaration (TA-LOW-02 satisfied).
- Module docstring and `TierConfig` class docstring updated to cite M15 T01.

**`tests/primitives/test_tierconfig_fallback.py`** (new)

4 hermetic tests, no provider calls, no disk I/O:
1. `test_tierconfig_fallback_field_accepts_flat_list` — 2-entry fallback (LiteLLMRoute + ClaudeCodeRoute); `len == 2`.
2. `test_tierconfig_fallback_field_rejects_nested_fallback` — nested fallback dict raises `ValidationError` with `"nested fallback is not allowed"` and `"fallback[0]"` in error text.
3. `test_tierconfig_fallback_defaults_to_empty_list` — no fallback kwarg; `tier.fallback == []`.
4. `test_tierconfig_fallback_roundtrip_via_model_dump` — 1-entry fallback round-trips through `model_dump(mode="json")` + `TypeAdapter(TierConfig).validate_python(...)`.

### Gate results

| Gate | Result |
|---|---|
| `uv run pytest --tb=short -q` | 1514 passed, 12 skipped, 22 warnings |
| `uv run lint-imports` | 5 contracts kept, 0 broken |
| `uv run ruff check` | All checks passed |

### Carry-over absorbed

| Item | Status |
|---|---|
| TA-LOW-01 — spec rename (done at orchestrator level) | Pre-satisfied, no Builder action needed |
| TA-LOW-02 — reuse `Route` alias | Satisfied — `list[Route]` uses alias directly |
| TA-LOW-03 — index in error message | Satisfied — `fallback[{i}]` in `_reject_nested_fallback` + asserted in test |
| TA-LOW-04 — `field_validator` import | Satisfied — import line extended |

### Acceptance criteria check

| AC | Status |
|---|---|
| AC-1: `TierConfig.fallback` schema | PASS |
| AC-2: Hermetic tests green (4 tests) | PASS |
| AC-3: Existing tests unchanged | PASS (1514 passed) |
| AC-4: Schema round-trip preserved | PASS (covered by AC-3 + round-trip test) |
| AC-5: Layer contract preserved | PASS (5 contracts kept, 0 broken) |
| AC-6: Gates green | PASS |
| AC-7: CHANGELOG entry | PASS |

### Deviations from spec

None.

### Planned commit message

```
M15 Task 01: TierConfig.fallback schema + hermetic tests (KDR-006/KDR-014)

Add fallback: list[Route] field to TierConfig with _reject_nested_fallback
pydantic field_validator. Schema foundation for M15 fallback cascade;
dispatch logic lives in T02 (TieredNode). 4 hermetic tests, all gates green.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

---

## Cycle 1 audit

**Audited on:** 2026-04-30
**Auditor verdict:** ✅ FUNCTIONALLY CLEAN (PASS)
**Audit scope:** `ai_workflows/primitives/tiers.py` (TierConfig.fallback schema), `tests/primitives/test_tierconfig_fallback.py` (4 hermetic tests), spec status flip, README task row, CHANGELOG entry.

### Phase 1 — Design-drift check

No drift detected. Cross-referenced against `architecture.md §4.1 + §9` and the seven load-bearing KDRs:

- **KDR-003 (no Anthropic API):** unchanged — no `anthropic` SDK import, no `ANTHROPIC_API_KEY` read added.
- **KDR-004 (validator pairing):** N/A at schema layer; T02 territory.
- **KDR-006 (RetryingEdge three-bucket):** unchanged — no retry logic in T01.
- **KDR-008 (FastMCP + pydantic):** schema-only change in `primitives`; MCP surface untouched (matches T01 out-of-scope §"No MCP schema change").
- **KDR-009 (SqliteSaver):** unchanged.
- **KDR-013 (user-owned external workflow code):** unchanged — `fallback` is a workflow-author surface, declared in user Python registries; framework rejects nested fallbacks at schema-validate time only, no runtime sandboxing added.
- **KDR-014 (framework owns tier policy):** **respected** — schema field added, no YAML-overlay loader, no env-var override path expanded. Matches the 2026-04-30 rescoping decision (M15 README §Rescoping note + roadmap.md line 56).
- **Layer discipline:** schema lives in `primitives/`; no upward import; lint-imports 5/0 confirms.
- **Architecture §4.1:** TierConfig is the canonical tier shape; adding an optional ordered-list field with default `[]` is backward-compatible — existing TierConfig instances without `fallback` round-trip unchanged (verified by AC-3 — full pytest 1514 passed).

No new dependency. No new module. No new layer. No new LLM call. No new MCP tool. No checkpoint logic. No retry logic. No observability backend. No `nice_to_have.md` adoption.

### Phase 2 — Gate re-run (from scratch)

| Gate | Command | Result |
|---|---|---|
| pytest (full) | `uv run pytest -q` | **PASS** — 1514 passed, 12 skipped, 22 warnings, 71.46s |
| pytest (new file) | `uv run pytest tests/primitives/test_tierconfig_fallback.py -q` | **PASS** — 4 passed, 0.04s |
| lint-imports | `uv run lint-imports` | **PASS** — 5 contracts kept, 0 broken |
| ruff | `uv run ruff check ai_workflows/primitives/tiers.py tests/primitives/test_tierconfig_fallback.py` | **PASS** — All checks passed |

**Smoke test (T01-specific):** spec is a pure-schema task; the explicit "smoke" surface called out in §Deliverables is the four hermetic tests in `tests/primitives/test_tierconfig_fallback.py`. They exercise: (a) flat acceptance with mixed `LiteLLMRoute` + `ClaudeCodeRoute` entries, (b) nested rejection with index-in-error assertion, (c) empty default, (d) round-trip through `model_dump(mode="json")` + `TypeAdapter`. The round-trip test in particular is the wire-level smoke — it confirms the schema serialises and re-validates losslessly, which is the integration property T02's cascade dispatch will rely on. Verified by running the new test file in isolation.

Builder-reported counts match auditor re-run exactly (1514 passed / 12 skipped). Gate integrity intact.

### Phase 3 — AC grading

| AC | Status | Notes |
|---|---|---|
| AC-1: `TierConfig.fallback` schema | ✅ MET | Field exists at `tiers.py:102-109`, defaults to `[]` via `Field(default_factory=list)`; `Route` discriminated union accepts both `LiteLLMRoute` and `ClaudeCodeRoute` (test 1 confirms); `_reject_nested_fallback` validator rejects nested at line 111-122 with `"nested fallback is not allowed: fallback[{i}] declares its own fallback field."` — index named, ADR-0006 cited. |
| AC-2: 4 hermetic tests pass | ✅ MET | All 4 tests in `test_tierconfig_fallback.py` pass in 0.04s; no provider calls, no disk I/O outside pytest's internal machinery. Test 2 explicitly asserts both `"nested fallback is not allowed"` AND `"fallback[0]"` in error text (line 75-76). |
| AC-3: Existing tests unchanged (1514) | ✅ MET | Full pytest = 1514 passed (4 more than the pre-T01 baseline of 1510 implied by the "+4 new" in the Builder report). No edits to `test_tiers_loader.py` or any other test module. |
| AC-4: Schema round-trip preserved | ✅ MET | Passively covered by AC-3; actively covered by `test_tierconfig_fallback_roundtrip_via_model_dump` which exercises `model_dump(mode="json")` → `TypeAdapter(TierConfig).validate_python(...)` → equality. |
| AC-5: lint-imports 5/0 | ✅ MET | 5 kept, 0 broken — `primitives` layer clean, no upward imports. |
| AC-6: All gates green | ✅ MET | pytest + lint-imports + ruff all green from scratch. |
| AC-7: CHANGELOG entry | ✅ MET | `[Unreleased]` carries `### Added — M15 Task 01: TierConfig.fallback schema + hermetic tests (2026-04-30)` with files-touched list, ACs, carry-over absorbed, and "Deviations: None". |

### Phase 4 — Critical sweep

- **ACs that look met but aren't:** none. Each AC has direct evidence.
- **Silently skipped deliverables:** none. Spec deliverables §1 (schema) + §2 (tests) both shipped verbatim. §3 explicitly says "no edits required" — confirmed.
- **Additions beyond spec:** `Any` was already imported (line 45 — `from typing import Annotated, Any, Literal`); the Builder correctly noted this rather than re-adding. Module + class docstrings updated to cite M15 T01 — minimal, justified, not scope creep.
- **Test gaps:** none. Each AC has at least one direct test assertion. Index-in-error assertion present (line 76).
- **Doc drift:** module docstring (`tiers.py:1-38`) updated to mention `fallback: list[Route]` cascade chain (line 18); `TierConfig` class docstring (`tiers.py:84-95`) updated with M15 T01 + ADR-0006 cross-reference. Spec `**Status:**` flipped to ✅ Built. README task row 01 flipped to ✅ Built (cycle 1). CHANGELOG entry present. No stale docstrings found.
- **Status-surface drift:** four surfaces checked.
  - (a) Per-task spec `**Status:**` line — ✅ Built (cycle 1, 2026-04-30). ✓
  - (b) Milestone README task table row — `01 | ... ✅ Built (cycle 1) | code + test`. ✓
  - (c) `tasks/README.md` — does not exist for milestone_15. N/A.
  - (d) Milestone README "Done when" / exit criteria — exit criterion 1 ("Fallback chain schema") is the T01 deliverable; not yet ticked at the README level (kept at exit-criteria-list shape, not checkbox), and the milestone is still 📝 Planned overall (T02-T05 outstanding). No drift — flipping the milestone-level surface waits for T05 close-out.
- **Carry-over checkbox-cargo-cult:** TA-LOW-01 `[x]` (orchestrator-rename) was pre-satisfied; verified `task_01_fallback_schema.md` exists and `task_01_overlay_and_fallback_schema.md` does not in this milestone. TA-LOW-02/03/04 are still `[ ]` in the spec carry-over section but have direct diff evidence (line 102 reuses `Route`, line 119 includes `fallback[{i}]` in the error message, line 48 imports `field_validator`). The spec convention for this repo leaves carry-over checkboxes unticked until close-out; the issue file's "Carry-over absorbed" table captures the satisfaction. No cargo-cult finding.
- **Secrets shortcuts:** none. Pure pydantic schema work.
- **Scope creep from `nice_to_have.md`:** none. The spec §"Out of scope" enumerates exactly what's deferred (cascade dispatch, cost attribution, CLI, ADR, YAML relocation). Builder respected each.
- **Silent architecture drift:** none.
- **Cycle-N-vs-cycle-(N-1) overlap:** no prior cycle; first audit on this task. N/A.
- **Rubber-stamp detection:** verdict PASS, diff is 57 lines (small), 0 HIGH/MEDIUM findings → MEDIUM threshold (50 lines) tripped, but verdict reasoning is direct: each AC has cited evidence; gates re-run from scratch matched Builder counts; KDR drift check is exhaustive across all 7 load-bearing KDRs; smoke surface (the 4 hermetic tests + round-trip) is verified at wire-level. **Not a rubber-stamp** — schema-only tasks legitimately produce small diffs; the task spec is narrow by design (rescoped 2026-04-30 to schema-only, with cascade dispatch deferred to T02). Critical sweep is genuine, not perfunctory.

### 🔴 HIGH

None.

### 🟡 MEDIUM

None.

### 🟢 LOW

None. The cycle is functionally clean.

### Additions beyond spec — audited and justified

| Addition | Justification |
|---|---|
| Module docstring update (`tiers.py:1-38`) — added `fallback: list[Route]` mention to §Responsibilities | Required for docstring discipline (every public surface change is documented). Minimal, factual, cites M15 T01. |
| `TierConfig` class docstring update (`tiers.py:84-95`) — added M15 T01 paragraph + ADR-0006 reference | Required for docstring discipline. Cites the ADR (which lands in T04) so future readers have a forward pointer. |

### Gate summary

| Gate | Command | Result |
|---|---|---|
| pytest | `uv run pytest -q` | PASS (1514 passed / 12 skipped) |
| lint-imports | `uv run lint-imports` | PASS (5 contracts kept, 0 broken) |
| ruff | `uv run ruff check ai_workflows/primitives/tiers.py tests/primitives/test_tierconfig_fallback.py` | PASS |

### Issue log — cross-task follow-up

None. No findings raised; no propagation needed.

### Deferred to nice_to_have

None this cycle.

### Propagation status

No forward-deferrals from this audit. T01 is closed; T02 (`TieredNode` cascade dispatch) will compose against the schema as-shipped without spec amendments.

---

## Sr. SDET review (2026-04-30)
**Test files reviewed:** `tests/primitives/test_tierconfig_fallback.py` | **Skipped:** none | **Verdict:** SHIP

### What passed review (one line per lens)

- **Lens 1 (wrong-reason):** All four assertions pin real behaviour — len check + isinstance, string containment of both the sentinel phrase and the index token, equality of empty list, structural equality after round-trip. No tautologies, no trivial `is not None` assertions, no stubbed TODOs.
- **Lens 2 (coverage gaps):** AC intent is fully covered. The mixed LiteLLMRoute + ClaudeCodeRoute flat-acceptance case is exercised in `test_tierconfig_fallback_field_accepts_flat_list:50-52` (both isinstance checks). The nested-rejection test uses index 0; a second-entry check (index 1) would be belt-and-suspenders but is not a gap given the validator iterates all entries and the error message pattern is already pinned. The validator only fires on `dict` entries, not on Route objects passed directly — this is correct because a pre-constructed `LiteLLMRoute` object cannot carry a `fallback` key at all; the `mode="before"` validator sees it only when the input is a raw dict, which is the YAML/JSON ingestion path. No gap.
- **Lens 3 (mock overuse):** No mocks at all. Tests compose directly over `TierConfig`, `LiteLLMRoute`, `ClaudeCodeRoute`. Correct boundary.
- **Lens 4 (fixture hygiene):** No fixtures beyond the module-level `_minimal_tier_config` helper (not a pytest fixture — a plain function). No order dependence, no monkeypatch, no scope mismatch.
- **Lens 5 (hermetic gating):** All four tests are fully hermetic. No network I/O, no subprocess, no disk I/O, no `AIW_E2E`/`AIW_EVAL_LIVE` guard needed or present. Correct.
- **Lens 6 (naming + assertion hygiene):** Names are descriptive and AC-keyed. `assert "nested fallback is not allowed" in error_text` and `assert "fallback[0]" in error_text` at lines 75-76 are plain string-in-string checks against a short, stable error message — no message argument needed at this granularity. Round-trip equality check at line 103 is augmented with three targeted field-level checks (104-106) that confirm discriminated-union deserialization, not just structural equality.

### Advisory

- `tests/primitives/test_tierconfig_fallback.py:15` imports `ValidationError` from pydantic with a `# noqa: TC002` comment (TYPE_CHECKING import guard suppression). `ValidationError` is used at runtime inside `pytest.raises`, so it is a runtime import; the noqa is correct but could be replaced by simply removing the suppression and letting ruff/pyright classify it naturally. Minor hygiene nit; no action required.

---

## Sr. Dev review (2026-04-30)
**Files reviewed:** `ai_workflows/primitives/tiers.py`, `tests/primitives/test_tierconfig_fallback.py` | **Skipped:** none | **Verdict:** SHIP

### BLOCK  (hidden bugs)

None.

### FIX    (idiom drift, defensive creep, premature abstraction)

None.

### Advisory  (comment hygiene, simplification)

**tiers.py:101 — Lens 5 (comment drift): task-ID inline comment**

`# Added in M15 T01 (fallback cascade).` is a task-ID reference on a source line. Per the project's docstring discipline rule, task citations belong in commit messages, not inline. The module-level docstring already cites `M15 T01` in the Responsibilities table (line 18), so the inline comment is redundant. Note: this pattern is consistent with how this file is maintained elsewhere (module docstrings cite milestones throughout), so it is not a drift-from-neighbour finding. Flagged for awareness only; no FIX required.

Action: Consider removing the inline comment at `tiers.py:101`; the module docstring `tiers.py:18` and the field's `description=` parameter already carry the provenance.

### What passed review

- **Lens 1 (bugs):** `mode="before"` scoping is correct — validator fires while items are still raw dicts, before pydantic coerces to `Route` instances. `isinstance(v, list)` guard is appropriate for a `mode="before"` validator (lets pydantic's own type machinery handle non-list inputs with its own error message). `Route` alias reused directly at line 102 — no re-declaration of the discriminator union. `default_factory=list` avoids mutable default. No off-by-one, no async misuse, no resource leak, no silent except.
- **Lens 2 (defensive creep):** No phantom guards. The `isinstance(v, list)` check in a `mode="before"` validator is the correct idiom, not creep.
- **Lens 3 (idiom alignment):** Pydantic V2 throughout — `field_validator`, `model_dump(mode="json")`, `TypeAdapter`. No `.dict()` calls. `@classmethod` decorator present. Matches neighbour `TierConfig` style exactly.
- **Lens 4 (premature abstraction):** Single validator method, one job. No new helper, mixin, or base class.
- **Lens 5 (comment/docstring):** Module docstring and `TierConfig` class docstring updated to cite M15 T01 and ADR-0006 forward-reference. One advisory inline comment flagged above; all other comments explain *why* rather than restate code.
- **Lens 6 (simplification):** Validator loop is minimal. No comprehension or `dict.update` simplification applicable. No two-line helper that could be inlined.

---

## Security review (2026-04-30)

**Reviewer:** security-reviewer
**Task:** M15 Task 01 — `TierConfig.fallback` schema
**Files reviewed:** `ai_workflows/primitives/tiers.py`, `tests/primitives/test_tierconfig_fallback.py`

### Threat model mapping

This task adds `fallback: list[Route]` to `TierConfig`. `Route` is the existing discriminated union `Annotated[LiteLLMRoute | ClaudeCodeRoute, Field(discriminator="kind")]`. The same route types already existed as the `route: Route` primary field — no new route types, no new subprocess-execution paths, no new network calls introduced at T01.

### Checks performed

**Wheel contents (item 1):** Checked `dist/jmdl_ai_workflows-0.4.0-py3-none-any.whl`. No prohibited paths present. T01 adds no new files to the package tree.

**Subprocess execution / ANTHROPIC_API_KEY (item 2):** `grep -rn "ANTHROPIC_API_KEY" ai_workflows/` returns zero hits. No subprocess spawning, no `shell=True` added. `ClaudeCodeRoute.cli_model_flag` in fallback entries is an opaque string stored in the schema only — dispatch wiring is T02 territory.

**Model-string / CLI-flag injection:** `fallback` entries carry the same `str`-typed fields as the existing `route` field. No execution occurs at T01. Identical posture to the pre-existing primary route field.

**`_reject_nested_fallback` validator:** `mode="before"` validator raises `ValueError` with a static template; only a numeric index is interpolated. No user-controlled data emitted to logs or shell. Safe.

**Env-var expansion:** `_expand_env_recursive` applies to all YAML string leaves including `fallback` entries, same as all other string fields. No new path-traversal or code-execution surface.

**Logging hygiene:** No logging calls added. No API keys, `Bearer`, or `Authorization` strings in new code.

**SQLite / storage:** T01 adds no storage interaction. No raw f-string SQL interpolation.

**Layer discipline:** `primitives/tiers.py` — no upward imports; lint-imports 5/0 confirmed.

### 🔴 Critical — must fix before publish/ship

None.

### 🟠 High — should fix before publish/ship

None.

### 🟡 Advisory — track; not blocking

None. The `fallback` field introduces identical security posture to the existing `route` field. No new attack surface at T01.

**Verdict:** SHIP
