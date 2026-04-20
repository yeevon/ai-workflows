# Task 08 — Milestone Close-out — Audit Issues

**Source task:** [../task_08_milestone_closeout.md](../task_08_milestone_closeout.md)
**Audited on:** 2026-04-20
**Audit scope:** the docs-only close-out for M3 — the `## Outcome (2026-04-20)` section appended to [milestone_3_first_workflow/README.md](../README.md), the `Status` flip on [roadmap.md](../../../roadmap.md) line 16, the new `## [M3 First Workflow — planner] - 2026-04-20` section in [CHANGELOG.md](../../../../CHANGELOG.md) (promoted T01–T07 entries + a new T08 close-out entry), and the `[Unreleased]` layout (now holding only the Architecture pivot entry, matching the post-M1/M2-close-out layout pinned by [M2 T09](../../milestone_2_graph/issues/task_09_issue.md)).
**Status:** ✅ PASS (2026-04-20, after T07a + T07b landed) — 0 HIGH / 0 MEDIUM / 0 LOW. All 5 ACs met. AC-3 closed by the post-T07b live run: `AIW_E2E=1 uv run pytest -m e2e -v` → `1 passed, 290 deselected, 2 warnings in 11.67s` (single-shot convergence on both tiers against live Gemini Flash). Resolution path: **M3-T08-ISS-02** (original finding — T03 tiered_node omits `output_schema=`) → filed [T07a](../task_07a_planner_structured_output.md) → T07a landed the `output_schema=` wiring and exposed a second layer of the same gap (`PlannerPlan` JSON Schema exceeding Gemini's structured-output budget) → filed [T07b](../task_07b_planner_schema_simplify.md) → T07b stripped the `PlannerStep` / `PlannerPlan` bounds → live e2e green. M3-T08-ISS-02 flipped to RESOLVED. Supersedes the earlier (withdrawn) M3-T08-ISS-01 credential-diagnosis finding.

---

## Design-drift check (against architecture.md + KDR-009 + KDR-007)

Docs-only close-out: no source file under `ai_workflows/` or `tests/` is touched by this task. Design-drift vectors are therefore mostly N/A, but the audit still walks the checklist:

| Vector | Finding |
| --- | --- |
| New dependency added? | No. No changes to `pyproject.toml` in this task — the M3 T07 marker registration was already landed under T07 and is merely referenced here. ✅ |
| New module or layer? | No `ai_workflows/` change. Four-layer contract untouched. ✅ |
| Import-linter contract | 3/3 kept (verified locally — 22 files, 32 deps, same counts as T07 close). ✅ |
| LLM call added? | No. The Outcome section *describes* the M3 LLM wiring (all through `TieredNode` + `ValidatorNode` per KDR-004) but adds no new wiring. ✅ |
| Checkpoint / resume logic? | No. The Outcome section points at the existing `AsyncSqliteSaver` wiring from T04/T05 and the KDR-009 binding from M2 T08. ✅ |
| Retry logic? | None added. ✅ |
| Observability? | None added. ✅ |
| Anthropic SDK import? | None. No occurrence of `"anthropic."` or `"ANTHROPIC_API_KEY"` in any file this task touches (verified by Grep over the diff). ✅ |
| `nice_to_have.md` adoption? | No. The Outcome section *cites* the T06/T07 reframe's deferral to [nice_to_have.md §9](../../../nice_to_have.md) but does not adopt anything. The pivot entry carried under `[Unreleased]` lists Langfuse / Instructor / LangSmith / Typer / Docker Compose / mkdocs / DeepAgents / standalone OTel — all of which remain parked with no trigger fired. ✅ |
| Test for every AC? | N/A for a docs-only close-out; the AC coverage tests belong to the T01–T07 tasks already audited green. T08's own ACs are executable commands (`uv run pytest`, `uv run lint-imports`, `uv run ruff check`) whose pass/fail is the gate itself — run live below. |
| Architecture grounding | [architecture.md](../../../architecture.md) §4.4 already reflects the T06 `aiw cost-report` drop and the M4 `get_cost_report` reframe inheritance (line 97 + 102) — verified via grep. No further architecture edits needed for close-out. ✅ |
| Forward-carry items landed? | Verified: M2-T07-ISS-01 (`wrap_with_error_handler`) landed in M2 T07 and is cited in the M2 Outcome; no M2 carry-over was forwarded to M3 T08. The T06 reframe's `nice_to_have.md §9` deferral is a parking-lot item (no target task), correctly not forward-carried to a task. ✅ |

No architecture section contradicted. No KDR violated.

---

## AC grading

| # | AC | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Every exit criterion in the milestone [README](../README.md) has a concrete verification (paths / test names / issue-file links). | ✅ | Exit-criteria table at README lines 92–99 lists all 6 exit criteria, each with an issue-file link (`task_03/04/05/06/07_issue.md` all ✅ PASS per `grep -m1 Status` on each) and a file path (`ai_workflows/workflows/planner.py`, `tests/cli/test_resume.py`, `tests/cli/test_list_runs.py`, `tests/e2e/test_planner_smoke.py`, `.github/workflows/ci.yml`). |
| 2 | `uv run pytest && uv run lint-imports && uv run ruff check` green on a fresh clone. | ✅ | Live run in this audit: `295 passed, 1 skipped, 2 warnings (pre-existing yoyo)` in 6.80s; `lint-imports` 3/3 kept, 0 broken (22 files, 32 deps); `ruff check` — `All checks passed!`. Snapshot recorded in both the README Outcome table (lines 83–88) and the T08 CHANGELOG entry (lines 124–129). |
| 3 | `AIW_E2E=1 uv run pytest -m e2e` green once (record in the close-out CHANGELOG entry). | 🔴 FAIL | **Live run performed on 2026-04-20** against real Gemini (`GEMINI_API_KEY` loaded from `.env` via `tests/conftest.py:16`). Result: **FAILED after ~32s** with `RetryableSemantic('explorer_validator: output failed ExplorerReport validation')`. Replay: explorer call #1 → Gemini output (76 in / 1397 out, $0.0035) → validator rejected → retry → explorer call #2 (76 in / 1265 out, $0.0032) → validator rejected → retry → explorer calls #3, #4, #5 hit Gemini 503 ServiceUnavailableError → retry budget exhausted. **Collection-only gate** (`AIW_E2E=1 uv run pytest tests/e2e/ --collect-only` → `1 test collected`) still holds and is recorded. Root cause + resolution path: see **M3-T08-ISS-02** below. |
| 4 | README and roadmap reflect ✅ status. | ✅ | README line 3 — `**Status:** ✅ Complete (2026-04-20).`; roadmap line 16 — `✅ complete (2026-04-20)`. Verified via direct Read. |
| 5 | CHANGELOG has a dated entry summarising M3; `[Unreleased]` remains at the top of the file holding only the Architecture pivot entry. | ✅ | CHANGELOG structure verified via `grep '^## \\[' CHANGELOG.md`: `[Unreleased]` (line 8) → Architecture pivot entry (line 10, single entry, carried since M1) → `[M3 First Workflow — planner] - 2026-04-20` (line 74) with T08 close-out at top (line 76), then T07/T06/T05/T04/T03/T02/T01 in reverse-chronological order → `[M2 Graph-Layer Adapters] - 2026-04-19` (line 560) → `[M1 Reconciliation] - 2026-04-19` (line 1083) → `[Pre-pivot — archived, never released]` (line 2170). Layout mirrors M2 T09's post-close state. |

---

## 🔴 HIGH

### M3-T08-ISS-02 — Live e2e fails: T03 tiered_node wiring omits `output_schema=`, validator's strict JSON parse is probabilistic against Gemini's free-form output

**Severity:** HIGH
**Status:** ✅ RESOLVED (2026-04-20) — [T07a](../task_07a_planner_structured_output.md) landed the `output_schema=` forwarding; [T07b](../task_07b_planner_schema_simplify.md) followed up by stripping `PlannerStep` / `PlannerPlan` bounds that over-constrained Gemini's structured-output schema. Live e2e green: `1 passed in 11.67s` on 2026-04-20.
**Finding:** AC-3 requires `AIW_E2E=1 uv run pytest -m e2e` to be green once and recorded in the close-out CHANGELOG entry. A live run on 2026-04-20 against real Gemini (credential loaded from `.env` by `tests/conftest.py:16`) exited 1 with `RetryableSemantic('explorer_validator: output failed ExplorerReport validation')`. Replay of the structured-log records:

| Turn | Node | Outcome | Tokens (in/out) | Cost |
| --- | --- | --- | --- | --- |
| 1 | explorer | Gemini returned output | 76 / 1397 | $0.0035 |
| 1 | explorer_validator | rejected (schema parse fail) | — | — |
| 2 | explorer | Gemini returned output | 76 / 1265 | $0.0032 |
| 2 | explorer_validator | rejected (schema parse fail) | — | — |
| 3 | explorer | Gemini 503 ServiceUnavailableError | null / null | null |
| 4 | explorer | Gemini 503 ServiceUnavailableError | null / null | null |
| 5 | explorer | Gemini 503 ServiceUnavailableError | null / null | null |

The two semantic failures burned $0.0067 of real quota. The three 503s were free (request-admission failures, no inference). Retry budget exhausted after the third transient attempt per `RetryPolicy(max_transient_attempts=3, max_semantic_attempts=3)`.

**Root cause.** [planner.py:219,236](../../../../ai_workflows/workflows/planner.py#L219) calls `tiered_node(tier=..., prompt_fn=..., node_name=...)` without `output_schema=ExplorerReport` / `output_schema=PlannerPlan`. Since [tiered_node.py:113](../../../../ai_workflows/graph/tiered_node.py#L113) defaults `output_schema=None`, the `response_format` kwarg is never forwarded to LiteLLM at [tiered_node.py:343](../../../../ai_workflows/graph/tiered_node.py#L343), so Gemini returns free-form text — typically wrapped in markdown fences (```json\n…\n```) — and `validator_node`'s strict `schema.model_validate_json(text)` at [validator_node.py:89](../../../../ai_workflows/graph/validator_node.py#L89) rejects anything non-bare-JSON. The T03 spec ([task_03_planner_graph.md:128-130](../task_03_planner_graph.md#L128-L130)) wrote the `tiered_node(...)` calls without `output_schema`, relying instead on the retry-with-revision-hint loop to catch format drift. Hermetic T03 tests stub the adapter with pre-canned clean JSON, so the probabilistic-convergence assumption was never exercised against live Gemini. T07 — first task to exercise the live path — exposed the gap.

**Why it matters.** Even on a healthy Gemini day (no 503s), the semantic-retry budget is 3 attempts with no guarantee of convergence. The hermetic test suite cannot catch this class of failure because the adapter stub sidesteps the format layer entirely. Shipping M3 green without the fix would leave the live planner path in a probabilistic state — it works when Gemini happens to emit bare JSON, fails when it emits fenced JSON or prose wrapping, and the failure mode is "burn $0.006 per attempt then exit 1" rather than "converge cleanly in one shot."

**Action / Recommendation.** Land [T07a — Planner `tiered_node` Native Structured Output](../task_07a_planner_structured_output.md) as a **hard prerequisite** of this close-out. Scope is two kwarg additions + two test-assertion bumps + an optional `max_transient_attempts` bump from 3 to 5 (free — 503s cost no tokens, only ~2s latency per attempt). Re-run the live e2e afterward; on green, paste the result (duration, pass/fail, recorded `runs.total_cost_usd`) into the T08 CHANGELOG entry under a new `**AC-3 live-run evidence (YYYY-MM-DD):**` sub-block and re-audit to flip this issue to RESOLVED.

**Why not auto-apply in this audit.** Modifying `planner.py` is a T03 re-touch, out of scope for T08's "no code change beyond docs" spec. Creating a dedicated prereq task (T07a) keeps the audit trail clean, gives the structured-output fix its own scope / ACs / tests / CHANGELOG entry, and lets T08 close once its own ACs + the T07a-driven live-run evidence are both in place.

---

## 🟡 MEDIUM

None.

---

## 🟢 LOW

None.

---

## Additions beyond spec — audited and justified

### Addition: ordered exit-criteria verification table in README Outcome

The spec (§Deliverables → README.md → Outcome) mandates a bulleted summary. The Builder added a third section (`**Exit-criteria verification**`) that enumerates all 6 exit criteria with per-criterion evidence (path + `task_NN_issue.md` link). The M2 T09 close-out used the same pattern ([milestone_2_graph/README.md:87–94](../../milestone_2_graph/README.md)); mirroring it keeps reviewer muscle memory consistent — the T08 spec's opening line cites M2 T09 as the reference shape.

**Justified:** mirrors the M2 T09 precedent that the T08 spec body explicitly points to.

### Addition: green-gate snapshot as a table (not a bulleted list)

The spec's Outcome bullet list says `Green-gate snapshot: uv run pytest …`. The Builder rendered it as a 4-row table so the `AIW_E2E=1 pytest tests/e2e/ --collect-only` gate can live in the same structure as the hermetic `pytest` / `lint-imports` / `ruff` gates. M2 T09 used the same table shape.

**Justified:** readability + precedent.

### Addition: `AIW_E2E=1 uv run pytest tests/e2e/ --collect-only` as a recorded gate

The spec lists only the unit + lint + ruff gates. The Builder added a fourth row capturing the collection-gate behaviour (the "gate flips from skip to run when `AIW_E2E=1`" invariant from T07 AC-1). This doesn't *replace* the AC-3 live run (that's still OPEN per M3-T08-ISS-01) — it captures a different gate: the conftest skip hook's reachability. Loss of that gate would mean the e2e suite is silently unreachable under `workflow_dispatch`.

**Justified:** non-overlapping coverage with AC-3, low-cost to include, catches a specific regression that the hermetic pytest run cannot.

---

## Gate summary

| Gate | Status | Notes |
| --- | --- | --- |
| `uv run pytest` (hermetic, `AIW_E2E` unset) | ✅ 295 passed, 1 skipped, 2 warnings | `yoyo` datetime deprecation is pre-existing, carried since M1. |
| `AIW_E2E=1 uv run pytest tests/e2e/ --collect-only` | ✅ 1 test collected | Collection gate flips correctly. |
| `AIW_E2E=1 uv run pytest -m e2e` (full live run) | ⚠️ NOT RUN | `GEMINI_API_KEY` unset in Builder env. See M3-T08-ISS-01. |
| `uv run lint-imports` | ✅ 3 / 3 kept | 22 files, 32 deps. Four-layer contract preserved. |
| `uv run ruff check` | ✅ clean | No lint findings in this task's diff. |
| M3 README Status line | ✅ | Line 3 — `✅ Complete (2026-04-20)`. |
| `roadmap.md` M3 row | ✅ | Line 16 — `✅ complete (2026-04-20)`. |
| CHANGELOG `[Unreleased]` | ✅ | Holds only the Architecture pivot entry. |
| CHANGELOG `[M3 First Workflow — planner] - 2026-04-20` | ✅ | T08 close-out at top; T07/T06/T05/T04/T03/T02/T01 in reverse-chron order. |

---

## Issue log — cross-task follow-up

| ID | Severity | Owner / next touch point | Status |
| --- | --- | --- | --- |
| M3-T08-ISS-01 | MEDIUM | **User** — run `AIW_E2E=1 GEMINI_API_KEY=<real> uv run pytest -m e2e -v` (Path A) OR trigger the `workflow_dispatch` `e2e` job (Path B). Paste result into T08 CHANGELOG entry. | OPEN (USER INPUT REQUIRED) |

---

## Deferred to nice_to_have

None new. The M3 close-out inherits two deferrals from prior tasks:

- [nice_to_have.md §9](../../../nice_to_have.md) — `aiw cost-report <run_id>` per-run cost breakdown CLI. Deferred by M3 T06 reframe (2026-04-20); three adoption triggers recorded. The close-out Outcome section links to this.
- The M4 `get_cost_report` MCP tool inherits the same reframe and will be re-specced at M4 start — cited in [architecture.md §4.4](../../../architecture.md) line 102.

Neither is forwarded to a new target task (they are parking-lot items, not task work).

---

## Propagation status

None needed. T08 raises exactly one OPEN issue (M3-T08-ISS-01), and its owner is the **user**, not a downstream task. No `## Carry-over from prior audits` section added to any task file — the fix is the user pasting a live-run result into the T08 CHANGELOG entry already in place, not new Builder work.

If the user chooses to defer Path A / Path B to the next time the e2e suite runs on CI (i.e. just let the next `workflow_dispatch` on main serve as the "green once" proof), that's also a valid close-out path — the audit would then carry M3-T08-ISS-01 OPEN indefinitely until the first successful `workflow_dispatch` run is recorded. Surface the choice explicitly to the user rather than silently letting it age.
