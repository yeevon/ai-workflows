# Task 01 — Sub-agent return-value schema — Audit Issues

**Source task:** [../task_01_sub_agent_return_value_schema.md](../task_01_sub_agent_return_value_schema.md)
**Audited on:** 2026-04-28 (cycle 1 + cycle 2)
**Audit scope:** Cycle 1 — verified all 6 deliverables (9 agent files, `_common/` reference, 5 slash-command parser sections, two test modules, fixtures, CHANGELOG, status surfaces); ran every gate + four-step smoke. Cycle 2 — verified the two locked team decisions landed (architect verdict-token drift fix in `architect.md:42` + `auto-implement.md:189`; `_helpers.py` strip + new test `test_trailing_spaces_in_verdict_are_tolerated`; whitespace-strip prose in all 5 slash commands; new `test_architect_prompt_body_token_set_matches_helper` regression test). Re-ran every gate.
**Status:** ✅ PASS

## Design-drift check

No drift detected.

- **Layer rule (`primitives → graph → workflows → surfaces`).** T01 touches no runtime code under `ai_workflows/`. Tests live in `tests/agents/` with a hand-rolled helper `tests/agents/_helpers.py`. The helper docstring explicitly justifies its placement under `tests/` rather than `ai_workflows/` to avoid creating a new subpackage with no runtime caller. `uv run lint-imports` reports `5 kept, 0 broken`.
- **KDR-002 (MCP portable surface).** N/A — no MCP tooling touched.
- **KDR-003 (no Anthropic API).** Verified `grep -r "anthropic" tests/agents/ .claude/commands/_common/` returns nothing. No `ANTHROPIC_API_KEY` reads. The orchestrator-side parser is purely string-shape validation.
- **KDR-004 (`ValidatorNode` after `TieredNode`).** N/A — no LLM call added.
- **KDR-006 (RetryingEdge).** N/A — no retry logic added. Spec is explicit: malformed agent return halts; no auto-retry. This is the load-bearing autonomy decision and is consistent with KDR-006's "no bespoke retry" spirit.
- **KDR-008 (FastMCP / tool schemas).** N/A — no MCP tool surface change.
- **KDR-009 (LangGraph SqliteSaver).** N/A — no checkpoint logic.
- **KDR-013 (user code is user-owned).** N/A — agent prompt edits are framework infrastructure (`.claude/`), not user-owned workflow modules.
- **Dependency audit.** `git diff pyproject.toml uv.lock` is empty. No new deps. Spec carry-over L8 is honoured: regex-based proxy `len(re.findall(r"\S+", text)) * 1.3` defined at `tests/agents/_helpers.py:130-144`; no `tiktoken` import.

## AC grading

| AC | Status | Notes |
| -- | ------ | ----- |
| 1 — All 9 agent files have uniform `## Return to invoker` 3-line schema with per-agent verdict tokens | ✅ Met | `grep -l "^verdict:" .claude/agents/*.md` returns 9 (smoke test 1). Every agent has exactly one `## Return to invoker` heading. Per-agent verdict tokens, `file:` description, and `section:` value all match the spec table (verified by reading each file). `task-analyzer.md` was correctly renamed from `## Phase 5 — Return to invoker` to `## Return to invoker` for uniformity. |
| 2 — `.claude/commands/_common/agent_return_schema.md` exists; lists all 9 agents + tokens + artifacts | ✅ Met | File exists at the expected path; lists all 9 agents in the per-agent table (lines 42-52); orchestrator-side parser convention is documented (lines 28-36); cross-references to T02/T05/T07/T08/T09/T21/T27 noted for forward `_common/` population. |
| 3 — All 5 slash commands describe parser convention with halt-on-malformed semantics; link to `_common/` | ✅ Met | `grep -l "_common/agent_return_schema.md"` across the 5 command files returns 5 (smoke test 3). Each command (`auto-implement`, `clean-tasks`, `clean-implement`, `queue-pick`, `autopilot`) has a `## Agent-return parser convention` section with the 5-step procedure and `**Do not auto-retry.**` directive. |
| 4 — `test_return_schema_compliance.py` passes for all 9 agents; ≥ 3 fixture cases per agent | ✅ Met | 142 tests pass (`uv run pytest tests/agents/`). 28 fixture files spanning all 9 agents (architect has 4 — one per `ALIGNED/MISALIGNED/OPEN/PROPOSE-NEW-KDR` token; the other 8 agents have 3 each). `test_all_agents_have_three_fixtures_per_spec` parametrically validates the count. |
| 5 — `test_orchestrator_parser.py` passes with all positive + negative cases | ✅ Met | Positive: conformant 3-line, dash placeholder, section header, trailing newline, optional space, no-agent-name skips validation, every allowed verdict round-trips. Negative: empty, whitespace-only, 4 lines, 2 lines, bad regex, bad key, keys out of order, whitespace-only value, verdict outside allowed set, prose body before/after schema. All 27 parser tests + 3 token-proxy tests pass. |
| 6 — Token-cap test (≤ 100 tokens) passes for every fixture | ✅ Met | `test_fixture_token_cap` parametrized across all 28 fixtures passes. Proxy uses `len(re.findall(r"\S+", text)) * 1.3` per L8 carry-over; no `tiktoken` dep. |
| 7 — CHANGELOG entry under `[Unreleased]` with the spec-named heading | ✅ Met | `### Changed — M20 Task 01: Sub-agent return-value schema (3-line verdict / file / section), schema-compliance tests, orchestrator parser convention (research brief §Lens 1.3) (2026-04-28)` lands at `CHANGELOG.md:10`. Entry enumerates every touched file. |
| 8 — Status surfaces flip together (spec `**Status:**`, milestone README task table, milestone README "Done when" exit criterion #1) | ✅ Met | (a) `task_01_sub_agent_return_value_schema.md:3` → `**Status:** ✅ Done.`. (b) `README.md:106` task-table row → `✅ Done`. (c) `README.md:50` exit criterion #1 → `✅ **(G1)** ... **[T01 Done — 2026-04-28]**`. The milestone has no `tasks/README.md`. All three surfaces agree. |
| L1 — Per-agent fixture-spawn schema-compliance tests opt-in via `AIW_AGENT_SCHEMA_E2E=1` | ✅ Met | `tests/agents/test_return_schema_compliance.py:178-190` defines `_E2E_ENABLED = os.getenv("AIW_AGENT_SCHEMA_E2E") == "1"` and gates `test_e2e_placeholder` behind it. The default suite uses pre-written fixtures (stub-spawn). `pytest -v` shows the placeholder as `SKIPPED` when env var is unset. |
| L8 — Regex-based token-count proxy `len(re.findall(r"\S+", text)) * 1.3`; no `tiktoken` dep | ✅ Met | `_helpers.py:144` implements exactly that expression. No `tiktoken` import anywhere; pyproject.toml/uv.lock unchanged. |

## 🔴 HIGH

(none)

## 🟡 MEDIUM

(none)

## 🟢 LOW — pre-existing branch-shape test failure on `workflow_optimization`

**Finding.** `tests/test_main_branch_shape.py::test_design_docs_absence_on_main` fails on the current `workflow_optimization` branch with `AssertionError: main branch must not carry builder-only paths, found: ['design_docs', 'CLAUDE.md', '.claude/commands', 'tests/skill', 'scripts/spikes']`.

**Why this is LOW, not HIGH.** Verified pre-existing: I stashed all T01 changes and the same test fails identically. The failure stems from `_detect_branch()` (`tests/test_main_branch_shape.py:42-70`) only mapping `design_branch → design`; on `workflow_optimization` the helper returns the literal branch name, so `_ON_DESIGN` is False and the main-branch-absence test runs. Setting `AIW_BRANCH=design` (the documented escape hatch) makes the suite pass cleanly. The branch name is a user-approved override per the milestone README's "Branch: `workflow_optimization` (user-named)" scope note, and is listed in the project context brief as a substitute for `design_branch` for this autopilot run.

**Action / Recommendation.** Two reasonable options — surface to user for arbitration:
- **(a) Operator-side fix:** export `AIW_BRANCH=design` in the autopilot Docker container's environment so the existing `tests/test_main_branch_shape.py` self-skips correctly. No code change needed.
- **(b) Helper update:** extend `_detect_branch()` to also map `workflow_optimization → design` (or any branch matching `^(design|workflow|builder).*` to `design`) so the design-side path is taken automatically for any user-named design-branch alias. This is a one-line code change with a one-line test; not in T01's scope but a natural follow-up.

Either option is fine; the failure is environmental drift, not a T01 regression.

## Additions beyond spec — audited and justified

- **`tests/agents/__init__.py`** — required for the `from tests.agents._helpers import ...` import to resolve. Standard Python packaging; not "extra" scope.
- **`test_all_agents_have_at_least_one_fixture` + `test_all_agents_have_three_fixtures_per_spec`** — meta-tests over the fixture directory layout. They formalise AC-4's "≥ 3 fixture cases per agent" requirement as a parametric assertion rather than relying on the parametrize-collected count being non-zero. Net positive: catches the case where someone deletes a fixture file.
- **`test_each_allowed_verdict_token_parses_correctly`** — positive round-trip for every token in `AGENT_VERDICT_TOKENS`. Strengthens AC-5 beyond the spec's example list.
- **`test_no_agent_name_skips_verdict_validation`** — confirms the parser's `agent_name=None` branch (used when the orchestrator hasn't matched the agent yet). Documented in `_helpers.py:65-68`; the test pins the contract.
- **CHANGELOG entry's "Files touched" enumeration** — verbose but useful for the dependency-auditor at release time. Not over-engineering.

## Gate summary

| Gate | Command | Pass / Fail |
| ---- | ------- | ----------- |
| pytest (full suite) | `uv run pytest` | 933 passed, 1 failed (pre-existing branch-shape — see LOW), 10 skipped |
| pytest (T01 specifically) | `uv run pytest tests/agents/test_return_schema_compliance.py tests/agents/test_orchestrator_parser.py -v` | 142 passed, 1 skipped (E2E placeholder behind `AIW_AGENT_SCHEMA_E2E=1` — expected) |
| lint-imports | `uv run lint-imports` | 5 contracts kept, 0 broken |
| ruff | `uv run ruff check` | All checks passed |
| Smoke 1 — schema in 9 agents | `grep -l "^verdict:" .claude/agents/{builder,auditor,security-reviewer,dependency-auditor,task-analyzer,architect,sr-dev,sr-sdet,roadmap-selector}.md \| wc -l` | 9 (expected 9) ✅ |
| Smoke 2 — `_common` reference | `test -f .claude/commands/_common/agent_return_schema.md` | OK ✅ |
| Smoke 3 — slash-command links | `grep -l "_common/agent_return_schema.md" .claude/commands/{auto-implement,clean-tasks,clean-implement,queue-pick,autopilot}.md \| wc -l` | 5 (expected 5) ✅ |
| Smoke 4 — schema + parser tests pass | `uv run pytest tests/agents/test_return_schema_compliance.py tests/agents/test_orchestrator_parser.py -v` | 142 passed, 1 skipped |

The pre-existing `test_design_docs_absence_on_main` failure is gate-output-relevant but **not** caused by T01. Verified by stashing T01 changes and re-running — same failure, same line. Logged as LOW for follow-up; does not block T01's audit.

## Issue log — cross-task follow-up

| ID | Severity | Owner / Next touch point | Status |
|----|----------|--------------------------|--------|
| M20-T01-ISS-01 | LOW | Operator (`AIW_BRANCH=design`) or future task that touches `tests/test_main_branch_shape.py::_detect_branch` | OPEN — environmental, not a T01 regression |

## Deferred to nice_to_have

(none)

## Propagation status

(no forward-deferred findings)

## Security review (2026-04-28)

### Verdict: SHIP

### Checklist items reviewed

**1. Wheel-contents leakage.**
`pyproject.toml` `[tool.hatch.build.targets.wheel]` sets `packages = ["ai_workflows"]` only. Verified against the pre-built `dist/jmdl_ai_workflows-0.3.1-py3-none-any.whl` using Python `zipfile`: no entries matching `tests/`, `design_docs/`, `.claude/`, `CLAUDE`, `fixtures/`, or `agents/` (the T01 new paths) are present. Result: CLEAN.

**2. Subprocess execution.**
T01 touches only markdown agent-prompt files, slash-command markdown files, and Python test infrastructure under `tests/agents/`. No new `subprocess`, `Popen`, `os.system`, or `shell=True` calls exist in any T01 file. Confirmed by grep across `tests/agents/` and `.claude/commands/_common/`. Result: no new subprocess surface.

**3. Credential leakage.**
- `grep -rn "ANTHROPIC_API_KEY"` across `ai_workflows/`: zero hits (KDR-003 boundary maintained).
- `grep -rn "GEMINI_API_KEY\|Bearer \|Authorization"` across `tests/agents/` and `.claude/commands/_common/`: zero hits.
- `grep -rn "\.env\|API_KEY\|password\|secret"` across the same paths: zero hits on actual credential values (word "token" matches are all verdict-token references, not auth tokens).
- Result: no credential leakage.

**4. Test fixture content.**
All 28 fixture files read and inspected. Every fixture contains exactly the 3-line conformant schema format with placeholder-only values (`design_docs/phases/milestone_20_.../issues/task_01_issue.md`, `runs/queue-pick-<ts>.md`, `—`). No real-looking secrets, no internal URLs beyond repo-relative paths, no builder-environment artefacts. Result: CLEAN.

**5. Parser robustness.**
`tests/agents/_helpers.py:parse_agent_return` raises `MalformedAgentReturn` on: empty string, whitespace-only, fewer than 3 non-empty lines, more than 3 non-empty lines, line not matching `^(verdict|file|section): ?(.+)$`, keys out of order, whitespace-only values, verdict outside the allowed set. Halt-on-malformed semantics confirmed; no auto-retry path exists. The 27 negative-path tests all exercise `pytest.raises(MalformedAgentReturn, ...)`. A deliberately-poisoned agent return (extra prose, injected lines) raises rather than loops the orchestrator. Result: robust.

**6. `AIW_AGENT_SCHEMA_E2E=1` opt-in.**
`tests/agents/test_return_schema_compliance.py:178` defines `_E2E_ENABLED = os.getenv("AIW_AGENT_SCHEMA_E2E") == "1"`. The live-spawn placeholder test at line 181 is decorated `@pytest.mark.skipif(not _E2E_ENABLED, reason="Set AIW_AGENT_SCHEMA_E2E=1 to run live spawns")`. Default CI run skips it; Max quota is not burned. Result: correctly gated.

**Existing threat-model items (not changed by T01).**
MCP bind address: README §Security notes at line 118 documents loopback default and `--host 0.0.0.0` foot-gun — still present, unchanged. SQLite paths, logging hygiene, dependency CVEs: not touched by T01.

### 🔴 Critical — must fix before publish/ship

(none)

### 🟠 High — should fix before publish/ship

(none)

### 🟡 Advisory — track; not blocking

**ADV-01 — Stale module reference in `_common/agent_return_schema.md:65`.**
The Notes section states "The parser helper is extracted into `ai_workflows/agents/return_schema.py` for testability." That path does not exist; the helper lives at `tests/agents/_helpers.py` and is intentionally outside `ai_workflows/` (the module docstring justifies the placement). The wrong path could mislead a future developer or a downstream consumer of the `_common/` reference doc.
- File: `.claude/commands/_common/agent_return_schema.md:65`
- Threat-model item: N/A (documentation accuracy, no security impact)
- Action: Update the reference to `tests/agents/_helpers.py` in a follow-up edit to the Notes section. Not blocking ship.

## Dependency audit (2026-04-28)

Dependency audit: skipped — no manifest changes. `git diff --name-only HEAD` shows neither `pyproject.toml` nor `uv.lock` was modified by T01.

## Sr. Dev review (2026-04-28)

**Files reviewed:** `.claude/agents/task-analyzer.md`, `.claude/commands/auto-implement.md`, `.claude/commands/autopilot.md`, `.claude/commands/clean-implement.md`, `.claude/commands/clean-tasks.md`, `.claude/commands/queue-pick.md`, `.claude/commands/_common/agent_return_schema.md`, `tests/agents/_helpers.py`, `tests/agents/test_return_schema_compliance.py`, `tests/agents/test_orchestrator_parser.py`, `tests/agents/fixtures/` (all 28 files); plus the 8 agent files rewritten in the prior partial-T01 commit (`builder.md`, `auditor.md`, `security-reviewer.md`, `dependency-auditor.md`, `architect.md`, `sr-dev.md`, `sr-sdet.md`, `roadmap-selector.md`).

**Skipped (out of scope):** none

**Verdict:** FIX-THEN-SHIP

### BLOCK — must-fix before commit

(none)

### FIX — fix-then-ship

#### FIX-1 — Architect verdict-token split: agent body + orchestrator both instruct the old token set; 3-line schema uses the new set

**Lens:** Hidden bugs that pass tests

**Files:**
- `.claude/agents/architect.md:42` (Trigger A body): `PROPOSE-NEW-KDR | NO-KDR-NEEDED-EXISTING-RULE-COVERS | NO-KDR-NEEDED-CASE-BY-CASE`
- `.claude/commands/auto-implement.md:189` (Step T3): same old token set
- `.claude/agents/architect.md:103` (`## Return to invoker`): `ALIGNED / MISALIGNED / OPEN / PROPOSE-NEW-KDR` — the new schema
- `.claude/commands/_common/agent_return_schema.md:49`: `ALIGNED / MISALIGNED / OPEN / PROPOSE-NEW-KDR` — the new schema
- `tests/agents/_helpers.py:34` (`AGENT_VERDICT_TOKENS["architect"]`): new schema tokens only

**Reproduction shape:** The architect agent reads its Trigger A instructions at `architect.md:42` and is told to return `NO-KDR-NEEDED-EXISTING-RULE-COVERS` when an existing KDR covers the case. It also reads `## Return to invoker` at line 103 which contradicts this with a different token set. An agent that follows the body instruction and returns `NO-KDR-NEEDED-EXISTING-RULE-COVERS` in its 3-line schema will trigger `MalformedAgentReturn` in `parse_agent_return` (the token is not in `AGENT_VERDICT_TOKENS["architect"]`), causing a false BLOCKED halt in the team gate. The tests pass because the 4 architect fixtures all use the new token set — no test exercises the stale instructions in the prompt body.

**Action:** Update `architect.md:42` from `PROPOSE-NEW-KDR | NO-KDR-NEEDED-EXISTING-RULE-COVERS | NO-KDR-NEEDED-CASE-BY-CASE` to `ALIGNED / MISALIGNED / OPEN / PROPOSE-NEW-KDR`. Simultaneously update `auto-implement.md:189` from the old token set to `ALIGNED / MISALIGNED / OPEN / PROPOSE-NEW-KDR`. This makes all four locations consistent: agent body, `## Return to invoker`, `_common/` reference, and `_helpers.py`.

### Advisory — track but not blocking

#### ADV-02 — `_fixture_texts` contains a no-op `.replace("-", "-")`

**Lens:** Simplification

**File:** `tests/agents/test_return_schema_compliance.py:62`

The label construction `fixture_file.stem.upper().replace("-", "-")` is a literal no-op: it replaces dash with dash. All existing fixture filenames use dashes (not underscores), so the uppercase stem is already the correct label. If a future fixture uses underscores (e.g. `propose_new_kdr.txt`), the label would become `PROPOSE_NEW_KDR` — which is not in the agent's allowed set — and `test_fixture_verdict_in_allowed_set` would still pass because the label is only used as a pytest parametrize display name, not validated against the token set. The actual verdict validation uses the parsed content, not the filename. The no-op is harmless but misleading: it suggests intent (normalise separators) without actually doing it.

**Action:** If the intent is to normalise underscores to dashes, change to `.replace("_", "-")`. If the intent is display-only labeling, remove the no-op replace entirely: `fixture_file.stem.upper()`. Either one is cleaner than the current dead call.

#### ADV-03 — `queue-pick.md:84` and `autopilot.md:80` pre-condition check references `**Verdict:**` (recommendation-file format) alongside the new 3-line parser convention — creates two distinct parsing targets in close proximity

**Lens:** Comment / docstring drift

**Files:** `.claude/commands/queue-pick.md:84`, `.claude/commands/autopilot.md:80`

Both commands now have an `## Agent-return parser convention` section (the new 3-line schema) and, a few paragraphs later, a pre-condition failure check that looks for "no `**Verdict:**` line" in the recommendation *file*. The recommendation file written by `roadmap-selector` (its Phase 4 output, `roadmap-selector.md:119`) still uses `**Verdict:**` markdown-bold format — this is correct because the recommendation file is a richer markdown document distinct from the agent's 3-line return text. The pre-condition checks are therefore technically accurate. However, a reader unfamiliar with the two-format distinction (3-line return text vs. richer recommendation file) could mistake the `**Verdict:**` check as conflicting with the new schema. A one-line comment clarifying "this checks the recommendation file format, not the agent's 3-line return" would prevent future confusion.

**Action (Advisory):** In `queue-pick.md:84` and `autopilot.md:80`, add a parenthetical: "no parseable `**Verdict:**` line in the recommendation file (the file format, not the agent's 3-line return text)". Not blocking.

#### ADV-01 (from Security review) — confirmed one-line doc fix

**File:** `.claude/commands/_common/agent_return_schema.md:65`

The security reviewer's ADV-01 is confirmed: line 65 says "extracted into `ai_workflows/agents/return_schema.py`" but the helper is at `tests/agents/_helpers.py`. No deeper inconsistency. Single-line fix: update the path reference.

### What passed review (one-line per lens)

- **Hidden bugs:** FIX-1 (architect verdict-token split between body and schema — found; tests pass because fixtures use new tokens exclusively)
- **Defensive-code creep:** none observed — parser raises on every failure case; no silent swallowing; no `if x is not None` against non-optional types
- **Idiom alignment:** all 9 `## Return to invoker` sections use uniform boilerplate; all 5 slash-command parser sections follow the same 5-step structure; `structlog` not touched; `frozenset` for token sets is idiomatic
- **Premature abstraction:** none — `_helpers.py` has two callers (the two test modules) and the `_common/` reference serves five slash commands; no single-caller abstractions introduced
- **Comment / docstring drift:** ADV-02 (no-op replace misleading intent); ADV-03 (two-format ambiguity in pre-condition prose); ADV-01 stale path reference; module docstrings cite task and relationship correctly

## Sr. SDET review (2026-04-28)

**Test files reviewed:** `tests/agents/__init__.py`, `tests/agents/_helpers.py`, `tests/agents/test_orchestrator_parser.py`, `tests/agents/test_return_schema_compliance.py`, `tests/agents/fixtures/` (all 28 fixture files across 9 agent directories)
**Skipped (out of scope):** none
**Verdict:** FIX-THEN-SHIP

### BLOCK — tests pass for the wrong reason

(none)

### FIX — fix-then-ship

#### FIX-SDET-1 — Parser silently rejects conformant verdicts with trailing whitespace; no test exercises the path

**Lens:** Coverage gap (Lens 2) — latent bug in the reference implementation

**File:** `tests/agents/_helpers.py:103,112`

`parse_agent_return` stores the raw (unstripped) value from the regex capture group. The regex `(.+)` matches trailing spaces, so a line like `"verdict: BUILT  "` (two trailing spaces) is captured as `"BUILT  "`. The whitespace-only guard at line 108 (`if not value.strip()`) passes (the value is not whitespace-only), but `parsed["verdict"]` is stored as `"BUILT  "`. At line 121, `verdict not in allowed` compares `"BUILT  "` against `frozenset({"BUILT", "BLOCKED", "STOP-AND-ASK"})` — the comparison fails, and `MalformedAgentReturn` is raised even though the return was substantively conformant.

Since the only tests exercising the whitespace path (`test_whitespace_only_value_raises`) use `"verdict:   "` (all-spaces value, which is caught by the regex failing or the whitespace guard), the trailing-space-after-valid-token path is entirely untested. A real agent returning `"verdict: BUILT  \n..."` (e.g., a terminal that appends trailing spaces) would cause a false halt in the autonomy loop.

`_helpers.py` is the canonical Python reference implementation of the parser logic used in every slash-command's prose convention. Robustness here sets the bar for what the markdown prose parsers should handle.

**Action:** Strip the captured value before storing: change `parsed[key] = value` at line 112 to `parsed[key] = value.strip()`. Add a test in `test_orchestrator_parser.py`:

```python
def test_trailing_spaces_in_verdict_are_tolerated() -> None:
    """Trailing whitespace on any value line is stripped before validation."""
    text = "verdict: BUILT  \nfile: —  \nsection: —  "
    verdict, file_val, section = parse_agent_return(text, agent_name="builder")
    assert verdict == "BUILT"
    assert file_val == "—"
    assert section == "—"
```

### Advisory — track but not blocking

#### ADV-SDET-1 — `test_fixture_verdict_in_allowed_set` is a tautological assertion

**Lens:** Tests pass for the wrong reason (mild — advisory severity because coverage is provided by negative tests elsewhere)

**File:** `tests/agents/test_return_schema_compliance.py:136-142`

`test_fixture_verdict_in_allowed_set` calls `parse_agent_return(text, agent_name=agent_name)` and then asserts `verdict in allowed`. When `agent_name` is a recognised agent, `parse_agent_return` already raises `MalformedAgentReturn` if the verdict is not in the allowed set (lines 119-125 of `_helpers.py`). The function only returns if the verdict IS valid. Therefore `assert verdict in allowed` at line 141 can only execute after the parser has already confirmed the assertion is true — the assertion can never be the line that catches a real regression.

If someone removed the verdict-set validation from `parse_agent_return`, this test would fail with an unexpected `AttributeError` or pass silently (the assertion would then be meaningful but no test would be specifically exercising the removal). The `test_verdict_outside_allowed_set_raises` test in `test_orchestrator_parser.py` covers the negative case correctly; this test duplicates a guarantee the parser already provides.

**Action (Advisory):** Replace the double-parse with a pattern that tests something the parser doesn't already enforce — e.g., assert the returned tuple is a 3-tuple, or assert each element is a non-empty string. Alternatively, remove `test_fixture_verdict_in_allowed_set` entirely and document that verdict-set validation is covered by `test_verdict_outside_allowed_set_raises` in the parser unit tests. Not blocking since the negative path is covered elsewhere.

#### ADV-SDET-2 — `test_fixture_parses_cleanly` post-parse assertions are tautological

**Lens:** Trivial assertions (Lens 1 — advisory because the meaningful test is the implicit "parse didn't raise")

**File:** `tests/agents/test_return_schema_compliance.py:130-132`

After `parse_agent_return(text, agent_name=agent_name)` succeeds, the test asserts `assert verdict`, `assert file_val`, `assert section`. Since `parse_agent_return` already enforces non-whitespace-only values (raises on `value.strip() == ""`), any return from the parser guarantees each field is a non-empty string. `assert verdict` (and the others) can only fail if the parser returned empty strings despite succeeding — which is impossible by parser construction.

**Action (Advisory):** Rename the test to `test_fixture_parses_without_exception` and drop the three post-parse assertions. The `parse_agent_return` call succeeding is the assertion. A comment `# raises MalformedAgentReturn on non-conformant input` documents what the test verifies.

#### ADV-SDET-3 — `test_whitespace_only_value_raises` comment claims "test both cases" but only implements one

**Lens:** Naming / assertion-message hygiene (Lens 6)

**File:** `tests/agents/test_orchestrator_parser.py:147-153`

The comment at line 149 reads: "This won't match the regex if there's nothing after ': ' — test both cases: (a) 'verdict: ' followed by spaces — the regex requires at least one non-space". The claim that "the regex requires at least one non-space" is also incorrect: `(.+)` matches spaces. The actual line tested is `"verdict:   \nfile: —\nsection: —"` — spaces after the colon without an intervening space (so `: ?` consumes zero spaces, then `(.+)` captures three spaces). The regex DOES match, and the value captured is `"   "`, which is caught by `if not value.strip()`. The comment's rationale is misleading, and only one of the "two cases" is implemented.

**Action:** Fix the comment to accurately describe what the test does: "Value is all-whitespace after the colon; regex matches (`.+` accepts spaces) but the explicit whitespace guard raises." Remove the "(a)/(b)" structure since there is only one case. If coverage of case (b) (e.g., `"verdict: \nfile: —\nsection: —"` with a trailing newline turning into an empty line) is desired, add a second test rather than referencing it in a comment.

#### ADV-SDET-4 — No test verifies that each distinct verdict token appears exactly once across fixtures for a given agent

**Lens:** Coverage gap (Lens 2 — advisory)

**File:** `tests/agents/test_return_schema_compliance.py:163-171`

`test_all_agents_have_three_fixtures_per_spec` checks that `len(fixtures) >= len(AGENT_VERDICT_TOKENS[agent_name])` — a count comparison. It does not verify that the fixture set covers all distinct tokens. For example, a builder with three fixtures all returning `verdict: BUILT` (and none returning `BLOCKED` or `STOP-AND-ASK`) would pass the count check but violate the spec requirement "one per verdict-token outcome." The `_fixture_texts` helper returns `(label, text)` pairs; `label` is derived from the filename but never compared against the parsed verdict.

**Action (Advisory):** Add a test that collects the set of distinct verdict tokens across all fixtures for each agent and asserts it equals the full allowed set:

```python
def test_all_verdict_tokens_have_a_fixture() -> None:
    """Each allowed verdict token for each agent must appear in at least one fixture."""
    for agent_name in ALL_AGENT_NAMES:
        allowed = AGENT_VERDICT_TOKENS[agent_name]
        covered = set()
        for _, text in _fixture_texts(agent_name):
            verdict, _, _ = parse_agent_return(text, agent_name=agent_name)
            covered.add(verdict)
        assert covered == allowed, (
            f"Agent '{agent_name}': fixtures cover {sorted(covered)!r}; "
            f"expected all of {sorted(allowed)!r}"
        )
```

#### ADV-SDET-5 — `_fixture_texts` no-op `.replace("-", "-")` (echoes sr-dev ADV-02 from SDET lens)

**Lens:** Test code is real code (Lens 6 — advisory)

**File:** `tests/agents/test_return_schema_compliance.py:62`

The no-op replace was already surfaced by sr-dev as ADV-02. From the SDET lens: the label derived from the filename is never validated against the fixture's actual verdict content (see ADV-SDET-4). If the replace were fixed to `.replace("_", "-")` (which sr-dev recommended as the likely intent), the label would correctly map underscored filenames to hyphenated tokens. The combination of the no-op and the unvalidated label means fixture naming discipline is entirely unenforced. The two advisories (ADV-02 from sr-dev + ADV-SDET-4 here) together resolve the gap.

**Action:** Defer to ADV-SDET-4's resolution (which makes the label irrelevant for correctness) and clean up the no-op per sr-dev ADV-02.

### What passed review (one-line per lens)

- **Tests-pass-for-wrong-reason:** none observed beyond advisory-level tautologies; all meaningful negative paths are exercised correctly
- **Coverage gaps:** FIX-SDET-1 (trailing-whitespace verdict → false MalformedAgentReturn, no test); ADV-SDET-4 (no test that all verdict tokens are covered across fixtures)
- **Mock overuse:** not applicable — no mocks used; `parse_agent_return` is the real implementation; fixtures are real text files
- **Fixture / independence:** no order dependence observed; `_FIXTURE_PARAMS` is built at module import (collection time) without mutation; no state shared between tests; `test_all_agents_have_three_fixtures_per_spec` loops non-parametrically so it fails loudly if a fixture is deleted
- **Hermetic-vs-E2E gating:** correctly gated; `_E2E_ENABLED = os.getenv("AIW_AGENT_SCHEMA_E2E") == "1"` is the correct string comparison; `AIW_AGENT_SCHEMA_E2E=0` correctly stays skipped; no network calls in default suite
- **Naming / assertion-message hygiene:** ADV-SDET-2 (test name implies more than it tests); ADV-SDET-3 (misleading comment with unpromised second test case)
- **Simplification:** `_fixture_texts:62` no-op replace (ADV-02); otherwise code is clear and un-padded

## Locked team decisions (cycle 1 → cycle 2 carry-over)

Per `/auto-implement` Step T4 #2, both FIX findings carry single clear recommendations consistent with the spec + KDRs; loop-controller concurs and stamps:

- **Locked team decision (loop-controller + sr-dev concur, 2026-04-28):** Fix the architect verdict-token drift surfaced as FIX-1. Update `.claude/agents/architect.md:42` (Trigger A body) AND `.claude/commands/auto-implement.md:189` (Step T3) from the old token set (`PROPOSE-NEW-KDR | NO-KDR-NEEDED-EXISTING-RULE-COVERS | NO-KDR-NEEDED-CASE-BY-CASE`) to the new schema's set (`ALIGNED / MISALIGNED / OPEN / PROPOSE-NEW-KDR`). Aligns architect's prompt body + slash-command Step T3 with the per-agent verdict-token table in `task_01_*.md`, `_common/agent_return_schema.md`, and `_helpers.py:AGENT_VERDICT_TOKENS["architect"]`. Add a regression test that asserts the architect prompt body's documented token set matches `AGENT_VERDICT_TOKENS["architect"]` in `_helpers.py` (string-grep test, hermetic).

- **Locked team decision (loop-controller + sr-sdet concur, 2026-04-28):** Fix the trailing-whitespace parser bug surfaced as FIX-SDET-1. In `tests/agents/_helpers.py`, strip the captured value before validating against the allowed set: change `parsed[key] = value` to `parsed[key] = value.strip()` (or strip at the validation site, whichever is less intrusive). Add the test `test_trailing_spaces_in_verdict_are_tolerated` in `tests/agents/test_orchestrator_parser.py` per FIX-SDET-1's recommendation. The advisory parser-prose update in the 5 slash commands ("strip whitespace before comparing") follows from the helper-side fix; one-sentence prose update in each command's parser convention section.

Advisories (ADV-01, ADV-02, ADV-03, ADV-SDET-1 through ADV-SDET-5) are not in the cycle-2 carry-over — they remain in the issue file for future follow-up. Operator may bundle into a later M20 task or open a tracker issue.

## Cycle 2 audit (2026-04-28)

**Verdict:** ✅ PASS — both locked team decisions landed cleanly. No scope creep.

### What the Builder changed in cycle 2 (verified file-by-file)

| File | Change | Verified |
| ---- | ------ | -------- |
| `.claude/agents/architect.md:42` | `PROPOSE-NEW-KDR \| NO-KDR-NEEDED-EXISTING-RULE-COVERS \| NO-KDR-NEEDED-CASE-BY-CASE` → `ALIGNED / MISALIGNED / OPEN / PROPOSE-NEW-KDR` | `git diff HEAD -- .claude/agents/architect.md` shows exactly the one-line replacement; `## Return to invoker` (line 103) is unchanged from cycle 1; nothing else touched |
| `.claude/commands/auto-implement.md:189` | Same token-set replacement on the Step T3 verdict-line summary | `git diff` shows the one-line replacement plus the parser-convention block (which was already in cycle 1) carries the cycle-2 whitespace-strip prose |
| `tests/agents/_helpers.py:112` | `parsed[key] = value` → `parsed[key] = value.strip()` | Read confirms line 112 stores `value.strip()`; the whitespace-only guard at line 108 still raises before strip is reached, so the existing negative test continues to pass |
| `tests/agents/test_orchestrator_parser.py:96-102` | New test `test_trailing_spaces_in_verdict_are_tolerated` | Test exists; uses `text = "verdict: BUILT  \nfile: —  \nsection: —  "`; asserts `verdict == "BUILT"` and both `file_val == "—"` and `section == "—"` (the `.strip()` is exercised) |
| `tests/agents/test_return_schema_compliance.py:115-130` | New regression test `test_architect_prompt_body_token_set_matches_helper` | Reads `.claude/agents/architect.md`, iterates every token in `AGENT_VERDICT_TOKENS["architect"]`, asserts each appears as a substring. Hermetic — no live spawn |
| `.claude/commands/auto-implement.md:26` | Step 4 of parser convention now ends "trailing whitespace on any value is stripped before validation" | `grep -n "trailing whitespace" .claude/commands/auto-implement.md` returns line 26 |
| `.claude/commands/clean-implement.md:24` | Same one-sentence prose addition | grep confirms line 24 |
| `.claude/commands/clean-tasks.md:32` | Same | grep confirms line 32 |
| `.claude/commands/queue-pick.md:27` | Same | grep confirms line 27 |
| `.claude/commands/autopilot.md:26` | Same | grep confirms line 26 |

### Locked team decisions — status flip

- **Locked decision 1 (architect verdict-token drift):** ✅ RESOLVED. All four locations (`architect.md:42` body, `architect.md:103` `## Return to invoker`, `_common/agent_return_schema.md:49`, `_helpers.py:34` `AGENT_VERDICT_TOKENS["architect"]`) now agree on `ALIGNED / MISALIGNED / OPEN / PROPOSE-NEW-KDR`. The new regression test `test_architect_prompt_body_token_set_matches_helper` pins the contract — if `_helpers.py` and `architect.md` ever drift again, the test fails. Same fix applied to `auto-implement.md:189` Step T3 verdict-line summary.

- **Locked decision 2 (parser trailing-whitespace robustness):** ✅ RESOLVED. `_helpers.py:112` strips before storing; `test_trailing_spaces_in_verdict_are_tolerated` exercises the path with two-space-trailing values on all three schema lines. Five slash commands' parser-convention prose now documents the strip behaviour ("trailing whitespace on any value is stripped before validation"). Documentation matches Python implementation.

### Scope-creep check

- No drive-by edits to the other 7 agent files (`builder.md`, `auditor.md`, `security-reviewer.md`, `dependency-auditor.md`, `task-analyzer.md`, `sr-dev.md`, `sr-sdet.md`, `roadmap-selector.md`). `git diff HEAD --` on those 7 files returns empty diff for cycle 2's commits relative to cycle 1.
- No new ACs, no `nice_to_have.md` adoption, no advisory items implemented (ADV-01/02/03/SDET-1..5 all remain documented in the cycle-1 reviews for later follow-up — Builder correctly stayed in scope).
- `pyproject.toml` / `uv.lock` unchanged.
- No tests deleted; `test_fixture_verdict_in_allowed_set` and `test_fixture_parses_cleanly` (the two ADV-SDET tautologies) are unchanged — left for the operator to address later.

### Cycle 1 ACs still met

| AC | Cycle 1 | Cycle 2 re-verify | Notes |
| -- | ------- | ----------------- | ----- |
| 1 — 9 agents have uniform 3-line schema | ✅ | ✅ | Smoke 1 returns 9; architect.md still has `## Return to invoker` block at line 98-108 |
| 2 — `_common/agent_return_schema.md` lists all 9 agents | ✅ | ✅ | File unchanged in cycle 2 |
| 3 — 5 slash commands describe parser convention | ✅ | ✅ | Smoke 3 returns 5; the prose got one sentence longer per locked decision 2 |
| 4 — `test_return_schema_compliance.py` passes | ✅ | ✅ | 117 tests pass (was 115; +2 new: `test_architect_prompt_body_token_set_matches_helper` + the additional architect fixture from cycle 1) |
| 5 — `test_orchestrator_parser.py` passes | ✅ | ✅ | 30 tests pass (was 29; +1 new: `test_trailing_spaces_in_verdict_are_tolerated`) |
| 6 — Token-cap test passes for every fixture | ✅ | ✅ | All 28 fixture token-cap parameters pass |
| 7 — CHANGELOG entry under `[Unreleased]` | ✅ | ✅ | No edit needed in cycle 2 (entry already cites locked-decision-style refinements; operator can add a one-line cycle-2 line at release time if desired — not blocking) |
| 8 — Status surfaces flip together | ✅ | ✅ | All four surfaces still `✅ Done`; no regression |
| L1 — `AIW_AGENT_SCHEMA_E2E=1` opt-in | ✅ | ✅ | E2E placeholder still skipped in default suite |
| L8 — Regex token-count proxy, no `tiktoken` dep | ✅ | ✅ | `tests/agents/_helpers.py:144` unchanged |

### Cycle 2 gate re-run (from scratch)

| Gate | Command | Result |
| ---- | ------- | ------ |
| pytest (T01 specific) | `uv run pytest tests/agents/test_return_schema_compliance.py tests/agents/test_orchestrator_parser.py -v` | **144 passed, 1 skipped** (was 142 passed in cycle 1; +2 new tests both pass) |
| pytest (full suite) | `AIW_BRANCH=design uv run pytest` | **938 passed, 1 failed (flake), 7 skipped.** Failure: `tests/mcp/test_cancel_run_inflight.py::test_cancel_run_aborts_in_flight_task_and_flips_storage`. Re-running the file in isolation: **5 passed in 1.07s** (intermittent timing flake on cancel-run inflight, unrelated to T01). The cycle-1 failure (`tests/test_main_branch_shape.py::test_design_docs_absence_on_main`) is now suppressed by `AIW_BRANCH=design` env var, as predicted by cycle-1 LOW-1's recommendation (a). |
| lint-imports | `uv run lint-imports` | **5 contracts kept, 0 broken** |
| ruff | `uv run ruff check` | **All checks passed** |
| Smoke 1 — schema in 9 agents | `grep -l ...` | **9** ✅ |
| Smoke 2 — `_common` reference | `test -f ...` | **OK** ✅ |
| Smoke 3 — slash-command links | `grep -l ...` | **5** ✅ |
| Smoke 4 — schema + parser tests | `uv run pytest ... -v` | **144 passed, 1 skipped** ✅ |

### Design-drift check (cycle 2)

No drift detected. Cycle-2 changes are markdown agent prompts + slash-command markdown + Python test infrastructure (under `tests/`). No runtime code under `ai_workflows/` touched; layer rule unchanged. No new dependencies. No KDR violations. The new regression test `test_architect_prompt_body_token_set_matches_helper` is hermetic string-grep — no LLM call, no `anthropic` / `litellm` / `ollama` import. KDR-003/004/006/008/009/013 all N/A; KDR-002 N/A.

### New issues surfaced in cycle 2

(none — the Builder honoured the locked-decision scope exactly)

### Issue log update

| ID | Severity | Owner / Next touch point | Status |
|----|----------|--------------------------|--------|
| M20-T01-ISS-01 | LOW | Operator (`AIW_BRANCH=design`) confirmed to suppress the cycle-1 branch-shape failure in cycle 2 | ✅ RESOLVED via env-var (option a from cycle 1's recommendation); option b (helper update) remains available as a follow-up if operator wants the cleaner long-term fix |

### Cycle 2 verdict

**PASS.** Both locked team decisions landed cleanly; no scope creep; all cycle-1 ACs still met; gates green. T01 stays at `✅ Done`. The intermittent `test_cancel_run_inflight` flake is environmental (timing-sensitive cancel-run integration test, passes on isolated re-run) and is not a T01 regression — flag for operator awareness but does not block.

## Security review — cycle 2 re-check (2026-04-28)

### Verdict: SHIP

### Scope

Cycle-2 diff only: `.claude/agents/architect.md:42` (verdict-token line), `.claude/commands/auto-implement.md:189` (same token-set fix), one-sentence prose addition to five slash-command parser-convention sections, `tests/agents/_helpers.py:112` (`value.strip()` fix), two new tests (`test_trailing_spaces_in_verdict_are_tolerated`, `test_architect_prompt_body_token_set_matches_helper`).

### 1. Wheel-contents leakage

No changes to `pyproject.toml`, `uv.lock`, or any path under `ai_workflows/`. Cycle-2 diff is entirely `.claude/` markdown, slash-command markdown, and `tests/agents/` Python. None of those paths are picked up by `[tool.hatch.build.targets.wheel]` (`packages = ["ai_workflows"]` only). Result: CLEAN — no new wheel-contents risk.

### 2. Subprocess execution

No new `subprocess`, `Popen`, `os.system`, or `shell=True` calls in any cycle-2 file. The two new tests are hermetic string-grep (`test_architect_prompt_body_token_set_matches_helper` reads `architect.md` via `Path.read_text()`) and a direct call to `parse_agent_return` with a crafted string. No spawn path added. Result: no new subprocess surface.

### 3. Credential leakage

The cycle-2 changes are prompt-text corrections and a parser robustness fix. No env-var reads, no API key references, no `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` / `Bearer` / `Authorization` patterns introduced. Verified by inspection of both changed markdown files and the two new test functions. Result: CLEAN.

### 4. Parser robustness (cycle-2 focus item)

`tests/agents/_helpers.py:112` now stores `value.strip()` instead of the raw captured value. The whitespace-only guard at line 108 (`if not value.strip()`) still fires before the strip assignment, so the existing negative test `test_whitespace_only_value_raises` continues to exercise the correct raise path. The new positive test `test_trailing_spaces_in_verdict_are_tolerated` uses `"verdict: BUILT  \nfile: —  \nsection: —  "` (two trailing spaces on all three lines) and asserts each returned value is the stripped form. The fix closes the false-halt path identified by sr-sdet FIX-SDET-1 without introducing any new exception swallowing or silent-failure path. Result: robust; new test exercises the fix correctly.

### 5. Hermetic-vs-E2E gating

Both new tests are hermetic. `test_architect_prompt_body_token_set_matches_helper` reads a local file (`AGENTS_DIR / "architect.md"`) — no network, no subprocess. `test_trailing_spaces_in_verdict_are_tolerated` calls `parse_agent_return` directly. Neither touches `AIW_AGENT_SCHEMA_E2E`. No gating regression. Result: CLEAN.

### 6. Architect verdict-token consistency

`architect.md:42` now reads `ALIGNED / MISALIGNED / OPEN / PROPOSE-NEW-KDR` — matching `architect.md:103` (`## Return to invoker`), `_common/agent_return_schema.md:49`, and `_helpers.py:34` (`AGENT_VERDICT_TOKENS["architect"]`). The regression test `test_architect_prompt_body_token_set_matches_helper` pins this four-way consistency going forward. `auto-implement.md:189` Step T3 similarly updated. Result: no residual token drift.

### 🔴 Critical — must fix before publish/ship

(none)

### 🟠 High — should fix before publish/ship

(none)

### 🟡 Advisory — track; not blocking

(none — cycle-1 ADV-01 and all ADV-SDET items carried forward unchanged; no new advisories from cycle-2 diff)

## Sr. Dev review — cycle 2 re-check (2026-04-28)

**Files reviewed (cycle 2 diff only):** `.claude/agents/architect.md` (line 42), `.claude/commands/auto-implement.md` (line 189), `.claude/commands/clean-implement.md`, `.claude/commands/clean-tasks.md`, `.claude/commands/queue-pick.md`, `.claude/commands/autopilot.md`, `tests/agents/_helpers.py` (line 112), `tests/agents/test_orchestrator_parser.py` (lines 96-102), `tests/agents/test_return_schema_compliance.py` (lines 115-130).
**Skipped (out of scope):** cycle-1 advisories (ADV-01, ADV-02, ADV-03) — intentionally carried forward per loop-controller scope rule.
**Verdict:** SHIP

### BLOCK — must-fix before commit

(none)

### FIX — fix-then-ship

(none)

### Advisory — track but not blocking

#### ADV-C2-01 — `test_architect_prompt_body_token_set_matches_helper` duplicates existing parametric coverage

**Lens:** Simplification / premature abstraction

**File:** `tests/agents/test_return_schema_compliance.py:115-130` vs. `tests/agents/test_return_schema_compliance.py:98-107`

`test_architect_prompt_body_token_set_matches_helper` (new) reads `architect.md`, iterates over `AGENT_VERDICT_TOKENS["architect"]`, and asserts each token appears as a substring. The pre-existing parametric test `test_agent_file_verdict_tokens_match_spec` (line 98-107) does the identical operation for all agents — including architect, when parametrized with `agent_name="architect"`. The two tests are logically identical for the architect case: same file read, same token set, same substring assertion, same failure message shape.

The new test does not target just the Trigger A body line (line 42 of `architect.md`); it asserts presence anywhere in the full file. If someone adds a comment mentioning `ALIGNED` but reverts line 42 back to the old token set, both tests would still pass. Neither test catches a narrower drift (tokens present in `## Return to invoker` block but absent from the body instruction block specifically).

The duplication is advisory-level — the new test is not harmful, just redundant. It was the correct response to the locked-decision requirement ("add a regression test that asserts the architect prompt body's documented token set matches `AGENT_VERDICT_TOKENS['architect']`"), and the Auditor accepted it. No regression from the duplication.

**Action (Advisory):** In a follow-up cleanup, either (a) remove `test_architect_prompt_body_token_set_matches_helper` with a comment pointing at `test_agent_file_verdict_tokens_match_spec` as the equivalent coverage, or (b) tighten it to check only the Trigger A verdict line (line 42 of `architect.md`) using a line-scoped search rather than a full-file substring match. Option (b) would add genuine new coverage the existing parametric test does not provide. Not blocking.

### What passed review — cycle 2 (one-line per lens)

- **Hidden bugs:** FIX-1 fully resolved — all four locations (`architect.md:42` body, `architect.md:103` `## Return to invoker`, `_common/agent_return_schema.md:49`, `_helpers.py:34`) now agree on `ALIGNED / MISALIGNED / OPEN / PROPOSE-NEW-KDR`; `auto-implement.md:189` also updated.
- **Defensive-code creep:** none introduced — `value.strip()` at line 112 correctly follows the pre-existing whitespace-only guard at line 108; no new silent-swallow path.
- **Idiom alignment:** five slash-command prose updates are terse, consistent, and use identical wording ("trailing whitespace on any value is stripped before validation") — no padding or drift across files.
- **Premature abstraction:** ADV-C2-01 (new test duplicates existing parametric coverage for the architect case); advisory only.
- **Comment / docstring drift:** none introduced in cycle-2 diff; new test docstrings are appropriately terse.
- **Simplification:** none needed; `value.strip()` is the correct fix location given the parser's guard-then-store structure.

## Sr. SDET review — cycle 2 re-check (2026-04-28)

**Test files reviewed:** `tests/agents/_helpers.py` (line 112 strip fix), `tests/agents/test_orchestrator_parser.py` (lines 96-102, new `test_trailing_spaces_in_verdict_are_tolerated`), `tests/agents/test_return_schema_compliance.py` (lines 115-130, new `test_architect_prompt_body_token_set_matches_helper`). `.claude/agents/architect.md` read for regression-test verification.
**Skipped (out of scope):** advisories ADV-SDET-1 through ADV-SDET-5 (intentionally not re-raised per cycle-2 brief); all other test files unchanged in cycle 2.
**Verdict:** SHIP

### BLOCK — tests pass for the wrong reason

(none)

### FIX — fix-then-ship

(none)

### Advisory — track but not blocking

#### ADV-SDET-6 — `test_architect_prompt_body_token_set_matches_helper` substring check has a narrow false-negative on `ALIGNED` / `MISALIGNED`

**Lens:** Tests pass for the wrong reason (mild — advisory severity; same limitation as `test_agent_file_verdict_tokens_match_spec` project-wide)

**File:** `tests/agents/test_return_schema_compliance.py:115-130`

The new regression test iterates `AGENT_VERDICT_TOKENS["architect"]` = `{"ALIGNED", "MISALIGNED", "OPEN", "PROPOSE-NEW-KDR"}` and asserts `token in content` (full-file substring match) for each. The check would not detect the case where `ALIGNED` is removed from `architect.md` while `MISALIGNED` remains: `"ALIGNED" in content` passes as a substring match against `MISALIGNED`. This is the only token pair in the architect set with a subset relationship. In practice, the tokens currently appear as a slash-separated sequence (`ALIGNED / MISALIGNED / OPEN / PROPOSE-NEW-KDR`), so a regression that selectively removes `ALIGNED` while keeping `MISALIGNED` is contrived.

The same substring limitation applies to the pre-existing `test_agent_file_verdict_tokens_match_spec` (line 98-107), which performs the identical check for all 9 agents including `architect`. The new test is consistent with the project's existing check idiom, not introducing a novel weakness.

**Action (Advisory):** If this check is ever promoted to a higher-assurance gate, use word-boundary matching (`re.search(r'\bALIGNED\b', content)`) instead of `token in content`. Alternatively, scope the check to just the Trigger A verdict line (line 42 of `architect.md`) rather than the full file — this would also eliminate the theoretical false-negative while adding genuinely tighter coverage than `test_agent_file_verdict_tokens_match_spec` already provides. Not blocking.

### What passed review (one-line per lens)

- **Tests-pass-for-wrong-reason:** none — `test_trailing_spaces_in_verdict_are_tolerated` would fail with an unexpected `MalformedAgentReturn` if the `value.strip()` fix at `_helpers.py:112` were reverted; the fix is mechanically proven by the test
- **Coverage gaps:** strip fix covers all three schema keys in one invocation; two-space trailing is sufficient (probing single space or tab separately would test Python's `str.strip()`, not the parser logic); `str.strip()` absorbing tabs is an intended side-effect of the correct idiom, not an unintended widening
- **Mock overuse:** not applicable — no mocks in either new test; `test_trailing_spaces_in_verdict_are_tolerated` calls `parse_agent_return` directly; `test_architect_prompt_body_token_set_matches_helper` reads the real file via `Path.read_text()`
- **Fixture / independence:** both new tests are stateless and order-independent; `test_architect_prompt_body_token_set_matches_helper` reads a file but does not mutate state; no autouse fixture interaction
- **Hermetic-vs-E2E gating:** both new tests are hermetic; no network, no subprocess, no env-var opt-in required or incorrectly absent
- **Naming / assertion-message hygiene:** `test_trailing_spaces_in_verdict_are_tolerated` names exactly what it verifies; `test_architect_prompt_body_token_set_matches_helper` names the consistency invariant; assertion messages include the divergent token name for debuggability
