# Task 06 — Milestone Close-out — Audit Issues

**Source task:** [../task_06_milestone_closeout.md](../task_06_milestone_closeout.md)
**Audited on:** 2026-04-21
**Audit scope:** T06 milestone close-out sweep — [CHANGELOG.md](../../../../CHANGELOG.md) promotion + T06 entry; [design_docs/phases/milestone_7_evals/README.md](../README.md) Status flip + Outcome section; [design_docs/roadmap.md](../../../roadmap.md) M7 row flip; root [README.md](../../../../README.md) status-table + narrative + What-runs-today + Next pointer; [design_docs/architecture.md](../../../architecture.md) §3 + §4.5 evals-layer documentation (M7-T01-ISS-01 carry-over); [tests/cli/test_eval_commands.py](../../../../tests/cli/test_eval_commands.py) snapshot+restore fixture (M7-T05-ISS-01 carry-over); [design_docs/nice_to_have.md](../../../nice_to_have.md) §13 + §14 (M7-T05-ISS-06 + live-mode tolerance deferrals); [design_docs/phases/milestone_7_evals/task_05_ci_hookup_seed_fixtures.md](../task_05_ci_hookup_seed_fixtures.md) in-place spec corrections (M7-T05-ISS-04 carry-over); full gate (`uv run pytest && uv run lint-imports && uv run ruff check`); every M7 sibling issue file (task_01..05) for propagation status; [CLAUDE.md](../../../../CLAUDE.md) close-out conventions; M6 T09 CHANGELOG entry as the "mirror" pattern per T06 spec.
**Status:** ✅ PASS — no OPEN issues. (Cycle 1 raised one MEDIUM — M7-T06-ISS-01, commit-sha baseline missing from CHANGELOG T06 entry — resolved in the Cycle 2 implement phase; audit file updated in place rather than re-written, per CLAUDE.md.)

## Design-drift check

Docs-only close-out plus one test-fixture edit. No new dependencies, no new modules, no new LLM calls, no checkpoint / retry / observability changes. The one code change — `tests/cli/test_eval_commands.py` `_reensure_planner_registered` fixture rewrite to snapshot+restore the workflow registry — is in-scope: the T06 spec's "Out of scope: Any code change" applies to *new findings*, and this change satisfies propagated carry-over **M7-T05-ISS-01 (MEDIUM)** with the audit-recommended "snapshot + restore as a whole" pattern. No drive-by.

Architecture.md §3 diagram + §4.5 Evals-layer subsection are the load-bearing **M7-T01-ISS-01 (LOW)** carry-over; §3 rules cover all six layer edges (graph→evals forbidden, workflows→evals allowed, evals→primitives/graph/workflows allowed, evals→surfaces forbidden) and explicitly cite the four-contract + AST-test enforcement shape. Consistent with `pyproject.toml` (`primitives cannot import graph/workflows/surfaces`, `graph cannot import workflows or surfaces`, `workflows cannot import surfaces`, `evals cannot import surfaces` — all four `KEPT` per `uv run lint-imports`).

No KDR violations. KDR-004 (prompting is a contract) is the milestone's whole reason for existing and is honoured by the deterministic `eval-replay` CI gate; KDR-010 (bare-typed schemas) applies to `EvalCase`/`EvalSuite`/`EvalTolerance` and was audited at T01. KDR-003 (no Anthropic API) and KDR-009 (SqliteSaver) were unaffected — close-out touched neither.

## AC grading

| AC | Grade | Evidence |
| --- | --- | --- |
| **1 — Every exit criterion in the milestone README has a concrete verification** (paths / test names / issue-file links) | ✅ PASS | Milestone README Outcome section lists per-task evidence: task-spec links, audited issue-file links, test-file links (`tests/workflows/test_dispatch_capture_opt_in.py`, `tests/evals/test_seed_fixtures_deterministic.py`, `tests/evals/test_layer_contract.py`), fixture links (three seed fixtures), CI YAML link. All five milestone exit criteria are addressed with concrete file references. |
| **2 — `uv run pytest && uv run lint-imports && uv run ruff check` green; 4 contracts kept** | ✅ PASS | pytest → **538 passed, 4 skipped, 2 warnings** (warnings are the pre-existing yoyo deprecation noise from sqlite3 datetime adapters, not introduced here). lint-imports → **4 kept, 0 broken** (`primitives cannot import graph/workflows/surfaces`, `graph cannot import workflows or surfaces`, `workflows cannot import surfaces`, `evals cannot import surfaces`). ruff → **All checks passed**. |
| **3 — Close-out CHANGELOG entry records live-replay runs for both `planner` and `slice_refactor` (commit sha + pass/fail counts)** | ✅ PASS (post Cycle 2 fix) | Pass/fail counts recorded: `planner` → 0/2 with the phrasing-drift example; `slice_refactor` → 0/1 with the diff-field drift note. Commit-sha baseline added at Cycle 2: **`1d85007` (m7 kickoff: "task for milestone 7 created") plus the uncommitted M7 T01–T06 working tree** — includes a per-file breakdown of what the uncommitted tree covers (`ai_workflows/evals/`, `.github/workflows/ci.yml`, `evals/` fixtures, `ai_workflows/cli.py`, `ai_workflows/graph/tiered_node.py`) and the reproduce-requires-combined-state note. Mirrors the M6 T09 shape. Tolerance-decision deferral to `nice_to_have.md §14` also recorded. |
| **4 — Close-out CHANGELOG entry records capture-mechanism choice locked at T04** | ✅ PASS | Explicit: "`aiw eval capture --run-id <id> --dataset <name>` uses **checkpoint-channel reconstruction** — reads `AsyncSqliteSaver.aget(cfg).channel_values` on a completed run... selected over the fallback re-run-with-`AIW_CAPTURE_EVALS=<dataset>` approach." The rationale ("free + deterministic + offline") and the documented fallback path are both present. |
| **5 — M7 milestone README + roadmap reflect `✅ Complete (2026-04-21)`** | ✅ PASS | Milestone README line 3: `**Status:** ✅ Complete (2026-04-21).` Roadmap line 20: `\| M7 \| Eval harness \| ... \| ✅ complete (2026-04-21) \|`. |
| **6 — CHANGELOG has a dated `## [M7 Eval Harness] - 2026-04-21` section; `[Unreleased]` preserved at top** | ✅ PASS | `CHANGELOG.md:8-10` — `## [Unreleased]` (empty) then `## [M7 Eval Harness] - 2026-04-21` then the T06 `### Changed` entry at the top of the new dated section, followed by the promoted T01–T05 entries (verified via `^## \[` grep: `[Unreleased]` at line 8, `[M7 Eval Harness]` at line 10, `[M6 Slice Refactor]` at line 585). |
| **7 — Root README updated: status table, post-M7 narrative, What-runs-today, Next → M8** | ✅ PASS | Status table (line 19): `\| **M7 — Eval harness** \| Complete (2026-04-21) \|`. Narrative (line 22): appended ~500-word M7 paragraph covering evals package, `CaptureCallback` opt-in pattern, `EvalRunner` deterministic+live modes, `aiw eval capture/run` CLI, `eval-replay` CI, subgraph-resolution retrofit. What-runs-today section already used `(post-M7)` heading. New bullets added: Evals-layer bullet (line 33), Eval-fixture-tree bullet (line 34). CLI bullet (line 27) now reads "five working commands" with `aiw eval` described. Import-linter reference (line 55) reads "Four contracts since M7". Architecture reference (line 55) cites `§3 / §4.5`. Project-layout block updated to include `evals/` package + committed `evals/` fixture tree. Next pointer (line 132): `M8 — [Ollama infrastructure]`. Gate snapshot (line 116): `538 passed, 4 skipped... 4 contracts kept, ruff clean`. |
| **8 — All M7 task issue files audited for propagation holes** | ✅ PASS | Verified each M7 issue file: task_01 → ✅ PASS, task_02 → ✅ PASS (Cycle 2 re-implement), task_03 → ✅ PASS (with 2026-04-21 addendum noting M7-T03-ISS-02 sub-graph resolution retrofit landed in T05), task_04 → ✅ PASS, task_05 → ✅ PASS. Single `DEFERRED` entry across all issue files (M7-T01-ISS-01 in task_01_issue.md:110) is propagated to T06 task-file carry-over and ticked RESOLVED. T05's three carry-overs (ISS-01/04/06) are also propagated to T06 task file and ticked (ISS-01 RESOLVED via fixture edit, ISS-04 RESOLVED via in-place spec amendment, ISS-06 DEFERRED to `nice_to_have.md §13`). No propagation holes. |

## 🟡 MEDIUM

### M7-T06-ISS-01 — CHANGELOG T06 entry missing the commit-sha baseline required by AC-3 — ✅ RESOLVED (Cycle 2, 2026-04-21)

**File:** [CHANGELOG.md:10-110](../../../../CHANGELOG.md) (the new `### Changed — M7 Task 06: Milestone Close-out (2026-04-21)` entry under `## [M7 Eval Harness] - 2026-04-21`).

**Finding:** T06 spec AC-3 prescribes "Close-out CHANGELOG entry records the live-replay runs for both `planner` and `slice_refactor` at close-out time (**commit sha** + pass/fail counts)". The entry records pass/fail counts and tolerance-decision rationale clearly, but it omits the commit-sha baseline. The M6 T09 entry the spec points at as the "shape to mirror" recorded the baseline as:

> Commit baseline: `e2af81f` (m6 kickoff) + uncommitted M6 T01–T08 working tree.

The analogous T06 line would read:

> Commit baseline: `1d85007` (m7 kickoff: "task for milestone 7 created") + uncommitted M7 T01–T06 working tree.

Without the baseline, a future reader cannot reproduce the 0/2 + 0/1 live-replay failure pattern against the exact code state that produced it — specifically whether the failures are sensitive to the committed fixtures, the adapter code, or the uncommitted T06 tree.

**Why MEDIUM, not LOW:** AC-3 is an explicit AC, not cosmetic. It is partially met (pass/fail counts present) but the sha half is missing. CLAUDE.md severity rubric: "MEDIUM — deliverable partial, convention skipped". Upgrading to MEDIUM over LOW because the mirror-pattern precedent (M6 T09) was called out in-spec and the omission is mechanical (no design judgement; just a missing line).

**Action / Recommendation:** append a single paragraph to the T06 entry under the existing `**Close-out-time live replay baseline (2026-04-21):**` heading. Proposed text (keeps the audit trail):

```markdown
**Commit baseline:** `1d85007` (m7 kickoff: "task for milestone 7 created")
+ uncommitted M7 T01–T06 working tree. The uncommitted tree covers every
file under `ai_workflows/evals/`, the `eval-replay` job in
`.github/workflows/ci.yml`, the three seed fixtures under `evals/`, the
CLI `aiw eval` subcommands in `ai_workflows/cli.py`, and the capture
hook in `ai_workflows/graph/tiered_node.py`.
```

No gate rerun needed — this is pure doc maintenance. One-line CHANGELOG edit + issue status flip to RESOLVED.

## 🔴 HIGH

None.

## 🟢 LOW

None.

## Additions beyond spec — audited and justified

- **Fixture-edit code change in `tests/cli/test_eval_commands.py`.** T06 spec explicitly states "Out of scope: Any code change." This edit is nevertheless in-scope because it satisfies propagated carry-over **M7-T05-ISS-01 (MEDIUM)** listed under `## Carry-over from prior audits` in the T06 task file. The carry-over section is part of the task file per CLAUDE.md Builder conventions ("Carry-over section at bottom of task file = extra ACs"). The fix chose the audit-recommended "snapshot as a whole" shape — `dict(workflows._REGISTRY)` → `_reset_for_tests` + planner re-register → `yield` → `_reset_for_tests` + restore snapshot — which is future-proof against later workflow additions. Gate confirms no regression (538 pytest rows, 4 contracts).
- **New `design_docs/nice_to_have.md` §13 + §14.** T06 spec anticipates this explicitly: carry-over M7-T05-ISS-06 recommends "record the trigger in nice_to_have.md if deferring" and the live-mode tolerance discussion under T05's Outcome section referenced §14 before this audit cycle. Both entries follow the existing nice_to_have.md entry template (Role / Replaces / Adds / Trigger / Why not now / Related history) and cite the M7 T06 close-out date. Not beyond-spec; in-spec per the propagated carry-overs.
- **architecture.md §3 rewrite + new §4.5 subsection.** Carry-over M7-T01-ISS-01 (LOW) explicitly asked for "Extend `architecture.md` §3 layer diagram to show `evals` as a peer of `graph` ... and add a `§4.5 Evals layer` subsection summarising the package's role." Landed as specified; the §3 rewrite covers all six layer edges (not just graph↔evals) to keep the contract read coherently.

## Gate summary

| Gate | Result |
| --- | --- |
| `uv run pytest` | **538 passed, 4 skipped**, 2 warnings (pre-existing yoyo sqlite3 datetime-adapter deprecation; not M7 T06 noise) |
| `uv run lint-imports` | **4 contracts kept, 0 broken** |
| `uv run ruff check` | **All checks passed** |

## Issue log — cross-task follow-up

| ID | Severity | Owner / next touch point |
| --- | --- | --- |
| M7-T06-ISS-01 | 🟡 MEDIUM → ✅ RESOLVED | Fixed in M7 T06 Cycle 2 (2026-04-21) — added a new **Commit baseline** paragraph (citing `1d85007` + the uncommitted M7 T01–T06 tree) under the existing **Close-out-time live replay baseline (2026-04-21)** heading in the CHANGELOG T06 entry. Gate re-run after edit: pytest 538 passed / 4 skipped, lint-imports 4 kept, ruff clean. No forward-deferral. |

## Deferred to nice_to_have

None. The live-mode tolerance refinement and the msgpack-registry warnings were already deferred by T05's audit + close-out carry-overs to `nice_to_have.md §13` + `§14` (landed at this T06 implement phase) — not net-new deferrals surfaced by this audit.

## Propagation status

- **M7-T01-ISS-01 (LOW)** — closed at this T06. Architecture.md §3 + §4.5 rewrite landed. Carry-over ticked in task_06_milestone_closeout.md.
- **M7-T03-ISS-02 (LOW)** — already noted as "landed in T05's working tree" in task_03_issue.md's status addendum. No T06 action; no open carry-over.
- **M7-T05-ISS-01 (MEDIUM)** — closed at this T06. `tests/cli/test_eval_commands.py` snapshot+restore fixture landed; T04 band-aid in `tests/evals/test_seed_fixtures_deterministic.py` retained as defence-in-depth. Carry-over ticked in task_06_milestone_closeout.md.
- **M7-T05-ISS-04 (LOW)** — closed at this T06. task_05_ci_hookup_seed_fixtures.md amended in place. Carry-over ticked.
- **M7-T05-ISS-06 (LOW)** — deferred to nice_to_have.md §13. Carry-over ticked.
- **M7-T06-ISS-01 (MEDIUM, new)** — resolved in-cycle at Cycle 2 implement phase; no forward-deferral owner needed.

No carry-overs open against future tasks after this milestone closes.
