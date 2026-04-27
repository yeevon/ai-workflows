# M12 — Task Analysis

**Round:** 3
**Analyzed on:** 2026-04-27
**Specs analyzed:** `task_05_run_audit_cascade_mcp_tool.md`
**Analyst:** task-analyzer agent

## Summary

| Severity | Count |
| --- | --- |
| 🔴 HIGH | 0 |
| 🟡 MEDIUM | 0 |
| 🟢 LOW | 2 (carried; new framing nit surfaced as L3) |
| Total | 3 |

**Stop verdict:** LOW-ONLY

All round-2 HIGH/MEDIUM fixes landed cleanly. Both round-2 LOWs are correctly parked in §Carry-over from task analysis as `[ ]` checkboxes with full Recommendation text. One small new LOW surfaced — a slightly inflated rationale sentence in the configurable-key block (R2 M2 fix area) where the spec claims `pricing={}` is "required" / would "crash with KeyError" but the underlying code paths show it actually defaults gracefully. Builder-absorbable; no implementation impact.

## Findings

### 🔴 HIGH

(none)

### 🟡 MEDIUM

(none)

### 🟢 LOW

#### L1 — TA-T05-LOW-01 (carried) — Validator error-message ordering / framing precision

**Task:** `task_05_run_audit_cascade_mcp_tool.md`
**Issue:** Carried from round 2. Confirmed parked in §Carry-over from task analysis (line 421-423) with full Recommendation text and `[ ]` checkbox. No movement; remains a cosmetic concern with no current caller affected. Standard pydantic instantiation always routes through the `@model_validator(mode="after")` in source order, so the question only matters if a future caller constructs via `model_construct()` to bypass validation.
**Recommendation:** No action this round.
**Push to spec:** already pushed (round 2). No further action needed.

#### L2 — TA-T05-LOW-02 (carried) — `architecture.md:105` secondary stale framing forward-deferred to T07

**Task:** `task_05_run_audit_cascade_mcp_tool.md`
**Issue:** Carried from round 2. Confirmed parked in §Carry-over from task analysis (line 425-427) with full Recommendation text and `[ ]` checkbox. The deferral to T07 close-out (alongside the ADR-0004 §Decision item 7 amendment) is consistent with §Propagation status and the spec's own framing.
**Recommendation:** No action this round.
**Push to spec:** already pushed (round 2). No further action needed.

#### L3 — `pricing={}` rationale at line 285/292/362 slightly overstates the requirement

**Task:** `task_05_run_audit_cascade_mcp_tool.md`
**Location:** spec §Standalone wiring lines 285, 292, and AC line 362.
**Issue:** The R2 M2 fix added a clean enumeration of the configurable dict keys (good). The accompanying rationale text says `pricing={}` is "required for `ClaudeCodeRoute` dispatch — without it `ClaudeCodeSubprocess` raises KeyError" (line 362) and "Without `pricing={}` the AIW_E2E test ... would crash inside `ClaudeCodeSubprocess` looking up the model rate" (line 292). Verified against live source:
- `tiered_node.py:218` reads `pricing: Mapping[str, ModelPricing] = configurable.get("pricing") or {}` — already defaults absent/None to `{}`.
- `claude_code.py:349` reads `row = pricing.get(model_id)` and returns `0.0` cost when the row is absent — no KeyError, just returns zero cost (which is correct behaviour under Max flat-rate).

So the *behaviour* the spec wants (Max flat-rate $0 cost) lands whether `pricing={}` is supplied explicitly or omitted. The explicit `pricing={}` is still good practice (defensive against future refactors that might change the default), but the framing "would crash" is overstated. This does not change what the Builder writes — the literal `pricing={}` still belongs in the configurable dict per the AC. Only the rationale sentences are slightly stronger than reality.
**Recommendation:** Builder at implement time can soften the inline comment from "required for ClaudeCodeRoute dispatch (Max flat-rate is $0; empty dict is fine — ClaudeCodeSubprocess accepts empty pricing and computes $0)" to "explicit per spec — Max flat-rate computes $0 with empty pricing; future per-tier-pricing change would surface non-zero values without code change." No spec edit needed; the Builder will see the live source and either keep the spec's framing or pick the lighter one. Either is fine.
**Push to spec:** yes — append to T05 carry-over as **TA-T05-LOW-03**: "Spec §Standalone wiring lines 285, 292, and AC line 362 frame `pricing={}` as 'required' / would 'crash with KeyError' if absent. Live code paths (tiered_node.py:218 + claude_code.py:349) actually default gracefully to `{}` and return `0.0` cost when model is absent from pricing table. Builder may soften the rationale at implement time. Functional behaviour unchanged — `pricing={}` is still passed explicitly per the AC for forward-compatibility."

## What's structurally sound

Round-2 fixes verified line-by-line:

- **H1 (parse step):** Lines 235-247 contain the explicit `raw_text = verdict_state.get("standalone_auditor_output", "") or ""` followed by `verdict = AuditVerdict.model_validate_json(raw_text)` wrapped in `try/except` raising `ToolError("auditor produced unparseable output — expected AuditVerdict JSON, got: ...")`. Mirrors `_audit_verdict_node`'s pattern at `audit_cascade.py:751`. AC line 361 captures the requirement explicitly. Round-2 H1 fully closed.
- **H2 (payload decode):** Line 260 explicitly states `_resolve_audit_artefact` returns `json.loads(row["payload_json"])` after the `read_artifact` row dict, with `ToolError` on `None`. Cites `storage.py:181-186` as the storage signature reference (verified — actual signature `write_artifact(run_id, kind, payload_json: str)` confirmed at storage.py:579-591; `read_artifact` returns full SQL row at storage.py:612-633). AC line 360 captures the json.loads + ToolError obligations. Round-2 H2 fully closed.
- **M1 (write_artifact signature in test #6):** Test #6 at line 331 uses `await storage.write_artifact(run_id, kind="plan", payload_json=json.dumps({"sample": "known dict"}))` — matches the actual signature. The assertion shape correctly checks for the inner-payload string `"sample"` AND absence of wrapper keys (`"payload_json"`, `"created_at"`, `"run_id"`). Pairs cleanly with H2's json.loads decode. Round-2 M1 fully closed.
- **M2 (configurable enumeration):** Lines 278-290 enumerate the dict shape explicitly: `tier_registry`, `cost_callback`, `run_id`, `pricing={}`, `workflow="standalone-audit"`, with explicit `# NOT supplied` comments for `semaphores` and `ollama_circuit_breakers`. AC line 362 reflects the same shape. Round-2 M2 fully closed (with one rationale-overstatement noted in L3 above).
- **M3 (stub-pattern citation):** Line 324 names `_StubClaudeCodeAdapter` from `tests/graph/test_audit_cascade.py:151` as the canonical pattern, with sibling variants `_FakeClaudeCodeAdapter` at `tests/graph/test_tiered_node.py:172` and `_E2EStubClaudeCodeAdapter` at `tests/workflows/test_slice_refactor_cascade_enable.py:509`. Builder can grep by class name to find any of them. (Two of the three line-numbers drifted slightly — actual `_StubClaudeCodeAdapter` is at line 103 not 151, and actual `_E2EStubClaudeCodeAdapter` is at line 388 not 509 — but the file paths and class names are correct, so the Builder grep will find them. Not surfacing as a finding; line-number drift inside test files between specs and code is normal turnover.) Round-2 M3 fully closed.
- **TA-T05-LOW-01 + TA-T05-LOW-02 carry-over:** Both lines 421-427 contain `[ ]` checkboxes with the LOW summary line + full Recommendation text. Format matches the established TA-Tnn-LOW-mm pattern (e.g. T01's TA-T01-LOW-* in the same milestone). Round-2 carry-over fully landed.
- **KDR re-grade (no movement):** All seven load-bearing KDRs still pass under the post-R2 spec. KDR-002, -003, -004, -006, -008, -009, -011, -013, -014 unchanged from round 2's grade.
- **Layer rule:** `_resolve_audit_artefact` correctly placed in `mcp/server.py` (NOT `workflows/_dispatch.py`); spec explicitly notes the layer-rule reason. No `workflows/` or `graph/` or `primitives/` diff in deliverables.
- **Status-surface enumeration (AC final):** Line 376 enumerates all 5 status surfaces (spec status; milestone README task-table row; milestone README §Exit-criteria bullets; architecture.md:105 task-number; adr/0004 lines 56 + 73). Builder has a complete checklist for close-out flip.

## Cross-cutting context

- **CS300 pivot:** Project memory marks M12 as part of the post-pivot continuation track. T05 work is unblocked.
- **Round 2 → 3 trajectory:** Round 2 surfaced 2 HIGH (parse step + payload decode — both architectural seams the cascade primitive normally hides) plus 3 MEDIUM (test signature, configurable enumeration, stub citation). All five fixed mechanically by the orchestrator between rounds. The spec is now LOW-ONLY at round 3 — exactly the predicted shape from round 2's "Round 3 should reach LOW-ONLY" cross-cutting note.
- **Loop-cap:** /clean-tasks cap is 5 rounds; T05 reached LOW-ONLY at round 3, well inside the cap. Orchestrator should push L3 to carry-over and exit the loop.
- **Pre-implementation handoff:** When `/clean-implement m12 t05` runs, the Builder will read the three carry-over LOWs (TA-T05-LOW-01..03) and the satisfied TA-T04-LOW-04. None of the three LOWs require a spec edit at implement time; all three are doc-sentence framings or future-defensive notes that the Builder can either honor verbatim or lightly soften without breaking any AC.
