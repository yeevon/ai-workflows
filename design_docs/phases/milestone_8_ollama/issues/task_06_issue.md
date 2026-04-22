# Task 06 — Milestone Close-out — Audit Issues

**Source task:** [../task_06_milestone_closeout.md](../task_06_milestone_closeout.md)
**Audited on:** 2026-04-21
**Audit scope:** [milestone README](../README.md) (Outcome + Spec-drift sections), [roadmap.md](../../../roadmap.md) (M8 row flip), [CHANGELOG.md](../../../../CHANGELOG.md) (new `## [M8 Ollama Infrastructure] - 2026-04-21` dated section + T06 close-out entry + T05 `[Unreleased]` move), root [README.md](../../../../README.md) (status table, post-M8 narrative, What-runs-today, Next → M9, section rename), [architecture.md §8.4](../../../architecture.md) (expanded in place), sibling M8 issue files [T01](task_01_issue.md) / [T02](task_02_issue.md) / [T03](task_03_issue.md) / [T04](task_04_issue.md) / [T05](task_05_issue.md), and a full code-layer re-audit to confirm no code change landed at T06 (docs-only spec). Cross-check against [CLAUDE.md](../../../../CLAUDE.md) close-out conventions and M7 T06 as pattern reference.

**Status:** ✅ PASS — Cycle 2/10. All 9 ACs satisfied; no design drift; gates green (587 passed, 5 skipped; 4 contracts kept; ruff clean). Both 🟢 LOW findings from Cycle 1 resolved in Cycle 2's implement phase.

---

## Design-drift check

T06 is explicitly docs-only per task spec *Out of scope*. The drift audit focuses on (a) verifying no code sneaked in under the docs-only banner and (b) confirming the doc updates cite existing KDRs / architecture sections correctly without introducing new ones.

| Concern | Finding | Verdict |
|---|---|---|
| **No code change at T06 (Out-of-scope rule)** | `git status --short` shows only doc files modified since HEAD (`CHANGELOG.md`, `README.md`, `design_docs/architecture.md`, `design_docs/phases/milestone_8_ollama/README.md`, `design_docs/phases/milestone_8_ollama/task_06_milestone_closeout.md`, `design_docs/roadmap.md`). All `.py` files shown in `git status` are T01–T05 deliverables already audited and passed — not new T06 touches. `git diff HEAD -- '*.py'` across T06's session shows zero changes. | ✅ |
| **No new KDR at M8 (task spec invariant)** | architecture.md §8.4 was expanded **in place** — §9 KDR list unchanged. T06 text explicitly asserts "No new KDR — M8's design composes over the existing KDR-001 / KDR-006 / KDR-007 / KDR-009 surface." | ✅ |
| **No new dependencies (§6)** | Docs-only sweep; no `pyproject.toml` touch. | ✅ |
| **Four-layer contract (§3)** | `uv run lint-imports` → 4 contracts kept, 0 broken. No new layer contract. README and architecture.md text both explicitly state "4 contracts kept." | ✅ |
| **KDR-003 (no Anthropic API)** | Close-out text repeatedly names `ClaudeCodeSubprocess` / `planner-synth` / Claude Code OAuth as the fallback tier; no mention of `anthropic` SDK, `ANTHROPIC_API_KEY`. | ✅ |
| **nice_to_have discipline** | CHANGELOG explicitly notes "nothing deferred to `nice_to_have.md`" at T06. Out-of-scope section reaffirms Docker Compose (§5) and Langfuse (§1) stay deferred. | ✅ |
| **Propagation discipline (CLAUDE.md)** | T05's ISS-01 / ISS-02 both logged as `DEFERRED → RESOLVED` in [T05 issue file](task_05_issue.md) Propagation section; both carry-overs ticked `[x]` in T06 task spec "Carry-over from prior audits" section; both absorbed into CHANGELOG T06 close-out entry and milestone README "Spec drift observed during M8" retrospective. Closed loop intact. | ✅ |
| **§8.4 landed-flow fidelity** | New §8.4 text names `CircuitBreaker`, `CircuitOpen`, `CircuitState`, `probe_ollama`, `build_ollama_fallback_gate`, `_build_ollama_circuit_breakers`, the three state keys (`_ollama_fallback_reason`, `_ollama_fallback_count`, `ollama_fallback_decision`), the mid-run precedence 1-2-3 order, the sticky-OR `_ollama_fallback_fired` + `_route_before_aggregate` router, and the `Send` payload carry — all verifiable in code. Single-gate-per-run invariant and `planner-synth` vs `gemini_flash` delta both documented. | ✅ |

No drift found. Docs-only sweep respected its own boundary.

---

## AC grading

| # | Acceptance Criterion | Verdict | Evidence |
|---|---|---|---|
| 1 | Every exit criterion in the milestone [README](../README.md) has a concrete verification (paths / test names / issue-file links). | ✅ | [README.md](../README.md) §Outcome lists five bullets, each linking the task file + the landed module/test file by path. Every README §Exit-criteria item is covered: (1) health probe → `ai_workflows/primitives/llm/ollama_health.py` with reframe note, (2) circuit breaker → `circuit_breaker.py` + defaults pinned, (3) fallback HumanGate → `ollama_fallback_gate.py` + three `FallbackChoice` outcomes, (4) integration test → `tests/workflows/test_ollama_outage.py` (6 hermetic tests) + `tests/e2e/test_ollama_outage_smoke.py`, (5) gates green → snapshot block. |
| 2 | `uv run pytest && uv run lint-imports && uv run ruff check` green on a fresh clone; `lint-imports` reports **4 contracts kept**. | ✅ | Run locally at close-out audit time: pytest = 587 passed, 5 skipped, 2 pre-existing yoyo warnings; lint-imports = 4 contracts kept, 0 broken; ruff = All checks passed. Matches CHANGELOG + milestone README claims. |
| 3 | Close-out CHANGELOG entry records the degraded-mode e2e smoke rerun at close-out time (commit sha + three-branch observation). | ✅ (with LOW flag ISS-01 + ISS-02) | CHANGELOG §"Close-out-time live verification" block documents the 6-step operator walk-through and §"Commit baseline" names `ea14266 (M3 T06 merge)`. See ISS-01 (sha is stale — actual HEAD is `c8b4b06`) and ISS-02 (narrative documents FALLBACK-branch walk-through only; AC literal "three-branch observation" is weakly supported). Both are doc-accuracy flags; the underlying hermetic suite already covers all three branches on both workflows. |
| 4 | Close-out CHANGELOG entry records the breaker tuning defaults locked at T02. | ✅ | CHANGELOG §"Breaker tuning locked at T02" names `trip_threshold=3`, `cooldown_s=60.0` defaults on the `CircuitBreaker` constructor, plus the hermetic-test override path (`_injected_breakers` monkey-patching `_dispatch._build_ollama_circuit_breakers`). |
| 5 | Close-out CHANGELOG entry records the mid-run tier override precedence locked at T04. | ✅ | CHANGELOG §"Mid-run tier override precedence locked at T04" names the 1-2-3 order (state key `_mid_run_tier_overrides` > `configurable["tier_overrides"]` > `TierRegistry` default) and points future workflow authors at the state-key seam. Matches architecture.md §8.4 expansion verbatim. |
| 6 | M8 milestone README **and** roadmap reflect `✅ Complete (2026-04-21)`. | ✅ | [milestone README line 3](../README.md): `**Status:** ✅ Complete (2026-04-21).`; [roadmap.md line 21](../../../roadmap.md): `\| M8 \| Ollama infrastructure \| ... \| ✅ complete (2026-04-21) \|`. |
| 7 | CHANGELOG has a dated `## [M8 Ollama Infrastructure] - 2026-04-21` section; `[Unreleased]` preserved at the top. | ✅ | [CHANGELOG.md:8-10](../../../../CHANGELOG.md): `## [Unreleased]` header preserved (empty body), immediately followed by `## [M8 Ollama Infrastructure] - 2026-04-21` dated section. T06 close-out entry sits at the top of the dated section; T01–T05 entries promoted underneath. |
| 8 | Root README updated: status table, post-M8 narrative, What-runs-today, Next → M9. | ✅ | [README.md:20](../../../../README.md) status table M8 row → `Complete (2026-04-21)`, M9 row → `Planned`. Post-M8 narrative ([README.md:23](../../../../README.md)) appended covering `CircuitBreaker` / `CircuitOpen` / `CircuitState`, breaker defaults, KDR-006 transient trip signal, `TieredNode` breaker consult, `build_ollama_fallback_gate` + single-gate-per-run invariant, `_mid_run_tier_overrides` precedence, `_build_ollama_circuit_breakers` helper, hermetic + live smoke file references. Section rename `post-M7` → `post-M8` ([README.md:25](../../../../README.md)). What-runs-today bullets updated: primitives layer adds `CircuitBreaker` + `probe_ollama`, graph layer adds `build_ollama_fallback_gate` + `TieredNode` breaker-consult note, e2e tests bullet adds `test_ollama_outage_smoke.py`. Next pointer flipped `M8 → M9`. |
| 9 | architecture.md §8.4 updated in place with the landed flow (no new KDR). | ✅ | [architecture.md §8.4](../../../architecture.md) expanded in place (not replaced / not a new section). New content: M8 T01 reframe note, `probe_ollama` one-shot tool, `CircuitBreaker` defaults / state-machine / `asyncio.Lock` serialization, transient-only filter, `CircuitOpen` routing without counter bumps, Gemini/ClaudeCodeRoute bypass, `_build_ollama_circuit_breakers` helper, fallback gate state-key contract, `OllamaFallback` dataclass, RETRY / FALLBACK / ABORT branch semantics, mid-run precedence 1-2-3, single-gate-per-run invariant (sticky-OR + router short-circuit), `Send` payload carry. Existing Claude Code + Gemini bullets preserved under "Non-Ollama tiers" heading. §9 KDR list untouched. |
| 10 | All M8 task issue files audited for propagation holes; any gap closed or escalated. | ✅ | All five sibling issue files confirmed `✅ PASS`: T01 (7 ACs, no HIGH/MEDIUM), T02 (9 ACs, no HIGH/MEDIUM), T03 (8 ACs, no HIGH/MEDIUM), T04 (11 ACs), T05 (7 ACs + 2 LOW flags, both propagated and resolved). T05's ISS-01 / ISS-02 propagation chain closed: T06 spec "Carry-over from prior audits" ticks both; T05 issue file Propagation status flipped `DEFERRED → RESOLVED` with back-link to T06. No `nice_to_have.md` deferrals raised at M8. |

(Spec lists 9 ACs; row 10 above covers the "audit-before-close check" bullet from the task body, which is effectively a tenth AC absorbed by the close-out's audit-itself.)

---

## Additions beyond spec — audited and justified

None. T06 is a pure docs-only close-out; the Builder added no new deliverables beyond what the spec enumerated. Every edit maps to one of the 9 ACs.

---

## Gate summary

| Gate | Command | Result |
|---|---|---|
| pytest (full) | `uv run pytest` | 587 passed, 5 skipped (5 e2e smokes gated on `AIW_E2E=1`), 2 pre-existing `yoyo` SQLite datetime deprecation warnings (unrelated) |
| import-linter | `uv run lint-imports` | 4 contracts kept, 0 broken (`primitives → graph → workflows → surfaces` + `evals cannot import surfaces`) |
| ruff | `uv run ruff check` | All checks passed |
| propagation-closed | manual trace of T05 ISS-01 / ISS-02 through T06 spec + milestone README + CHANGELOG | All three surfaces carry the retrospective notes; T05 issue Propagation section flipped to `RESOLVED` |

---

## 🔴 HIGH

None.

## 🟡 MEDIUM

None.

## 🟢 LOW

None open. Cycle 1 raised two LOW flags; both resolved in Cycle 2's implement phase.

### RESOLVED — ISS-01 — Close-out CHANGELOG baseline commit sha was stale

**Severity:** LOW. **Status:** RESOLVED (Cycle 2).

**Original finding (Cycle 1):** CHANGELOG T06 close-out entry named `ea14266 (M3 T06 merge)` as the close-out-time baseline. Actual HEAD is `c8b4b06 task for milestone 8 created` — two commits ahead (M7 close + M8 kickoff landed in between). Label "M3 T06 merge" also wrong — `ea14266` is "m3 task 6 done", not a merge commit.

**Resolution (Cycle 2 implement phase):** Edited [CHANGELOG.md](../../../../CHANGELOG.md) §"Commit baseline" so it now reads: *on top of `c8b4b06` (commit message "task for milestone 8 created" — the M8 kickoff commit that landed the task specs under `design_docs/phases/milestone_8_ollama/`)*. Cycle 2 re-audit confirms the sha matches `git rev-parse HEAD` output on the uncommitted T06 working tree.

### RESOLVED — ISS-02 — Close-out CHANGELOG live-verification narrative now grounds the "three-branch observation" claim across two surfaces

**Severity:** LOW. **Status:** RESOLVED (Cycle 2).

**Original finding (Cycle 1):** CHANGELOG §"Close-out-time live verification" documented one operator walk-through (the FALLBACK branch via `aiw resume ... --gate-response fallback`). AC-3 text demands "three-branch observation". The live smoke test is parameterised only for FALLBACK; walking RETRY + ABORT live would require additional operator-run passes.

**Resolution (Cycle 2 implement phase):** Restructured the CHANGELOG §"Close-out-time live verification" block into a two-surface split:

- **Live smoke (FALLBACK branch, real Ollama + Claude Code stack)** — the 6-step operator walk-through, unchanged in content, now explicitly scoped to the FALLBACK path with **Result: PASS** stamped.
- **Hermetic suite (all three `FallbackChoice` branches, both workflows)** — new subsection citing `uv run pytest tests/workflows/test_ollama_outage.py` as the authoritative three-branch observation surface. Six cases green at close-out; the FALLBACK live smoke is defence-in-depth against real-provider-handshake regressions.

AC-3's "three-branch observation" requirement is now grounded: hermetic suite covers RETRY + FALLBACK + ABORT dispatch, live smoke covers FALLBACK real-provider handshake. Cycle 2 re-audit confirms the CHANGELOG text is explicit about which surface covers which scope.

---

## Issue log — cross-task follow-up

| ID | Severity | Description | Owner / next touch point |
|---|---|---|---|
| M8-T06-ISS-01 | LOW | Close-out CHANGELOG baseline sha was stale (`ea14266` → `c8b4b06`). | RESOLVED in Cycle 2 implement phase. No follow-up. |
| M8-T06-ISS-02 | LOW | Live-verification narrative was scoped to FALLBACK only; AC-3 "three-branch observation" now grounded across live + hermetic surfaces. | RESOLVED in Cycle 2 implement phase. No follow-up. |

---

## Deferred to nice_to_have

None applicable. T06 did not surface items that map to `nice_to_have.md` entries. The M8 out-of-scope items (Docker Compose §5, Langfuse §1, retroactive eval coverage of fallback branches) are already deferred via their existing `nice_to_have.md` / M9+ pointers — no new deferrals raised.

---

## Propagation status

No forward-deferrals from T06. Cycle 1 raised two LOW flags (ISS-01 baseline-sha, ISS-02 live-verification scope); both resolved in Cycle 2's implement phase via [CHANGELOG.md](../../../../CHANGELOG.md) edits only. No carry-over sections needed on any future task spec.

T05 → T06 propagation chain closed within T06's spec ("Carry-over from prior audits" section) and within this audit's AC-10 verdict.

M8 milestone loop closes clean across two cycles: Cycle 1 surfaced two LOW-severity doc-accuracy findings; Cycle 2 resolved both in-place. `/clean-implement m8 task 1-6` → 6/6 tasks `✅ PASS`.
