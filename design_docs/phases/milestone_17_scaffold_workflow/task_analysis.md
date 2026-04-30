# M17 — Task Analysis

**Round:** 3 | **Analyzed on:** 2026-04-30 | **Analyst:** task-analyzer agent
**Specs analyzed:** `task_01_scaffold_workflow.md` + milestone `README.md` (T02–T04 incremental-spec, absent by design).

## Summary

| Severity | Count |
| --- | --- |
| 🔴 HIGH | 0 |
| 🟡 MEDIUM | 0 |
| 🟢 LOW | 4 |

**Stop verdict:** LOW-ONLY

Round-3 hostile re-read confirms the round-2 HIGH+MEDIUM fixes all landed correctly:

- **H1 (round 2):** README:64 now reads `aiw resume scaffold-qg-1 --gate-response approved   # or --gate-response rejected to retry`. Verified `cli.py:525-527` matches: `--gate-response` is the only flag exposed; no `--approve` / `--reject` strings remain anywhere in the M17 specs (`grep -n -- "--approve\|--reject"` returns zero hits).
- **M1 (round 2):** README §Why + §What M17 ships swept to `WorkflowSpec` + `register_workflow(spec)` voice. Lines 31, 40, 41, 44, 48, 61, 78, 92, 101, 116 all consistent — validator framing is `register_workflow()` everywhere it matters; the only bare `register(...)` mention is the deliberate Tier-4 escape-hatch sentence at README:76 which now correctly reads *"Tier-4 escape-hatch — the scaffold itself is imperative; the code it emits uses the declarative `WorkflowSpec` + `register_workflow(spec)` API"*. T01:22 + T01:105 carry the matching "Why register_workflow, not register" rationale.
- **M2 (round 2):** AC-3 at T01:182 now reads *"Five validator tests pass (three reject cases + two accept cases including the Name-reference form)"* — arithmetic now matches the list at lines 136–140 (3 reject + 2 accept = 5).
- **M3 (round 2):** Risk #1 at T01:216 now reads *"a single `register_workflow(SPEC)` call importing the spec from elsewhere"* — post-pivot canonical form. No bare `register(...)` example remains.
- **M4 (round 2):** README:148 collapsed to *"`RetryingEdge` retries the LLM call (per the `classify()` taxonomy). The validator's failure message is re-rendered into the next prompt attempt to guide the model. T01 scope is the retry wiring; retry-budget tuning and gate-surfacing on exhaustion are T02 scope."* — aligns with T01 AC-10 (retry wiring at T01, budget tuning at T02). The orchestrator chose option (b) — keep T01 scope minimal.

The four LOWs from round 2 (L1–L4) are re-evaluated below — none promote to MEDIUM/HIGH; L1–L3 carry forward to spec carry-over per LOW-ONLY discipline; L4 was already applied in round 2 and is closed as a no-op.

No new findings from the hostile re-read. Specs ready for `/clean-implement`.

## Findings

### 🟢 LOW

#### L1 — Validator minimum-length-floor + `test_validator_rejects_trivially_short_source` retune as T02 carry-over

**Task:** T01.
**Location:** `task_01_scaffold_workflow.md:140` (test) + `task_01_scaffold_workflow.md:216` (Risk #1).
**Issue:** Risk #1 mentions tunability but T01 has no carry-over section binding the 80-char floor to the test's expected-rejection length. If T02 retunes the floor without retuning the test, the test silently passes for the wrong reason (rejection happens for a different fixture).
**Recommendation:** Add a carry-over note at the bottom of T01.
**Push to spec:** Add to `task_01_scaffold_workflow.md` carry-over section: *"Carry-over to T02 — the validator's 80-char minimum-length floor and the `test_validator_rejects_trivially_short_source` fixture's source length must retune together. T02's prompt iteration may surface a more realistic floor; if it changes, both the floor and the test fixture move in lockstep."*

#### L2 — Risk #5 (re-registration on re-run) doesn't address gate-rejection retry path

**Task:** T01.
**Location:** `task_01_scaffold_workflow.md:220` (Risk #5).
**Issue:** Risk #5 covers the user-reruns-with-`--force` path but not the *gate-rejected* → *fresh-run-id* → *new-goal* iteration loop. Operators iterating on a scaffold prompt may expect rejection to leave a recoverable artefact (it does not).
**Recommendation:** Brief carry-over note clarifying rejection terminates the run.
**Push to spec:** Add a final risk bullet (or extend Risk #5) at `task_01_scaffold_workflow.md:220`: *"Gate rejection on a `run_id` is terminal for that run; users iterate by invoking `aiw run scaffold_workflow` again with a fresh `run_id` + revised `--goal`. The scaffold does not store rejected attempts for later review."*

#### L3 — `os.replace` atomicity claim should call out same-filesystem requirement explicitly

**Task:** T01.
**Location:** `task_01_scaffold_workflow.md:71-77` (`atomic_write` docstring) + Risk #4 at line 219.
**Issue:** The docstring says *"Uses `tempfile.NamedTemporaryFile` in the same directory, then `os.replace()` to swap"* — "same directory" implies same FS, but a reviewer skimming may miss the load-bearing constraint that `os.replace()` is only POSIX-atomic across same-FS targets.
**Recommendation:** Strengthen the docstring to make the same-FS dependency explicit.
**Push to spec:** Edit `task_01_scaffold_workflow.md:74` (`atomic_write` docstring): change *"Uses tempfile.NamedTemporaryFile in the same directory, then os.replace() to swap"* → *"Uses `tempfile.NamedTemporaryFile(dir=target.parent)` to guarantee same-filesystem placement (required for `os.replace` atomicity on POSIX), then `os.replace()` to swap."*

#### L4 — CHANGELOG branch-pair already correct (round-2 confirmed; closing as no-op)

**Task:** T01.
**Location:** `task_01_scaffold_workflow.md:176` (Deliverable §9 CHANGELOG entry) + `task_01_scaffold_workflow.md:196` (AC-17).
**Issue:** Round-1 L4 wanted the "on both branches" framing replaced with `design_branch` only + promotion-to-`main` at T04 close-out. Verified line 176 now reads *"Under `[Unreleased]` on `design_branch` — new `### Added — M17 Task 01: …` entry. Names the new modules… and the ADR-0010 placeholder (filled at T03). Promotion to `main` happens at milestone close-out (T04 scope)."* AC-17 at line 196 mirrors the same framing.
**Recommendation:** None. Closed.

## What's structurally sound

- **All round-1 + round-2 HIGH+MEDIUM fixes verified.** ADR-0010 sweep, `gate_response` sweep (CLI + MCP), `AIW_EXTRA_WORKFLOW_MODULES` sweep, `list_workflows()` Python API in AC-1, WorkflowSpec/`register_workflow(spec)` pivot complete on all surfaces. Bare `register(...)` only appears in the four legitimate Tier-4 escape-hatch contexts: T01:22, T01:105, T01:180 (AC-1), README:76. Each is gated by explicit "the scaffold *itself* uses Tier-4; the code *it generates* is declarative" framing.
- **CLI flag verified against source.** `cli.py:525-527` exposes `--gate-response` / `-r` only; `cli.py:423` and `cli.py:588` re-emit the literal `aiw resume {run_id} --gate-response <approved|rejected>` stdout pin. README + T01 match.
- **Symbol grounding verified.** `register_workflow` lives at `ai_workflows/workflows/spec.py:372` and is re-exported from `ai_workflows/workflows/__init__.py:85` (in `__all__` at line 106). T01:4 grounding cites `__init__.py:54-110` as the public-surface block — matches the docstring + re-export region. `WorkflowSpec` at `spec.py:329`. `list_workflows` at `__init__.py:167` (in `__all__`). `summarize.py:121` uses `register_workflow(_SPEC)` — confirms the WorkflowSpec form is the canonical shipped pattern. (Note: `planner.py:849` and `slice_refactor.py:1812` still use bare `register(...)` — those are pre-M19 imperative workflows. The scaffold mirrors planner/slice_refactor for its *own* graph and emits summarize-style declarative code — internally consistent.)
- **Tier-registry naming convention verified load-bearing.** `_dispatch.py:264` defines `_resolve_tier_registry(workflow, module)` and `_dispatch.py:581 + :921` invoke it on the workflow module. T01 AC-9 + spec line 21 carry the load-bearing-name warning.
- **Layer rule + four-kept claim.** New modules (`scaffold_workflow.py`, `_scaffold_write_safety.py`, `_scaffold_validator.py`) all in `workflows/`. AC-12 4-kept claim is reachable.
- **KDR alignment.** KDR-003 (no Anthropic SDK) — AC-14. KDR-004 (validator pairing) — AC-13. KDR-006 (RetryingEdge) — AC-10 + graph diagram. KDR-008 (FastMCP) — AC-8 (no schema drift). KDR-009 (SqliteSaver) — implicit, no checkpoint changes. KDR-013 (user-owned external code) — entire risk-ownership boundary section. KDR-014 (per-call tier rebind) — `tier_preferences` dropped, `--tier-override` / `tier_overrides` everywhere.
- **ADR-0010 slot still free.** `design_docs/adr/` lists 0001/0002/0004/0005/0007/0008/0009 — slot 0010 remains open and unclaimed.
- **0.4.0 framing intact.** Additive-minor: scaffold workflow + CLI alias + MCP exposure (existing tool, new workflow name). No breaking changes.
- **Status surfaces consistent.** README:127 task-table row Kind = `code + test`; T01 `Status: 📝 Planned`. Both match.

## Cross-cutting context

- **Memory + state:** project memory (`project_m13_shipped_cs300_next.md`) flags M17 as spec'd-not-yet-implemented; autopilot is paused on M21 T15 (`project_m21_autopilot_2026_04_29_checkpoint.md`). M17 is pre-implementation hygiene only — no in-flight implementation.
- **All round-2 LOWs re-evaluated.** Re-read confirms none promote: L1 is small spec ergonomics (Builder can absorb); L2 is operator-affordance prose; L3 is docstring strengthening; L4 is closed.
- **No new round-3 findings.** Hostile re-read confirms the H2 WorkflowSpec pivot + H1 CLI-flag fix are now consistent across all surfaces. No new drift, no new contradictions, no new dependency holes.
- **LOW-ONLY → push to carry-over.** Per orchestrator convention, the three actionable LOWs (L1–L3) get pushed to T01's carry-over section (or applied as one-line edits) before `/clean-implement` kicks off. L4 needs no action.
- **Specs ready for implementation.** Once L1–L3 are carry-over'd, the M17 specs are clean for `/clean-implement m17 t01`.
