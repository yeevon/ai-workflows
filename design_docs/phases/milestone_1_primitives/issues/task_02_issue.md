# Task 02 — Shared Types — Audit Issues

**Source task:** [../task_02_shared_types.md](../task_02_shared_types.md)
**Audited on:** 2026-04-18 (initial) · 2026-04-18 (re-audit) · 2026-04-18 (reopened — design-change sweep)
**Audit scope:** full Task 02 surface —
`ai_workflows/primitives/llm/types.py`, `tests/primitives/test_types.py`,
`CHANGELOG.md` (M1 Task 02 section), `pyproject.toml` (no changes
expected), `ai_workflows/primitives/llm/__init__.py`,
`.github/workflows/ci.yml`, milestone `README.md`, all sibling task
files in `milestone_1_primitives/` (to catch cross-task spec drift on
`WorkflowDeps`, `TokenUsage`, `ContentBlock`, `ClientCapabilities`),
and `design_docs/issues.md`. All three gates executed locally; Pydantic
v2 discriminator behaviour independently verified via a REPL probe
(`typing.get_args(ContentBlock)[1]` → `discriminator='type'`). Re-audit
additionally probed `Message.model_json_schema()` (discriminator
present on `content.items`) and mutable-default isolation on
`WorkflowDeps.allowed_executables` (per-instance copy — mutation on one
instance does not leak to a second).
**Status:** 🔴 REOPENED (2026-04-18) — spec was amended post-audit to
adopt the Claude Code CLI design (SD-03). `types.py` still advertises
the pre-amendment literal. See **M1-T02-ISS-06** below. ISS-01 through
ISS-05 remain resolved; ISS-03's "fix" is now stale (captured under the
new issue).

---

## 🔴 HIGH

### M1-T02-ISS-06 — `ClientCapabilities.provider` literal missing `"claude_code"` (OPEN)

**Severity:** HIGH · **Status:** 🔴 OPEN (2026-04-18) — introduced by the SD-03 design change

**What's wrong.** The Task 02 spec
([task_02_shared_types.md:74](../task_02_shared_types.md#L74)) now declares
`provider: Literal["claude_code", "openai_compat", "ollama", "google"]`.
The implementation at
[types.py:87](../../../../ai_workflows/primitives/llm/types.py#L87)
still declares the pre-CLI literal
`Literal["anthropic", "openai_compat", "ollama", "google"]`. Any caller
constructing `ClientCapabilities(provider="claude_code", ...)` — which
Task 03's `_build_claude_code()` branch and Task 07's canonical
`tiers.yaml` will do — fails at Pydantic validation.

**Why this matters.** SD-03 / project-memory
`project_provider_strategy.md` makes `claude_code` a first-class
runtime provider (opus / sonnet / haiku tiers). Blocks the T03-DRIFT
resolution and prevents loading the 5-tier `tiers.yaml`. The stale
ISS-03 resolution (below) captures how the literal was amended before
the CLI design landed; the amendment needs to be extended, not
replaced — per memory, `anthropic` must stay alongside `claude_code` so
the third-party `AnthropicModel` code path keeps a typed home.

**Recommendation.** Update the literal to
`Literal["claude_code", "anthropic", "openai_compat", "ollama", "google"]`
(keeping `anthropic` for third-party callers). Add
`test_client_capabilities_claude_code_provider_roundtrips` mirroring the
ISS-03 test. Update the module docstring's enumeration if present.
Update CHANGELOG with a new subsection under `M1 Task 02`. Reflip
ISS-03's note to point at the new literal shape.

## 🟡 MEDIUM

None.

## 🟢 LOW

### ✅ RESOLVED — M1-T02-ISS-01 — AC-3 test accepts any one literal instead of asserting all three

**Resolved on:** 2026-04-18

Changed `or` to `and` in `test_invalid_type_raises_validation_error` — all
three discriminator tag names (`text`, `tool_use`, `tool_result`) must now
appear in the Pydantic error string. Replacing the discriminated union with a
plain `Union` would break the test as intended.

### ✅ RESOLVED — M1-T02-ISS-02 — AC-2 timing test has no CI fudge factor

**Resolved on:** 2026-04-18 (option (b), per user direction).

`tests/primitives/test_types.py::test_fifty_tool_use_blocks_parse_quickly`
threshold raised from `< 5 ms` to `< 25 ms` with an inline comment
explaining the 5× CI headroom and the regression-detection intent.
Spec's 5-ms target is documented in the comment as the actual
performance contract; the 25-ms ceiling only exists to keep short-
window wall-clock flakes from blocking CI. Local re-run: test still
passes in ~0.06 s overall.

**Verdict:** fully resolved.

### ✅ RESOLVED — M1-T02-ISS-03 — `ClientCapabilities.provider` literal omits `google`

**Resolved on:** 2026-04-18

Extended `provider` literal to `Literal["anthropic", "openai_compat", "ollama", "google"]`
in `types.py` and `task_02_shared_types.md`. Added
`test_client_capabilities_google_provider_roundtrips` in `tests/primitives/test_types.py`
(verifies JSON round-trip with `max_context=1_000_000` and `provider="google"`).
Task 03 Builder can consume the extended literal without touching Task 02 files.

> **Superseded by M1-T02-ISS-06 (2026-04-18):** the post-CLI design
> (SD-03) requires adding `"claude_code"` to the literal. The ISS-03
> shape above is the pre-CLI state; the amended shape includes
> `"claude_code"` alongside `"anthropic"`. See ISS-06 for the fix.

### ✅ RESOLVED — M1-T02-ISS-04 — `design_docs/issues.md` entries for CRIT-05 and CRIT-09 still marked `[ ]`

**Resolved on:** 2026-04-18

- **CRIT-09** flipped to `[x]` with "Resolved by M1 Task 02" pointer.
- **CRIT-05** flipped to `[~]` with note: type declared in M1 Task 02; per-adapter
  factory wiring lands in M1 Task 03.

### ✅ RESOLVED — M1-T02-ISS-05 — Task-completion marking not applied

**Resolved on:** 2026-04-18 (same-day re-audit follow-up).

- [`task_02_shared_types.md`](../task_02_shared_types.md) — added
  top-of-file `**Status:** ✅ Complete (2026-04-18) — see
  [issues/task_02_issue.md](issues/task_02_issue.md).` line and
  ticked all four AC checkboxes to `[x]`.
- [`../README.md`](../README.md) line 53 — appended `— ✅
  **Complete** (2026-04-18)` to the Task 02 entry, matching the
  Task 01 convention on line 52.
- `CHANGELOG.md` — logged under the existing M1 Task 02 `[Unreleased]`
  heading as a `#### Completion marking` subsection (parallels the
  Task 01 pattern).

**Verdict:** fully resolved. No code or test changes were needed;
design-doc bookkeeping only.

---

## Additions beyond spec — audited and justified

| Addition | Justification |
| --- | --- |
| Module docstring citing "Produced by M1 Task 02" | CLAUDE.md §Non-negotiables requires module docstrings to name the producing task. |
| Per-class docstrings on every public type | CLAUDE.md requires "every public class and function has a docstring". |
| `test_message_parses_tool_use_block_from_dict` / `_tool_result_block_from_dict` / `_mixed_content` | Complements AC-1 — AC phrased the example as `text` only, but a real discriminator must dispatch all three variants. Zero added risk; explicit coverage. |
| `test_all_types_importable` | Cheap smoke test — if a future edit to `__init__.py` accidentally hides a symbol, this fails fast. |
| `test_token_usage_defaults` / `test_workflow_deps_defaults` / `test_response_model` | Sibling tasks (T03, T09, T10) depend on these defaults; pinning them now avoids a downstream-task regression. |

No additions introduce imports outside `pydantic` + stdlib. No
adapter-specific types leaked into `primitives/llm/types.py`.

---

## Gate summary

| Gate | Result (initial) | Result (re-audit) |
| --- | --- | --- |
| `uv run pytest` | ✅ 41/41 | ✅ 41/41 (15 Task 02 + 26 Task 01) — 0.39 s |
| `uv run lint-imports` | ✅ 2 kept / 0 broken | ✅ 2 kept / 0 broken — primitives still free of components/workflows imports |
| `uv run ruff check` | ✅ | ✅ All checks passed |
| `import ai_workflows.primitives.llm.types` (REPL) | ✅ `get_args(ContentBlock)[1].discriminator == "type"` | ✅ re-verified |
| `Message.model_json_schema()` exposes discriminator | — (not probed initially) | ✅ `discriminator` present on `content.items` |
| `WorkflowDeps.allowed_executables` mutable-default safety | — (not probed initially) | ✅ Pydantic v2 per-instance copy — one instance's `.append()` does not leak to a second |
| `ClientCapabilities` JSON round-trip (REPL) | ✅ All 8 fields serialised | ✅ re-verified |
| Pydantic discriminator error names all three tags (REPL) | ✅ `'text', 'tool_use', 'tool_result'` all present | ✅ re-verified |
| CHANGELOG entry format matches CLAUDE.md prescription | ✅ `### Added — M1 Task 02: Shared Types (2026-04-18)` | ✅ unchanged |

---

## Acceptance-criterion grading

| AC | Verdict | Evidence |
| --- | --- | --- |
| AC-1: discriminated union dispatches `{"type":"text","text":"hi"}` | ✅ PASS | `test_message_parses_text_block_from_dict` + three sibling block-parse tests + REPL discriminator inspection |
| AC-2: 50 tool_use blocks parse < 5 ms | ✅ PASS | `test_fifty_tool_use_blocks_parse_quickly` — elapsed well under 1ms locally (see ISS-02 re: CI headroom) |
| AC-3: invalid `type` raises clear error naming allowed literals | ✅ PASS (test is weaker than the AC — see ISS-01) | `test_invalid_type_raises_validation_error`; REPL verified Pydantic message lists all three tags |
| AC-4: `ClientCapabilities` JSON serializable (round-trip lossless) | ✅ PASS | `test_client_capabilities_roundtrips_json` + `_dict` + `_serializes_to_json` |

---

## Issue log — tracked for cross-task follow-up

- **M1-T02-ISS-01** (LOW) ✅ RESOLVED (2026-04-18) — AC-3 test assertion
  tightened from `or` to `and`; all three discriminator tags must appear.
- **M1-T02-ISS-02** (LOW) ✅ RESOLVED (2026-04-18) — threshold widened
  to `< 25 ms` with a comment citing the 5-ms spec target and the 5× CI
  headroom intent.
- **M1-T02-ISS-03** (LOW) ✅ RESOLVED (2026-04-18) — `"google"` added to
  `ClientCapabilities.provider` literal; spec and tests updated.
- **M1-T02-ISS-04** (LOW) ✅ RESOLVED (2026-04-18) — CRIT-09 flipped
  `[x]`, CRIT-05 flipped `[~]` in `design_docs/issues.md`.
- **M1-T02-ISS-05** (LOW) ✅ RESOLVED (2026-04-18) — task spec
  AC checkboxes ticked and top-of-file `Status: ✅ Complete` line
  added; milestone README entry flagged `— ✅ **Complete**
  (2026-04-18)`; CHANGELOG updated with a completion-marking
  subsection.
- **M1-T02-ISS-06** (HIGH) 🔴 OPEN (2026-04-18) — `ClientCapabilities.provider`
  literal in `types.py` still reads `["anthropic", ...]`; spec was
  amended to `["claude_code", ...]` when SD-03 landed. Fix: extend the
  literal to `["claude_code", "anthropic", "openai_compat", "ollama",
  "google"]` (keep `anthropic` for third-party callers per project
  memory), add round-trip test for `claude_code`. Blocks Task 03
  claude_code branch + Task 07 tiers.yaml load. Must be paired with
  M1-T02 task-status flip (✅ Complete → 🔴 Reopened) until fixed.
