# Task 04 — Telemetry: `TokenUsage.role` tag + `CostTracker.by_role` + cascade-step records — Audit Issues

**Source task:** [../task_04_telemetry_role_tag.md](../task_04_telemetry_role_tag.md)
**Audited on:** 2026-04-27
**Audit scope:** spec + 3 source files (`primitives/cost.py`, `graph/tiered_node.py`, `graph/audit_cascade.py`) + 2 test files (`tests/primitives/test_cost_by_role.py` NEW, `tests/graph/test_audit_cascade.py` extended) + CHANGELOG entry + status surfaces (per-task spec + milestone README task-table row + §Exit-criteria bullet 6) + KDR-014 boundary check across `workflows/_dispatch.py`, `workflows/spec.py`, `cli.py`, `mcp/`, and workflow modules + KDR-003 guardrail re-run + 5 import-linter contracts + ruff + full pytest re-run from scratch + carry-over LOW verification.
**Status:** ✅ PASS

## Design-drift check

No drift detected.

- **KDR-014 boundary holds.** `grep -rn 'role' ai_workflows/workflows/_dispatch.py ai_workflows/workflows/spec.py ai_workflows/cli.py ai_workflows/mcp/` returns ZERO matches. The `role` tag is purely a primitive-layer construction parameter on `tiered_node()` + a `TokenUsage` field; it never surfaces on `*Input` models, `WorkflowSpec`, CLI flags, or MCP tool input schemas. The pre-existing `{"role": "user", "content": ...}` chat-message constructions in `workflows/planner.py:349,370` and `workflows/slice_refactor.py:795` are pre-T04 and unrelated to the new `TokenUsage.role` field. Spec §Locked decisions explicitly states "KDR-014 does not apply" and the implementation matches.
- **KDR-011 (cascade telemetry) satisfied.** T04 lands the empirical `by_role` aggregation surface ADR-0004 §Decision item 6 names. Wire-level smoke confirms the cascade emits exactly 2 role-tagged TokenUsage records per cascade cycle (primary→author, auditor→auditor), and `CostTracker.by_role` aggregates them per the documented shape.
- **KDR-003 preserved.** `tests/workflows/test_slice_refactor_e2e.py::test_kdr_003_no_anthropic_in_production_tree` re-ran clean over the modified `cost.py` + `tiered_node.py` + `audit_cascade.py`. No `anthropic` SDK import added, no `ANTHROPIC_API_KEY` read added.
- **KDR-009 preserved.** `TokenUsage.role` rides the existing in-memory `CostTracker._entries` dict — no hand-rolled checkpoint write, no SQLite schema change. Spec §Out of scope explicitly defers SQLite persistence to a future task per KDR-009.
- **KDR-006 untouched.** No bespoke retry loops added; the cascade's existing `RetryingEdge` wiring is preserved.
- **KDR-004 untouched.** Validator pairing unchanged.
- **Layer rule (`primitives → graph → workflows → surfaces`) preserved.** All 3 source-code edits land in `primitives/cost.py` (primitives layer) + `graph/tiered_node.py` (graph layer) + `graph/audit_cascade.py` (graph layer). Zero `workflows/` source edit, zero `mcp/` edit, zero `cli.py` edit. `lint-imports` 5 contracts kept (audit_cascade contract from M12 T02 still holds).
- **Factory-time role binding (Option 4) honoured.** `tiered_node` reads `role` from the closure-captured factory parameter, NOT from `state['cascade_role']`. Test 13 (`test_cascade_role_attribution_survives_audit_retry_cycle`) wire-level proves immunity to state-channel staleness across an auditor-fail-then-pass retry cycle.

## AC grading

| AC | Status | Notes |
| -- | ------ | ----- |
| `TokenUsage.role: str = ""` field with M12 T04 / KDR-011 docstring | ✅ | `cost.py:96-101` — field present, docstring cites M12 T04 + KDR-011 + the `tiered_node.py:264-268` stamp site. |
| `CostTracker.by_role(run_id)` mirrors `by_tier` shape; sub-model costs roll into parent role; empty-string bucket for non-cascade calls | ✅ | `cost.py:154-170` — uses the unchanged `_roll_cost` helper (sub-model rollup matches `by_tier`); empty-string bucket pinned by test 5 (`test_by_role_includes_empty_string_bucket_for_non_cascade_calls`). |
| `tiered_node()` factory accepts `role: str = ""` keyword-only kwarg; default preserves all existing callers byte-for-byte | ✅ | `tiered_node.py:122` — kwarg lives between `node_name` (required) and the function body; `*` at line 117 makes it keyword-only. Default `""` confirmed; existing T01-T03 + T08 callers unchanged (verified via test suite — 799 passed, no regression). |
| `tiered_node` stamps `usage.role` from constructor-bound `role` parameter (NOT from `state.get('cascade_role')`) immediately after the existing `tier` stamp | ✅ | `tiered_node.py:286-290` — `usage_with_role = usage_with_tier if usage_with_tier.role else usage_with_tier.model_copy(update={"role": role})` — the `role` here is the closure-captured factory parameter, not a state read. Lands directly between the existing `tier` stamp (`tiered_node.py:274-278`) and the `cost_callback.on_node_complete(...)` call (`tiered_node.py:296`). |
| Cascade primitive passes `role="author"` to primary `tiered_node()` and `role="auditor"` to auditor `tiered_node()`; verdict node does NOT pass `role="verdict"` | ✅ | `audit_cascade.py:287` (`role="author"`), `audit_cascade.py:323` (`role="auditor"`). Verdict node (`_audit_verdict_node`, `audit_cascade.py:716-812`) is a pure `AuditVerdict.model_validate_json` parse — no `tiered_node` involvement, no LLM dispatch, no `TokenUsage` recorded. Pinned by test 12's exactly-2-records assertion. |
| Existing `_stamp_role_on_success` state-channel wrapper left in place unchanged | ✅ | `audit_cascade.py:601-657` — wrapper unchanged; serves the existing `test_cascade_role_tags_stamped_on_state` test (test 6, `test_audit_cascade.py:576-619`) which reads final state, independent of the ledger role stamp. Both surfaces coexist as spec requires. |
| All 5 new `tests/primitives/test_cost_by_role.py` tests pass | ✅ | 5 passed (re-ran). |
| New `test_cascade_records_role_tagged_token_usage_per_step` passes — wire-level proof | ✅ | PASSED. Wire-level: real `CostTracker` + real `CostTrackingCallback` + real cascade `compile()` + real `tiered_node` factory; `_StubLiteLLMAdapter` / `_StubClaudeCodeAdapter` substitute only the LLM dispatch surface (legitimate hermetic substitution). Asserts exactly 2 records: `records[0].role == "author"`, `records[1].role == "auditor"`. |
| New `test_cascade_role_attribution_survives_audit_retry_cycle` passes — H2 mitigation | ✅ | PASSED. Asserts 4 records (2 author + 2 auditor) across an auditor-fail-then-pass cycle; no cross-contamination. Pins Option 4's factory-time binding immunity to state-channel staleness. |
| All existing tests remain green (backward-compat) | ✅ | 799 passed / 9 skipped (zero regressions, +8 vs prior cycle's 791). Existing `TokenUsage()` construction without `role` arg works (defaults to `""`); existing `by_tier` / `by_model` aggregations unchanged (no test failure on `tests/primitives/test_cost.py`); existing `tiered_node` invocations across T01-T03 + T08 work without passing `role`. |
| No `ai_workflows/workflows/` / `ai_workflows/mcp/` / `ai_workflows/cli.py` source diff | ✅ | `git status --short` confirms only `primitives/cost.py`, `graph/tiered_node.py`, `graph/audit_cascade.py` (source), CHANGELOG, README, spec, and 2 test files modified. Zero workflow/MCP/CLI source edits. |
| No `pyproject.toml` / `uv.lock` diff | ✅ | `git status` confirms neither file modified. |
| KDR-003 guardrail test still passes | ✅ | `test_kdr_003_no_anthropic_in_production_tree` PASSED — re-ran explicitly. Iterates `ai_workflows/`'s `.py` files via `rglob`, so the modified files are automatically in scope. |
| `uv run pytest` + `uv run lint-imports` (5 contracts) + `uv run ruff check` all clean | ✅ | pytest: 799 passed / 9 skipped; lint-imports: 5/5 KEPT (audit_cascade contract preserved); ruff: All checks passed. |
| CHANGELOG entry under `[Unreleased]` cites KDR-011 + backward-compat + Option 4 | ✅ | `CHANGELOG.md:10-50` — `### Added` framing per TA-LOW-02 recommendation; cites KDR-011 (line 46), backward-compat (line 48), Option 4 lock (line 27). |
| Wire-level smoke per CLAUDE.md non-inferential rule | ✅ | `test_cascade_records_role_tagged_token_usage_per_step` exercises the full production cost-callback path: real `CostTracker.record` ← real `CostTrackingCallback.on_node_complete` ← real `tiered_node` (with `role="author"` / `role="auditor"` factory-bound) — same code path a downstream consumer hits. Stub adapter substitution is at the LLM-dispatch boundary only; the role-stamp logic is exercised end-to-end. |
| Status surfaces flipped together (spec Status, README task-table row 04, README §Exit-criteria bullet 6) | ✅ | (a) spec line 3: `**Status:** Complete (2026-04-27).`; (b) README line 67: `\| 04 \| ... \| code + test \| ✅ Complete (2026-04-27) \|` (Kind column unchanged); (c) README line 31: `6. ✅ (T04 complete 2026-04-27) ...`. Three surfaces in agreement; no `tasks/README.md` exists in this project. |
| TA-LOW-01 ticked | ✅ | Informational; spec section was already rewritten to no longer reference `tiered_node.py:194`. The implemented role-stamp block at `tiered_node.py:286-290` matches the spec's `264-274ish` approximate bound. |
| TA-LOW-02 ticked | ✅ | CHANGELOG uses `### Added` framing per the recommendation; KDR-011 cited. |
| TA-LOW-03 ticked | ✅ | Test 12's exactly-2-records assertion pins the verdict-no-dispatch contract; future regressions would be caught. |
| TA-LOW-04 ticked | ✅ | Forward-deferral note remains in spec §Propagation status pending T05 spec creation; correct deferral pattern under "no spec exists yet". See **Propagation status** below for confirmation. |
| TA-LOW-05 ticked | ✅ | Role stamp landed at `tiered_node.py:286-290`, between the existing tier stamp at `tiered_node.py:274-278` and the `cost_callback.on_node_complete` at `tiered_node.py:296`. Spec's `264-274ish` approximate bound was acceptable; live offsets are within tolerance. |
| TA-LOW-06 ticked | ✅ | Spec §"Out of scope" line 196 was reworded to: `**No cascade-primitive (audit_cascade_node) signature change.** The tiered_node factory signature gains a backward-compatible role: str = "" kwarg per Option 4 (default preserves all 25+ existing callers byte-for-byte). T08's skip_terminal_gate was the cascade-primitive amendment; T04's primitive-layer change is the symmetric role-kwarg extension on tiered_node, not on audit_cascade_node.` — verbatim match to recommendation text. |

All 24 graded ACs PASS.

## 🔴 HIGH

None.

## 🟡 MEDIUM

None.

## 🟢 LOW

### M12-T04-LOW-01 — Builder addition: `log_node_event` reads from `usage_with_role` instead of `usage`

**Where:** `tiered_node.py:388-390` — the `node_completed` log event now reads `input_tokens` / `output_tokens` / `cost_usd` from `usage_with_role` instead of `usage` (pre-T04 baseline read from `usage`).

**Severity rationale:** Behaviourally a no-op today — the role-stamp at `tiered_node.py:286-290` only updates the `role` field via `model_copy(update={"role": role})`, leaving `input_tokens` / `output_tokens` / `cost_usd` byte-identical to the upstream `usage`. The change is a forward-looking consistency fix (if a future stamp grows scope to numeric fields, the log line stays consistent with the cost record). Not strictly within spec deliverables but reasonable additive coupling — log surface is the operator's secondary signal next to the ledger; reading from the same `usage_with_role` object that flows into `cost_callback.on_node_complete(...)` keeps the two surfaces in lock-step.

**Action / Recommendation:** No action. Acceptable additive fix. If a future spec wants to lock this contract explicitly ("the structured log MUST mirror the recorded TokenUsage fields"), add an AC then.

## Additions beyond spec — audited and justified

- **`log_node_event` success-path reads from `usage_with_role`.** See M12-T04-LOW-01 above. Behaviourally no-op today; forward-looking consistency. ACCEPTED.

No other additions detected. The 3 source files modified match the spec's enumeration exactly.

## Gate summary

| Gate | Command | Result |
| ---- | ------- | ------ |
| Test suite | `uv run pytest` | ✅ 799 passed / 9 skipped (+8 vs prior cycle baseline) |
| Layer rule | `uv run lint-imports` | ✅ 5 contracts kept (incl. audit_cascade composes only graph + primitives) |
| Lint | `uv run ruff check` | ✅ All checks passed |
| KDR-003 grep | `uv run pytest tests/workflows/test_slice_refactor_e2e.py::test_kdr_003_no_anthropic_in_production_tree` | ✅ Passed |
| KDR-014 grep | `grep -rn 'role' ai_workflows/workflows/_dispatch.py ai_workflows/workflows/spec.py ai_workflows/cli.py ai_workflows/mcp/` | ✅ Zero matches (no role on user-facing surfaces) |
| Wire-level smoke | `uv run pytest tests/graph/test_audit_cascade.py::test_cascade_records_role_tagged_token_usage_per_step -v` | ✅ Passed (real CostTracker + real cascade compile) |
| Retry-cycle role attribution | `uv run pytest tests/graph/test_audit_cascade.py::test_cascade_role_attribution_survives_audit_retry_cycle -v` | ✅ Passed (Option 4 immunity proven) |
| `by_role` unit suite | `uv run pytest tests/primitives/test_cost_by_role.py -v` | ✅ 5 passed |

## Issue log — cross-task follow-up

- **M12-T04-LOW-01** (LOW, owner: none — accepted as additive consistency fix): `log_node_event` now reads from `usage_with_role`. No-op today; future-proofs the log/ledger consistency contract. Status: ACCEPTED on first audit.

No HIGH or MEDIUM findings. No DEFERRED items beyond the existing TA-LOW-04 forward-deferral (already tracked in spec §Propagation status; lands on T05 when T05 spec is drafted).

## Deferred to nice_to_have

- *None applicable.* Spec §Out of scope's "No telemetry export to external systems" defers Langfuse / OpenTelemetry to existing `nice_to_have.md` entries; T04's in-process aggregation surface is the right scope for M12.

## Propagation status

- **TA-LOW-04 forward-deferral (T05 `run_audit_cascade` MCP tool may surface `by_role` aggregation in output schema):** T05 spec does NOT exist yet (per M12 README convention — per-task specs land as predecessors close). Tracking remains in `task_04_telemetry_role_tag.md` §Propagation status (line 204) until the T05 spec is drafted. When `/clean-tasks m12 t05` runs (post-T04 close), the orchestrator picks up this note and lands it as a carry-over in T05's spec. **Status: pending T05 spec creation.** Not a Builder/Auditor responsibility this cycle.

No other propagations from this cycle.

**Status:** ✅ PASS

---

## Security review (2026-04-27)

### Scope

M12 T04 touches three source files (`primitives/cost.py`, `graph/tiered_node.py`, `graph/audit_cascade.py`) and two test files. No `pyproject.toml` / `uv.lock` changes; dependency-auditor skipped per invocation brief.

### Threat-model items checked

**1. KDR-003 boundary — no ANTHROPIC_API_KEY, no new subprocess spawn**

`grep -rn "ANTHROPIC_API_KEY" ai_workflows/` returns zero hits. T04 adds no subprocess spawn, no new env reads, no `anthropic` SDK import. The `role` kwarg is a pure Python string parameter flowing from factory call sites in `audit_cascade.py:287,323` ("author" / "auditor" literals) into the `tiered_node` closure and from there into `TokenUsage.model_copy(update={"role": role})`. It never reaches any subprocess argument list. Clean.

**2. Role string injection / structured-log safety**

The `role` value is used in exactly one place beyond the `TokenUsage` ledger field: `usage_with_role.model_copy(update={"role": role})` at `tiered_node.py:289`. The `role` is then stored in `CostTracker._entries` (pure in-memory dict) and queried by `CostTracker.by_role()`.

The `role` value is NOT passed to `log_node_event` at the `node_completed` emit site (`tiered_node.py:378-393`). Only `input_tokens`, `output_tokens`, and `cost_usd` are read from `usage_with_role` there. The role string is therefore not interpolated into any log record — there is no vector for a newline-injection escape from a crafted role string into the structured log.

`log_node_event` itself calls `emit(event, ..., **extra)` using structlog's keyword-argument API — parameterised emit, not string concatenation. Even if a future path surfaced the role string to `log_node_event`, structlog would serialise it as a typed key-value pair under its own key, not into the event string. Clean.

All role values in T04 are hard-coded string literals at cascade construction time (`"author"`, `"auditor"`). No user-supplied input flows through the role path in any code path T04 introduces or modifies.

**3. Role string in SQL / shell contexts**

`CostTracker.by_role` uses `entry.role` only as a dict key (`totals[entry.role] += ...`). It is never passed to `aiosqlite` or any shell command. No SQL injection surface. Clean.

**4. Wheel-contents impact**

T04 modifies `ai_workflows/primitives/cost.py`, `ai_workflows/graph/tiered_node.py`, `ai_workflows/graph/audit_cascade.py` — all inside the `ai_workflows/` package tree. New tests land under `tests/` (not packaged). No new data files, no config files, no `.env`-shaped content added. The existing dist/ artefact is 0.3.1 (pre-T04); the assessment is structural — when a wheel is rebuilt for the next release, T04's changes do not introduce any non-wheel-appropriate content. Clean.

**5. Logging hygiene — no API key or token leakage**

`grep -rn "GEMINI_API_KEY\|Bearer \|Authorization" ai_workflows/` returns zero hits across the entire package. T04 adds no logging of API keys, OAuth tokens, prompt content, or message bodies. The `by_role` aggregation surface returns `{str: float}` (role label to USD cost) — no sensitive data. Clean.

**6. Subprocess CWD / env leakage (pre-existing; no T04 regression)**

T04 introduces no new subprocess spawns and modifies no subprocess dispatch paths. The existing `ClaudeCodeSubprocess` and `LiteLLMAdapter` dispatch paths in `_dispatch()` are unmodified. No new env vars are read. Not a T04 concern.

### 🔴 Critical — must fix before publish/ship

None.

### 🟠 High — should fix before publish/ship

None.

### 🟡 Advisory — track; not blocking

None. T04's change surface is narrow and entirely within the in-memory cost-ledger path. All role values are compile-time string literals; no user-controlled input reaches the role stamp path.

### Verdict: SHIP

---

## Sr. Dev review (2026-04-27)

**Files reviewed:**
- `ai_workflows/primitives/cost.py` — `TokenUsage.role` field + `CostTracker.by_role`
- `ai_workflows/graph/tiered_node.py` — `role: str = ""` factory kwarg + `usage_with_role` stamp
- `ai_workflows/graph/audit_cascade.py` — `role="author"` / `role="auditor"` at construction sites; `_stamp_role_on_success` wrapper
- `tests/primitives/test_cost_by_role.py` (new, 5 tests)
- `tests/graph/test_audit_cascade.py` (extended, tests 12-13)

**Skipped (out of scope):** none — all files are within the task-declared touch set.

**Verdict:** SHIP

### BLOCK — must-fix before commit

None.

### FIX — fix-then-ship

None.

### Advisory — track but not blocking

**ADV-01 — Wire-level tests (12 and 13) read `tracker._entries` directly rather than calling `tracker.by_role()`**

File: `tests/graph/test_audit_cascade.py:938,1017` — Hidden-bugs / simplification lens.

Tests 12 and 13 are the designated wire-level smoke for T04's new API. Both inspect the ledger with `tracker._entries.get(run_id, [])` — a private attribute read — and assert `records[n].role`. They do not call `tracker.by_role(run_id)`. The new public method is unit-tested separately in `test_cost_by_role.py`, so there is no correctness gap, but the wire-level smoke never exercises `by_role` end-to-end through the cascade dispatch path. A future regression where `by_role` silently returns wrong buckets (e.g. a copy-paste error changes `entry.role` to `entry.tier` in the aggregation loop) would not be caught by the cascade tests.

Action/Recommendation: In test 12, add a single assertion after the `len(records) == 2` check:
`role_buckets = tracker.by_role("r_t04a"); assert role_buckets.get("author", 0) > 0; assert role_buckets.get("auditor", 0) == 0` (or similar). This wires the public API into the smoke test without restructuring the test. Not a bug today — the unit tests cover `by_role` — but the two-tests-at-different-levels gap is worth closing.

**ADV-02 — `_stamp_role_on_success` docstring references T04 telemetry as its own justification, but T04 superseded that rationale**

File: `ai_workflows/graph/audit_cascade.py:608-610` — Comment / docstring drift lens.

The docstring says the state-channel stamp exists "so T04's telemetry can attribute `TokenUsage` records to the correct cascade role." Under Option 4 (locked 2026-04-27), T04's ledger attribution uses factory-time binding on `tiered_node` directly and has zero dependence on `state['cascade_role']`. The state-channel stamp's current purpose is to surface the role to graph-layer state consumers (the existing `test_cascade_role_tags_stamped_on_state` test reads `final["cascade_role"]`). The docstring justification is now a historical artefact of the pre-Option-4 design.

Action/Recommendation: Replace the phrase "so T04's telemetry can attribute `TokenUsage` records to the correct cascade role" with "so graph-layer state consumers (e.g. outer-graph routing logic or observability tooling) can read the current cascade role from `state['cascade_role']`". One-line change; no behaviour change.

**ADV-03 — Shared mutable class-level lists on `_StubLiteLLMAdapter` / `_StubClaudeCodeAdapter` are a latent test-isolation hazard**

File: `tests/graph/test_audit_cascade.py:78-79,112-113` — Hidden-bugs lens (test-side).

Both stub classes declare `script: list[Any] = []` and `calls: list[dict] = []` as class-level attributes. These are the canonical mutable-default-argument shape. They are safe now only because the `autouse=True` `_reset_stubs` fixture reassigns them to fresh lists before each test. If a future test author adds a new stub class without including it in `_reset_stubs`, cross-test contamination will follow. The pattern itself is not introduced by T04 (the stubs predate this task), so this is out-of-scope rot noted as advisory.

Action/Recommendation: Out-of-scope for this task; no action required from T04 Builder. Advisory for awareness: when the cascade test file is next substantially edited, consider using instance-level attrs in `__init__` instead of class-level lists, or document the reset contract explicitly above the class definition.

### What passed review (one-line per lens)

- **Hidden bugs:** None in source code. Wire-level test 12/13 use private `_entries` instead of `by_role` (ADV-01); the gap is in test coverage depth, not production correctness.
- **Defensive-code creep:** None. The `if usage_with_tier.role else` guard in `tiered_node.py:286-289` mirrors the pre-existing `tier` stamp pattern identically; the "respect any role the adapter may have stamped" comment is proportionate to the decision.
- **Idiom alignment:** Clean. `by_role` mirrors `by_tier` shape exactly — same `defaultdict(float)` + `_roll_cost` helper + `dict(totals)` return. The `role: str = ""` factory kwarg mirrors `tier: str` symmetrically. `structlog.get_logger(__name__)` used throughout; no stdlib logging drift.
- **Premature abstraction:** None. No new helper or base class introduced for a single caller. The `_stamp_role_on_success` wrapper predates T04; T04 only passes `role=` to `tiered_node` at the two construction sites.
- **Comment / docstring drift:** One post-Option-4 docstring inaccuracy in `_stamp_role_on_success` (ADV-02). Duplicate docstring content on `TokenUsage.role` (both the class-level docstring paragraph at lines 82-86 and the field-level docstring at lines 97-101 describe the same field with nearly identical text) — minor redundancy, not a functional issue.
- **Simplification:** None required. `by_role` is as concise as `by_tier`. The role-stamp block is 4 lines mirroring the 4-line tier-stamp block above it.

---

## Sr. SDET review (2026-04-27)

**Test files reviewed:**
- `tests/primitives/test_cost_by_role.py` (NEW — 5 tests)
- `tests/graph/test_audit_cascade.py` (EXTENDED — tests 12-13, positions ~884 and ~963)

**Skipped (out of scope):** `tests/primitives/test_cost.py` (pre-T04, not in T04 touch set; one out-of-scope advisory noted below).

**Verdict:** SHIP

### BLOCK — tests pass for the wrong reason

None.

### FIX — fix-then-ship

None.

### Advisory — track but not blocking

**ADV-SDET-01 — Tautological cross-contamination loop in test 13 (confirmed pre-identified, severity: cosmetic)**

File: `tests/graph/test_audit_cascade.py:1043-1046`

Lens: Lens 1 (tautology variant — no hidden bug, correctness is already pinned by prior assertions).

The final assertion loops `for r in author_records: assert r.role == "author"` and `for r in auditor_records: assert r.role == "auditor"`. Both lists are defined by filtering `records` on `r.role` (lines 1025-1026), so these assertions are guaranteed by list construction and can never fail independently of the prior count assertions. The load-bearing claims (`len(records) == 4`, `len(author_records) == 2`, `len(auditor_records) == 2`) are correct and sufficient. The redundant loops are self-identified in the inline comment at lines 1041-1042 ("trivially guaranteed...but pin it explicitly for clarity"), so the author is aware. Not a hidden correctness risk.

Action/Recommendation: No immediate action required. If test 13 is ever restructured, remove lines 1043-1046 or replace with a single `assert set(r.role for r in records) == {"author", "auditor"}` which is non-tautological and covers the cross-contamination contract more clearly.

**ADV-SDET-02 — Wire-level tests (12 and 13) read `tracker._entries` directly rather than calling `tracker.by_role()` (echoes sr-dev ADV-01, confirmed from SDET lens)**

File: `tests/graph/test_audit_cascade.py:938, 1017`

Lens: Lens 2 (coverage gap — `by_role` public API not exercised via the cascade dispatch path).

Both wire-level tests bypass `tracker.by_role(run_id)` entirely; they assert `role` correctness by reading the private `tracker._entries` dict directly. The 5 unit tests in `test_cost_by_role.py` cover `by_role`'s aggregation logic with hand-crafted records, which is sufficient to catch most `by_role` implementation bugs (e.g., substituting `entry.tier` for `entry.role` would be caught immediately by the unit tests). The residual gap is narrow: a regression where records populated via the real cascade dispatch path are aggregated differently by `by_role` than records constructed directly. Given that `by_role` reads from `self._entries` which is identical regardless of how entries were created, the practical risk of an undetected regression is low — but the public API is the spec-facing contract and the wire-level smoke is the natural place to verify it.

Action/Recommendation: In test 12 (`test_cascade_records_role_tagged_token_usage_per_step`), add a single `by_role` call immediately after the `len(records) == 2` assertion:
`role_buckets = tracker.by_role("r_t04a"); assert role_buckets.get("author", 0.0) > 0.0; assert "auditor" in role_buckets`. This is a two-line addition that closes the gap between the unit-tested aggregation and the cascade-dispatch population path without restructuring the test. Not blocking — the unit tests cover `by_role` adequately; this adds depth.

**ADV-SDET-03 — `test_cost_tracker_structural_compat_with_magic_mock_spec` in `test_cost.py` does not list `by_role` (out-of-scope advisory)**

File: `tests/primitives/test_cost.py:372` (out-of-scope for T04 touch set)

Lens: Lens 2 (coverage gap — pre-existing structural compat test not updated for T04's new public method).

The test at `test_cost.py:362-373` checks that `MagicMock(spec=CostTracker)` exposes the five pre-T04 methods (`record`, `total`, `by_tier`, `by_model`, `check_budget`). It does not include `by_role`. Any downstream code using `MagicMock(spec=CostTracker)` and calling `by_role` would get an `AttributeError` at test time — caught at runtime but not surfaced proactively by the structural compat test. This file is outside T04's declared touch set; the Auditor did not flag it.

Action/Recommendation: Out of scope for T04. Recommend adding `"by_role"` to the `for attr in (...)` list in `test_cost.py:372` when that file is next touched (no urgent trigger required). Alternatively, include this file in T05's touch set if T05 amends the `CostTracker` surface further.

**ADV-SDET-04 — Dead `checkpointer` parameter in `_build_config` helper is a pre-existing pattern; tests 12-13 deviate from it without introducing risk**

File: `tests/graph/test_audit_cascade.py:186-203` (pre-existing); tests 12-13 at lines ~908-933, ~989-1015.

Lens: Lens 4 (fixture hygiene — cosmetic).

`_build_config` accepts `checkpointer` as a parameter but never uses it (all 11 pre-T04 tests pass the checkpointer to `_build_config` which ignores it). Tests 12-13 build the config inline (to inject a custom `tracker`) and also create a checkpointer that is only used in the `finally: await checkpointer.conn.close()` cleanup. The resource management is correct (no leak), and the cascade graph runs correctly without a checkpointer. The pre-existing dead-parameter pattern and the tests-12-13 deviation are both cosmetic — no correctness risk.

Action/Recommendation: No action required. The dead `checkpointer` parameter in `_build_config` is pre-existing rot (out-of-scope). Tests 12-13's inline config approach is cleaner in spirit (explicit about what they need) even though the created-but-unused `checkpointer` object adds noise.

### What passed review (one-line per lens)

- Tests-pass-for-wrong-reason: None observed. All 7 new tests make meaningful assertions against real contracts.
- Coverage gaps: `by_role` not called from wire-level cascade tests (ADV-SDET-02, echoing sr-dev ADV-01); `test_cost.py` structural compat missing `by_role` (ADV-SDET-03, out of scope). Unit tests cover `by_role` logic adequately; risk is advisory only.
- Mock overuse: None. Wire-level tests 12-13 use real `CostTracker` + real `CostTrackingCallback` + real cascade compile + real `tiered_node` factory. Stub adapters substitute only at the LLM-dispatch boundary (legitimate hermetic boundary). No mocking of `RetryingEdge` or `SQLiteStorage`.
- Fixture / independence: Clean. `_reset_stubs` autouse fixture correctly resets class-level lists and uses `monkeypatch.setattr` (function-scoped revert); no bleed between tests. Each test uses `tmp_path`-scoped SQLite files with distinct names. `asyncio_mode = "auto"` set globally.
- Hermetic-vs-E2E gating: Clean. All 7 new tests are hermetic — no real LLM dispatch, no subprocess, no network. No missing `AIW_E2E=1` guard needed.
- Naming / assertion-message hygiene: Clean. Test names are descriptive (`test_by_role_sub_models_inherit_parent_role`, `test_cascade_role_attribution_survives_audit_retry_cycle`). Assertion failure messages include `f"..."` interpolation at every non-trivial assert, enabling debuggability without a pretty-printer.
