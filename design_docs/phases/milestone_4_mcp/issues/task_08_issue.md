# Task 08 — Milestone Close-out — Audit Issues

**Source task:** [../task_08_milestone_closeout.md](../task_08_milestone_closeout.md)
**Audited on:** 2026-04-20
**Audit scope:** `design_docs/phases/milestone_4_mcp/README.md` (milestone), `design_docs/roadmap.md`, root `README.md`, `CHANGELOG.md`, full gate run (`uv run pytest`, `uv run lint-imports`, `uv run ruff check`). Cross-referenced against [architecture.md §3 / §4.4 / §8.7](../../../architecture.md), KDR-002, KDR-008, the T01–T07 issue files in this directory, and [M3 T08 close-out](../../milestone_3_first_workflow/task_08_milestone_closeout.md) as the shape-mirror.
**Status:** 🚧 USER INPUT REQUIRED — AC-3 (manual `claude mcp add` verification) cannot be completed autonomously. One OPEN issue (M4-T08-ISS-01).

---

## Design-drift check (architecture.md + KDRs)

| Concern | Finding |
| --- | --- |
| New dependency added? | **None.** T08 is docs-only. `pyproject.toml` unchanged. |
| New module or layer? | **None.** No code touched. Lint-imports 3/3 KEPT. |
| LLM call added? | **None.** No test, no module, no runtime code changed. |
| Checkpoint / resume logic? | **None.** |
| Retry logic? | **None.** |
| Observability? | **None.** |
| KDR-002 MCP portable surface | Root README's post-M4 narrative + `## What runs today` section call out the shared dispatch helper ([`ai_workflows/workflows/_dispatch.py`](../../../../ai_workflows/workflows/_dispatch.py)) as the KDR-002 promise made concrete. ✓ |
| KDR-003 Anthropic boundary | Not touched by docs. ✓ |
| KDR-008 FastMCP | Milestone README + root README explicitly name FastMCP as the MCP substrate. ✓ |
| architecture.md §4.4 four-tool surface | Milestone README Outcome section + root README enumerate all four tools (`run_workflow`, `resume_run`, `list_runs`, `cancel_run`) and explicitly note `get_cost_report` was dropped at M4 kickoff. ✓ |
| architecture.md §8.7 M4/M6 cancellation split | Root README `## What runs today` bullet for `aiw-mcp` cites §8.7 and explicitly flags "in-flight task abort lands at M6". ✓ |

**Verdict:** no drift. Docs-only close-out.

---

## Acceptance-criteria grading

| # | AC | Grade | Evidence |
| --- | --- | --- | --- |
| 1 | Every exit criterion has concrete verification | ✅ | Milestone README lines 60-68 ship an exit-criteria verification table — every criterion 1–5 maps to a file path / test name / issue-file link. Criterion 3 cross-refers to the T08 CHANGELOG entry for the manual verification, which is where AC-3 below is tracked. |
| 2 | `uv run pytest && uv run lint-imports && uv run ruff check` green on a fresh clone | ✅ | Auditor re-ran locally: **332 passed, 1 skipped** (M3 e2e, gated by `AIW_E2E=1`), **3 contracts kept**, **ruff clean**. Gate snapshot pinned in the T08 CHANGELOG entry. |
| 3 | Manual `claude mcp add` verification recorded in the close-out CHANGELOG entry (command + output) | 🚧 | **BLOCKED pending user action.** The T08 CHANGELOG entry at [CHANGELOG.md:47-61](../../../../CHANGELOG.md) contains a **PENDING USER ACTION** checklist with the three commands the user must run (`claude mcp add …`, then a fresh Claude Code session invoking `run_workflow` + `resume_run`) and paste the raw payloads back into the entry. The Builder cannot run `claude mcp add` or spawn a fresh Claude Code session autonomously. Tracked as M4-T08-ISS-01 below. |
| 4 | README (milestone) and roadmap reflect ✅ status | ✅ | [milestone README line 3](../README.md#L3): `**Status:** ✅ Complete (2026-04-20).` [roadmap.md line 17](../../../roadmap.md#L17): `\| M4 \| MCP server (FastMCP) \| … \| ✅ complete (2026-04-20) \|`. |
| 5 | CHANGELOG has a dated `## [M4 MCP Server] - YYYY-MM-DD` section; `[Unreleased]` preserved at the top | ✅ | [CHANGELOG.md:8-10](../../../../CHANGELOG.md): `## [Unreleased]` (empty, preserved at top) immediately followed by `## [M4 MCP Server] - 2026-04-20`. `grep '^## \['` across the file shows the expected top-down order: `[Unreleased]` → `[M4 MCP Server]` → `[M3 First Workflow — planner]` → `[M2 Graph-Layer Adapters]` → `[M1 Reconciliation]` → `[Pre-pivot]`. |
| 6 | Root README updated: status table, post-M4 narrative, What-runs-today, Next → M5 | ✅ | Root `README.md`: status table row M4 → Complete (line 15); post-M4 narrative paragraph at line 19 names the four FastMCP tools + shared dispatch helper + `claude mcp add` walkthrough; `## What runs today (post-M4)` section (line 21) opens with the `aiw-mcp` bullet citing [mcp_setup.md](../mcp_setup.md); `## Next` (line 119) points at M5 multi-tier planner. |

**Carry-over (from M4-T06-ISS-01):**

| # | Carry-over AC | Grade | Evidence |
| --- | --- | --- | --- |
| CO-1 | Manual `claude mcp add` → `run_workflow` → `resume_run` round-trip verbatim in T08 CHANGELOG entry | 🚧 | **Same blocker as AC-3.** Task spec's Carry-over line 52 requires user-level action. PENDING USER ACTION checklist is in place in the T08 CHANGELOG entry at lines 47-61. Tracked as M4-T08-ISS-01 below (single tracking ID — AC-3 and CO-1 collapse to the same real-world action). |

Six of six spec ACs: 5 ✅ + 1 🚧. One carry-over AC: 🚧 (same action). One OPEN issue.

---

## 🔴 HIGH — (none)

## 🟡 MEDIUM

### M4-T08-ISS-01 🚧 BLOCKED — manual `claude mcp add` verification requires user action

**What's missing:** AC-3 (`Manual claude mcp add verification recorded in the close-out CHANGELOG entry`) and the M4-T06-ISS-01 carry-over both require running `claude mcp add ai-workflows --scope user -- uv run aiw-mcp` (modifies the user's Claude Code MCP registry — a side effect outside the repo), then spawning a fresh Claude Code session and asking it to invoke `run_workflow` + `resume_run` against the planner. The Builder cannot run `claude mcp add` autonomously nor spawn a fresh Claude Code session to act as an MCP client against itself.

**Current state:** the T08 CHANGELOG entry at [CHANGELOG.md:47-61](../../../../CHANGELOG.md) holds a **PENDING USER ACTION** checklist with three numbered steps:

1. Run `claude mcp add ai-workflows --scope user -- uv run aiw-mcp` (user-scope registry modification).
2. From a fresh Claude Code session, ask it to call `run_workflow(workflow_id="planner", inputs={"goal": "<short>"}, run_id="<fresh>")` and capture the returned `{run_id, status: "pending", awaiting: "gate", …}` payload verbatim.
3. Ask Claude Code to call `resume_run(run_id="<same>", gate_response="approved")` and capture the returned `{status: "completed", plan: {…}}` payload verbatim.

Then paste both commands + both responses into the T08 CHANGELOG entry below the PENDING USER ACTION sub-list and tick the `[x] PENDING USER ACTION` checkbox.

**Why MEDIUM, not HIGH:** everything else in T08 is done. The gate snapshot is pinned. The in-process smoke test ([`tests/mcp/test_server_smoke.py`](../../../../tests/mcp/test_server_smoke.py)) already validates the full four-tool surface hermetically on every `uv run pytest`. The manual verification is the "proof that the stdio transport reaches a real Claude Code host" check — high-value signal, but not a correctness gate on the shipped code. The milestone cannot be pronounced "done" without it, but the code is stable in the meantime.

**Action (user):** run the three numbered steps above, paste the four captures into [CHANGELOG.md](../../../../CHANGELOG.md) directly below the `**PENDING USER ACTION**` sub-list in the T08 entry, and tick the checkbox. On next audit, flip this issue to ✅ RESOLVED and the milestone to CLEAN.

**Does not require Builder work.** Re-audit after the user completes the three steps.

---

## 🟢 LOW — (none)

---

## Additions beyond spec — audited and justified

1. **Close-out entry describes the retroactive M3-era orphan promotion** (T08 CHANGELOG entry, description paragraph). The entry explicitly names the retroactive entries that were parked in `[Unreleased]` post-M3-close-out and are being swept into `[M4 MCP Server]` now: KDR-010 / ADR-0002, M3 close-out docs cleanup, M3 T07b, M3 T07a, and the 2026-04-19 Architecture pivot entry. *Justified.* Without this note, a future reader doing `git blame` on the Architecture pivot entry dated 2026-04-19 would be confused by its placement inside a 2026-04-20 M4 dated section. The narrative sentence costs one line and documents the reality.

2. **Outcome section exit-criteria verification table in the milestone README** (lines 60-68). *Justified.* AC-1 of this task explicitly requires "Every exit criterion has a concrete verification (paths / test names / issue-file links)" — a table is the shape that satisfies this cleanly, matches the [M3 close-out](../../milestone_3_first_workflow/task_08_milestone_closeout.md) shape the spec mirrors, and gives reviewers one-glance evidence.

No new dependencies, no new modules, no new public API.

---

## Gate summary

| Gate | Command | Result |
| --- | --- | --- |
| Full pytest | `uv run pytest` | **332 passed, 1 skipped** (1 skipped = pre-existing `AIW_E2E=1`-gated M3 e2e) |
| Layer contract | `uv run lint-imports` | **3 / 3 contracts kept** |
| Lint | `uv run ruff check` | **All checks passed** |

---

## Issue log — cross-task follow-up

| ID | Severity | Owner / next touch point |
| --- | --- | --- |
| M4-T08-ISS-01 | 🟡 MEDIUM / 🚧 BLOCKED | **User action.** Run `claude mcp add` + the two MCP tool calls from a fresh Claude Code session; paste outputs into [CHANGELOG.md](../../../../CHANGELOG.md) T08 entry; re-audit. |

---

## Deferred to nice_to_have

None raised.

---

## Propagation status

No forward-deferrals from T08. This is a terminal milestone close-out; any finding would surface on M5 or later milestones as they begin. M4-T08-ISS-01 is a blocker on this audit, not a forward-deferral.
