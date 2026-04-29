# Task 02 — Sub-agent input prune — Audit Issues

**Source task:** [../task_02_sub_agent_input_prune.md](../task_02_sub_agent_input_prune.md)
**Audited on:** 2026-04-28
**Audit scope:** Cycle 1. Inspected:
- `.claude/commands/_common/spawn_prompt_template.md` (NEW canonical scaffold)
- 5 spawning slash commands (`auto-implement`, `clean-tasks`, `clean-implement`, `queue-pick`, `autopilot`) — `## Spawn-prompt scope discipline` sections + per-spawn output budget directives + token-instrumentation paths.
- `tests/orchestrator/` (`__init__.py`, `_helpers.py`, `test_spawn_prompt_size.py`, `test_kdr_section_extractor.py`, `fixtures/m12_t01_pre_t02_spawn_prompt.txt`).
- `CHANGELOG.md` `[Unreleased]` entry.
- Status surfaces — task spec line 3 + milestone README task table row + Done-when exit criterion #2.
- Critical preservation check: `.claude/agents/auditor.md` not modified (the agent's "load full task scope" mandate is intact).
- All gates re-run from scratch.

**Status:** ✅ PASS (cycle 2 — locked-decision verification clean)

---

## Design-drift check

No drift detected.

T02 changes only `.claude/commands/` (slash-command markdown), `tests/orchestrator/` (hermetic test infra under `tests/`), and documentation (`CHANGELOG.md` + spec + milestone README). Zero changes to `ai_workflows/` runtime code; the four-layer rule, the seven load-bearing KDRs (002, 003, 004, 006, 008, 009, 013) are not exercised by this task.

- KDR-002 / KDR-008 (MCP / FastMCP surface): untouched. No tool surface change.
- KDR-003 (no Anthropic API): untouched. No LLM-call code added.
- KDR-004 (validator pairing): untouched. No new LLM nodes.
- KDR-006 (RetryingEdge): untouched. No retry logic added.
- KDR-009 (SqliteSaver): untouched. No checkpoint code.
- KDR-013 (user-owned external workflows): untouched. No registration code.
- Layer rule (`primitives → graph → workflows → surfaces`): re-verified `uv run lint-imports` — 5 / 5 contracts kept.

The new `tests/orchestrator/_helpers.py` module is intentionally sited under `tests/` (not `ai_workflows/`) — the test package's `__init__.py` documents that placing this in the runtime package would create a dead-end subpackage with no runtime caller, violating layer discipline. Correct decision.

**Critical-preservation check (spec line 13):** `.claude/agents/auditor.md` is unchanged on this branch — `git status` returns no entries under `.claude/agents/`. The Auditor's "load the full task scope, not the diff" mandate at line 16 is intact. T02 prunes only the *orchestrator's pre-load* via the slash commands, not the Auditor's own internal Read discipline. This audit demonstrates the design works: the orchestrator passed only path references and KDR identifiers, and this Auditor pulled `architecture.md` + KDR rows + sibling spec content + test files via its own Read tool.

---

## AC grading

| AC | Status | Notes |
| -- | ------ | ----- |
| 1 — 5 slash commands describe pruned spawn convention + per-agent minimal pre-load + output budget directive | ✅ PASS | All 5 commands carry a `## Spawn-prompt scope discipline` section; each enumerates its applicable per-agent pre-load sets + the verbatim output budget directive. `grep -l "Output budget:" <5 files>` returns 5. |
| 2 — `.claude/commands/_common/spawn_prompt_template.md` exists; each slash command links to it | ✅ PASS | File exists (5,620 bytes). `grep -l "_common/spawn_prompt_template.md" <5 commands>` returns 5; each command's discipline section opens with `**Reference:** [...](...)`. |
| 3 — `tests/orchestrator/test_spawn_prompt_size.py` passes with per-agent ceilings | ✅ PASS | 24 tests in this module pass. Builder ≤ 8K, Auditor ≤ 6K, reviewers ≤ 4K, task-analyzer ≤ 6K, roadmap-selector ≤ 4K all asserted via `AGENT_SPAWN_CEILINGS`. |
| 4 — `tests/orchestrator/test_kdr_section_extractor.py` passes with positive + edge cases | ✅ PASS | 19 tests cover: 2-KDR extract, no-KDR empty list, single-digit normalisation, dedup, sort, code-block citation, partial-word non-match, compact-pointer for 1/2/empty, full-table extract for cited rows, table-fallback for unknown KDR, header-always-present, size-vs-full-table, end-to-end pipeline. |
| 5 — Per-spawn token-count instrumentation at `runs/<task>/cycle_<N>/spawn_<agent>.tokens.txt` | ✅ PASS | Path convention documented in `spawn_prompt_template.md` §"Per-spawn token-count instrumentation" + each slash command's discipline section. Hermetic test `TestSpawnTokenInstrumentation` writes a token-count file to verify naming + format (integer, no `_<cycle>` suffix). The convention is documented prose for the orchestrator (which is itself a Claude Code conversation, not Python code) — this is the right shape for an orchestration-layer change. |
| 6 — Validation re-run: ≥ 30% reduction against M12 T01 pre-T02 baseline | ✅ PASS | `test_m12_t01_audit_spawn_30pct_reduction` passes. Re-ran the test in isolation: pre-T02 baseline = ~2,016 tokens (synthetic fixture); post-T02 = ~224 tokens; **reduction = 88.9%**, well above the 30% threshold. The fixture is a *conservative* synthetic proxy (it inlines only §1/§2/§3/§9 of architecture.md, not the full 320-line file + 94-line milestone README + sibling issues + gate stdout), so a real-world pre-T02 spawn would be larger and the actual reduction higher. The test is meaningful — it exercises the pruning logic against a representative inlined-content shape, not a tautology. |
| 7 — CHANGELOG `[Unreleased]` `### Changed — M20 Task 02: ...` entry with research-brief reference | ✅ PASS | Entry present at top of `[Unreleased]`; cites "research brief §Lens 2.3" per spec; lists 12 files touched + 8 ACs. |
| 8 — Status surfaces flip together at task close | ✅ PASS | (a) spec line 3: `**Status:** ✅ Done (2026-04-28).`; (b) milestone README task table line 107: `\| 02 \| ... \| ✅ Done \|`; (c) milestone README Done-when exit criterion line 51: `2. ✅ **(G1)** ... [T02 Done — 2026-04-28]`. There is no `tasks/README.md` for M20, so surface (d) does not apply. All applicable surfaces agree. |

**8 / 8 ACs met.**

---

## Gate summary

| Gate | Command | Result |
| ---- | ------- | ------ |
| Full pytest | `AIW_BRANCH=design uv run pytest` | **PASS** — 983 passed, 7 skipped, 22 deprecation warnings (pre-existing, unrelated). |
| Orchestrator-tests | `AIW_BRANCH=design uv run pytest tests/orchestrator/ -v` | **PASS** — 44 / 44 (24 spawn-size + 19 KDR + 1 30%-reduction). |
| Validation re-run | `AIW_BRANCH=design uv run pytest tests/orchestrator/test_spawn_prompt_size.py::test_m12_t01_audit_spawn_30pct_reduction -v` | **PASS** — 1 / 1. |
| Layer contracts | `uv run lint-imports` | **PASS** — 5 / 5 contracts kept. |
| Lint | `uv run ruff check` | **PASS** — All checks passed. |
| Smoke 1 — common template exists | `test -f .claude/commands/_common/spawn_prompt_template.md` | **PASS** — file present (5,620 bytes). |
| Smoke 2 — 5 commands link template | `grep -l "_common/spawn_prompt_template.md" <5 cmds> \| wc -l` | **PASS** — 5. |
| Smoke 3 — 5 commands name budget directive | `grep -l "Output budget:" <5 cmds> \| wc -l` | **PASS** — 5. |

The Builder's gate-pass claim is verified — every gate passes from a clean re-run.

---

## Critical sweep

Inspected for: ACs that look met but aren't / silently skipped deliverables / additions adding coupling / test gaps / doc drift / secrets shortcuts / scope creep / silent architecture drift / status-surface drift.

- **No silent skips.** Every spec deliverable is implemented.
- **No nice_to_have.md adoption.** No items pulled from deferred parking lot.
- **No secrets shortcuts.** No env-var changes or credential paths added.
- **No status-surface drift.** Three applicable surfaces agree.
- **No agent-prompt drift.** `.claude/agents/auditor.md` and the other 8 agent prompts are unchanged on this branch.
- **No KDR drift.** No runtime code touched.
- **No scope creep.** The `_common/spawn_prompt_template.md` references future M20 task files (`parallel_spawn_pattern.md`, `dispatch_table.md`, etc.) under §Notes as forward markers — this is documentation pointing forward, not adoption. Acceptable.
- **Test gaps:** none for the implementation. (See LOW-1 below for one gap that does not block: a missing test that would assert the slash-command markdown actually carries the discipline section content — currently only smoke greps verify presence.)

---

## 🔴 HIGH — none

No HIGH findings.

## 🟡 MEDIUM — none

No MEDIUM findings.

## 🟢 LOW

### LOW-1 — `auto-implement.md` reviewer-spawn section header omits `dependency-auditor`

`.claude/commands/auto-implement.md` line 80: `### Reviewer spawns (sr-dev, sr-sdet, security-reviewer)` — the section title enumerates only three agents. The dependency-auditor is correctly covered by the canonical template (`_common/spawn_prompt_template.md` §"Reviewer spawns (sr-dev, sr-sdet, security-reviewer, dependency-auditor)") and its budget appears in both ceiling tables, so functionally the rule applies. But the slash-command's own section header reads as if dependency-auditor isn't covered, which is a minor doc-clarity gap. (`clean-implement.md` line 111 correctly says `### Reviewer spawns (security-reviewer, dependency-auditor)` — that command's reviewer composition.)

**Action / Recommendation:** edit `.claude/commands/auto-implement.md` line 80 to read `### Reviewer spawns (sr-dev, sr-sdet, security-reviewer, dependency-auditor)`. Push to T02 carry-over (do *not* attempt the edit in this audit — Auditor is read-only on source). Trade-off: trivial 1-word addition; no semantic change. Low priority — the canonical template already governs.

**Owner:** carry-over on this same task at the next touch (or roll into M20 T03 close-out fold).

### LOW-2 — Test fixture is a conservative synthetic proxy, not a captured real pre-T02 spawn

The pre-T02 baseline at `tests/orchestrator/fixtures/m12_t01_pre_t02_spawn_prompt.txt` is a hand-crafted 185-line synthetic representation. It contains only §1, §2, §3, and §9 of `architecture.md`, plus a stubbed milestone README — the actual full architecture.md is 320 lines and the M12 README is 94 lines. A truly captured pre-T02 Auditor spawn (had it been recorded during M12 T01's audit) would likely be 2–3× larger. The 30% threshold is therefore very conservative against this fixture — the test passes at ~89% reduction.

The test still does its job (it asserts the *discipline rules* produce a substantial reduction against any reasonable inlined-content shape), but the threshold is not calibrated against captured production data.

**Action / Recommendation:** when T22 (per-cycle telemetry) lands, capture a real pre-T22 Auditor spawn for one M20 task and use it as the new baseline; tighten the threshold then. No action required for T02 itself — the fixture is honest about being a synthetic proxy (it carries `PRE-T02 bloat` markers in its section headers). Document this as a forward-looking note. **No carry-over needed; resolved when T22 telemetry data lands.**

**Owner:** flagged in this audit only; T22's natural scope.

### LOW-3 — Spawn-prompt template references future task files under §Notes

`_common/spawn_prompt_template.md` lines 168–171 list forward markers like `parallel_spawn_pattern.md (T05)`, `dispatch_table.md (T07)`, `gate_parse_patterns.md (T08)`, `integrity_checks.md (T09)`, `effort_table.md (T21)`, `auditor_context_management.md (T27)`. None of these files exist yet; they are signposts for future tasks to populate the `_common/` directory. Markdown links to non-existent files would be a minor link-rot concern — but these are *bare filenames in a paragraph*, not hyperlinks, so no link-checker would flag them. Cosmetic only.

**Action / Recommendation:** none required. Each future task that creates the named file should update the corresponding §Notes line to point to its real path. Self-resolving.

**Owner:** future-task-by-future-task closure.

---

## Additions beyond spec — audited and justified

- **`tests/orchestrator/_helpers.py` provides Python implementations of orchestrator rules.** The spec's deliverables are slash-command markdown changes; the helpers exist purely to make the hermetic tests for AC-3 / AC-4 / AC-6 possible. Without them, the tests would have no Python to call. The helpers' own docstring documents this rationale and the deliberate `tests/`-not-`ai_workflows/` placement. **Justified.**
- **`tests/orchestrator/__init__.py`** — minimal package init to make `tests.orchestrator` importable. Required for `from tests.orchestrator._helpers import ...`. **Justified.**
- **`extract_kdr_sections()` (in `_helpers.py`) — content form of the KDR pre-load rule.** The spec calls for the *compact-pointer* form (`build_kdr_compact_pointer`). `extract_kdr_sections` is a content-form alternative used only by `test_kdr_section_extractor.py`'s test cases (header-always-present, full-table-vs-extracted-size). It's test infra; not exposed to the orchestrators. **Justified.**

No additions outside test infrastructure. Spec scope respected.

---

## Issue log — cross-task follow-up

| ID | Severity | Owner / next touch point | Status |
| --- | --- | --- | --- |
| M20-T02-ISS-01 | LOW | T02 carry-over for next touch (or roll into M20 T03) | OPEN — header text fix in `auto-implement.md` line 80. |
| M20-T02-ISS-02 | LOW | T22 (per-cycle telemetry) | OPEN — replace synthetic baseline fixture with captured real pre-T22 spawn when telemetry lands; tighten threshold. |
| M20-T02-ISS-03 | LOW | future-task-by-future-task | OPEN — `_common/` forward-marker paths get populated as each downstream task lands. |

---

## Deferred to nice_to_have

None. T02's findings are all minor LOWs naturally cleared by the next touch on the same task or by future M20 tasks; no nice_to_have.md mapping applies.

---

## Propagation status

No forward-deferrals propagated. Two LOWs (ISS-02, ISS-03) are forward-looking notes that resolve naturally when later M20 tasks land — no carry-over edits required to those specs because the resolution is intrinsic to those tasks' scope. ISS-01 stays as a same-task carry-over (next-touch fix).

---

## Verdict

**PASS** — all 8 ACs satisfied, all gates green, design-drift check clean, critical-preservation invariant verified intact, status surfaces aligned. Three LOWs surfaced for forward-tracking, none blocking.

---

## Security review (2026-04-28)

### Verdict: SHIP

### Scope

T02 touches only `.claude/commands/` (slash-command markdown), `tests/orchestrator/` (hermetic test infrastructure), and documentation files (`CHANGELOG.md`, spec, milestone README). Zero changes to `ai_workflows/` runtime code. The two real attack surfaces — published wheel and subprocess execution — are structurally unaffected.

### Threat-model checklist

**1. Wheel contents (primary concern)**

Wheel: `dist/jmdl_ai_workflows-0.3.1-py3-none-any.whl` inspected via `python3 zipfile`. Contents: `ai_workflows/`, `migrations/`, `dist-info/` only. No `.claude/`, no `tests/`, no `design_docs/`, no `.env*`, no `runs/`, no `*.sqlite3`. Clean.

Note: The 0.3.1 wheel predates T02; a fresh `uv build` after T02 will produce the same result because `[tool.hatch.build.targets.wheel] packages = ["ai_workflows"]` limits the wheel to the runtime package. T02's new files all live outside `ai_workflows/`, so they cannot appear in the wheel by construction.

sdist (`jmdl_ai_workflows-0.3.1.tar.gz`) contains `.env.example` and `.github/` — both pre-existing inclusions, not introduced by T02. `.env.example` contains only placeholder values (the `GEMINI_API_KEY=` line is intentionally blank; no real keys). `.github/` contains `ci.yml` and `CONTRIBUTING.md` — no secrets. These are Advisory-only pre-existing items, unchanged by T02.

**2. Subprocess execution (KDR-003)**

No new subprocess calls introduced. `tests/orchestrator/_helpers.py` is pure Python (`re`, `pathlib` only — confirmed via grep). No `subprocess`, `shell`, `os.system`, or `Popen` in any T02 file. The `runs/<task>/cycle_<N>/spawn_<agent>.tokens.txt` convention is orchestrator-level documentation prose for the Claude Code conversation; it does not constitute a Python `open()` or subprocess invocation in `ai_workflows/`.

`ANTHROPIC_API_KEY` grep over `ai_workflows/`: zero hits. KDR-003 boundary clean.

**3. Credential leakage — fixture file**

`tests/orchestrator/fixtures/m12_t01_pre_t02_spawn_prompt.txt` is a 185-line synthetic prose fixture. Grep for `GEMINI_API_KEY`, `API_KEY`, `token`, `secret`, `password`, `Bearer`, `Authorization`, `http`, `localhost`, `127.`, `PYPI`, `.env` all returned zero hits. The fixture contains only synthetic task-spec content with `PRE-T02 bloat` markers; no real-looking secrets or internal URLs. Clean.

**4. KDR-section extractor robustness**

`extract_cited_kdrs()` in `_helpers.py`: uses `re.compile(r"\bKDR-(\d{1,3})\b")` — word-boundary anchored, 1–3 digits only. Malformed `KDR-ABC` inputs are correctly rejected (test `test_not_matched_on_partial_word` verifies). Empty input returns empty list (test `test_empty_string_returns_empty` verifies). No crash path on malformed input — the regex simply matches nothing.

`extract_kdr_sections()`: missing §9 header in `architecture_text` → `_KDR_ROW_RE.finditer` returns no matches → falls through to `build_kdr_compact_pointer(cited_kdrs)` (the non-empty fallback). No panic. Malformed table rows (missing `|` delimiters) are skipped by the regex without raising. No silent content pass-through: if no rows match, the compact pointer is returned rather than empty string.

`build_kdr_compact_pointer([])`: returns `_KDR_GRID_HEADER` (the compact header-only string). Confirmed safe for empty input.

**5. runs/ path traversal**

`runs/<task>/cycle_<N>/spawn_<agent>.tokens.txt` — this is documentation prose for the orchestrator (a Claude Code conversation), not Python code. The `<task>` value comes from the slash-command's `$ARGUMENTS` (a task identifier like `m12 t01`), and `<agent>` comes from the agent registry (`builder`, `auditor`, etc.) — both are controlled, not external attacker input. In this single-user, local-machine threat model there is no untrusted external source for these values. No path-traversal risk.

**6. Spec-preservation invariant (spec line 13)**

`.claude/agents/auditor.md` is unchanged on this branch (`git status` confirms no entries under `.claude/agents/`). The "load the full task scope, not the diff" mandate at line 16 of `auditor.md` is intact. T02 prunes the *orchestrator's pre-load* via slash commands; the Auditor's own internal Read discipline is separate and unaffected.

**7. Logging hygiene**

No new `StructuredLogger` calls added. No `ai_workflows/` code changed. No log-hygiene concern introduced by T02.

**8. Dependency CVEs**

No `pyproject.toml` or `uv.lock` changes in T02. Dependency audit not triggered; defer to prior dependency-auditor pass.

### 🔴 Critical — must fix before publish/ship

None.

### 🟠 High — should fix before publish/ship

None.

### 🟡 Advisory — track; not blocking

**SDist includes `.github/` and `.env.example`** (pre-existing, not T02-introduced). `.env.example` is placeholder-only; `.github/` contains CI config with no secrets. These were present before T02 and are excluded from the wheel by `packages = ["ai_workflows"]`. No action required for T02; carry-forward from prior audits if ever remediated.

## Dependency audit (2026-04-28)

Dependency audit: skipped — no manifest changes. `git diff --name-only HEAD` shows neither `pyproject.toml` nor `uv.lock` was modified by T02.

---

## Sr. Dev review (2026-04-28)

**Files reviewed:**
- `.claude/commands/auto-implement.md`
- `.claude/commands/clean-implement.md`
- `.claude/commands/clean-tasks.md`
- `.claude/commands/queue-pick.md`
- `.claude/commands/autopilot.md`
- `.claude/commands/_common/spawn_prompt_template.md`
- `tests/orchestrator/_helpers.py`
- `tests/orchestrator/test_spawn_prompt_size.py`
- `tests/orchestrator/test_kdr_section_extractor.py`

**Skipped (out of scope):** `.claude/agents/auditor.md` — confirmed unchanged; Auditor-preservation invariant intact.

**Verdict:** FIX-THEN-SHIP

---

### 🔴 BLOCK — must-fix before commit

None.

---

### 🟠 FIX — fix-then-ship

#### FIX-1 — Stale procedure prose contradicts scope-discipline section in `auto-implement.md` and `clean-implement.md`

**Lens:** Hidden bugs that pass tests.

**Files:** `.claude/commands/auto-implement.md:184`, `.claude/commands/auto-implement.md:208`, `.claude/commands/clean-implement.md:149`, `.claude/commands/clean-implement.md:173`.

Both files now contain two layers of guidance: (a) a `## Spawn-prompt scope discipline` section (added by T02) that correctly states "remove architecture.md content, pass only cited KDR identifiers"; (b) the pre-T02 procedure step paragraphs at Steps 2 and S1 that still read `architecture docs + KDR paths`. An orchestrator following the step text — which reads sequentially and is operationally closer than the section header — would pass full `architecture docs` content inline, directly defeating the pruning that T02 exists to establish.

The tests pass because `tests/orchestrator/test_spawn_prompt_size.py` exercises `_helpers.py` builder functions that implement the discipline correctly — they have no binding to the step paragraphs the orchestrator actually reads. The contradiction is between two regions of the same prose file; the tests cannot catch it.

Reproduction shape: orchestrator follows Step 2 text literally → Auditor spawn includes `architecture docs + KDR paths` (full content) → spawn bloats past the 6K ceiling → T02's stated purpose is not achieved even though all tests pass.

**Action:** Edit `auto-implement.md` Step 2 (line 184) and Step S1 (line 208), and the identical lines in `clean-implement.md` (lines 149 and 173), to replace `architecture docs + KDR paths, gate commands,` with `cited KDR identifiers (compact pointer per scope-discipline section above), gate commands,`. This makes the step text agree with the discipline section.

**Trade-off:** One-line prose fix per occurrence; no semantic change to the discipline section; no test changes needed. Single clear recommendation; no KDR conflict.

---

#### FIX-2 — `autopilot.md` summary table omits `dependency-auditor` and `architect` from Reviewers row

**Lens:** Idiom alignment / drift between template and commands.

**File:** `.claude/commands/autopilot.md:51`.

The autopilot summary table row for "Reviewers" lists `sr-dev, sr-sdet, security-reviewer` but omits `dependency-auditor`. This matches the LOW-1 pattern the Auditor already flagged for `auto-implement.md`'s section *header* — but the autopilot table is the operative reference that an orchestrator running autopilot reads when composing reviewer spawns. Additionally, `architect` has a budget entry in the canonical template (line 110 of `spawn_prompt_template.md`) but appears nowhere in `autopilot.md`'s summary table.

The canonical template's `### Reviewer spawns` header (line 56) explicitly names all four: `sr-dev, sr-sdet, security-reviewer, dependency-auditor`. The `architect` section is a separate entry (lines 84–90). The autopilot table collapses these into one Reviewers row without mentioning either dependency-auditor or architect, creating a decision gap: should the autopilot orchestrator apply dependency-auditor's scope discipline or not?

**Action:** Edit `.claude/commands/autopilot.md` line 51 to read `Reviewers (sr-dev, sr-sdet, security-reviewer, dependency-auditor)` and add a row for `architect` pointing to `spawn_prompt_template.md §architect`. This is a documentation fix with no semantic change to the underlying logic (the `auto-implement.md` procedure already describes the architect spawn in Step T3).

**Trade-off:** Two-line table change; aligns the autopilot table with the canonical template. No KDR conflict; single clear recommendation.

---

### 🟡 Advisory — track but not blocking

#### ADV-1 — `build_reviewer_spawn_prompt` in `_helpers.py` uses `agent_name` parameter but never incorporates it into the returned prompt text

**Lens:** Simplification / hidden cost.

**File:** `tests/orchestrator/_helpers.py:272–317`.

`build_reviewer_spawn_prompt` accepts `agent_name: str = "reviewer"` but the parameter is never used in the returned string — the budget directive and schema reminder are identical for all reviewer agents, and nothing in the prompt is keyed to `agent_name`. The parameter exists in the signature with no runtime effect. The tests pass correctly because the ceiling assertions don't depend on agent-specific content being stamped into the prompt. This is a cosmetic dead parameter, not a bug.

**Action / Recommendation:** Remove `agent_name` from the signature (or use it to stamp the agent name into a header line). One-line change; Advisory only because the tests exercise the function without it and the ceiling assertions remain valid.

#### ADV-2 — `token_count_proxy` returns `float` but `AGENT_SPAWN_CEILINGS` maps to `int`; comparison is implicit

**Lens:** Simplification.

**File:** `tests/orchestrator/_helpers.py:27–40`.

`token_count_proxy` returns `float` (Python multiplies `int * float` to `float`). `AGENT_SPAWN_CEILINGS` values are `int`. The comparison `token_count_proxy(prompt) <= AGENT_SPAWN_CEILINGS["builder"]` is `float <= int`, which Python evaluates correctly. Not a bug. But the spec says "truncated to int" for the instrumentation files. The helper's return type (`float`) diverges from the prose spec ("truncated to int") and from the test that reads `spawn_<agent>.tokens.txt` expecting an integer. Consider returning `int(len(re.findall(...)) * 1.3)` so the helper matches the spec and the file format.

**Action / Recommendation:** Change return to `int(len(re.findall(r"\S+", text)) * 1.3)` in `_helpers.py:40`. One-line fix; keeps the helper type-consistent with both the spec and the file-format tests.

---

### What passed review (one-line per lens)

- **Hidden bugs:** FIX-1 above — stale procedure prose in Step 2 / Step S1 contradicts scope-discipline section in both `auto-implement.md` and `clean-implement.md`; tests pass because helpers implement the discipline correctly but don't bind to the prose orchestrators actually follow.
- **Defensive-code creep:** None observed. No gratuitous guards, no backwards-compat shims, no multi-mode flags.
- **Idiom alignment:** FIX-2 above — autopilot summary table omits dependency-auditor and architect vs. canonical template; pattern matches Auditor LOW-1 but at a more operationally consequential location (table vs. header text). `_helpers.py` uses `structlog`-free, `logging`-free design appropriate for test infrastructure under `tests/`.
- **Premature abstraction:** None. `_common/spawn_prompt_template.md` has 5 immediate callers (all 5 commands) — not a single-caller abstraction. `_helpers.py` helper functions have 2 test files as callers; justified by the Auditor's own justification in the issue file.
- **Comment / docstring drift:** None. Module docstring cites M20 T02 and relationship to other modules per project convention. Function docstrings are appropriately concise.
- **Simplification:** ADV-1 (dead `agent_name` parameter) and ADV-2 (`float` vs. `int` return type mismatch with spec prose) — both Advisory.

---

## Sr. SDET review (2026-04-28)

**Test files reviewed:**
- `tests/orchestrator/__init__.py`
- `tests/orchestrator/_helpers.py`
- `tests/orchestrator/test_kdr_section_extractor.py`
- `tests/orchestrator/test_spawn_prompt_size.py`
- `tests/orchestrator/fixtures/m12_t01_pre_t02_spawn_prompt.txt`

**Skipped (out of scope):** `tests/agents/_helpers.py` (T01 scope; read for proxy-constant drift comparison only — not reviewed as a T02 deliverable).

**Verdict:** FIX-THEN-SHIP

---

### 🔴 BLOCK — tests pass for the wrong reason

None.

---

### 🟠 FIX — fix-then-ship

#### FIX-SDET-1 — `test_spawn_tokens_no_cycle_suffix_in_filename` is a tautological assertion (Lens 1)

`tests/orchestrator/test_spawn_prompt_size.py:484–492`

The test constructs the string `filename = "spawn_auditor.tokens.txt"` itself (a literal defined in the test body) and then asserts properties about that literal:

```python
filename = "spawn_auditor.tokens.txt"
assert not re.search(r"_\d+\.tokens\.txt$", filename)
assert filename.startswith("spawn_")
assert filename.endswith(".tokens.txt")
```

All three assertions trivially pass because the test authored the value being tested. No production code is exercised. If the orchestrator instrumentation used `spawn_auditor_1.tokens.txt` as its naming convention, this test would still pass unchanged. The test gives false coverage signal for AC-5 alongside the companion `test_spawn_tokens_file_path_convention` which does use `tmp_path` and creates a real file.

The companion test (line 454) is sound — it builds an auditor prompt, writes the token count, and asserts the file has the right name and integer content. The tautology test adds no incremental coverage.

**Action / Recommendation:** Delete `test_spawn_tokens_no_cycle_suffix_in_filename` (lines 484–492) and, if the naming-convention assertion is considered valuable, extend `test_spawn_tokens_file_path_convention` to parametrise over at least two agent names (e.g. `auditor` and `builder`) and verify that neither produces a `_<N>` suffix in its filename. This keeps the convention test data-driven rather than self-proving.

---

#### FIX-SDET-2 — `dependency-auditor` missing from reviewer ceiling parametrize (Lens 2)

`tests/orchestrator/test_spawn_prompt_size.py:290`

```python
@pytest.mark.parametrize("agent_name", ["sr-dev", "sr-sdet", "security-reviewer"])
def test_token_count_within_ceiling(self, agent_name: str) -> None:
```

`AGENT_SPAWN_CEILINGS` in `_helpers.py:55` defines `"dependency-auditor": 4_000`. The `dependency-auditor` is a reviewer-group agent sharing `build_reviewer_spawn_prompt`, yet it is absent from the parametrize. Its 4K ceiling is never asserted by any test. The Auditor's AC-3 grading counts 24 passing tests and states "reviewers ≤ 4K all asserted" but one reviewer-group member is not covered.

This is the test-side mirror of Auditor LOW-1 and Sr. Dev FIX-2: the `dependency-auditor` is structurally included in the reviewer group throughout the codebase but excluded from the test parametrize.

**Action / Recommendation:** Add `"dependency-auditor"` to the parametrize list:
```python
@pytest.mark.parametrize("agent_name", ["sr-dev", "sr-sdet", "security-reviewer", "dependency-auditor"])
```
One-word addition; `AGENT_SPAWN_CEILINGS["dependency-auditor"]` already exists so the ceiling lookup will resolve without further changes.

---

#### FIX-SDET-3 — `extract_kdr_sections` normalisation asymmetry is a latent bug with no test (Lens 2)

`tests/orchestrator/_helpers.py:155` / `tests/orchestrator/test_kdr_section_extractor.py` (no test covers this path)

`extract_kdr_sections` builds `cited_set` directly from the caller-supplied list without normalising (line 155: `cited_set = set(cited_kdrs)`), but normalises table-row IDs in the match loop (line 164: `f"KDR-{parts[1].zfill(3)}"`). If a caller passes unnormalised IDs (e.g. `["KDR-3"]` instead of `["KDR-003"]`) directly to `extract_kdr_sections` — bypassing `extract_cited_kdrs` — the match fails silently and the compact-pointer fallback fires. The caller receives no rows even though the KDR exists in the table.

All current tests use the full pipeline (`extract_cited_kdrs` → `extract_kdr_sections`) which pre-normalises, so the bug is latent. The docstring says `cited_kdrs: Identifiers to extract (from :func:\`extract_cited_kdrs\`)`, which is the intended usage, but a callers who skips the pipeline get wrong results silently with no error.

**Action / Recommendation:** Choose one of:
- (a) Add a test that passes `["KDR-3"]` directly to `extract_kdr_sections` and asserts the compact-pointer fallback — this documents the footgun as intended behaviour.
- (b) Add a normalisation step inside `extract_kdr_sections` (`cited_set = {f"KDR-{c.split('-')[1].zfill(3)}" for c in cited_kdrs if '-' in c}`) to make it robust to unnormalised input, then add a test that verifies the unnormalised path produces rows. Option (b) eliminates the footgun; option (a) documents it.

---

### 🟡 Advisory — track but not blocking

#### ADV-SDET-T02-1 — `test_no_full_source_inlined` banned markers are strings that `build_reviewer_spawn_prompt` would never produce even if broken (Lens 1 adjacent)

`tests/orchestrator/test_spawn_prompt_size.py:332–352`

The banned markers `"from ai_workflows.primitives"` and `"class TierConfig:"` are Python module-level import and class definition strings. `build_reviewer_spawn_prompt` constructs a prompt from path strings, `project_context_brief`, `files_touched` paths, and a `git_diff` — none of which would contain these strings unless the caller deliberately injected them into the `git_diff` fixture. The test cannot detect the actual concern (bulk milestone-README or full architecture.md content being inlined) because it checks for markers that would only appear from a verbatim file-read, not from partial-content inlining.

**Recommendation:** Supplement with a test that places a synthetic "banned slug" (e.g. `"## Milestone README content (inlined"`) in a modified fixture and confirms it is absent from the reviewer spawn prompt. This gives the test real discriminating power against content that plausibly could be inlined.

#### ADV-SDET-T02-2 — `test_result_is_sorted` uses a self-referential assertion pattern (Lens 6)

`tests/orchestrator/test_kdr_section_extractor.py:111–115`

`assert result == sorted(result)` is not a tautology (if `result` were unsorted, the assertion would fail), but it is harder to read and debug than an explicit expected value. On failure, the error message shows two differently-ordered lists but does not communicate what the canonical sort order should be.

**Recommendation:** Replace with `assert result == ["KDR-003", "KDR-006", "KDR-013"]` and add a failure message. The explicit expected list documents the sort order as ground truth and produces a clear failure message naming the expected sequence.

#### ADV-SDET-T02-3 — Duplicate `token_count_proxy` in T01 and T02 helpers; 1.3 constant is consistent (no drift) (Lens 3 adjacent)

`tests/agents/_helpers.py:130–144` and `tests/orchestrator/_helpers.py:27–40`

Both modules define identical `token_count_proxy` implementations with `* 1.3`. The constant is consistent — no drift between T01 and T02 (verified by reading both files). Dual definitions mean a future calibration change must update both. No action required for T02; worth consolidating when T22/T23 land (both reference the same proxy per spec).

**Recommendation:** When T22 adds the per-cycle telemetry module, consider extracting the proxy into `tests/_proxy.py` or a `tests/conftest.py` fixture to make it a single source of truth.

---

### What passed review (one-line per lens)

- Tests-pass-for-wrong-reason: FIX-SDET-1 (`test_spawn_tokens_no_cycle_suffix_in_filename` tests a string literal the test itself defined — tautology); no hidden production bug found, but false coverage signal for AC-5.
- Coverage gaps: FIX-SDET-2 (`dependency-auditor` ceiling absent from parametrize); FIX-SDET-3 (`extract_kdr_sections` normalisation asymmetry untested — latent footgun for direct callers); ADV-SDET-T02-1 (absence-of-string banned markers too specific to detect real inlining).
- Mock overuse: none — all tests use pure Python string manipulation; no mocks anywhere in `tests/orchestrator/`.
- Fixture / independence: clean — `tmp_path` used correctly in `TestSpawnTokenInstrumentation`; module-level constants are immutable strings; no env var bleed; no order dependence between tests.
- Hermetic-vs-E2E gating: clean — no network calls, no subprocess invocations, no `AIW_E2E` gate needed or missing in `tests/orchestrator/`.
- Naming / assertion-message hygiene: ADV-SDET-T02-2 (self-referential sortedness assertion — correct but opaque); ADV-SDET-T02-3 (dual `token_count_proxy` — 1.3 constant consistent, no drift).

## Locked team decisions (cycle 1 → cycle 2 carry-over)

Per `/auto-implement` Step T4 #2 (auditor-agreement bypass on FIX-THEN-SHIP), the five FIX findings carry single clear paths consistent with the spec + KDRs (FIX-SDET-3 has two options but the agent's framing ("(b) eliminates the footgun; (a) documents it") makes (b) the obvious robust choice; loop-controller selects (b)). No KDR conflict, no scope expansion, no future-task deferral. Stamped:

- **Locked team decision (loop-controller + sr-dev concur, 2026-04-28)** — FIX-1: Edit `.claude/commands/auto-implement.md` Step 2 (line 184) and Step S1 (line 208), and the identical lines in `.claude/commands/clean-implement.md` (lines 149 and 173), to replace `architecture docs + KDR paths, gate commands,` with `cited KDR identifiers (compact pointer per scope-discipline section above), gate commands,`. Aligns the step prose with the `## Spawn-prompt scope discipline` section in the same file; eliminates the contradiction that would have orchestrators inline architecture.md content despite T02's pruning rules.

- **Locked team decision (loop-controller + sr-dev concur, 2026-04-28)** — FIX-2: Edit `.claude/commands/autopilot.md` line 51 (Reviewers row in the summary table) to read `Reviewers (sr-dev, sr-sdet, security-reviewer, dependency-auditor)`, and add a row for `architect` pointing to `spawn_prompt_template.md §architect`. Aligns the autopilot table with the canonical template's reviewer-group enumeration.

- **Locked team decision (loop-controller + sr-sdet concur, 2026-04-28)** — FIX-SDET-1: Delete `test_spawn_tokens_no_cycle_suffix_in_filename` (lines 484–492 of `tests/orchestrator/test_spawn_prompt_size.py`) and extend `test_spawn_tokens_file_path_convention` to parametrize over at least two agent names (`auditor`, `builder`) verifying neither produces a `_<N>` suffix. Removes the tautological self-defined-string assertion and replaces it with real coverage.

- **Locked team decision (loop-controller + sr-sdet concur, 2026-04-28)** — FIX-SDET-2: Add `"dependency-auditor"` to the `@pytest.mark.parametrize("agent_name", [...])` list at `tests/orchestrator/test_spawn_prompt_size.py:290`. The 4K ceiling defined in `AGENT_SPAWN_CEILINGS["dependency-auditor"]` will then be asserted alongside the other reviewer-group agents.

- **Locked team decision (loop-controller + sr-sdet concur, 2026-04-28)** — FIX-SDET-3 (option b chosen): Add a normalisation step inside `extract_kdr_sections` (`tests/orchestrator/_helpers.py:155`) so it is robust to unnormalised KDR-ID input from direct callers who skip `extract_cited_kdrs`. Replace `cited_set = set(cited_kdrs)` with a normalising comprehension along the lines of `cited_set = {f"KDR-{c.split('-')[1].zfill(3)}" for c in cited_kdrs if '-' in c}` (Builder picks the exact form). Add a test that verifies the unnormalised path (`["KDR-3"]`) produces rows. Eliminates the silent-empty-result footgun rather than merely documenting it.

Advisories (ADV-1, ADV-2, ADV-SDET-T02-1, ADV-SDET-T02-2, ADV-SDET-T02-3) are not in cycle-2 carry-over — they remain documented for future follow-up.

---

## Cycle 2 audit (2026-04-28)

**Verdict:** ✅ PASS — all 5 locked team decisions landed cleanly; no scope creep; cycle-1 ✅ PASS state preserved for everything else; gates green from clean re-run.

### Locked-decision verification (file-by-file)

| # | Decision | Verification |
| --- | --- | --- |
| 1 | `auto-implement.md` Step 2 + Step S1 + `clean-implement.md` Step 2 + Step S1 prose fix | `git diff` confirms both files at the expected lines: `architecture docs + KDR paths` → `cited KDR identifiers (compact pointer per scope-discipline section above)`. `auto-implement.md:184` (Step 2) + `auto-implement.md:208` (Step S1); `clean-implement.md:149` (Step 2) + `clean-implement.md:173` (Step S1). 4 occurrences fixed, no regressions. |
| 2 | `autopilot.md` summary table — add `dependency-auditor` to Reviewers row + new `architect` row | `autopilot.md:51` now reads `Reviewers (sr-dev, sr-sdet, security-reviewer, dependency-auditor)`; `autopilot.md:52` is the new `architect` row pointing to `spawn_prompt_template.md §architect`. Verified via direct grep. |
| 3 | Delete `test_spawn_tokens_no_cycle_suffix_in_filename`; extend `test_spawn_tokens_file_path_convention` to parametrize `["auditor", "builder"]` | The tautological test is gone (grep returns 0). `test_spawn_tokens_file_path_convention` at `tests/orchestrator/test_spawn_prompt_size.py:457` is now `@pytest.mark.parametrize("agent_name", ["auditor", "builder"])` (line 456). It builds a real prompt for the agent under test, writes a real token-count file via `tmp_path`, and asserts no `_<N>` suffix in the filename. Both parametrize cases pass. |
| 4 | Add `"dependency-auditor"` to `test_token_count_within_ceiling` parametrize | `tests/orchestrator/test_spawn_prompt_size.py:290–292` now reads `@pytest.mark.parametrize("agent_name", ["sr-dev", "sr-sdet", "security-reviewer", "dependency-auditor"])`. The `AGENT_SPAWN_CEILINGS["dependency-auditor"] = 4_000` ceiling is now asserted. The new `[dependency-auditor]` parametrize ID passes. |
| 5 | Normalise input KDR IDs in `extract_kdr_sections` + add `test_unnormalised_kdr_id_still_produces_rows` test | `tests/orchestrator/_helpers.py:159–162` now contains the normalising comprehension: `cited_set = {f"KDR-{c.split('-', 1)[1].zfill(3)}" if c.startswith("KDR-") and "-" in c else c for c in cited_kdrs}`. The new test at `tests/orchestrator/test_kdr_section_extractor.py:227–245` calls `extract_kdr_sections(_ARCH_MD_SECTION_9, ["KDR-3"])` (unnormalised input) and asserts the matching row appears. Test passes — the silent-empty-result footgun is closed. |

All 5 locked decisions are present, exactly as written. No deviations.

### Scope-creep / drive-by check

`git diff --stat` against the last commit shows 8 modified files + 3 untracked:

```
.claude/commands/auto-implement.md                 | 69 ++++++++++++++++++++-
.claude/commands/autopilot.md                      | 35 ++++++++++++
.claude/commands/clean-implement.md                | 69 ++++++++++++++++++++-
.claude/commands/clean-tasks.md                    | 29 +++++++++
.claude/commands/queue-pick.md                     | 28 +++++++++
CHANGELOG.md                                       | 41 ++++++++++++
design_docs/phases/milestone_20_autonomy_loop_optimization/README.md | 4 +-
design_docs/phases/milestone_20_autonomy_loop_optimization/task_02_sub_agent_input_prune.md | 2 +-
```

This is the cumulative cycle-1+cycle-2 diff; T02 has no commits yet (orchestrator owns commits). The cycle-2 increment (vs. cycle-1 baseline reviewed in the existing audit body above) is precisely the 5 locked-decision changes:
- `auto-implement.md` two prose lines (Steps 2 + S1)
- `clean-implement.md` two prose lines (Steps 2 + S1)
- `autopilot.md` one row updated (Reviewers) + one row added (architect)
- `tests/orchestrator/test_spawn_prompt_size.py` two parametrize edits + one test deleted + one test extended to `tmp_path`
- `tests/orchestrator/_helpers.py` one normalisation block (lines 155–162) — replaces single-line `set(cited_kdrs)`
- `tests/orchestrator/test_kdr_section_extractor.py` one new test method

No other code paths touched. No `ai_workflows/` changes. No `pyproject.toml` / `uv.lock` changes (dependency-audit not triggered). No new files. No new dependencies.

### Cycle-1 ✅ PASS state preserved

- `.claude/agents/auditor.md`: unchanged. `git status .claude/agents/` returns no entries. The Auditor's "load full task scope, not the diff" mandate at line 16 is intact.
- All 8 ACs from cycle 1 still met. AC-3 expanded: now 26 tests in `test_spawn_prompt_size.py` (was 24 — `test_spawn_tokens_no_cycle_suffix_in_filename` deleted, `test_spawn_tokens_file_path_convention` parametrized × 2 = +2 passes net, plus `dependency-auditor` parametrize on `test_token_count_within_ceiling` = +1 net = 24 + 2 = 26 actually). AC-4 expanded: 20 tests in `test_kdr_section_extractor.py` (was 19; +1 for the unnormalised test). All other ACs unchanged in shape.
- Status surfaces still aligned (spec, milestone README task table, milestone README Done-when checkbox 2). No status-surface drift introduced.
- Layer rule still kept: 5 / 5 contracts.
- Smoke tests still pass: common template exists, 5 commands link it, 5 commands name "Output budget:".

### Gate re-run table (cycle 2, fresh)

| Gate | Command | Result |
| ---- | ------- | ------ |
| Full pytest | `AIW_BRANCH=design uv run pytest` | **PASS** — 985 passed, 7 skipped, 22 deprecation warnings (pre-existing). +2 vs. cycle 1 (was 983) = +2 new tests (dependency-auditor parametrize, test_unnormalised_kdr_id_still_produces_rows) — 1 deletion (tautology) + 1 parametrize-doubling (auditor + builder) = net +2. |
| Orchestrator-tests | `AIW_BRANCH=design uv run pytest tests/orchestrator/ -v` | **PASS** — 46 / 46 (was 44). |
| Validation re-run | `AIW_BRANCH=design uv run pytest tests/orchestrator/test_spawn_prompt_size.py::test_m12_t01_audit_spawn_30pct_reduction -v` | **PASS** — 1 / 1, ~89% reduction. |
| Layer contracts | `uv run lint-imports` | **PASS** — 5 / 5 contracts kept. |
| Lint | `uv run ruff check` | **PASS** — All checks passed. |
| Smoke 1 — common template exists | `test -f .claude/commands/_common/spawn_prompt_template.md` | **PASS**. |
| Smoke 2 — 5 commands link template | `grep -l "_common/spawn_prompt_template.md" <5 cmds>` | **PASS** — 5. |
| Smoke 3 — 5 commands name budget directive | `grep -l "Output budget:" <5 cmds>` | **PASS** — 5. |

All gates green from clean re-run. The Builder's cycle-2 gate-pass claim is verified.

### New issues — none

The 5 locked decisions land cleanly with no new findings. No new HIGH, MEDIUM, or LOW. The three pre-existing LOWs (ISS-01 auto-implement.md line 80 header text, ISS-02 fixture is conservative synthetic proxy, ISS-03 spawn_prompt_template.md forward markers) remain OPEN as documented — none of them block.

Note on ISS-01: cycle 1's LOW-1 flagged that `auto-implement.md:80` reads `### Reviewer spawns (sr-dev, sr-sdet, security-reviewer)` — missing `dependency-auditor`. Cycle 2's locked decision FIX-2 fixed the analogous omission in `autopilot.md` line 51 (operationally consequential — orchestrator reads the table) but did not extend to `auto-implement.md:80` (the canonical template at `_common/spawn_prompt_template.md:56` already governs reviewer composition, so this header is cosmetic in `auto-implement.md`). ISS-01 stays as a same-task carry-over for next-touch fix; not in cycle-2 scope per the locked decisions.

### Verdict

**PASS** — cycle 2 closes cleanly. The 5 FIX findings from cycle 1 are all resolved at the named locations with the named text. The auditor-preservation invariant (`.claude/agents/auditor.md` unchanged) is intact. All gates re-run green from scratch. No scope creep. No new findings.

---

## Security review — cycle 2 re-check (2026-04-28)

### Scope

Cycle 2 incremental diff only. Five locked-decision changes:
1. `auto-implement.md` Step 2 + Step S1 — prose-only edit (`architecture docs + KDR paths` → `cited KDR identifiers (compact pointer per scope-discipline section above)`).
2. `clean-implement.md` lines 149 / 173 — identical prose edit.
3. `autopilot.md` — added `dependency-auditor` to Reviewers row; added new `architect` row in summary table.
4. `tests/orchestrator/test_spawn_prompt_size.py` — deleted `test_spawn_tokens_no_cycle_suffix_in_filename`; extended `test_spawn_tokens_file_path_convention` to parametrize `["auditor", "builder"]`; added `"dependency-auditor"` to `test_token_count_within_ceiling` parametrize.
5. `tests/orchestrator/_helpers.py` — `extract_kdr_sections` normalises caller-supplied IDs (zero-pads single-digit numbers).
6. `tests/orchestrator/test_kdr_section_extractor.py` — new test `test_unnormalised_kdr_id_still_produces_rows`.
7. `CHANGELOG.md` — single-line cycle-2 note.

### Threat-model checklist (cycle 2 delta)

**1. Wheel-contents leakage**

All cycle-2 changes are in `.claude/commands/` (prose markdown), `tests/orchestrator/` (hermetic test infrastructure), and `CHANGELOG.md`. None of these paths are inside `ai_workflows/` and none are picked up by `[tool.hatch.build.targets.wheel] packages = ["ai_workflows"]`. Wheel contents are identical to cycle 1. No new leakage.

**2. KDR-section normalisation robustness (`tests/orchestrator/_helpers.py:159–162`)**

The new comprehension in `extract_kdr_sections`:

```python
cited_set = {
    f"KDR-{c.split('-', 1)[1].zfill(3)}" if c.startswith("KDR-") and "-" in c else c
    for c in cited_kdrs
}
```

Traced against adversarial inputs:

- `["KDR-"]` (empty suffix): `split('-', 1)[1]` returns `""` (empty string); `"".zfill(3)` returns `"000"`; produces `"KDR-000"`. No table row matches this — safe-fail, no crash.
- `["KDR-foo"]` (non-digit suffix): `split('-', 1)[1]` returns `"foo"`; `"foo".zfill(3)` returns `"foo"` unchanged (string already length 3, `zfill` only pads when shorter than the width); produces `"KDR-foo"`. No table row matches — safe-fail, no crash.
- `["KDR-3"]` (single-digit, intended case): produces `"KDR-003"` — correctly matches the table row. Verified by `test_unnormalised_kdr_id_still_produces_rows`.
- `[]` (empty list): short-circuits at line 152 (`if not cited_kdrs: return _KDR_GRID_HEADER`) before reaching the comprehension. No change to existing safe path.

No panic path, no exception, no silent incorrect match. Safe-fail is the correct behaviour for non-normalised non-integer IDs because they cannot map to any real KDR row.

**3. No new credentials or subprocess calls**

Grep for `subprocess`, `shell=True`, `os.system`, `ANTHROPIC_API_KEY`, `Bearer`, `Authorization` in all three modified slash-command files returns zero hits. Test files (`_helpers.py`, `test_spawn_prompt_size.py`, `test_kdr_section_extractor.py`) confirmed in cycle 1 to use `re` and `pathlib` only — unchanged in cycle 2 (the normalisation addition uses only string operations: `startswith`, `split`, `zfill`, `f-string`).

**4. Autopilot table change**

Documentation-only. No executable code path added. No new agent spawns, no new subprocess calls, no credential reads. The `architect` row and the `dependency-auditor` addition are prose alignment with `_common/spawn_prompt_template.md` — the canonical template already governed these reviewer agents' spawn discipline.

**5. No `pyproject.toml` / `uv.lock` changes**

Confirmed — dependency audit not triggered. No new packages.

### 🔴 Critical — must fix before publish/ship

None.

### 🟠 High — should fix before publish/ship

None.

### 🟡 Advisory — track; not blocking

None new. The pre-existing Advisory from cycle 1 (sdist includes `.github/` and `.env.example`, placeholder-only) is unchanged.

### Verdict: SHIP

---

## Sr. Dev review — cycle 2 re-check (2026-04-28)

**Files reviewed (cycle-2 delta only):**
- `.claude/commands/auto-implement.md` (lines 184, 208)
- `.claude/commands/clean-implement.md` (lines 149, 173)
- `.claude/commands/autopilot.md` (lines 51–52)

**Skipped (out of scope):** All files outside the cycle-2 diff; cycle-1 findings already recorded above.

**Verdict:** SHIP

---

### FIX-1 — resolved

`auto-implement.md:184` now reads `cited KDR identifiers (compact pointer per scope-discipline section above), gate commands,` — the stale `architecture docs + KDR paths` phrase is gone. `auto-implement.md:208` (Step S1) identical fix confirmed. `clean-implement.md:149` and `clean-implement.md:173` carry the same replacement. All four occurrences verified by direct read. The step prose now agrees with the `## Spawn-prompt scope discipline` section in both files.

### FIX-2 — resolved

`autopilot.md:51` reads `Reviewers (sr-dev, sr-sdet, security-reviewer, dependency-auditor)` — `dependency-auditor` present. `autopilot.md:52` is the new `architect` row: `architect | recommendation file path, issue path, context brief, KDR identifiers | full source files, full architecture.md content — see spawn_prompt_template.md §architect`. Both additions match the canonical template at `_common/spawn_prompt_template.md` lines 51–52. No stale prose remains.

### No new findings

No additional BLOCK, FIX, or Advisory findings surfaced in the cycle-2 delta. The cycle-1 advisories (ADV-1 dead `agent_name` parameter, ADV-2 float vs int return type) were not addressed per instructions and are not re-raised here.

### What passed review (cycle-2 delta)

- Hidden bugs: none in cycle-2 diff; FIX-1 prose contradiction closed.
- Defensive-code creep: none introduced.
- Idiom alignment: FIX-2 table alignment complete; template and autopilot table now agree.
- Premature abstraction: none introduced.
- Comment / docstring drift: none introduced.
- Simplification: no new opportunities in cycle-2 delta.

---

## Sr. SDET review — cycle 2 re-check (2026-04-28)

**Test files reviewed:**
- `tests/orchestrator/_helpers.py` (normalisation comprehension at lines 155–162)
- `tests/orchestrator/test_spawn_prompt_size.py` (parametrize changes + tautology deletion)
- `tests/orchestrator/test_kdr_section_extractor.py` (new `test_unnormalised_kdr_id_still_produces_rows`)

**Skipped (out of scope):** cycle-1 advisories ADV-SDET-T02-1 through ADV-SDET-T02-3 per invoker instruction.

**Verdict:** SHIP

---

### 🔴 BLOCK — tests pass for the wrong reason

None.

---

### 🟠 FIX — fix-then-ship

None.

---

### 🟡 Advisory — track but not blocking

None new. All three cycle-1 FIX findings verified closed; no regressions.

---

### Verification findings (four questions from invoker)

**Q1 — Deleted tautology vs. extended parametrize: coverage intact?**

Confirmed intact. `test_spawn_tokens_file_path_convention` (lines 456–508) is now `@pytest.mark.parametrize("agent_name", ["auditor", "builder"])`. For each agent it builds a real prompt via the production helper, writes the token-count file to `tmp_path`, reads it back, and asserts `content.isdigit()`, `not re.search(r"_\d+\.tokens\.txt$", tokens_file.name)`, and `tokens_file.name == f"spawn_{agent_name}.tokens.txt"`. The no-suffix assertion now exercises a `Path.name` derived from the actual file written, not a self-defined string literal. Coverage is correct and improved versus the deleted test.

**Q2 — Is `test_unnormalised_kdr_id_still_produces_rows` genuinely discriminating?**

Yes. Lines 227–245 call `extract_kdr_sections(_ARCH_MD_SECTION_9, ["KDR-3"])` (the exact spec example). Without the normalisation comprehension, `cited_set` would be `{"KDR-3"}`, which would not match the `"KDR-003"` row — the function would fall through to `build_kdr_compact_pointer`, returning the grid header. The grid header does not contain `"No Anthropic API"` or `"KDR-003"` as a table row. Both assertions at lines 241 and 245 would therefore fail. The test catches a genuine regression in the comprehension.

**Q3 — Normalisation comprehension edge-case robustness (`_helpers.py:159–162`):**

All edge cases are safe-fail with no crash and no silent miscoercion:

- `"KDR-"` (empty suffix): `split('-', 1)[1]` = `""`; `"".zfill(3)` = `"000"`; produces `"KDR-000"`. No table row matches. Safe-fail.
- `"KDR-foo"` (non-digit suffix): `"foo".zfill(3)` = `"foo"` (already 3 chars; `zfill` only left-pads, never truncates). Produces `"KDR-foo"`. No table row matches. Safe-fail.
- `"KDR-9999"` (already 4 digits): `"9999".zfill(3)` = `"9999"` (zfill never truncates). Produces `"KDR-9999"`. No table row matches. Safe-fail.
- Multi-dash `"KDR-0-extra"`: `split('-', 1)` gives `["KDR", "0-extra"]`; `"0-extra".zfill(3)` = `"0-extra"`. Produces `"KDR-0-extra"`. No table row matches. Safe-fail.
- `"not-a-kdr"`: `startswith("KDR-")` is False; falls to `else c` branch and passes through unchanged. No match.

The `split('-', 1)` maxsplit guard means `[1]` is safe whenever `"-" in c` is True (two-element list guaranteed). No `IndexError` path exists. Consistent with security reviewer's analysis in the cycle-2 security re-check section above.

**Q4 — Cycle-1 advisories not re-raised:** Correctly omitted per invoker scope restriction.

---

### What passed review (one-line per lens)

- Tests-pass-for-wrong-reason: none observed — extended `test_spawn_tokens_file_path_convention` asserts against a real file path, not a self-defined literal; `test_unnormalised_kdr_id_still_produces_rows` would catch a regression in the normalisation comprehension.
- Coverage gaps: none — FIX-SDET-1 (tautology deletion + parametrize extension), FIX-SDET-2 (`dependency-auditor` parametrize addition), and FIX-SDET-3 (normalisation + new test) all confirmed closed at their named locations.
- Mock overuse: none — tests remain pure-Python string manipulation; no mocks introduced by cycle-2 changes.
- Fixture / independence: clean — `tmp_path` scoping correct for both parametrize variants; module-level constants immutable; no env-var bleed; no order dependence.
- Hermetic-vs-E2E gating: clean — no network calls, no subprocess invocations, no missing gate.
- Naming / assertion-message hygiene: clean — `test_unnormalised_kdr_id_still_produces_rows` is descriptive; failure message at line 242 names the expected normalisation and shows `result!r`.
