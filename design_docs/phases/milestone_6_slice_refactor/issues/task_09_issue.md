# Task 09 — Milestone Close-out — Audit Issues

**Source task:** [../task_09_milestone_closeout.md](../task_09_milestone_closeout.md)
**Audited on:** 2026-04-20
**Audit scope:** full T09 delivery — milestone README status flip +
Outcome section + carry-over tick; roadmap.md row flip; root README.md
narrative + status table + What-runs-today + Next pointer; CHANGELOG.md
dated section + T09 close-out entry with live `AIW_E2E=1` capture and
manual `aiw-mcp` two-gate round-trip capture; propagation hygiene across
every M6 task issue file; full-suite + lint + ruff re-runs.
**Status:** ✅ PASS — 0 OPEN issues; all 8 ACs met; 0 design drift.
Propagation hole in [task_02_issue.md](task_02_issue.md)
(M6-T02-ISS-01 still marked DEFERRED despite T03 resolution) surfaced
and fixed in-audit per CLAUDE.md issue-file maintenance rules.

## Design-drift check

T09 is doc-only — no `ai_workflows/**/*.py` touched, no new dependency,
no schema change. The drift axes collapse to "do the narrative updates
still truthfully describe the architecture?"

| Axis | Verdict | Evidence |
| --- | --- | --- |
| New dependency | ✅ None | `pyproject.toml` unchanged. |
| New module or layer | ✅ None | No files under `ai_workflows/`. |
| LLM call added | ✅ N/A | Docs only. |
| KDR-003 (no Anthropic API) | ✅ Language preserved | Root README + milestone README reiterate "OAuth-only via `claude` CLI subprocess" and "narrow regex catches only `import anthropic` / `ANTHROPIC_API_KEY`". |
| KDR-004 (validator after every LLM node) | ✅ Language preserved | Root README's `slice_refactor` bullet explicitly names `_slice_worker_validator` as the per-branch KDR-004 pairing. |
| KDR-006 (3-bucket retry via `RetryingEdge`) | ✅ Language preserved | No claim of bespoke retry logic. |
| KDR-008 (FastMCP surface) | ✅ Language preserved | `aiw-mcp` bullet unchanged in structure. |
| KDR-009 (SqliteSaver) | ✅ Language preserved | `durability="sync"` through `AsyncSqliteSaver` called out verbatim. |
| Architecture §8.2 (double-failure hard-stop) | ✅ Covered | Root README + milestone Outcome + CHANGELOG all cite the `len(slice_failures) >= 2` + `runs.status = "aborted"` terminal. |
| Architecture §8.3 (strict-review no-timeout) | ✅ Covered | "First `strict_review=True` use in the codebase; no-timeout semantics verified" — milestone Outcome + root README. |
| Architecture §8.6 (per-tier semaphore) | ✅ Covered | Root README + milestone Outcome cite `_build_semaphores(tier_registry)` + `config["configurable"]["semaphores"]` + per-tier-per-run-process-local scoping. |
| Architecture §8.7 (in-flight cancel) | ✅ Covered | Root README CLI bullet names `_ACTIVE_RUNS` + `task.cancel()` + `durability="sync"`. |
| Observability (StructuredLogger) | ✅ No change | T09 did not add logging. |
| `nice_to_have.md` scope creep | ✅ None | No new primitives, MCP tools, workflows, or dependency-adoption language. |
| Docstring + module header discipline | ✅ N/A | No module touched. |
| CI gate impact | ✅ No regression | 475 passed + 3 skipped under `uv run pytest`; 3/3 contracts kept; ruff clean. |
| Layer discipline | ✅ Kept | No code change. |

No drift found. No document claims an architectural behaviour that is
not actually implemented in the M6 tree.

## Acceptance criteria grading

| # | AC | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Every exit criterion in milestone README has a concrete verification (paths / test names / issue-file links) | ✅ | `README.md` Outcome section walks every task 01–08 with clickable task-file + test-file + issue-file links; Green-gate snapshot line pins the numeric gate result. Cross-referenced each exit criterion (§1–7 of milestone README) against the Outcome bullets — every one has evidence. |
| 2 | `uv run pytest && uv run lint-imports && uv run ruff check` green | ✅ | Re-run during this audit: **475 passed, 3 skipped, 2 warnings** (the three `AIW_E2E=1`-gated e2e smokes skip cleanly); `Contracts: 3 kept, 0 broken`; `All checks passed!`. |
| 3 | `AIW_E2E=1 uv run pytest tests/e2e/test_slice_refactor_smoke.py` recorded in the close-out CHANGELOG entry | ✅ | CHANGELOG §"Live `AIW_E2E=1` `slice_refactor` smoke captured" records command, commit baseline `e2af81f` + uncommitted M6 T01–T08 tree, goal string, wall-clock (129.97s / 2m 10s), run_id `e2e-slice-40b12463`, per-call timing breakdown (explorer 58.3s, synth 9.7s, workers 24.4/43.0/60.7s), aggregate `total_cost_usd=0.0`, approved slice count = 3. |
| 4 | Manual `aiw-mcp` two-gate round-trip recorded (command + observed payload) | ✅ | CHANGELOG §"Manual `aiw-mcp` two-gate round-trip captured" lists the 4 MCP calls (`run_workflow` + 2× `resume_run` + `list_runs`) for `run_id="manual-m6-closeout"`, each with the observed JSON response payload; `started_at`/`finished_at` timestamps stamped; 3-step plan titles verbatim; wall-clock ~2m 13s. |
| 5 | README (milestone) and roadmap reflect ✅ status | ✅ | `milestone_6_slice_refactor/README.md:3` → `**Status:** ✅ Complete (2026-04-20)`; `roadmap.md:19` → `✅ complete (2026-04-20)`. |
| 6 | M4-T05 carry-over item in milestone README flipped to `✅ RESOLVED (landed in task 02)` | ✅ | `milestone_6_slice_refactor/README.md:71` → `- [x] **M4 T05 — in-flight cancel_run (MEDIUM, owner: task 02).** ✅ RESOLVED (landed in task 02)`; links back to T02 deliverables and retains the original description for audit trail. |
| 7 | CHANGELOG has a dated `## [M6 Slice Refactor] - 2026-04-20` section; `[Unreleased]` preserved at the top | ✅ | `CHANGELOG.md:8-10` → empty `## [Unreleased]` header followed by `## [M6 Slice Refactor] - 2026-04-20`; T09 close-out entry is the first block under the dated section; M6 T01–T08 entries promoted into the dated section (verified by scanning for each task's Added header). |
| 8 | Root README updated: status table, post-M6 narrative, What-runs-today, Next → M7 | ✅ | `README.md:17-18` → M6 row added; `README.md:20` → narrative paragraph extended with M6 summary covering fan-out + strict-review + hard-stop + semaphore + `cancel_run`; `README.md:22` → heading `post-M5` → `post-M6`; new `slice_refactor` workflow bullet at line 27 covers every architectural contract; `test_slice_refactor_smoke.py` + `test_slice_refactor_e2e.py` bullet added to e2e tests section; gate snapshot updated `366 → 475 passed, 2 → 3 skipped`; `Next` pointer at `README.md:125` retargeted to M7 eval harness. |

## 🔴 HIGH

None.

## 🟡 MEDIUM

None.

## 🟢 LOW

None OPEN.

### M6-T09-OBS-01 — T02 originating issue file was not flipped when T03 resolved M6-T02-ISS-01 — ✅ RESOLVED in-audit

**Observation:** [task_02_issue.md](task_02_issue.md) carried
`M6-T02-ISS-01` as `DEFERRED (owner: M6 T03)` in both the issue-detail
section and the Issue-log table. T03's Builder landed the refactor
(`slice_worker` split + `slice_worker_validator` + `retrying_edge`) and
T03's Auditor ticked the carry-over in `task_03_issue.md` — but the
originating `task_02_issue.md` was never updated to reflect the
resolution. This violates CLAUDE.md's Forward-deferral propagation
rule: "When the target Builder finishes, they tick the carry-over; on
re-audit, flip `DEFERRED → RESOLVED` in the originating issue file."

**Why this matters now:** T09's close-out scope is "every exit
criterion verified"; an orphaned `DEFERRED` in an originating issue
file would force a future reader to chase two files to learn the
actual state. By contrast, `task_04_issue.md`'s `M6-T04-ISS-01` was
correctly flipped at T07 Builder — the asymmetry is noise.

**Resolution applied during this audit (doc-maintenance only, spirit
of CLAUDE.md "Update the existing issue file on re-audit — tick items
off, flip severities, mark RESOLVED as work lands"):**

- [task_02_issue.md](task_02_issue.md) §"M6-T02-ISS-01" status line flipped
  `DEFERRED (owner: M6 T03)` → `✅ RESOLVED in M6 T03 Builder (2026-04-20)`
  with a citation of the T03 issue-file evidence.
- Issue-log table row flipped `DEFERRED → ✅ RESOLVED (M6 T03 Builder, 2026-04-20)`
  with a one-line summary of the refactor.
- Propagation-status footer updated to record the T09 close-out flip.
- Milestone [README.md](../README.md) §"Issues" updated to list **three**
  resolved carry-overs (was "two" — `M6-T02-ISS-01` previously omitted).

No code change, no test change. Cost < 3 lines of edits per file.

## Observational notes

### OBS-01 — Dispatch-helper return shape surfaces both `PlannerPlan` and `applied_artifact_count` in the manual round-trip

**Observation:** The manual `aiw-mcp` Call 3 response in the CHANGELOG
(strict-review gate approval) returns `plan: {…PlannerPlan…}` alongside
`total_cost_usd: 0` and `status: "completed"`. Reading
[`_dispatch.run_workflow`](../../../../ai_workflows/workflows/_dispatch.py)
confirms the return shape reads `state.get("plan")` and
`state.get("applied_artifact_count")` independently — `slice_refactor`'s
terminal state legitimately writes both (the planner sub-graph wrote
`plan`, the `apply` node wrote `applied_artifact_count`). Not a bug —
the MCP response shape surfaces whichever completion signals the
workflow wrote, which for `slice_refactor` happens to be both. The
CHANGELOG entry calls this out as expected behaviour.

**Resolution:** No action. Useful as a diagnostic for future readers
comparing `planner`-only vs `slice_refactor` response shapes.

### OBS-02 — Architecture §11 cross-reference unchanged from T08

**Observation:** T08's audit (OBS-01) flagged that `architecture.md §11`
is "What this document is not", not "Testing strategy". T09 is
doc-only scope — the architecture document is not in T09's deliverable
list, so this observation carries forward unchanged. Flag for a future
doc-sweep KDR or nice_to_have item if desired.

**Resolution:** No action at T09. Out of T09 scope by spec.

## Additions beyond spec — audited and justified

| Addition | Justification |
| --- | --- |
| Milestone README's Outcome section breaks each task's evidence into named keywords (`_slice_list_normalize`, `_ACTIVE_RUNS`, `_route_before_aggregate`, etc.) rather than narrative prose | Mirrors the M5 T07 close-out style; future readers auditing the M6 delivery can ctrl-F to the exact symbol. Zero extra scope — the spec requires an Outcome section "summarising" each task; level-of-detail is a style choice. |
| Root README's `slice_refactor` bullet inlines the full tier-registry and architecture-section citations (§8.2 + §8.6) | The spec says "`slice_refactor` workflow + strict-review gate + in-flight `cancel_run` all documented" — no prescribed depth. Citing the architecture sections keeps the root README consistent with the `planner` bullet pattern above it. |
| CHANGELOG §"Live `AIW_E2E=1` …" records per-call timing breakdown (explorer 58.3s, synth 9.7s, workers 24.4/43.0/60.7s) | Spec asks for "commit sha + observed `runs.total_cost_usd` range + the goal string used + approved slice count". Per-call timing is a small bonus that pins the `max_concurrency=1` serialised-fan-out behaviour against a concrete wall-clock — useful for future regression detection if the semaphore wiring changes. |
| In-audit flip of `task_02_issue.md` propagation (see M6-T09-OBS-01) | Not in T09 spec, but is mandated by CLAUDE.md's Auditor conventions ("Update the existing issue file on re-audit") and by the forward-deferral propagation rule. Closing a known propagation hole in-audit is strictly inside the auditor's hat. |

All additions are doc-only; none touch `ai_workflows/`.

## Gate summary

| Gate | Verdict | Evidence |
| --- | --- | --- |
| `uv run pytest` | ✅ 475 passed + 3 skipped | Three e2e smokes (`test_planner_smoke.py`, `test_tier_override_smoke.py`, `test_slice_refactor_smoke.py`) skip cleanly without `AIW_E2E=1`. |
| `uv run lint-imports` | ✅ 3/3 contracts kept | `primitives → graph → workflows → surfaces`. |
| `uv run ruff check` | ✅ All checks passed | Clean. |
| `## [Unreleased]` preserved | ✅ Present (empty) | Top-of-file header at `CHANGELOG.md:8` with no entries; dated `## [M6 Slice Refactor] - 2026-04-20` section follows at `CHANGELOG.md:10`. |
| M4-T05 carry-over flipped | ✅ `✅ RESOLVED (landed in task 02)` | Milestone README line 71. |
| AIW_E2E capture present | ✅ Full capture | CHANGELOG §"Live `AIW_E2E=1` `slice_refactor` smoke captured" — 7 bullet points with run_id + wall-clock + per-call timing. |
| Manual MCP round-trip capture present | ✅ 4 calls captured | CHANGELOG §"Manual `aiw-mcp` two-gate round-trip captured" — Call 1–4 with observed JSON payloads. |
| Root README status table | ✅ M6 → Complete (2026-04-20); M7–M9 → Planned | `README.md:17-18`. |
| Root README Next pointer | ✅ → M7 eval harness | `README.md:125` (line after the existing "M6 — …" text replaced with "M7 — eval harness" text). |

## Issue log — cross-task follow-up

| ID | Severity | Owner / next touch point | Status |
| --- | --- | --- | --- |
| M6-T09-OBS-01 | 🟢 OBSERVATION | — (closed in-audit) | ✅ RESOLVED (2026-04-20, this audit) |

No cross-task issues surfaced that require forward propagation. The
one propagation hole this audit discovered (`M6-T02-ISS-01`) is closed
in-audit because it is documentation-maintenance work, not Builder
work.

## Deferred to nice_to_have

None.

## Propagation status

- No forward-deferrals introduced by this audit.
- Backwards-fix applied to [task_02_issue.md](task_02_issue.md) —
  flipped `M6-T02-ISS-01` from `DEFERRED → ✅ RESOLVED (M6 T03 Builder,
  2026-04-20)` in three places (detail status line, issue-log row,
  propagation-status footer). Milestone README §"Issues" updated to
  cite three resolved carry-overs (was two).
- No carry-over ticks required on M7 task spec files.

## Milestone close-out verdict

✅ **M6 `slice_refactor` — CLOSED GREEN (2026-04-20).**

All nine tasks landed CLEAN. Every exit criterion from the milestone
README has on-file evidence (test names, code paths, issue-file links).
Every KDR the milestone depends on (KDR-003, KDR-004, KDR-006, KDR-008,
KDR-009) is upheld. Every architecture section the milestone exercises
(§4.3 canonical DAG, §8.2 double-failure hard-stop, §8.3 strict-review
no-timeout, §8.6 per-tier semaphore, §8.7 in-flight cancel) is live
under real providers per the `AIW_E2E=1` capture. The M4-T05
in-flight-`cancel_run` carry-over is resolved. The `[Unreleased]`
section is clean for M7.

Ready for M7 — eval harness.
