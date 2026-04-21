# Task 06 — Milestone Close-out

**Status:** 📝 Planned.
**Grounding:** [milestone README](README.md) · [CLAUDE.md](../../../CLAUDE.md) close-out conventions · [M7 T06](../milestone_7_evals/task_06_milestone_closeout.md) (pattern to mirror).

## What to Build

Close M8. Confirm every exit criterion from the
[milestone README](README.md). Update [CHANGELOG.md](../../../CHANGELOG.md),
flip M8 complete in [roadmap.md](../../roadmap.md), and refresh the
root [README.md](../../../README.md). No code change beyond docs —
any code finding surfaced during close-out becomes a forward-deferred
carry-over on the appropriate M9 task or a new nice_to_have.md entry,
never a drive-by fix.

Mirrors [M7 Task 06](../milestone_7_evals/task_06_milestone_closeout.md)
so reviewers get identical close-out muscle memory.

## Deliverables

### [README.md](README.md) (milestone)

- Flip **Status** from `📝 Planned` to `✅ Complete (<YYYY-MM-DD>)`.
- Append an **Outcome** section summarising:
  - Health probe ([task 01](task_01_health_check.md)) —
    `probe_ollama` + `HealthResult` primitive landed under
    `ai_workflows/primitives/llm/ollama_health.py`; never raises;
    five reason strings (`ok`, `connection_refused`, `timeout`,
    `http_<status>`, `error:<type>`).
  - Circuit breaker ([task 02](task_02_circuit_breaker.md)) —
    `CircuitBreaker` / `CircuitOpen` / `CircuitState` under
    `ai_workflows/primitives/circuit_breaker.py`; process-local,
    `asyncio.Lock`-guarded; CLOSED → OPEN → HALF_OPEN → CLOSED
    transitions verified under concurrent branches.
  - Fallback gate ([task 03](task_03_fallback_gate.md)) —
    `build_ollama_fallback_gate` under
    `ai_workflows/graph/ollama_fallback_gate.py`; strict-review;
    `FallbackChoice.{RETRY, FALLBACK, ABORT}`; state-key contract
    `_ollama_fallback_reason` / `_ollama_fallback_count` /
    `ollama_fallback_decision` locked.
  - Integration ([task 04](task_04_tiered_node_integration.md)) —
    `TieredNode` reads `ollama_circuit_breakers` from `configurable`;
    `CircuitOpen` routes planner + slice_refactor through a single
    fallback gate per run (slice_refactor's parallel branches share
    the gate); mid-run tier override via `_mid_run_tier_overrides`
    takes precedence over configurable + registry.
  - Degraded-mode tests ([task 05](task_05_degraded_mode_e2e.md)) —
    hermetic suite covers all three `FallbackChoice` branches on
    both workflows; operator-run e2e smoke documented.
  - Manual verification: degraded-mode e2e smoke rerun once at
    close-out time with a real Ollama instance; the operator
    procedure in the test docstring works from a fresh clone.
  - Green-gate snapshot: `uv run pytest`, `uv run lint-imports`
    (**4 contracts kept** — no new layer contract added at M8;
    all new modules fit existing primitives + graph layers),
    `uv run ruff check`.
- Keep the **Carry-over from prior milestones** section intact
  (currently: *None* — M7 T06 closed clean).

### [roadmap.md](../../roadmap.md)

Flip M8 row `Status` from `planned` to `✅ complete (<YYYY-MM-DD>)`.

### [CHANGELOG.md](../../../CHANGELOG.md)

Promote accumulated `[Unreleased]` entries from M8 tasks into a dated
section `## [M8 Ollama Infrastructure] - <YYYY-MM-DD>`. Keep the
top-of-file `[Unreleased]` section intact. Add a T06 close-out entry
at the top of the new dated section — mirror M7 T06's shape. Record
in this entry:

- The degraded-mode e2e smoke rerun at close-out time — commit sha
  baseline + the operator's pass/fail observation (the three branches
  were exercised manually).
- The `uv run lint-imports` 4-contract snapshot confirming no new
  contracts landed at M8.
- The breaker tuning locked at T02 (default `trip_threshold=3`,
  `cooldown_s=60.0`) — so future operators know which defaults to
  override.
- The mid-run tier override precedence decision (state > configurable
  > registry) documented in T04 — so future workflow authors know
  which seam to plumb into.

### Root [README.md](../../../README.md)

Update to M8-closed state, matching the M7 close-out shape:

- **Status table** — M8 row → `✅ Complete (<YYYY-MM-DD>)`.
- **Narrative** — append a post-M8 paragraph covering:
  - The circuit-breaker-per-Ollama-tier model (KDR-006 transient bucket
    as the trip signal, process-local state).
  - The strict-review fallback gate with three choices (retry /
    fallback / abort) and the single-gate-per-run invariant for
    parallel fan-out.
  - The mid-run tier override mechanism and why it's needed (it's
    the execution path of `FallbackChoice.FALLBACK`).
- **What runs today** — add a `CircuitBreaker` bullet under the
  primitives layer; add a `build_ollama_fallback_gate` bullet under
  the graph layer; note both planner + slice_refactor now compose
  the fallback path.
- **Next** pointer — flip `→ M8 Ollama infrastructure` to
  `→ M9 Skill` (or the next planned milestone as of close-out date).

Section-heading rename: `post-M7` → `post-M8`.

### [architecture.md](../../architecture.md) §8.4 update

Expand §8.4 in place (not a new section) to document the landed flow:

- Reference `CircuitBreaker` + `CircuitOpen` + `build_ollama_fallback_gate`
  by name.
- Describe the state-key contract (`_ollama_fallback_reason`,
  `_ollama_fallback_count`, `ollama_fallback_decision`).
- Describe the mid-run tier override precedence.
- Pin the single-gate-per-run invariant for parallel branches (this
  is the subtlest design point and belongs in architecture.md so
  future milestone authors don't relitigate it).

No new KDR. The M8 design composes over existing KDRs (006 retry,
001/009 LangGraph-native gates, 007 LiteLLM routing). Documenting
that composition is what §8.4 is for.

### Audit-before-close check

The close-out Builder opens **every** M8 task issue file
(`design_docs/phases/milestone_8_ollama/issues/task_0[1-5]_issue.md`)
and confirms:

- No OPEN `🔴 HIGH` or `🟡 MEDIUM` entries.
- Every `DEFERRED` entry has a matching carry-over in its target task
  spec (propagation discipline, CLAUDE.md *Forward-deferral propagation*).
- Every nice_to_have.md deferral has a §N reference recorded.

Any hole found is the close-out's to fix in-audit (doc maintenance
only, not code). If a gap can't be closed with a doc edit, stop and
ask the user.

## Acceptance Criteria

- [ ] Every exit criterion in the milestone [README](README.md) has a
      concrete verification (paths / test names / issue-file links).
- [ ] `uv run pytest && uv run lint-imports && uv run ruff check`
      green on a fresh clone; `lint-imports` reports **4 contracts kept**.
- [ ] Close-out CHANGELOG entry records the degraded-mode e2e smoke
      rerun at close-out time (commit sha + three-branch observation).
- [ ] Close-out CHANGELOG entry records the breaker tuning defaults
      locked at T02.
- [ ] Close-out CHANGELOG entry records the mid-run tier override
      precedence locked at T04.
- [ ] M8 milestone README **and** roadmap reflect
      `✅ Complete (<YYYY-MM-DD>)`.
- [ ] CHANGELOG has a dated `## [M8 Ollama Infrastructure] - <YYYY-MM-DD>`
      section; `[Unreleased]` preserved at the top.
- [ ] Root README updated: status table, post-M8 narrative,
      What-runs-today, Next → M9.
- [ ] architecture.md §8.4 updated in place with the landed flow
      (no new KDR).
- [ ] All M8 task issue files audited for propagation holes; any gap
      closed or escalated.

## Dependencies

- [Task 01](task_01_health_check.md) through [Task 05](task_05_degraded_mode_e2e.md).

## Out of scope (explicit)

- Any code change. Close-out is docs-only; findings flow to M9+
  carry-over or nice_to_have.md.
- Docker Compose packaging of Ollama — see
  [nice_to_have.md §5](../../nice_to_have.md).
- Langfuse-backed observability of the circuit breaker — see
  [nice_to_have.md §1](../../nice_to_have.md).
- Retroactive eval coverage for the fallback branches (M9+ captures
  under its own tasks, not back-filled here).

## Carry-over from prior milestones

*None.* M7 T06 closed clean with the four carry-overs resolved or
deferred to nice_to_have.md §13. No open items land on M8.
