# Milestone 10 — Ollama Fault-Tolerance Hardening

**Status:** 📝 Planned (drafted 2026-04-21).
**Grounding:** [architecture.md §8.4](../../architecture.md) · [roadmap.md](../../roadmap.md) · [M8 post-mortem deep-analysis](../milestone_8_ollama/README.md).

## Why this milestone exists

M8 shipped a correct, composable Ollama fault-tolerance surface (circuit breaker + fallback gate + mid-run tier override) on 2026-04-21. The close-out deep-analysis pass on the same day surfaced a cluster of fragility + technical-debt items that the mechanical audit loop did **not** catch — they are design-rationale gaps and UX weaknesses, not AC misses. M10 closes those gaps without changing M8's core design.

Every fix composes over existing primitives (KDR-001 LangGraph, KDR-006 three-bucket retry, KDR-007 LiteLLM, KDR-009 SqliteSaver-only checkpoints). No new KDR. No new dependencies.

Sits after M9 in roadmap order because M10 touches code and M9 is optional packaging-only — either milestone can land first without blocking the other.

## Goal

Close the six named gaps from the M8 deep-analysis post-mortem:

1. **Design-rationale gap** — `fallback_tier="planner-synth"` (Claude Code Opus) was locked at M8 T04 implicitly with no written rationale. The spec body anticipated `gemini_flash`; the implementation chose Opus. The cost + availability trade-offs were never documented. Retroactive ADR closes this.
2. **RETRY UX gap** — the fallback gate's RETRY branch requires the operator to wait ≥ `cooldown_s` before resuming (or the breaker is still OPEN and the next call re-trips the gate immediately). The gate prompt today doesn't say so. Silent footgun.
3. **Single-gate-per-run maintainability gap** — the sticky-OR `_ollama_fallback_fired` + `_route_before_aggregate` router invariant lives in `slice_refactor.py`'s workflow wiring, not in `build_ollama_fallback_gate`'s surface. A future workflow author composing a new parallel DAG can silently regress to multi-gate-per-run without anything failing.
4. **Send-payload carry regression guard** — the `_mid_run_tier_overrides` propagation across re-fanned `Send(...)` payloads is a LangGraph-specific invariant ("keys absent from the payload don't propagate"). If LangGraph changes `Send` semantics, the override silently fails to propagate and no test catches it.
5. **Process-local breaker scope undocumented** — the `CircuitBreaker` is process-local by construction. The assumption is load-bearing but not recorded anywhere in architecture.md. If M9+ ships a long-lived multi-process deployment (MCP service, container), each worker trips independently and the breaker becomes lies.
6. **Deferred items without nice_to_have.md entries** — empirical breaker tuning (needs telemetry), second-level fallback chain (Ollama → Claude Code → Gemini), multi-process shared-state breaker, single-gate refactor into factory, Gemini-tier breaker coverage. Each needs a `nice_to_have.md` entry with explicit trigger so they are not re-discovered from scratch.

## Exit criteria

1. [ADR-0003](../../adr/0003_ollama_fallback_tier_choice.md) documents the `fallback_tier="planner-synth"` decision: cost implications, availability coupling, "Gemini Flash as fallback" as the rejected alternative with rationale. `PLANNER_OLLAMA_FALLBACK` + `SLICE_REFACTOR_OLLAMA_FALLBACK` docstrings cite ADR-0003 and name the trade-off in one sentence.
2. `render_ollama_fallback_prompt` includes a sentence warning the operator to wait ≥ `cooldown_s` seconds before choosing RETRY (to avoid the OPEN-breaker re-trip loop). A hermetic test asserts the prompt text contains the guidance and names the actual breaker cooldown value (not a hard-coded 60).
3. A hermetic cross-workflow invariant test (`tests/workflows/test_ollama_fallback_single_gate_invariant.py`) composes a minimal two-branch `Send`-based workflow that uses `build_ollama_fallback_gate` + the documented sticky-OR wiring, and asserts that N parallel `CircuitOpen` emissions result in exactly one `record_gate('ollama_fallback')` call. Architecture.md §8.4 grows an explicit "Composing the fallback path into a new parallel workflow" subsection naming the sticky-OR + `_route_before_aggregate` pattern and citing this invariant test as the regression guard.
4. A hermetic invariant test (`tests/workflows/test_ollama_fallback_send_payload_carry.py`) asserts that a re-fired `Send(...)` payload post-FALLBACK includes `_mid_run_tier_overrides` — catches LangGraph `Send`-semantics regressions.
5. Architecture.md §8.4 records an explicit **Limitations** paragraph naming the process-local breaker assumption and linking the promotion trigger to `nice_to_have.md §17` (below).
6. `nice_to_have.md` gains five new entries, each with a named trigger:
   - **§17** — Multi-process / shared-state circuit breaker. Trigger: M9+ ships a long-lived multi-process deployment (MCP service, container, web UI).
   - **§18** — Empirical breaker tuning (`trip_threshold`, `cooldown_s`) from production telemetry. Trigger: observability backend (Langfuse §1) lands + a full milestone of trip/recovery data accumulates.
   - **§19** — Second-level fallback chain (Ollama → Claude Code → Gemini Flash). Trigger: an incident where Claude Code is also unavailable when Ollama trips, causing FALLBACK to fail opaquely.
   - **§20** — Refactor single-gate-per-run sticky-OR wiring into `build_ollama_fallback_gate` factory surface. Trigger: a third parallel-fan-out workflow lands, making the current per-workflow copy-paste of the sticky-OR pattern a real maintenance cost.
   - **§21** — Extend `CircuitBreaker` coverage to Gemini-backed LiteLLM tiers. Trigger: first observed Gemini partial outage under parallel fan-out that thrashes without a "stop trying" signal.
7. Gates green (`uv run pytest` + `uv run lint-imports` (4 contracts kept) + `uv run ruff check`). No regression on M8's hermetic suite or live smoke.

## Non-goals

- **No change to `CircuitBreaker` defaults (`trip_threshold=3`, `cooldown_s=60.0`).** Retuning requires telemetry; Langfuse is deferred. §18 captures the trigger.
- **No multi-process / shared-state breaker.** Deferred to §17 — single-process assumption stays load-bearing for M10.
- **No second-level fallback chain.** Deferred to §19. M10 documents the single-level limitation; does not add Gemini as a second fallback step.
- **No Gemini-tier circuit breaker.** Deferred to §21. M10 does not extend `_build_ollama_circuit_breakers` to cover LiteLLM Gemini routes.
- **No refactor of the single-gate sticky-OR into the gate factory.** Deferred to §20. M10 documents the pattern + adds the invariant test; the refactor is premature until a third parallel workflow appears.
- **No code change to `fallback_tier`.** `planner-synth` stays — ADR-0003 locks the choice with rationale, not a switch to `gemini_flash`.

## Key decisions in effect

| Decision | Reference |
| --- | --- |
| `fallback_tier="planner-synth"` (retroactive lock) | [ADR-0003](../../adr/0003_ollama_fallback_tier_choice.md) (lands at T01) |
| 3-bucket retry taxonomy feeds breaker | KDR-006 |
| Process-local breaker scope | architecture.md §8.4 (limitation paragraph lands at T05) |
| Single-gate-per-run for parallel fan-out | architecture.md §8.4 + [T03 invariant test](#) |
| LangGraph `Send` payload semantics | architecture.md §8.4 + [T04 invariant test](#) |
| Compose over existing KDRs — no new KDR at M10 | [CLAUDE.md non-negotiables](../../../CLAUDE.md) |

## Task order

| # | Task | Kind |
| --- | --- | --- |
| 01 | [ADR-0003 — lock `fallback_tier` decision + OllamaFallback docstrings](task_01_fallback_tier_adr.md) | doc + docstring |
| 02 | [Gate prompt UX — RETRY cooldown guidance in `render_ollama_fallback_prompt`](task_02_retry_cooldown_prompt.md) | code + test |
| 03 | [Single-gate-per-run pattern docs + cross-workflow invariant test](task_03_single_gate_invariant.md) | doc + test |
| 04 | [`_mid_run_tier_overrides` Send-payload carry invariant test](task_04_send_payload_invariant.md) | test |
| 05 | [Documentation sweep — architecture.md §8.4 limitations + 5 `nice_to_have.md` entries](task_05_doc_sweep.md) | doc |
| 06 | [Milestone close-out](task_06_milestone_closeout.md) | doc |

Per-task spec files landed when the milestone is promoted from `📝 Planned` to active. The README alone is enough context to start T01; each successor task's spec is written at the tail of the prior task's close-out so the scope stays calibrated against the landed surface.

## Traceability to M8 deep-analysis

Every M10 task maps to at least one item from the [M8 deep-analysis post-mortem](../milestone_8_ollama/README.md) (see the 2026-04-21 *§"What's fragile"* + *§"Outstanding technical debt"* sections referenced through the analysis preserved in the session transcript):

| M8 analysis item | Classification | M10 task |
| --- | --- | --- |
| `fallback_tier` decision buried in config (fragile #3) | design-rationale gap | T01 |
| `fallback_tier` retroactive ADR (debt #3) | design-rationale gap | T01 |
| RETRY UX weak (fragile #4) | UX gap | T02 |
| Gate prompt RETRY wait sentence (debt #2) | UX gap | T02 |
| Single-gate invariant lives in workflow code (fragile #5) | maintainability gap | T03 |
| `_mid_run_tier_overrides` Send-payload carry (fragile #6) | regression-guard gap | T04 |
| Process-local scope undocumented (fragile #1) | doc gap | T05 |
| Process-local nice_to_have entry (debt #1) | doc gap | T05 (§17) |
| Heuristic tuning without empirical basis (fragile #2) | telemetry-blocked | T05 (§18) |
| Second-level fallback chain (debt #4) | deferral trigger | T05 (§19) |
| Gemini-tier breaker coverage (debt #5, fragile #7) | deferral trigger | T05 (§21) |

The single-gate factory refactor (nice_to_have §20) and Gemini-tier breaker extension (nice_to_have §21) are deferrals, not M10 work. T05 writes the deferral entries with triggers; no code change.

## Carry-over from prior milestones

*None.* M8 T06 closed clean across two `/clean-implement` cycles (Cycle 1 raised 2 LOW doc-accuracy findings; Cycle 2 resolved both). All five M8 task issue files are `✅ PASS`; no `DEFERRED` items landed on M10. The M10 scope is forward-looking only — it addresses gaps surfaced by the M8 deep-analysis synthesis step, which is a separate audit surface from the `/clean-implement` loop's per-task audit.

## Issues

Land under [issues/](issues/) after each task's first audit.
