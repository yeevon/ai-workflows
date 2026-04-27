# Task 08 — T02 amendment: `audit_cascade_node(skip_terminal_gate)` — Audit Issues

**Source task:** [../task_08_audit_cascade_skip_terminal_gate.md](../task_08_audit_cascade_skip_terminal_gate.md)
**Audited on:** 2026-04-27 (cycle 1 of 10 — initial; cycle 2 of 10 — re-audit after doc-surface fix; both autonomous mode)
**Audit scope (cycle 2):** Verified the three cycle-2 doc deltas landed cleanly (spec status line, README task-table row, TA-T08-LOW-01 checkbox). Re-ran all three gates from scratch (pytest 775 passed / 9 skipped, lint-imports 5/5 kept, ruff clean — same as cycle 1). Verified Builder did NOT touch source code, tests, CHANGELOG, the issue file, or run any forbidden git/publish operation (reflog shows no new commits during cycle 2; the cycle-1 source/test/CHANGELOG diff is unchanged from cycle-1 audit). Sibling README rows 01 + 02 still render `✅ Complete (2026-04-27)` — no accidental damage.
**Status:** ✅ PASS — FUNCTIONALLY CLEAN, ready for security gate. Cycle-2 doc-surface fix landed (HIGH-01 + LOW-01 resolved). TA-T08-LOW-02 (T03 dependency-block hash substitution) intentionally remains unticked — owned by orchestrator commit-ceremony per spec. Acknowledged as orchestrator-owned and does NOT block FUNCTIONALLY CLEAN.

---

## Design-drift check

No drift. Cross-checked against `architecture.md §4.2` (graph-layer adapters) and the seven load-bearing KDRs:

- **KDR-003** — no `anthropic` import added; no `ANTHROPIC_API_KEY` read added. `tests/workflows/test_slice_refactor_e2e.py::test_kdr_003_no_anthropic_in_production_tree` re-run independently and passes.
- **KDR-004** — `ValidatorNode` pairing preserved; the new code path does not bypass shape validation (validator runs the same regardless of `skip_terminal_gate`).
- **KDR-006** — three-bucket retry taxonomy unchanged. `AuditFailure` (RetryableSemantic subclass) and `NonRetryable` continue to flow through `wrap_with_error_handler` → `_failure_state_update` → `state['last_exception']`. The amendment changes only the *terminal* destination (END vs `human_gate`), not the bucket routing or retry counters.
- **KDR-009** — checkpoint persistence unchanged; the cascade's compiled sub-graph is still compiled from a `StateGraph(_DynamicState)` and routes through LangGraph's standard checkpoint mechanism.
- **KDR-011** — cascade primitive contract preserved. Default `skip_terminal_gate=False` is byte-for-byte T02 behaviour. The new mode is a documented opt-in for parallel-fan-out callers; ADR-0004's gate-on-exhaustion contract is honoured for default-path callers, and the alternative escalation surface (caller's outer-graph state inspection) is documented in the docstring.
- **KDR-014** — N/A; no new policy knob added to public input schemas, `WorkflowSpec` fields, CLI flags, or MCP tool schemas. `skip_terminal_gate` is a **graph-construction-time parameter on a primitive factory**, consumed by the *workflow author* at module-import time. This is exactly the pattern KDR-014 prescribes.
- **Layer rule** — `audit_cascade.py` continues to import only `primitives` + sibling `graph/` modules. `lint-imports` re-run from scratch: 5 contracts kept, including the dedicated `audit_cascade composes only graph + primitives` contract.
- **Sub-graph wiring** — verified the round-2 H1 fix from spec §Sub-graph wiring change is in place:
  - `audit_cascade.py:482-484` — `add_node(f"{name}_human_gate", gate)` only when `not skip_terminal_gate`.
  - `audit_cascade.py:492-498` — when `skip_terminal_gate=True`, `add_conditional_edges(validator, _decide_after_validator, [primary, auditor, END])` correctly omits the gate AND adds END (matching `_decide_after_validator` returning END for the `NonRetryable` path).
  - `audit_cascade.py:510-516` — when `skip_terminal_gate=True`, `add_conditional_edges(verdict, _decide_after_verdict, [primary, END])` correctly omits the gate.
  - `audit_cascade.py:523-524` — `add_edge(f"{name}_human_gate", END)` only when `not skip_terminal_gate`.
  - `_decide_after_validator` (lines 370-383) and `_decide_after_verdict` (lines 398-435) read `skip_terminal_gate` via closure capture; every `f"{name}_human_gate"` return becomes `END` under the new mode. No unregistered destinations possible at compile time.

---

## AC grading

| AC | Status | Notes |
| -- | ------ | ----- |
| 1. Signature gains `skip_terminal_gate: bool = False` (between `cascade_context_fn` and `name`) | ✅ MET | `audit_cascade.py:130-144`. Inserted at the documented position. |
| 2. Docstring `Parameters` block documents the new parameter with parallel-fan-out use case | ✅ MET | `audit_cascade.py:188-217`. Three paragraphs covering default semantics, True semantics, use case, and backward-compatibility note — verbatim per spec. |
| 3. Default `False` preserves T02 behaviour — 7 prior cascade tests pass unchanged | ✅ MET | Re-ran `tests/graph/test_audit_cascade.py` from scratch: 11 passed (7 prior + 4 new). All 7 T02 cascade tests show PASSED. |
| 4. `skip_terminal_gate=True` → `f"{name}_human_gate" not in compiled.nodes` | ✅ MET | `test_skip_terminal_gate_true_omits_human_gate_node_from_compiled_subgraph` PASSED. Pinned by `add_node` wrapped in `if not skip_terminal_gate:`. |
| 5. `skip_terminal_gate=True` → verdict-exhaustion routes to END with `AuditFailure` in `state["last_exception"]` (+ `failure_reasons` + `suggested_approach`) | ✅ MET | `test_skip_terminal_gate_true_routes_exhaustion_to_END_with_audit_failure_in_state` PASSED — wire-level smoke; assertions cover every payload field cited in the AC. |
| 6. `skip_terminal_gate=True` → validator-exhaustion routes to END with `NonRetryable` in `state["last_exception"]`; auditor never invoked | ✅ MET | `test_skip_terminal_gate_true_routes_validator_exhaustion_to_END_with_nonretryable_in_state` PASSED. Auditor adapter call count asserted == 0. |
| 7. All 4 new tests pass | ✅ MET | All four named tests appear in the verbose pytest output and each shows PASSED. |
| 8. All existing T02 tests (7 cascade + 5 template) still pass | ✅ MET | 7 cascade tests verified by name in verbose run. The 5 template tests in `tests/primitives/test_audit_feedback_template.py` are part of the full 775-passed run; no diff to `_render_audit_feedback` so no regression vector exists. |
| 9. No `ai_workflows/workflows/` diff, no `ai_workflows/mcp/` diff, no `ai_workflows/primitives/retry.py` diff | ✅ MET | `git diff HEAD -- <those paths>` returns empty. Only `ai_workflows/graph/audit_cascade.py` touched in production tree. |
| 10. No `pyproject.toml` diff (no new import-linter contract) | ✅ MET | `git diff HEAD -- pyproject.toml uv.lock` returns empty. Existing 5 contracts (including T02's `audit_cascade composes only graph + primitives`) all KEPT. |
| 11. KDR-003 guardrail tests pass | ✅ MET | `test_kdr_003_no_anthropic_in_production_tree` re-run independently → PASSED. Module-level `anthropic` grep across `ai_workflows/` returns only docstring strings explicitly documenting the ban. |
| 12. `uv run pytest` + `uv run lint-imports` (5 contracts kept) + `uv run ruff check` all clean | ✅ MET | pytest: 775 passed / 9 skipped / 33 warnings. lint-imports: 5/5 contracts kept. ruff: All checks passed. All re-run from scratch this cycle. |
| 13. CHANGELOG entry under `[Unreleased]` uses `### Changed` (not `### Added`) citing T02 amendment + KDR-006/011 preservation + backward-compat | ✅ MET | `CHANGELOG.md:10` opens with `### Changed — M12 Task 08: ...`. Entry covers files touched, KDR preservation, backward-compat, and AC-by-AC satisfaction notes. |
| 14. Smoke test (wire-level) — `test_skip_terminal_gate_true_routes_exhaustion_to_END_with_audit_failure_in_state` exercises real `tiered_node` + `validator_node` + `wrap_with_error_handler` + `retrying_edge` (LLM dispatch only stubbed) | ✅ MET | Test invokes the compiled cascade end-to-end. The cascade source (`audit_cascade.py:262-329`) calls real `tiered_node`, `validator_node`, `wrap_with_error_handler`, `retrying_edge` — only the LLM adapter classes (`LiteLLMAdapter`, `ClaudeCodeSubprocess`) are monkey-patched on `tiered_node_module`. Wire-level path is genuinely exercised. |
| 15. Status surfaces flipped together at close — spec `**Status:**` line + milestone README task-table row 08 status indicator (no exit-criteria bullet for T08; T03's bullet 5 covers the consumer) | ❌ UNMET — see HIGH-01 below | Both surfaces flipped to `Complete (2026-04-27)` but **without the leading ✅ checkmark** the AC explicitly requires (`to ✅ Complete (YYYY-MM-DD).`). Rows 01 and 02 in the same table use ✅; row 08 does not. Inconsistent with sibling rows AND with the AC text. |

**Carry-over from task analysis (graded individually):**

| ID | Status | Notes |
| -- | ------ | ----- |
| TA-T08-LOW-01 — no positional test references in new code | ✅ MET (substance), 🟢 LOW housekeeping (checkbox) | No new docstring or comment in `audit_cascade.py` or `test_audit_cascade.py` references tests by position. The new tests are referenced by name in the file's module docstring (lines 19-25) and CHANGELOG. The carry-over **checkbox in the spec is unticked** despite being satisfied — discipline gap, not substance gap. See LOW-01 below. |
| TA-T08-LOW-02 — T03 dependency-block hash substitution at T08 close | ⏭ DEFERRED to orchestrator commit-ceremony | Builder correctly did not perform this — the spec explicitly hands it to the orchestrator's commit-ceremony (`task_03_workflow_wiring.md:326` still reads `Spec at \`task_08_...\` (drafted 2026-04-27 after round-4 H1 arbitration).`). Orchestrator must run `Edit` on T03's `## Dependencies` block in the same commit that lands T08 (substituting `Met: T08 shipped at <hash>` for the placeholder) per the spec's explicit instruction. Builder discipline preserved. |

---

## 🔴 HIGH

### HIGH-01 — Status-surface drift: missing ✅ checkmark on T08 status surfaces — RESOLVED (cycle 2)

**Where:**
- `design_docs/phases/milestone_12_audit_cascade/task_08_audit_cascade_skip_terminal_gate.md:3` — was `**Status:** Complete (2026-04-27).`, now `**Status:** ✅ Complete (2026-04-27).`
- `design_docs/phases/milestone_12_audit_cascade/README.md:71` — was `Complete (2026-04-27)`, now `✅ Complete (2026-04-27)`

**Cycle-2 verification:** Both surfaces re-read in cycle 2; both now lead with `✅`. Sibling rows 01 and 02 still render `✅ Complete (2026-04-27)` — no accidental damage. AC-15 (spec line 131) now satisfied verbatim.

**Original finding (kept for traceability):** AC-15 explicitly required `to ✅ Complete (YYYY-MM-DD).`. Cycle-1 Builder shipped the date and word "Complete" but omitted the leading ✅ checkmark, breaking sibling-row consistency and CLAUDE.md "Status-surface discipline". HIGH per CLAUDE.md non-negotiable.

**Status:** ✅ RESOLVED in cycle 2 (no commit hash yet — orchestrator commits after audit closes clean).

---

## 🟡 MEDIUM

*None.*

---

## 🟢 LOW

### LOW-01 — Carry-over checkboxes in spec remain unticked despite satisfaction — RESOLVED (cycle 2)

**Where:** `task_08_audit_cascade_skip_terminal_gate.md:160` (TA-T08-LOW-01) — was `- [ ]`, now `- [x]`. `:164` (TA-T08-LOW-02) intentionally remains `- [ ]`.

**Cycle-2 verification:** TA-T08-LOW-01 checkbox confirmed `[x]` in cycle 2 spec read. TA-T08-LOW-02 confirmed still `[ ]` — correct (orchestrator's commit-ceremony owns the T03 dependency-block hash substitution per the spec; flips when the orchestrator's edit lands).

**Status:** ✅ RESOLVED in cycle 2 for the in-scope checkbox (LOW-01). LOW-02 remains an orchestrator-owned action — not a Builder gap; does NOT block FUNCTIONALLY CLEAN.

---

## Additions beyond spec — audited and justified

*None observed.* The diff is exactly:
- 1 new keyword-only parameter on the factory signature.
- 4 conditional gate-omission branches in the sub-graph compose (gate construction, `add_node`, `add_conditional_edges` × 2, `add_edge`) — all spec-mandated.
- 2 closure-captured `skip_terminal_gate` reads in `_decide_after_validator` and `_decide_after_verdict` — spec-mandated.
- Module docstring amended (lines 15-20) to cite T08 — appropriate per architecture.md amendment rule.
- 4 new tests + 1 helper factory (`_cascade_skip` at line 648) + module docstring update + 2 import additions (`AuditFailure`, `NonRetryable`) — all spec-mandated.
- CHANGELOG entry — spec-mandated.

No drive-by refactors, no scope creep, no `nice_to_have.md` adoption.

---

## Gate summary

| Gate | Command | Result |
| ---- | ------- | ------ |
| Tests | `uv run pytest` | ✅ 775 passed / 9 skipped / 33 warnings (40.70s) |
| Layer rule | `uv run lint-imports` | ✅ 5 contracts kept, 0 broken (incl. `audit_cascade composes only graph + primitives`) |
| Lint | `uv run ruff check` | ✅ All checks passed (6970 files compiled) |
| KDR-003 guardrail | `uv run pytest tests/workflows/test_slice_refactor_e2e.py -k kdr_003` | ✅ 1 passed |
| T08 cascade tests (focused) | `uv run pytest tests/graph/test_audit_cascade.py -v` | ✅ 11 passed (7 prior + 4 new) |
| T08 wire-level smoke | `uv run pytest tests/graph/test_audit_cascade.py::test_skip_terminal_gate_true_routes_exhaustion_to_END_with_audit_failure_in_state` | ✅ PASSED |

All gates re-run from scratch this cycle. Builder's gate counts (775 passed / 9 skipped) match exactly.

---

## Issue log — cross-task follow-up

| ID | Severity | Owner / next touch point | Status history |
| -- | -------- | ------------------------ | -------------- |
| M12-T08-ISS-01 | HIGH | Builder, same cycle (HIGH-01 — 2-char edits to two doc surfaces) | OPEN (cycle 1) → RESOLVED (cycle 2, no commit hash yet) |
| M12-T08-ISS-02 | LOW | Builder, same cycle (LOW-01 — tick TA-T08-LOW-01 checkbox; orchestrator owns LOW-02) | OPEN (cycle 1) → RESOLVED (cycle 2, no commit hash yet) for LOW-01; LOW-02 remains orchestrator-owned |

---

## Deferred to nice_to_have

*None.* No finding maps to a `design_docs/nice_to_have.md` item.

---

## Propagation status

**No carry-over to forward-defer.** All findings are addressable in the current Builder cycle (HIGH-01 + LOW-01 are spec-already-required corrections to the T08 surfaces themselves; LOW-02 is the orchestrator's commit-ceremony job per the spec, not a forward-deferral to a future task).

**TA-T08-LOW-02 (T03 dependency-block hash substitution)** — owned by the autopilot orchestrator's commit-ceremony at T08 commit time. The substitution target is `design_docs/phases/milestone_12_audit_cascade/task_03_workflow_wiring.md:326`: replace `Spec at \`task_08_audit_cascade_skip_terminal_gate.md\` (drafted 2026-04-27 after round-4 H1 arbitration).` with `**Met:** T08 shipped at \`<commit-hash>\`.`. The edit lands in the same commit as T08 (NOT a separate commit — keeps the T03/T08 bidirectional reference atomic per the spec). On T03's first audit cycle, this will be verified. T08 spec's carry-over LOW-02 stays unticked until the orchestrator commit lands.

---

**Status (cycle 2 close):** ✅ PASS — FUNCTIONALLY CLEAN, ready for security gate. HIGH-01 + LOW-01 resolved by cycle-2 doc-surface edits; LOW-02 (T03 dependency-block hash substitution) remains orchestrator-owned and acknowledged as out-of-scope for FUNCTIONALLY CLEAN. All three gates re-run from scratch this cycle: pytest 775 passed / 9 skipped, lint-imports 5/5 contracts kept, ruff clean. No git mutations during cycle 2 (reflog confirms). No source code, tests, CHANGELOG, or issue-file source changes from Builder this cycle (only the 3 spec/README doc edits). Status surface now consistent across (a) spec line 3 ✅ Complete, (b) milestone README task table row 08 ✅ Complete, (c) no `tasks/README.md` for M12 (not applicable), (d) milestone README "Done when" — T08 has no exit-criteria bullet (T03's bullet 5 covers the consumer; spec AC-15 documents this).

---

## Sr. Dev review (2026-04-27)

**Files reviewed:**
- `ai_workflows/graph/audit_cascade.py` — `skip_terminal_gate: bool = False` kwarg; conditional gate-omission at 4 wiring sites; closure-captured flag in `_decide_after_validator` + `_decide_after_verdict`.
- `tests/graph/test_audit_cascade.py` — 4 new tests (T08 tests 8–11); `_cascade_skip()` helper factory; `AuditFailure`/`NonRetryable` import additions.
- `CHANGELOG.md` — `### Changed — M12 Task 08` entry.
- Spec + milestone README + issue file (status surfaces — doc-only, out of scope for code review).

**Skipped (out of scope):** Pre-existing T02 code (`_wrap_verdict_with_transcript`, `_stamp_role_on_success`, `_audit_verdict_node`, `_cascade_gate_prompt_fn`, `_decide_after_verdict` body — none modified by T08). Class-level mutable stubs (`_StubLiteLLMAdapter.script`, `_StubClaudeCodeAdapter.calls`) pre-exist from T02 and are reset correctly by the autouse fixture.

**Verdict:** SHIP

### BLOCK — must-fix before commit

None.

### FIX — fix-then-ship

None.

### Advisory — track but not blocking

**ADV-01** — `tests/graph/test_audit_cascade.py:718` — unused `tmp_path` fixture parameter in test 9.

Lens: simplification.

Test 9 (`test_skip_terminal_gate_true_omits_human_gate_node_from_compiled_subgraph`) is a purely structural / compile-time test that never invokes the graph — it only calls `_cascade_skip()` and inspects `cascade.nodes`. The `tmp_path: Path` parameter is declared but never used. Ruff did not catch this because `tmp_path` is a pytest fixture parameter, not an unused import. It causes no test failure and is not a logic gap, but it adds noise.

Recommendation: remove `tmp_path: Path` from the test signature — the test needs no filesystem access.

**ADV-02** — `ai_workflows/graph/audit_cascade.py:467-468` — `_DynamicState` always declares the `f"{name}_audit_exhausted_response"` gate channel even when `skip_terminal_gate=True`.

Lens: defensive-code creep (minor).

When `skip_terminal_gate=True`, the gate node is omitted from the graph, so no node will ever write to or read from `f"{name}_audit_exhausted_response"`. The channel remains in the compiled sub-graph's schema as a dead key. LangGraph tolerates this (`total=False` TypedDict; unused channels are inert) — it is not a bug. However, it is a mild inconsistency: the schema declares a channel that the skip path structurally cannot use. The cost is negligible (one extra key in the schema dict); making it conditional would add complexity that exceeds the benefit given the `total=False` semantics.

Recommendation: No action required for this task. If T03's slice_refactor integration later surfaces confusion about which channels are active, consider conditionalising the schema in a follow-on cleanup. Not worth a separate task at this scope.

### What passed review (one-line per lens)

- Hidden bugs: None. Closure capture of `bool` is sound (immutable; per-call scope). Destination lists in both conditional branches are complete and non-overlapping — verified against all possible return values of `_decide_after_validator_base` (retrying_edge) and the `NonRetryable` interception. `gate = None` is never passed to `add_node` (both guarded by `if not skip_terminal_gate:`). No unregistered destination is reachable at LangGraph compile time in either mode.
- Defensive-code creep: ADV-02 (dead schema channel, pre-existing T02 shape carried forward, no action needed).
- Idiom alignment: Follows established cascade / graph-layer patterns exactly. `structlog` not used in this module (none in T02 either); no stdlib logging introduced. Closure pattern mirrors T02's existing `_decide_after_validator_base` usage. `_cascade_skip()` factory shape is a clean mirror of `_cascade()`.
- Premature abstraction: None. `_cascade_skip()` is a test-local factory with two direct callers (tests 10 and 11) — a third caller (test 9) uses it too, so this is a justified two-call extraction.
- Comment / docstring drift: None. Module docstring correctly cites T08. Inline comments at the 4 wiring sites are brief and explain why (LangGraph compile-time destination-list validation constraint) — not what. Docstring `Parameters` block for `skip_terminal_gate` matches the spec verbatim with use-case explanation.
- Simplification: ADV-01 (unused `tmp_path` in test 9 — trivial one-line removal).

## Security review (2026-04-27)

**Scope:** T08 diff only — `ai_workflows/graph/audit_cascade.py` (new `skip_terminal_gate` kwarg + conditional wiring); `tests/graph/test_audit_cascade.py` (4 new tests + `_cascade_skip` helper); `CHANGELOG.md` (entry only). No `pyproject.toml` / `uv.lock` changes; dependency-auditor pass skipped per orchestrator.

### Threat-model items checked

**1. KDR-003 boundary — ANTHROPIC_API_KEY / anthropic SDK**
`grep -rn "ANTHROPIC_API_KEY" ai_workflows/` returns zero hits. `grep -n "import anthropic" audit_cascade.py` returns zero hits. T08 adds no subprocess spawn, no provider call, no new import. The existing KDR-003 guardrail test (`test_kdr_003_no_anthropic_in_production_tree`) was re-run by the auditor and passed. No violation.

**2. KDR-003 boundary — subprocess integrity**
T08 introduces no subprocess calls. The change is purely graph-topology: a conditional omission of one `add_node` / `add_conditional_edges` / `add_edge` call at sub-graph compile time. No `shell=True`, no argv concatenation, no new provider dispatch path.

**3. Gate-bypass privilege concern**
`skip_terminal_gate=True` removes the cascade's internal `interrupt()` surface for the exhaustion path and instead routes to `END` with `state['last_exception']` set. Single-user local threat model: operator IS user; no privilege boundary exists between the cascade's `interrupt()` and the caller's outer-graph `last_exception` inspection. The change shifts arbitration surface from the sub-graph's HumanGate to the caller's outer graph — which is also user code (KDR-013 scope). No security implication.

**4. Silent success-lookalike on exhaustion**
Verified `_decide_after_verdict` (`audit_cascade.py:398-435`): success (routed to `END`) always has `exc is None`; exhaustion (also routed to `END` under `skip_terminal_gate=True`) always has a typed exception (`AuditFailure` or `NonRetryable`) in `state['last_exception']`. These two conditions are structurally distinct — a caller cannot consume exhaustion output as a successful verdict without explicitly ignoring `last_exception`. The wire-level smoke test (AC-14, test 10) asserts `isinstance(exc, AuditFailure)` on the exhaustion path. No silent pass-through path exists.

**5. Wheel contents**
Pre-existing 0.3.1 wheel inspected (`dist/jmdl_ai_workflows-0.3.1-py3-none-any.whl`). Contents: `ai_workflows/` package + `migrations/` (intentional runtime data per M13 T01 `force-include` in `pyproject.toml:102-103`) + dist-info. No `.env*`, no `design_docs/`, no `runs/`, no `*.sqlite3`, no `.claude/`, no `htmlcov/`, no `.github/`. T08's `audit_cascade.py` change will land inside `ai_workflows/graph/` on the next wheel build — correctly in-package. The 4 new tests are in `tests/` (excluded by `packages = ["ai_workflows"]`).

**6. Logging hygiene**
`audit_cascade.py` contains zero logging calls (no `StructuredLogger`, no `logging.*`). No API keys, OAuth tokens, or prompt content are emitted from the modified file. The `_default_auditor_prompt_fn` renders LLM prompt content only as a return value passed to `tiered_node` — not logged.

**7. Subprocess CWD / env leakage**
Not applicable to this diff. No subprocess spawned; no `env=` concern introduced.

**8. Dependency CVEs**
No `pyproject.toml` / `uv.lock` changes. Dependency-auditor pass not required for this task.

### 🔴 Critical — must fix before publish/ship

None.

### 🟠 High — should fix before publish/ship

None.

### 🟡 Advisory — track; not blocking

None.

### Verdict: SHIP

## Sr. SDET review (2026-04-27)

**Test files reviewed:**
- `tests/graph/test_audit_cascade.py` — 4 new T08 tests (tests 8-11) + `_cascade_skip()` helper + `AuditFailure`/`NonRetryable` import additions.

**Skipped (out of scope):** Pre-existing T02 tests (1-7); `tests/primitives/test_audit_feedback_template.py` (untouched by T08).

**Verdict:** SHIP

### BLOCK — tests pass for the wrong reason

None.

### FIX — fix-then-ship

None.

### Advisory — track but not blocking

**ADV-SDET-01** — `tests/graph/test_audit_cascade.py:717` — test 9 asserts `cascade.nodes` only; does not separately assert that the `add_conditional_edges` destination lists omit the gate key.

Lens: coverage gap (minor, below BLOCK threshold).

Test 9 checks `"ac_human_gate" not in cascade.nodes`. This is a meaningful assertion: the `_cascade_skip()` call compiles the sub-graph at line 729 — and LangGraph `add_conditional_edges` with an unregistered destination member raises `ValueError: At 'X' node, 'condition' branch found unknown target 'Y'` at compile time. So if the destination lists had been left erroneously containing `f"{name}_human_gate"`, the call to `_cascade_skip()` at line 729 would raise before the `assert` is even reached, and the test would fail with `ValueError` rather than an `AssertionError`. This means the compile step already provides a de-facto gate against the destination-list bug. The `cascade.nodes` assertion then adds a clean positive pin on the structural absence. The combination is sound: compile failure prevents "gate absent from nodes but still in edge lists" from being a silent pass-through.

However, the test docstring claims it pins "no gate allocated at all" without noting that the compile-time check is implicit. A reader unfamiliar with LangGraph's destination-list validation might doubt that the `cascade.nodes` check is sufficient. The assertion message ("Expected 'ac_human_gate' absent from compiled sub-graph nodes when skip_terminal_gate=True, but it was present") is clear and debuggable. No action required — the assertion shape is correct and complete.

Recommendation: no code change needed. If the spec's rationale "LangGraph compile-time validation enforces it" is ever questioned in review, a one-line comment in the test body (`# NOTE: compile above would have raised ValueError if destination lists still referenced the gate`) would make the implicit guarantee explicit. Not worth a separate fix cycle.

**ADV-SDET-02** — The "double-failure hard-stop" path (`_non_retryable_failures >= 2`) under `skip_terminal_gate=True` has no dedicated test.

Lens: coverage gap (advisory, not blocking).

`_decide_after_verdict` lines 412-414 contain a fast-path: `if failures >= 2: return _terminal`. Under `skip_terminal_gate=True`, `_terminal` is `END`. This path is exercised by the default-False tests only indirectly (the exhaustion tests use `max_semantic_attempts=2` which exhausts the `RetryableSemantic` budget at lines 428-432, not the `_non_retryable_failures` counter). No test seeds `_non_retryable_failures=2` under `skip_terminal_gate=True` to confirm the `END` destination fires (rather than the gate). In practice the path is strongly implied correct — the `_terminal` variable is assigned once at line 410 and reused at all four exit branches; if it were wrong the wire-level test (test 10) would catch it for the auditor-exhaustion path. The double-failure guard is a different trigger condition (two concurrent `NonRetryable` events) not realistically exercisable in the current 2-attempt policy tests. Treat as advisory.

Recommendation: if T03's slice_refactor integration creates a scenario where two `NonRetryable` events can accumulate within a single cascade invocation, add a test seeding `_non_retryable_failures=2` into the initial outer state with `skip_terminal_gate=True` and asserting `END` with a `NonRetryable`-or-`AuditFailure`-typed `last_exception`. Deferred to T03 scope.

**ADV-SDET-03** — `tests/graph/test_audit_cascade.py:718` — `tmp_path: Path` fixture parameter declared but unused in test 9.

Lens: naming / fixture hygiene (mirrors sr-dev ADV-01 — keeping for completeness).

Test 9 is a compile-time structural test: it calls `_cascade_skip(name="ac")` and checks `cascade.nodes`. No filesystem access occurs. The `tmp_path` fixture parameter is declared in the function signature but never referenced in the body. Ruff does not flag pytest fixture parameters as unused imports so it passed lint. No correctness impact.

Recommendation: remove `tmp_path: Path` from the test-9 signature. One-line change. Deferred to the sr-dev ADV-01 advisory resolution if the orchestrator elects to fix ADV-01.

### What passed review (one-line per lens)

- Tests-pass-for-wrong-reason: none — all four T08 tests assert real behavioural contracts; the compile step provides an implicit correctness gate for test 9's structural assertion; tests 10 and 11 are wire-level smokes that exercise real `tiered_node` + `validator_node` + `retrying_edge` with only LLM dispatch stubbed.
- Coverage gaps: double-failure hard-stop path (`_non_retryable_failures >= 2` under `skip_terminal_gate=True`) has no dedicated test — advisory only; the `_terminal` variable is shared across all four exit branches so test 10's auditor-exhaustion path transitively validates the variable's value.
- Mock overuse: none — stubs replace only the LLM dispatch layer (`LiteLLMAdapter`, `ClaudeCodeSubprocess`) via `monkeypatch.setattr` on the module-level names; real `SQLiteStorage`, `build_async_checkpointer`, `TierConfig`, `CostTracker` used throughout; no `MagicMock()` without `spec=`.
- Fixture / independence: `_reset_stubs` autouse fixture correctly resets class-level mutable state (`script`, `calls`) and reinstalls `monkeypatch.setattr` before each test; no order dependence; each test uses distinct `tmp_path` sub-paths (`cp_t08a`, `cp_t08b`, `cp_t08c`) so no cross-test SQLite file collision; `_cascade_skip()` and `_cascade()` both default `name="ac"` — naming is consistent, prefix reuse is correct.
- Hermetic-vs-E2E gating: all four T08 tests are fully hermetic; no network call, no subprocess, no `AIW_E2E=1` guard needed or missing.
- Naming / assertion-message hygiene: test names are descriptive and self-documenting; assertion failure messages include `f"..."` context strings on every assertion that touches a complex value (tests 10 and 11); test 9's single `assert` includes a compound message; test 8's `assert` messages are sparse but the assertions are single-valued booleans where pytest's own output is sufficient.
