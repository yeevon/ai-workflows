# Task 21 — Adaptive-thinking migration — Audit Issues

**Source task:** [../task_21_adaptive_thinking_migration.md](../task_21_adaptive_thinking_migration.md)
**Audited on:** 2026-04-28 (cycle 1)
**Audit scope:** 7 slash-command frontmatters, 9 agent frontmatters, `.claude/commands/_common/effort_table.md`, two new hermetic tests, CHANGELOG entry, status surfaces (spec / milestone-README task row / Exit-criterion #8). Re-ran all gates from scratch under `AIW_BRANCH=design`.
**Status:** ✅ PASS

---

## Phase 1 — Design-drift check

**Result: no drift detected.**

| KDR | Verification | Outcome |
|---|---|---|
| KDR-002 (MCP server surface) | T21 is prompt-frontmatter only; no MCP tool changes | ✅ N/A |
| **KDR-003 (no Anthropic API)** | `grep -rnE "ANTHROPIC_API_KEY\|^import anthropic\|^from anthropic" .claude/` returns 5 hits, **all of them documentary mentions** in audit/builder/security-reviewer/task-analyzer prompts that *enforce* the rule (e.g. "zero `anthropic` SDK imports, zero `ANTHROPIC_API_KEY` reads"). Zero new SDK imports, zero new env-var reads, zero new Anthropic-API call paths. T21 sets effort directives consumed by Claude Code's harness — orthogonal to KDR-003. | ✅ Clean |
| KDR-004 (ValidatorNode after TieredNode) | No runtime code touched | ✅ N/A |
| KDR-006 (RetryingEdge) | No runtime code touched | ✅ N/A |
| KDR-008 (FastMCP / Pydantic schemas) | No MCP surface touched | ✅ N/A |
| KDR-009 (SqliteSaver) | No checkpoint code touched | ✅ N/A |
| KDR-013 (user code is user-owned) | No external-loader changes | ✅ N/A |

Layer rule: untouched (no `ai_workflows/` imports modified). `lint-imports` confirms 5/5 contracts kept.

No new dependencies. No new module / boundary crossings. No `nice_to_have.md` adoption.

---

## Phase 2 — Gate re-run (from scratch, `AIW_BRANCH=design`)

| Gate | Command | Result |
|---|---|---|
| Hermetic pytest (full) | `AIW_BRANCH=design uv run pytest -q` | ✅ **1061 passed, 7 skipped, 22 warnings in 43.77s** |
| Layer contracts | `uv run lint-imports` | ✅ **Contracts: 5 kept, 0 broken** |
| Lint | `uv run ruff check` | ✅ **All checks passed** |
| Spec smoke 1 — no `thinking:` shorthand | `grep -rnE "thinking:[[:space:]]*(max\|high\|medium\|low\|xhigh)" .claude/` | ✅ **exit=1 (zero hits)** |
| Spec smoke 2 — no `budget_tokens` | `grep -rn "budget_tokens" .claude/` | ✅ **exit=1 (zero hits)** |
| Spec smoke 3 — 7 commands have `type: adaptive` | per-file `grep -A 2 "^thinking:" \| grep -q "type: adaptive"` | ✅ **7/7 OK** (auto-implement, audit, clean-tasks, clean-implement, queue-pick, autopilot, implement) |
| Spec smoke 4 — T21 hermetic tests | `uv run pytest tests/orchestrator/test_no_deprecated_thinking_directives.py tests/orchestrator/test_effort_table_consistency.py -v` | ✅ **11 passed in 0.03s** |

All gates pass cleanly. No Builder gate-integrity drift to flag.

---

## Phase 3 — AC grading

| AC | Status | Notes |
|---|---|---|
| AC-1: Zero `thinking: <literal>` shorthand directives in `.claude/` | ✅ Met | `grep -rnE "thinking:[[:space:]]*(max\|high\|medium\|low)" .claude/` → exit 1 (zero hits). Plus `xhigh` covered in test regex. |
| AC-2: Zero `budget_tokens` literals in `.claude/` | ✅ Met | `grep -rn "budget_tokens" .claude/` → exit 1 (zero hits). |
| AC-3: All 7 slash commands have `thinking: { type: adaptive }` + correct `effort:` | ✅ Met | Per-file inspection: auto-implement=high, audit=high, clean-tasks=high, clean-implement=high, queue-pick=medium, autopilot=high, implement=high. Matches spec lines 60-66 and effort_table.md exactly. |
| AC-4: All 9 agents have `thinking: { type: adaptive }` + correct `effort:` | ✅ Met | builder=high, auditor=high, security-reviewer=high, dependency-auditor=medium, architect=high, sr-dev=high, sr-sdet=high, task-analyzer=high, roadmap-selector=medium. Matches spec per-role table (lines 21-31). |
| AC-5: `_common/effort_table.md` exists and matches frontmatters | ✅ Met | File present with full slash-command table (7 rows) + agent table (9 rows) + Haiku-policy stub. Cross-checked against frontmatters by `test_effort_table_consistency.py`. |
| AC-6: `test_no_deprecated_thinking_directives.py` passes | ✅ Met | 6/6 tests pass. Regex covers max/high/medium/low/xhigh shorthand. |
| AC-7: `test_effort_table_consistency.py` passes | ✅ Met | 5/5 tests pass. Parses table rows + frontmatter values, asserts both match `EXPECTED_*_EFFORTS` constants. |
| AC-8: CHANGELOG entry under `[Unreleased]` | ✅ Met | Line 10: `### Changed — M20 Task 21: Adaptive-thinking migration (eliminate thinking: max; per-role effort settings; research brief §Lens 3.3; required for T06 + T07) (2026-04-28)`. |
| AC-9: Status surfaces flip together | ✅ Met | (a) spec line 3 `**Status:** ✅ Done (2026-04-28)`, (b) milestone README task table line 122 `✅ Done`, (c) Exit-criterion #8 line 57 `**[T21 Done — 2026-04-28]**`. M20 has no separate `tasks/README.md`; the Exit-criteria block is the milestone Done-when surface. |

**9/9 ACs met.**

---

## Phase 4 — Critical sweep

| Sweep | Result |
|---|---|
| ACs that look met but aren't | None. Each AC has both grep evidence and a hermetic test. |
| Silently skipped deliverables | None. Every deliverable in spec §"Deliverables" is on disk. |
| Additions beyond spec | None. The two new test files + the new effort_table.md are exactly what spec §"Tests" + §"Deliverables" call for. No drive-by edits to any agent prompt body, runtime code, or other docs. |
| Test gaps | The hermetic tests cover (a) zero shorthand, (b) zero `budget_tokens`, (c) every file has adaptive block, (d) every file has `effort:` line, (e) table lists every file, (f) table values match frontmatter values. Every AC has a corresponding assertion. |
| Doc drift | CHANGELOG entry present; spec status flipped; milestone README row + Exit criterion both flipped. effort_table.md self-consistent. |
| Secrets shortcuts | None. T21 is 100% prompt-frontmatter + tests; no env-var or token surfaces touched. |
| Scope creep from `nice_to_have.md` | None. |
| Silent architecture drift Phase 1 might have missed | Re-checked — no `ai_workflows/` files modified; `lint-imports` confirms layer contracts intact. |
| Status-surface drift | None — three surfaces agree (spec, README task row, Exit criterion #8). |

---

## Additions beyond spec — audited and justified

None. Builder stayed strictly within scope.

The Haiku-policy stub at the bottom of `effort_table.md` ("If any are added in the future, omit `effort:` and use prompt-level brevity directives") is a documentary note rather than an addition — spec §"Out of scope" line 132 calls it out and the table needs to say something about Haiku for completeness.

---

## Gate summary

| Gate | Command | Pass / Fail |
|---|---|---|
| pytest (full hermetic) | `AIW_BRANCH=design uv run pytest -q` | ✅ 1061 passed, 7 skipped |
| lint-imports | `uv run lint-imports` | ✅ 5/5 contracts kept |
| ruff | `uv run ruff check` | ✅ pass |
| Spec smoke (4 commands) | per spec lines 109-126 | ✅ all 4 pass; 7/7 commands report `OK` |
| T21-specific tests | `uv run pytest tests/orchestrator/test_{no_deprecated_thinking_directives,effort_table_consistency}.py -v` | ✅ 11 passed |

---

## Issue log — cross-task follow-up

None. Cycle 1 closed clean — no HIGH, no MEDIUM, no LOW. Nothing to forward-defer.

---

## Deferred to nice_to_have

None. T21 is a pure migration; no findings naturally map to nice_to_have items.

---

## Propagation status

No forward-deferrals to propagate.

---

## Next action

T21 ships. Recommend `/auto-implement` orchestrator proceed to terminal gate (sr-dev + sr-sdet + security-reviewer). With KDR-003 verified clean and no runtime changes, security-reviewer surface area for this task is minimal (frontmatter + tests + CHANGELOG only).

Phase C ordering on the milestone README (T21 → T22 → T06 → T07) is now unblocked at the T21 gate.

---

## Sr. Dev review (2026-04-28) — cycle 1 terminal gate

**Verdict:** SHIP

(Stitched from `runs/m20_t21/cycle_1/sr-dev-review.md`.)

No BLOCK / no FIX. One advisory: positive-assertion file lists in the new tests (`AGENT_FILES`, `SLASH_COMMAND_FILES`) match the on-disk set exactly today. A future-added agent without any `thinking:` block would not trip `test_no_thinking_shorthand_in_claude_dir` (no shorthand to catch) and would not appear in the positive list. Track-only — when T06/T07 add new agents, extend the positive list or switch to a glob-based discovery. KDR-003 cross-check clean (no SDK import, no `ANTHROPIC_API_KEY`).

---

## Sr. SDET review (2026-04-28) — cycle 1 terminal gate

**Verdict:** SHIP

(Stitched from `runs/m20_t21/cycle_1/sr-sdet-review.md`.)

No BLOCK / no FIX. Three advisories tracked:
- **ADV-1 (Lens 1 — discriminating-positive, weak):** `test_no_budget_tokens_in_claude_dir` is vacuous against the pre-existing state (project never had `budget_tokens` literals); valid future-regression guard but not load-bearing for THIS migration.
- **ADV-2 (Lens 1 — effort-value specificity):** the `test_no_deprecated_thinking_directives` positive assertion checks each frontmatter HAS an `effort:` line, but doesn't pin the exact value to the spec's per-role table (lines 21-31). The separate `test_effort_table_consistency` does cross-check the table vs frontmatters, but if both the table AND the frontmatter drift in the same direction (e.g., both flip Builder from `high` to `medium`), neither test fires. Track-only — the spec is the source of truth and the table-vs-frontmatter cross-check catches one-sided drift; bilateral drift is captured by code review.
- **ADV-3 (Lens 2 — out-of-scope):** the spec's "Auditor (Opus 4.7 hostile-spec) → max" note is forward-looking; T21 sets a single `effort: high` for the auditor today (the hostile-spec branch isn't a separate spawn). Spec explicitly defers tuning to T06; out-of-scope per spec line 131.

---

## Security review (2026-04-28) — cycle 1 terminal gate

**Verdict:** SHIP

(Stitched from `runs/m20_t21/cycle_1/security-review.md`.)

KDR-003 clean: zero `import anthropic`, zero `ANTHROPIC_API_KEY`, zero `os.environ.get("ANTHROPIC_API_KEY")` across cycle-1 diff. Wheel surface unchanged (no `pyproject.toml`, no `[tool.hatch.build]`). Subprocess surface unchanged. New hermetic tests use `Path.read_text` against repo-local files only — no network, no subprocess, no credential surface. No Critical / High / Advisory.

---

## Cycle 1 terminal gate — TERMINAL CLEAN

All three reviewers verdict SHIP. dependency-auditor not spawned (no `pyproject.toml`/`uv.lock` change in this task). Per T05's new precedence rule: TERMINAL CLEAN. Proceed to commit ceremony.

**Final task close-out summary**
- Cycles run: 1 (Builder BUILT → Auditor PASS → Terminal gate CLEAN, no bypass needed).
- Auditor verdict: PASS.
- Reviewer verdicts: sr-dev SHIP, sr-sdet SHIP, security SHIP.
- Dependency: N/A (no manifest change).
- KDR additions: none.
- Open issues at close: 4 track-only advisories (1 sr-dev positive-list-tightness; 3 sr-sdet vacuous + bilateral-drift + hostile-effort-future). All track-only — none blocks close-out, all deferred to future tasks (T06/T07 will naturally extend the positive lists; bilateral drift is review-discipline).
