# Task 02 — Milestone Close-out — Audit Issues

**Source task:** [../task_02_milestone_closeout.md](../task_02_milestone_closeout.md)
**Audited on:** 2026-04-22 (Cycle 1)
**Audit scope:** the T02 deliverables end-to-end — ADR-0005, architecture.md §4.4 citation, 5 new tests in `tests/mcp/test_http_transport.py`, milestone README status flip + Outcome + Propagation, roadmap.md M14 row flip, CHANGELOG promote + T02 entry, root README.md milestone-table row + `## Next` narrative trim, live HTTP smoke, gate sweep. Full project scope re-read: `CLAUDE.md`, `design_docs/architecture.md` (esp. §3 four-layer, §4.4 surfaces, §9 KDRs), every KDR cited by the task (KDR-002, KDR-008, KDR-009), the M14 README in full, T01 task file, T01 issue file, [deep_analysis.md](../deep_analysis.md), sibling close-out patterns ([M11 T02](../../milestone_11_gate_review/task_02_milestone_closeout.md), [M9 T04](../../milestone_9_skill/task_04_milestone_closeout.md)), `pyproject.toml`, `.github/workflows/ci.yml`.
**Status:** ✅ PASS (Cycle 1) — all 16 ACs met, all gates green, no OPEN issues, no drift.

---

## Design-drift check

Cross-referenced every T02 change against [`design_docs/architecture.md`](../../architecture.md):

| Drift axis | T02 change | Finding |
| --- | --- | --- |
| New dependency added? | None. `inspect` (stdlib), `httpx` / `fastmcp` / `pytest` already in `pyproject.toml`. Starlette remains transitive via FastMCP + uvicorn — ADR-0005 only *documents* the import, adds no new pin. | ✅ Clean. `pyproject.toml` byte-identical at T02. |
| New module or layer? | None. Only `tests/mcp/test_http_transport.py` (+5 tests appended to existing file), `design_docs/adr/0005_*.md` (new doc), and docs. Zero `ai_workflows/` diff at T02. | ✅ Clean. Four-layer contract ([architecture.md §3](../../architecture.md)) preserved. `uv run lint-imports` reports **4 kept, 0 broken**. |
| LLM call added? | None. | N/A. KDR-003 / KDR-004 unaffected. |
| Checkpoint / resume logic added? | None. T02 tests *exercise* the existing `_dispatch` path over HTTP but add no new checkpoint code. | ✅ Clean. KDR-009 preserved. |
| Retry logic added? | None. | N/A. KDR-006 preserved. |
| Observability added? | None. | N/A. |
| KDR-002 (skill packaging stdio-primary). | `.claude/skills/ai-workflows/SKILL.md` byte-identical at M14; skill install doc §5 landed at T01, unchanged at T02. | ✅ Preserved. |
| KDR-008 (MCP schemas are public contract). | T02 adds `test_http_run_workflow_schema_parity_with_stdio` as an *active regression guard* on this exact invariant — a FastMCP minor that diverged stdio vs HTTP serialisation would now fail the suite. | ✅ Preserved and now regression-guarded. |
| ADR-0005 relationship to KDRs. | ADR-0005 is local to the M14 transport surface and refines *how* CORS is wired in FastMCP 3.2.4. It does not mutate any KDR, does not add a KDR, and does not claim architectural status beyond the M14 call-site. Cited from [architecture.md §4.4](../../architecture.md) sub-bullet (one-line addition, as per T02 deliverable §6). | ✅ Scope-correct. [`design_docs/adr/`](../../../adr/) sibling pattern matches ADR-0001 / ADR-0002 / ADR-0004. |
| [nice_to_have.md](../../../nice_to_have.md) adoption? | None. Per task spec and operator direction, zero new entries at M14. M14-DA-06 (CORS + stdio UX guard) and the prior §17 hosting-polish proposal were dropped entirely — verified by grepping `nice_to_have.md`: no M14 references, no `§17` entry. | ✅ Clean. |

**No drift found.** The task is a tests + docs + ADR close-out; zero runtime-code diff; every KDR cited by the task is preserved (KDR-002 / KDR-008 / KDR-009) and one (KDR-008) is now actively regression-guarded.

---

## Acceptance Criteria — grading

| # | AC | Grade | Evidence |
| --- | --- | --- | --- |
| AC-1 | `design_docs/adr/0005_fastmcp_http_middleware_accessor.md` exists with Context / Decision / Rejected alternatives / Consequences sections. | ✅ PASS | File present. Sections verified at lines 8, 53, 88, 139 of the ADR. Three rejected alternatives captured (A: `http_app + uvicorn.run`; B: `server.add_middleware`; C: Starlette-first wrapping). Consequences section names the revisit triggers explicitly. |
| AC-2 | `architecture.md` §4.4 sub-bullet cites ADR-0005 with a working relative link. | ✅ PASS | [architecture.md:107](../../architecture.md) reads: *"CORS middleware accessor recorded in [ADR-0005](adr/0005_fastmcp_http_middleware_accessor.md)"*. Relative link resolves against `design_docs/`. No new KDR; no new row in §9 — scope-correct per task spec deliverable §6. |
| AC-3 | `test_http_cli_default_transport_is_stdio` passes; pins Typer `--transport` default to `"stdio"`. | ✅ PASS | Test at [test_http_transport.py:336-351](../../../../tests/mcp/test_http_transport.py). Inspects `_cli` signature default and asserts `default.default == "stdio"`. Passes in the suite. |
| AC-4 | HTTP/stdio schema-parity test for `run_workflow` passes; asserts equal dicts modulo allowed-to-vary fields. | ✅ PASS | Test at [test_http_transport.py:354-454](../../../../tests/mcp/test_http_transport.py). Drives both stdio (`server.get_tool("run_workflow").fn(...)`) and HTTP (`fastmcp.Client.call_tool`) with the same stub script, asserts top-level dict equality modulo `{"run_id"}`, then diffs `gate_context` stable keys (`gate_prompt`, `workflow_id`) explicitly. Passes. |
| AC-5 | `test_http_list_runs_roundtrip` passes. | ✅ PASS | Test at [test_http_transport.py:457-490](../../../../tests/mcp/test_http_transport.py). Seeds two runs via `SQLiteStorage.create_run`, calls `list_runs` via `fastmcp.Client`, unwraps the `{"result": [...]}` envelope, asserts both run_ids land. Passes. |
| AC-6 | `test_http_cancel_run_roundtrip` passes. | ✅ PASS | Test at [test_http_transport.py:493-527](../../../../tests/mcp/test_http_transport.py). Seeds a `pending` run, invokes `cancel_run` via HTTP, asserts envelope `status == "cancelled"` + Storage row flipped. Passes. |
| AC-7 | `test_http_resume_run_roundtrip_returns_envelope` passes. | ✅ PASS | Test at [test_http_transport.py:530-594](../../../../tests/mcp/test_http_transport.py). Runs planner to gate pause via HTTP, resumes with `approved` over HTTP, asserts completed envelope: `status="completed"`, `plan is not None`, `error is None`, `total_cost_usd == pytest.approx(0.0033)`. Passes. |
| AC-8 | Milestone README Status flipped to `✅ Complete` with date; Outcome covers T01 + T02 with deep-analysis propagation summary; Propagation status filled. | ✅ PASS | [README.md:3](../README.md) reads `**Status:** ✅ Complete (2026-04-22).`. Outcome section at lines 112-138 covers both tasks, green-gate snapshot, manual smoke, deep-analysis propagation (moot findings recorded but not carried; M14-DA-06 dropped). Propagation status at lines 145-150 names the ADR + 5 tests + "zero carry-over, zero `nice_to_have.md` entries, no new milestone". |
| AC-9 | `roadmap.md` M14 row reflects complete status with the close-out date. | ✅ PASS | [roadmap.md:26](../../../roadmap.md) reads: `M14 \| MCP HTTP transport \| ... \| ✅ complete (2026-04-22) \|`. M13's row re-graded to "depends on M11 + M14 — both complete; unblocked". |
| AC-10 | CHANGELOG has dated `[M14 MCP HTTP Transport]` section with T01 Unreleased entry promoted + T02 close-out entry at top; `[Unreleased]` retained. | ✅ PASS | [CHANGELOG.md:10](../../../../CHANGELOG.md) reads `## [M14 MCP HTTP Transport] - 2026-04-22` (promoted dated section). T02 close-out block (`### Changed — M14 Task 02: Milestone Close-out`) sits above the promoted `### Added — M14 Task 01: ...` block. Top-of-file `## [Unreleased]` section (now empty) retained at line 8 — consumes no content, matches M11 T02's pattern. |
| AC-11 | Root `README.md` M14 row updated to `Complete (<date>)`; any M14-era links still resolve. | ✅ PASS | [README.md:25](../../../../README.md) reads `**M14 — MCP HTTP transport** \| Complete (2026-04-22)`. M13 row re-graded to `Planned (M11 + M14 complete; unblocked)`. The `## Next` narrative at line 202+ trimmed — M14 removed from the planned list; M13's dependency line updated. Link to `design_docs/phases/milestone_14_mcp_http/README.md` still resolves (path unchanged). |
| AC-12 | Manual HTTP smoke recorded in CHANGELOG T02 entry with commit sha baseline + pass/fail observation. | ✅ PASS | [CHANGELOG.md:75-99](../../../../CHANGELOG.md). Commit baseline `cdb2b03` stamped (prior commit on the branch; working tree pre-commit). Smoke recorded in two parts: (1) `curl -i -X OPTIONS` preflight — real response headers captured verbatim (`access-control-allow-origin: http://localhost:4321`, `access-control-allow-methods: GET, POST, OPTIONS`, `vary: Origin`, `server: uvicorn`), **Pass**; (2) `fastmcp.Client` round-trip — `list_tools()` returned all four M4 tools, `list_runs` call returned len=7 RunSummary list against dev storage, **Pass**. Server ran in background on TCP/18999; stopped cleanly. No runtime errors, no schema drift against stdio. |
| AC-13 | `uv run pytest` green (existing 607 + 5 new = ~612 tests). | ✅ PASS | Final gate sweep at close-out: **612 passed, 5 skipped, 2 warnings in 20.72s**. Exactly the predicted count (607 post-T01 + 5 new T02 tests). The 5 skipped are the four `AIW_E2E=1`-gated smokes + the double-gated live eval replay. 2 warnings are pre-existing deprecation warnings in `yoyo.backends.base` — not a T02 regression. |
| AC-14 | `uv run lint-imports` reports 4 contracts kept, 0 broken. | ✅ PASS | Final snapshot: *"primitives cannot import graph, workflows, or surfaces — KEPT"*, *"graph cannot import workflows or surfaces — KEPT"*, *"workflows cannot import surfaces — KEPT"*, *"evals cannot import surfaces — KEPT"*. **Contracts: 4 kept, 0 broken.** No new contract at M14 (surface-only milestone; the `ai_workflows/mcp/` diff at T01 stays within the `surfaces` layer). |
| AC-15 | `uv run ruff check` clean. | ✅ PASS | `All checks passed!`. One ruff regression (E501 line-too-long in the schema-parity test's divergence-diff f-string) was caught and fixed in the same cycle — refactored into a named `_divergent` list comprehension. |
| AC-16 | Zero runtime-code diff in `ai_workflows/` during T02. | ✅ PASS | `git status --porcelain` against T01 baseline: the only `ai_workflows/` path touched in the working tree is `ai_workflows/mcp/__main__.py` — that diff is from T01 (the Typer CLI), not T02. T02 touched only `tests/mcp/test_http_transport.py`, `design_docs/adr/0005_*.md` (new), `design_docs/architecture.md` (§4.4 citation), `design_docs/phases/milestone_14_mcp_http/README.md`, `design_docs/roadmap.md`, `CHANGELOG.md`, root `README.md`. Zero `ai_workflows/` diff at T02. |

**All 16 ACs met.**

---

## 🔴 HIGH

*None.*

## 🟡 MEDIUM

*None.*

## 🟢 LOW

*None.*

---

## Additions beyond spec — audited and justified

- **CHANGELOG T02 entry scope.** The T02 entry at [CHANGELOG.md:12-102](../../../../CHANGELOG.md) covers more than the spec's bulleted list: it enumerates the four deep-analysis findings with their IDs (M14-DA-04 / -05 / -SP / -LR) + adds an "Invariants preserved" section naming KDR-002 / KDR-008 / KDR-009. Justified — mirrors the M11 T02 CHANGELOG entry's depth (KDR citations + invariant-preservation paragraph) for consistency across close-out entries. Zero new surface.
- **Schema-parity test's explicit `gate_context` diff.** The test compares `gate_context` sub-dict keys separately from the top-level dict. The spec said *"diff the full dict and enumerate the allowed-to-vary keys explicitly so a silent field addition fails"*. The implementation pops `gate_context` from both dicts, asserts `stdio_gc is None == http_gc is None`, asserts keyset equality, then pins the stable sub-keys `gate_prompt` + `workflow_id` value-for-value. Justified — `gate_context` legitimately carries volatile fields (`checkpoint_ts`, `gate_id` threaded with per-checkpoint IDs) so a flat equality would false-positive on every run; the two-tier diff is the minimal shape that makes the assertion meaningful while still pinning KDR-008 at the stable fields. Tested and passes.

**No scope creep from `nice_to_have.md` or beyond.** Zero adoption of deferred items.

---

## Gate summary

| Gate | Result | Notes |
| --- | --- | --- |
| `uv run pytest` | ✅ 612 passed, 5 skipped | +5 over T01's 607. Zero regressions. |
| `uv run lint-imports` | ✅ 4 kept, 0 broken | No new layer contract. |
| `uv run ruff check` | ✅ All checks passed | One E501 caught + fixed mid-cycle. |
| Markdown lint (IDE) | 🟢 noise-only | Flagged warnings (MD004/MD031/MD032/MD036) are pre-existing to CHANGELOG.md's historical content (lines 343, 543, 1112+, 1666+, 1805+, 2344+) — none in the 75-99 range where T02's content lives. Not a T02 regression; deferring the whole-file markdown-style cleanup outside this task. |

---

## Issue log — cross-task follow-up

*Empty.* No forward-deferrals. No cross-task items raised at T02.

Per [deep_analysis.md](../deep_analysis.md), the four legit findings (M14-DA-04 / -05 / -SP / -LR) all absorb at T02 and carry no downstream owner. The five moot findings (M14-DA-01 / -02 / -03 / -07 / -08) stay recorded in `deep_analysis.md` with explicit re-open triggers but **do not** propagate to a future task — under the local-only / solo-use invariant, their threat-model preconditions have not fired. M14-DA-06 was dropped entirely per operator direction.

---

## Deferred to nice_to_have

*None.* M14 generated zero `nice_to_have.md` entries — matches the [task spec §Out of scope](../task_02_milestone_closeout.md) commitment and the operator direction on hosting-adjacent polish.

---

## Propagation status

- **All four legit deep-analysis findings absorbed in T02.** ADR-0005 + 5 tests. Zero carry-over to future tasks.
- **Moot findings** stay recorded in [`deep_analysis.md`](../deep_analysis.md) with explicit re-open triggers. None propagate.
- **No new milestone generated.** M14 closes the HTTP-transport workstream; M13 (v0.1.0 release) is the next load-bearing milestone and is now unblocked — both of its prerequisites (M11 gate-pause projection, M14 HTTP transport) are complete and audited clean.
- **Carry-over sections.** No future task's spec file needs a `## Carry-over from prior audits` addition at M14 T02 close-out. Verified by re-reading `task_02_milestone_closeout.md` §Propagation status and cross-checking against the T02 spec's "Out of scope" line.

---

**Cycle summary:** one /clean-implement cycle, stop condition **CLEAN**. No further cycles required.
