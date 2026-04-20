# Task 09 — Milestone Close-out — Audit Issues

**Source task:** [../task_09_milestone_closeout.md](../task_09_milestone_closeout.md)
**Audited on:** 2026-04-19 (cycles 1 + 2)
**Audit scope:** `design_docs/phases/milestone_2_graph/README.md`, `design_docs/roadmap.md`, `CHANGELOG.md`, the milestone README's exit criteria, every M2 sibling task's issue file (T01–T08). Cross-checked against [architecture.md](../../../architecture.md) §3 / §4.1–§4.2 / §6 and KDRs 001, 003, 004, 006, 007, 008, 009. Verified the claimed file paths (`ai_workflows/graph/*.py`, `ai_workflows/primitives/llm/litellm_adapter.py`, `ai_workflows/primitives/llm/claude_code.py`, `tests/graph/test_smoke_graph.py`) resolve. Re-ran all three gates (`uv run pytest`, `uv run lint-imports`, `uv run ruff check`) locally on both cycles — green.
**Status:** ✅ PASS. All four ACs met; no OPEN issues. One LOW raised in cycle 1 (CHANGELOG `[Unreleased]` mid-file) RESOLVED in cycle 2 — pivot block restored to the top of the file.

## Design-drift check

| Axis | Verdict | Evidence |
| --- | --- | --- |
| New dependency | None | Docs-only task. `pyproject.toml` unchanged. |
| Four-layer contract | KEPT | `uv run lint-imports` — 3 / 3 contracts kept, 0 broken (21 files, 17 deps). |
| New module or layer | None | No Python files added or edited. |
| LLM call added | None | No code touched. |
| KDR-003 (no Anthropic API) | Met | `grep -r "anthropic\|ANTHROPIC_API_KEY" design_docs/phases/milestone_2_graph/README.md design_docs/roadmap.md CHANGELOG.md` → 0 runtime matches; a handful of historical mentions exist in CHANGELOG M1 entries referring to removals / negative assertions, unrelated to this task. |
| KDR-004 (validator-after-LLM) | Met (pre-existing) | Outcome section documents the pairing; no new LLM nodes added. |
| KDR-006 (3-bucket retry) | Met (pre-existing) | Outcome section names `RetryingEdge` + `wrap_with_error_handler` as the only retry path; no new retry logic added. |
| KDR-007 (LiteLLM adapter) | Met (pre-existing) | Outcome section names `LiteLLMAdapter` at its actual path. |
| KDR-008 (FastMCP for MCP) | Not exercised in M2 (M4 scope) | Outcome section only references cost-callback wiring "per KDR-008"; no MCP server work introduced. |
| KDR-009 (LangGraph owns checkpoints) | Met (pre-existing) | Outcome section pins the checkpointer factory path + "distinct file from the Storage DB" invariant; no hand-rolled checkpoint writes added. |
| Observability | `StructuredLogger` only (pre-existing) | No new backends pulled in. |
| Secrets | None read | Docs-only. |
| `nice_to_have.md` adoption | None | No items pulled in. |

No drift. Task passes the design-drift gate.

## AC grading

| AC | Verdict | Evidence |
| --- | --- | --- |
| AC-1 — Every exit criterion in the milestone `README` has a concrete verification | ✅ | `README.md` Outcome section at [milestone_2_graph/README.md](../README.md#outcome-2026-04-19) enumerates all 6 exit criteria with per-criterion evidence: (1) adapter files listed with paths + per-task `✅ PASS` issue links, (2) `LiteLLMAdapter` at [ai_workflows/primitives/llm/litellm_adapter.py](../../../../ai_workflows/primitives/llm/litellm_adapter.py) + T01 issue link, (3) `ClaudeCodeSubprocess` at [ai_workflows/primitives/llm/claude_code.py](../../../../ai_workflows/primitives/llm/claude_code.py) + T02 issue link, (4) smoke graph test + T08 issue link, (5) gate snapshot table (236 / 3 contracts / ruff clean), (6) `lint-imports` output pinning the layer contract. |
| AC-2 — `uv run pytest && uv run lint-imports && uv run ruff check` green on a fresh clone | ✅ | Re-run locally during the audit phase: `uv run pytest` → 236 passed, 2 warnings (pre-existing `yoyo` datetime deprecation, unrelated); `uv run lint-imports` → 3 kept, 0 broken; `uv run ruff check` → All checks passed. All three runs captured in the Gate summary below. |
| AC-3 — `README` and roadmap reflect ✅ status | ✅ | [README.md:3](../README.md#L3) now reads `**Status:** ✅ Complete (2026-04-19).`; [roadmap.md:15](../../../roadmap.md#L15) M2 row `Status` column now reads `✅ complete (2026-04-19)`. Both were `📝 Planned` / `planned` before. |
| AC-4 — `CHANGELOG` has a dated entry summarising M2 | ✅ | [CHANGELOG.md:74](../../../../CHANGELOG.md#L74) reads `## [M2 Graph-Layer Adapters] - 2026-04-19` (moved below the top-of-file `[Unreleased]` section in cycle 2). Under that heading land a new T09 close-out entry (files touched / ACs / deviations) plus all prior M2 task entries (T01–T08) promoted out of `[Unreleased]`. `grep "^## \[M2" CHANGELOG.md` → 1 match. |

## 🔴 HIGH

None.

## 🟡 MEDIUM

None.

## 🟢 LOW

### M2-T09-ISS-01 — RESOLVED (cycle 2, 2026-04-19)

**Original finding (cycle 1):** `## [Unreleased]` sat below `## [M2 Graph-Layer Adapters] - 2026-04-19` because the Architecture pivot block was physically appended below the M2 task entries during M2 work, and cycle 1 promoted the M2 entries into a dated section without moving the pivot block up. Non-standard per Keep-a-Changelog convention.

**Resolution (cycle 2):** Two sequential `Edit`s on [CHANGELOG.md](../../../../CHANGELOG.md): (1) inserted a fresh top-of-file `## [Unreleased]` heading + the full Architecture pivot entry above the M2 dated section; (2) removed the now-duplicated mid-file `[Unreleased]` + pivot block using the unique trailing line of the preceding M2 T01 entry as the disambiguating anchor. Post-fix `grep "^## " CHANGELOG.md` returns: `## [Unreleased]` (line 8), `## [M2 Graph-Layer Adapters] - 2026-04-19` (line 74), `## [M1 Reconciliation] - 2026-04-19` (line 595), `## [Pre-pivot — archived, never released]` (line 1682) — `[Unreleased]` is now at the top, every dated section is correctly labelled, no duplicate headings. Re-ran all three gates post-fix: `uv run pytest` 236 passed, `uv run lint-imports` 3 kept / 0 broken, `uv run ruff check` clean. CHANGELOG T09 entry updated to record the reorder under `Files touched`.

## Additions beyond spec — audited and justified

1. **Outcome section includes an "Exit-criteria verification" numbered list in addition to the four summary buckets the spec names (adapters / providers / checkpointer + smoke graph / green-gate snapshot).** The spec lists those four as required buckets; adding a numbered-list pairing each of the milestone README's six exit criteria with a one-line "where this is verified" pointer directly satisfies AC-1 (`Every exit criterion in the milestone README has a concrete verification`) without making the Outcome section redundant — the four summary buckets document *what shipped*, the numbered verification documents *how each exit criterion was checked*. This is the minimum honest way to grade AC-1 as ✅ rather than hand-waving from "everything shipped" to "therefore every exit criterion is met". Not a scope expansion.

2. **CHANGELOG T09 entry tagged `### Changed` (not `### Added`).** The Builder-conventions template in [CLAUDE.md](../../../../CLAUDE.md) says `### Added — M<N> Task <NN>: <Title>`, but M1 Task 13 (the precedent close-out) used `### Changed — M1 Task 13: Milestone Close-out` at [CHANGELOG.md:595](../../../../CHANGELOG.md#L595). Close-out tasks change milestone status without adding code or features — `### Changed` is the Keep-a-Changelog-correct tag. Following M1's precedent preserves consistency across milestone close-outs.

## Gate summary

Cycle 2 snapshot — taken after the CHANGELOG reorder landed.

| Gate | Result |
| --- | --- |
| `uv run pytest` | ✅ 236 passed, 2 warnings (pre-existing `yoyo` datetime deprecation inside `SQLiteStorage.open`, unrelated to T09 — docs-only task) in 3.14s |
| `uv run lint-imports` | ✅ 3 contracts kept, 0 broken (21 files, 17 deps analyzed) |
| `uv run ruff check` | ✅ All checks passed |
| `README.md` status line flip | ✅ `📝 Planned` → `✅ Complete (2026-04-19)` |
| `roadmap.md` M2 row flip | ✅ `planned` → `✅ complete (2026-04-19)` |
| `CHANGELOG.md` top-of-file `[Unreleased]` | ✅ `## [Unreleased]` now at line 8 holding only the Architecture pivot entry (post-M1-close-out shape restored) |
| `CHANGELOG.md` dated M2 section present | ✅ `## [M2 Graph-Layer Adapters] - 2026-04-19` at line 74 with T09 close-out + T01–T08 entries |
| `CHANGELOG.md` no duplicate headings | ✅ `grep "^## "` returns 4 unique section headings (`[Unreleased]`, `[M2 Graph-Layer Adapters] - 2026-04-19`, `[M1 Reconciliation] - 2026-04-19`, `[Pre-pivot — archived, never released]`) |
| Claimed-path verification | ✅ Every file referenced from the Outcome section resolves (graph modules, `primitives/llm/*`, smoke test) |
| Sibling issue files review | ✅ T01–T08 all `✅ PASS`; no open blockers inherited into T09 |

## Issue log — cross-task follow-up

**M2-T09-ISS-01 — RESOLVED (cycle 2, 2026-04-19).** Originally raised at cycle 1 as a LOW style observation (CHANGELOG `[Unreleased]` sat mid-file). Fixed in cycle 2 via a two-edit reorder: inserted `[Unreleased]` + pivot at the top, removed the mid-file duplicate. Gates re-verified green post-fix. No propagation needed.

No other follow-ups. Every sibling M2 issue file reports `✅ PASS`; M2-T07-ISS-01 was resolved at T08's audit (end-to-end retry-loop proof landed in `tests/graph/test_smoke_graph.py`).

## Deferred to nice_to_have

None.

## Propagation status

- M2-T09-ISS-01 resolved in-cycle (cycle 2) — no forward-deferral required; no target task needs a carry-over section.
- [../task_09_milestone_closeout.md](../task_09_milestone_closeout.md) — no carry-over section needed (all T09 ACs met; no cross-cutting follow-up blocks close-out).
