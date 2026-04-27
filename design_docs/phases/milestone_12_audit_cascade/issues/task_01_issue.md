# Task 01 — Auditor TierConfigs — Audit Issues

**Source task:** [../task_01_auditor_tier_configs.md](../task_01_auditor_tier_configs.md)
**Audited on:** 2026-04-27 (cycle 1 + cycle 2)
**Audit scope:** Cycle 1 of /auto-implement reviewed: `ai_workflows/workflows/planner.py` (auditor entries), `ai_workflows/workflows/summarize_tiers.py` (auditor entries + imports + docstring), `ai_workflows/workflows/slice_refactor.py` (docstring), `tests/workflows/test_auditor_tier_configs.py` (new, 7 tests), `tests/graph/test_auditor_tier_override.py` (new, 4 tests), `tests/workflows/test_slice_refactor_fanout.py` (composes-tiers test extended), CHANGELOG entry, spec `**Status:**` line + AC ticks + carry-over ticks, milestone README task-table row + Exit-criteria bullet 1, ADR-0004, architecture.md §3 / §4.1 / §4.2 / §9 (KDR-003 / KDR-004 / KDR-006 / KDR-011 / KDR-013), `claude_code.py` driver, `primitives/tiers.py` (zero diff confirmed), `pricing.yaml` (`claude-sonnet-4-6`, `claude-opus-4-7`, `claude-haiku-4-5-20251001` already at zero rate). Cycle 2 re-grade verified: spec lines 4 + 10 (LOW-1 fixes), zero source/test/CHANGELOG/ADR/pricing.yaml diff (Builder docs-only delta), pytest re-run twice consecutively (759 passed / 9 skipped both runs — no flake reproduced).
**Status:** ✅ PASS — FUNCTIONALLY CLEAN, ready for security gate. LOW-1 resolved in cycle 2; LOW-2 deferred to M12 T07; LOW-3 deferred-informational (self-resolves at T02 cycle 1). All 11 ACs met; all 5 carry-over items resolved or properly deferred.

## Design-drift check

- **KDR-003 (no Anthropic API).** Both new tier registrations route through `ClaudeCodeRoute(cli_model_flag="sonnet"|"opus")` which the existing `ClaudeCodeSubprocess` driver invokes via `claude --print --model <flag>` (OAuth subprocess). Zero new `anthropic` SDK imports, zero new `ANTHROPIC_API_KEY` reads in any modified file. Tree-wide guard `tests/workflows/test_slice_refactor_e2e.py::test_kdr_003_no_anthropic_in_production_tree` re-run from scratch — PASS. File-scoped guard `test_no_anthropic_sdk_import_in_planner_or_claude_code_driver` — PASS.
- **KDR-004 (validator pairing).** N/A at T01 — no new TieredNode wired in; validator pairing concern lands at T02/T03.
- **KDR-006 (3-bucket retry).** N/A at T01 — no new exception surface; `AuditFailure` lands at T02 per spec.
- **KDR-008 (FastMCP public contract).** No `ai_workflows/mcp/` diff. Confirmed via `git diff HEAD -- ai_workflows/mcp/` (empty).
- **KDR-009 (SqliteSaver-only).** N/A — no checkpoint code.
- **KDR-011 (tiered audit cascade).** This task implements the foundation row 1 of KDR-011 ("auditor tiers route through `ClaudeCodeRoute`(...sonnet/opus) over the OAuth CLI — KDR-003 preserved"). Landing site (workflow modules, not `primitives/tiers.py`) deviates from ADR-0004 §Decision item 1 framing but is consistent with the post-M19 workflow-scoped registry pattern; spec carry-over TA-LOW-03 already flags this as a known stale framing in ADR-0004.
- **KDR-013 (user-owned external code).** N/A — no external loader change.
- **Four-layer rule.** No layer crossings. `workflows/summarize_tiers.py` import surface grew `ClaudeCodeRoute` from `primitives/tiers` only — `workflows → primitives` is an allowed direction. `lint-imports` re-run from scratch — 4 contracts kept.
- **No drift detected** in code surface. The only drift-adjacent observation is the unfixed-but-ticked spec citations (TA-LOW-01 / TA-LOW-04) — see findings below.

## AC grading

| AC | Status | Notes |
| -- | ------ | ----- |
| AC-1 — `auditor-sonnet` exists with `ClaudeCodeRoute(cli_model_flag="sonnet")` | ✅ MET | Present in `planner_tier_registry()` lines 692-697 + `summarize_tier_registry()` lines 59-64 + (via composition) `slice_refactor_tier_registry()`. Asserted by `test_auditor_sonnet_tier_resolves_to_cli_sonnet_in_planner` + sibling tests across all three registries. |
| AC-2 — `auditor-opus` exists with `ClaudeCodeRoute(cli_model_flag="opus")` | ✅ MET | Present in `planner_tier_registry()` lines 698-703 + `summarize_tier_registry()` lines 65-70 + (via composition) slice_refactor. Asserted across all three registries. |
| AC-3 — Pricing covered by existing `pricing.yaml` | ✅ MET | `claude-sonnet-4-6`, `claude-opus-4-7`, `claude-haiku-4-5-20251001` already in `pricing.yaml` at zero rate (Max flat-rate). `_find_primary_key` substring match resolves `--model sonnet` → `claude-sonnet-4-6`. No `pricing.yaml` edit required. The TA-LOW-05 belt-and-braces spot-check (a real `claude --print --model sonnet` ping) was *not* run in cycle 1 — see LOW-3 below. |
| AC-4 — `per_call_timeout_s=300` matches `planner-synth` baseline | ✅ MET | All four new entries (sonnet+opus across planner+summarize) carry `max_concurrency=1` + `per_call_timeout_s=300`. Asserted on every new test. No deviation; no named-evidence comment needed. |
| AC-5 — `_mid_run_tier_overrides` resolves new tiers by name | ✅ MET | `tests/graph/test_auditor_tier_override.py` covers state-layer override for both `auditor-sonnet → auditor-opus` and `auditor-opus → planner-synth` plus identity fall-through for both. `_resolve_tier` is called directly with the documented signature; M8 T04 precedence rule unchanged. |
| AC-6 — KDR-003 guardrail tests pass | ✅ MET | Re-ran `test_kdr_003_no_anthropic_in_production_tree` (tree-wide grep) and `test_no_anthropic_sdk_import_in_planner_or_claude_code_driver` (file-scoped) — both PASS. The single `anthropic` token in `planner.py:21` is in a docstring asserting *absence* of the SDK; the existing tree-wide grep already accommodates docstring mentions (it matches actual import statements + env-var reads, not arbitrary substring). |
| AC-7 — No `ai_workflows/workflows/` *cascade-wiring* diff | ✅ MET | Spec was amended in cycle 1 (added "cascade-wiring" qualifier + clarifying note). The amendment is consistent with §Deliverables, which names workflow files as the explicit landing site for tier-registration. No `AuditCascadeNode` import, no `audit_cascade_enabled` field, no new edges/nodes — `grep -rn "AuditCascadeNode\|audit_cascade_enabled" ai_workflows/` returns only the docstring forward-reference at `summarize_tiers.py:41`. Cascade wiring is correctly deferred to T03. Builder's interpretation accepted. |
| AC-8 — No `ai_workflows/mcp/` diff | ✅ MET | `git diff HEAD -- ai_workflows/mcp/` empty. |
| AC-9 — Gates clean (`pytest`, `lint-imports`, `ruff check`) | ✅ MET | Re-run from scratch: `uv run pytest` → 759 passed, 9 skipped (Builder's report verified). `uv run lint-imports` → 4 contracts kept. `uv run ruff check` → All checks passed!. |
| AC-10 — CHANGELOG entry under `[Unreleased]` | ✅ MET | Entry at lines 10-53 of CHANGELOG; lists files touched, ACs satisfied (1-11), KDR-003 note. Cites ADR-0004 + KDR-011. |
| AC-11 — Status surfaces flipped together | ✅ MET | (a) Per-task spec `**Status:**` → `✅ Complete (2026-04-27)`. (b) Milestone README task table row 01 → `✅ Complete (2026-04-27)` (table grew a `Status` column in this cycle, all rows populated). (c) Milestone README §Exit criteria bullet 1 → checkmarked + dated. There is no `tasks/README.md` for M12. The milestone README top-level `**Status:**` remains `📝 Planned` which is correct (only T01 of 7 is done). |

**Carry-over from task analysis (graded individually):**

| TA item | Status | Notes |
| ------- | ------ | ----- |
| TA-LOW-01 — Drop stray `claude_code.py:254` cross-reference from spec | ✅ APPLIED (cycle 2) | Cycle-2 diff confirms §Grounding line 4 changed `[claude_code.py:9,119-129,254]` → `[claude_code.py:9,119-129]`; §What-to-Build line 10 dropped the parenthetical `, [claude_code.py:254](...)`. LOW-1 closed. |
| TA-LOW-02 — `isinstance(route, ClaudeCodeRoute)` narrowing in tests #1/#2 | ✅ APPLIED (cycle 1) | `test_auditor_tier_configs.py` lines 45-47 + 64-66 use `assert isinstance(route, ClaudeCodeRoute)` before accessing `cli_model_flag`. Optional `route.kind == "claude_code"` assertion also added (lines 48 + 67). |
| TA-LOW-03 — ADR-0004 §Decision item 1 stale framing | ✅ HONOURED AS WRITTEN | TA-LOW-03's own recommendation is "Do not amend ADR-0004 as part of T01; flag for the Auditor's surface-cite check at audit time." Re-confirmed: ADR-0004 line 25 still reads `"Both sit in the TierRegistry (ai_workflows/primitives/tiers.py) next to planner-synth"` which is stale, and ADR line 55 still says new TierConfigs land in `ai_workflows/primitives/tiers.py`. Per the carry-over's recommendation, this is correctly deferred to milestone close-out (M12 T07). See LOW-2 (informational forward-deferral). |
| TA-LOW-04 — Reorder §Grounding architecture cite to `§4.2 / §4.1` | ✅ APPLIED (cycle 2) | Cycle-2 diff confirms §Grounding line 4 changed `architecture.md §4.1 / §4.2` → `architecture.md §4.2 (graph adapters where TieredNode resolves the tier) / §4.1 (primitives where TierConfig is defined)`. LOW-1 closed. |
| TA-LOW-05 — `pricing.yaml` spot-check via real `claude --print` ping | ⚠️ OPTIONAL, NOT EXECUTED — DEFERRED | Recommendation was a real-CLI ping to verify `modelUsage` keys. Builder ticked `[x]` without running the ping; cycle-2 audit-recommendation was to leave deferred (T02 will exercise the path naturally; OAuth-touching ping is `AIW_E2E=1` territory). AC-3 is met by the existing `pricing.yaml` rows + substring-match resolution. See LOW-3 (informational, owner = T02 Builder or operator). |

## 🔴 HIGH

*None.*

## 🟡 MEDIUM

*None.* The unfixed spec citations are cosmetic and do not affect runtime behaviour, tests, or the ledger; AC-3's pricing coverage is empirically present in `pricing.yaml`. No code-surface concern justifies MEDIUM.

## 🟢 LOW

### LOW-1 — TA-LOW-01 + TA-LOW-04 ticked done without the spec edits applied (spec drift) — RESOLVED (cycle 2, 2026-04-27)

**Symptom (cycle 1).** The spec's §Carry-over from task analysis section was edited so that all five `[ ]` boxes flipped to `[x]`. For TA-LOW-02 and TA-LOW-05, the underlying recommendation was either applied (LOW-02 — `isinstance` narrowing visible in the test file) or honoured as written (LOW-05 — optional spot-check, AC met by other evidence). For TA-LOW-01 and TA-LOW-04, the recommendation was a one-line spec edit (drop `,254` from §Grounding + drop the §What-to-Build line-10 cite to `:254`; reorder §Grounding to `§4.2 / §4.1`). Neither edit was applied; the boxes were ticked anyway.

**Cycle-2 resolution.** Builder applied both missed edits in cycle 2 (docs-only delta, zero source/test/CHANGELOG diff). Verified by `git diff HEAD -- design_docs/phases/milestone_12_audit_cascade/task_01_auditor_tier_configs.md`:
- §Grounding line 4: `[claude_code.py:9,119-129,254]` → `[claude_code.py:9,119-129]` ✅
- §Grounding line 4: `architecture.md §4.1 / §4.2` → `architecture.md §4.2 (graph adapters where TieredNode resolves the tier) / §4.1 (primitives where TierConfig is defined)` ✅
- §What-to-Build line 10: parenthetical `, [claude_code.py:254](...)` dropped ✅

LOW-1 closed.

### LOW-2 — ADR-0004 §Decision item 1 + §Consequences carry stale `primitives/tiers.py` framing (forward-deferred per TA-LOW-03)

**Symptom.** ADR-0004 line 25 (`Both sit in the TierRegistry (ai_workflows/primitives/tiers.py) next to planner-synth`) and line 55 (`New TierConfigs. auditor-sonnet + auditor-opus land in ai_workflows/primitives/tiers.py (M12 T01) with matching pricing entries`) describe a landing site that the M19-era workflow-scoped registry pattern superseded. T01 spec correctly lands the entries in workflow modules (`workflows/planner.py`, `workflows/summarize_tiers.py`).

**Impact.** Documentation drift only. Future readers consulting ADR-0004 to understand T01's landing site will find a citation that does not match the code.

**Action / Recommendation.** Per TA-LOW-03's explicit recommendation, deferred to M12 close-out (T07) for a standalone ADR amendment (a one-line tweak to lines 25 + 55 noting "landing site amended at M12 T01 spec authoring — see workflow tier registries"). DO NOT amend ADR-0004 as part of T01. Owner: M12 T07 (close-out).

**Forward-deferral propagation.** M12 T07 spec does not yet exist (per `Per-task spec files land as each predecessor closes`). When T07 is spec'd, this issue should be added to its `## Carry-over from prior audits` section. Until then, the `## Propagation status` footer below tracks this as `DEFERRED (owner: M12 T07, spec pending)`.

### LOW-3 — `pricing.yaml` real-CLI spot-check not executed (TA-LOW-05 optional carry-over)

**Symptom.** TA-LOW-05 recommended a real `claude --print --output-format json --model sonnet --tools '' 'ping'` invocation to confirm the `modelUsage` keys returned actually match the existing `pricing.yaml` entries (`claude-sonnet-4-6` / `claude-opus-4-7`). The ticked checkbox in the spec implies this was done; no evidence (commit log, comment, fixture) confirms it.

**Impact.** Low risk. AC-3's hedge (`if the CLI's modelUsage returns a model ID not yet in the file, add it at zero rate`) only fires if the real-CLI key differs from the existing entries. `_find_primary_key` (claude_code.py:251-267) already does substring-match fallback (`"sonnet"` matches `"claude-sonnet-4-6"`), so even if the CLI emits a date-suffixed variant, the cost computation degrades gracefully to zero rather than misattributing. The empirical worst case is a tier whose tokens never reach the ledger — which is acceptable under Max flat-rate billing. AC-3 is met by the existing pricing rows.

**Action / Recommendation.** Either run the spot-check ad-hoc when convenient (under `AIW_E2E=1` since it touches Claude OAuth), or accept the empirical worst case and let T02's `AuditCascadeNode` integration test surface any pricing-row gap when an auditor tier actually fires for the first time. Owner: T02 Builder (will exercise the path naturally) or operator (one-off ping). If T02 cycle 1 surfaces an unrecognised `modelUsage` key, the LOW upgrades to MEDIUM at that point.

## Additions beyond spec — audited and justified

- **`tests/workflows/test_auditor_tier_configs.py::test_planner_existing_tiers_unchanged_after_auditor_addition`** (lines 154-167). Regression guard that the M5 T01/T02 `planner-explorer` + `planner-synth` entries weren't accidentally clobbered by the new auditor entries. Not in spec; defensible — spec asks for "register-shape assertions" and a guard against silent regressions on adjacent rows is a natural extension. No coupling added; reads only what the canonical tests already touch. Acceptable.
- **`tests/graph/test_auditor_tier_override.py` — three extra tests beyond the one spec'd** (lines 43-61). Spec named only `test_auditor_tiers_override_via_mid_run_channel`; Builder added an opus-as-key variant + two identity fall-through tests. Defensible — the fall-through identity case pins the M8 T04 precedence layer 3 (registry default), which would silently break if someone later changed `_resolve_tier`'s missing-override return value. Low cost, no coupling. Acceptable.
- **`summarize_tier_registry` adds *both* `auditor-sonnet` and `auditor-opus`.** Per ADR-0004 §Decision item 3, summarize (Gemini Flash) only needs `auditor-sonnet` (small tier → audited by sonnet; sonnet → audited by opus). Adding `auditor-opus` to summarize is over-inclusive relative to the cascade tier-pairing rule but is *exactly* what the spec §Deliverables instructs ("Add the entries directly; this registry does not compose another"). Spec wins. Acceptable; no architecture drift since `auditor-opus` is just a registry entry (no auto-pairing). Defensible — keeps the tier-naming surface uniform across all in-tree registries so T02's `AuditCascadeNode` can resolve by name without per-workflow special-casing.

## Gate summary

| Gate | Command | Result |
| ---- | ------- | ------ |
| Layer contracts | `uv run lint-imports` | ✅ 4 contracts kept (analyzed 44 files, 109 dependencies) |
| Lint | `uv run ruff check` | ✅ All checks passed! |
| Tests (full, cycle 1) | `uv run pytest` | ✅ 759 passed, 9 skipped, 22 warnings (40.29s) |
| Tests (full, cycle 2 re-run #1) | `uv run pytest` | ✅ 759 passed, 9 skipped, 22 warnings (44.57s) |
| Tests (full, cycle 2 re-run #2 — flake check) | `uv run pytest` | ✅ 759 passed, 9 skipped, 22 warnings (43.92s) — Builder's "transient ordering flake" claim NOT reproduced; identical result twice in a row, no flake exists |
| KDR-003 tree-wide grep | `uv run pytest tests/workflows/test_slice_refactor_e2e.py::test_kdr_003_no_anthropic_in_production_tree` | ✅ PASS |
| KDR-003 file-scoped grep | `uv run pytest tests/workflows/test_planner_synth_claude_code.py::test_no_anthropic_sdk_import_in_planner_or_claude_code_driver` | ✅ PASS |
| New workflow-layer shape tests (7) | `uv run pytest tests/workflows/test_auditor_tier_configs.py` | ✅ 7 PASS |
| New graph-layer override tests (4) | `uv run pytest tests/graph/test_auditor_tier_override.py` | ✅ 4 PASS |
| Smoke (registry resolution + override path) | Hermetic — exercised by the 11 new tests above | ✅ PASS |

**Smoke discipline (CLAUDE.md non-inferential rule).** T01 is a tier-registration task; no new TieredNode invocation, no new graph wiring, no surface change. The "smoke" the spec implicitly relies on is registry resolution + the `_mid_run_tier_overrides` precedence path — both fully exercised hermetically. A real-CLI smoke (a `claude --print --model sonnet 'ping'` round-trip) is *optional* per AC-3's hedge wording and per TA-LOW-05's "if you want belt-and-braces" framing. T02's `AuditCascadeNode` is the first surface that actually fires the auditor tier; the wire-level smoke naturally lands there. Accepting hermetic smoke as sufficient at T01.

## Issue log — cross-task follow-up

| ID | Severity | Owner / next touch point | Status |
| -- | -------- | ------------------------ | ------ |
| M12-T01-ISS-01 (LOW-1) | LOW | T01 cycle 2 Builder | RESOLVED (cycle 2, 2026-04-27 — both spec edits applied; verified via `git diff`) |
| M12-T01-ISS-02 (LOW-2) | LOW | M12 T07 (spec pending) | DEFERRED (cycle 2: ADR-0004 zero diff confirmed) |
| M12-T01-ISS-03 (LOW-3) | LOW | T02 Builder (natural exercise) OR operator ad-hoc ping | DEFERRED-INFORMATIONAL (cycle 2: pricing.yaml zero diff confirmed; AC-3 met by existing rows) |

**Cycle-2 audit verdict.** All 11 ACs met (re-verified). 4 of 5 carry-over items applied/honoured (TA-LOW-01, -02, -03, -04); TA-LOW-05 deferred-informational (recommendation accepted). LOW-1 resolved. LOW-2 + LOW-3 properly deferred with owners. No new findings introduced. Builder respected scope boundary (docs-only delta in cycle 2; zero source/test/CHANGELOG/ADR/pricing.yaml diff). No forbidden git/publish operation. Status: ✅ PASS — FUNCTIONALLY CLEAN, ready for security gate.

## Deferred to nice_to_have

*None.* No findings naturally map to `nice_to_have.md` items at T01.

## Propagation status

- **M12-T01-ISS-02 (TA-LOW-03 / ADR-0004 stale framing).** DEFERRED to M12 T07. T07 spec does not yet exist (M12 README §Task order: "Per-task spec files land as each predecessor closes"). When T07 is authored, this carry-over must be added to its `## Carry-over from prior audits` section with text:

  > **M12-T01-ISS-02 — Amend ADR-0004 §Decision item 1 + §Consequences for stale `primitives/tiers.py` landing site** (severity: LOW, source: M12 T01 audit issue file, original carry-over TA-LOW-03)
  > ADR-0004 line 25 reads `"Both sit in the TierRegistry (ai_workflows/primitives/tiers.py) next to planner-synth"` and line 55 reads `"New TierConfigs. auditor-sonnet + auditor-opus land in ai_workflows/primitives/tiers.py"`. Both citations are stale; T01 landed entries in workflow modules per the M19-era workflow-scoped registry pattern. Add a one-line note at each location: `"(Landing amended M12 T01 — see workflow tier registries: planner.py, summarize_tiers.py.)"`
  > **Recommendation:** Single docs commit; no source-code change.

  Confirmation footer: until T07 is authored, this propagation is `PENDING` (no target spec exists to write into). The loop controller / next /clean-tasks pass should pick this up when M12 T06 closes.

- **M12-T01-ISS-01 (LOW-1, ticked-without-applying spec edits).** Self-contained to T01; either fixed in cycle 2 or rolled into the same M12 T07 docs sweep as ISS-02. No upstream propagation needed.

- **M12-T01-ISS-03 (LOW-3, optional pricing spot-check).** Self-resolves at T02 cycle 1 when `AuditCascadeNode` first invokes the auditor tier. No spec edit required.

**Status:** ✅ PASS — FUNCTIONALLY CLEAN, ready for security gate. LOW-1 resolved cycle 2; LOW-2 deferred to M12 T07; LOW-3 deferred-informational (self-resolves at T02). All 11 ACs met. Zero source/test/CHANGELOG/ADR/pricing.yaml diff in cycle 2 (Builder respected scope boundary). No forbidden git/publish operation.

## Security review (2026-04-27)

Scope: files touched across cycles 1 + 2 of M12 T01. Threat model: single-user local machine; two real surfaces (published wheel, subprocess execution). Checked against all eight threat-model items.

### Threat item 1 — Wheel contents

Inspected `dist/jmdl_ai_workflows-0.3.1-py3-none-any.whl` (Python `zipfile`). Contents:
- `ai_workflows/**` package files only, plus `migrations/*.sql` (runtime data, intended), `METADATA`, `WHEEL`, `entry_points.txt`, `licenses/LICENSE`, `RECORD`.
- No `.env*`, no `design_docs/`, no `runs/`, no `*.sqlite3`, no `htmlcov/`, no `.coverage`, no `.pytest_cache/`, no `.claude/`, no `tests/`, no `evals/`, no `dist/`, no `.github/`.
- The new files added by T01 (`ai_workflows/workflows/summarize_tiers.py` extended, `ai_workflows/workflows/planner.py` extended) are both `ai_workflows/` package files — correct landing site.
- Test files (`tests/workflows/test_auditor_tier_configs.py`, `tests/graph/test_auditor_tier_override.py`) are absent from the wheel — correct.

Result: clean.

### Threat item 2 — KDR-003 / OAuth subprocess integrity

`ClaudeCodeSubprocess.complete()` in `ai_workflows/primitives/llm/claude_code.py`:

- **argv construction** (`claude_code.py:119-129`): argv is built as a Python `list[str]` with each element a separate positional argument. `self._route.cli_model_flag` is a `str` field on a `ClaudeCodeRoute` Pydantic model. The new registrations supply static literals `"sonnet"` and `"opus"` at construction time in `planner_tier_registry()` and `summarize_tier_registry()`. No user-influenced path reaches `cli_model_flag` at these call sites.
- **No `shell=True`**: `asyncio.create_subprocess_exec(*argv, ...)` is used, not `create_subprocess_shell`. Confirmed by direct grep — zero hits.
- **Timeout enforcement** (`claude_code.py:143-154`): `asyncio.wait_for(..., timeout=self._per_call_timeout_s)` with signal-based kill (`proc.kill()` + `await proc.wait()`) on `TimeoutError`. `per_call_timeout_s=300` is set on both new tiers.
- **Stderr capture** (`claude_code.py:135-139`): `stderr=asyncio.subprocess.PIPE` — captured. On `CalledProcessError`, `classify()` in `retry.py:176-184` extracts and logs stderr up to 2000 chars via `_LOG.warning(...)`. The 0.1.3 fix is in place.
- **`ANTHROPIC_API_KEY`**: `grep -rn "ANTHROPIC_API_KEY" ai_workflows/` returns zero hits. KDR-003 boundary intact.
- **Prompt via stdin, not argv**: The user prompt travels through `stdin_payload` (`claude_code.py:133`), not argv. `--system-prompt` carries the system string via argv (`claude_code.py:131-132`) but that is a fixed structured field, not user-supplied free text subject to shell interpretation (and `shell=False` is the execution model).

Result: clean.

### Threat item 3 — External workflow load path (KDR-013)

No changes to `ai_workflows/workflows/loader.py` in this task. Out of scope for this diff; pre-existing status unchanged.

### Threat item 4 — MCP HTTP transport bind address

`ai_workflows/mcp/__main__.py` line 74: `typer.Option("127.0.0.1", "--host", ...)`. Default is loopback. Documentation of `0.0.0.0` foot-gun present in the same file (line 78). No diff to MCP files in this task.

Result: clean.

### Threat item 5 — SQLite paths

No changes to storage layer or checkpointer in this task.

### Threat item 6 — Subprocess CWD / env leakage

`asyncio.create_subprocess_exec` in `claude_code.py` does not pass an explicit `env=` argument, so the child process inherits the parent environment. This is the intended design for the Claude Code OAuth path (the CLI reads its own auth from the keychain / CLI config, not from env vars controlled by this process). No new env-var reads or subprocess spawns were introduced in this task. The existing pattern is unchanged from prior audits.

Result: no new exposure.

### Threat item 7 — Logging hygiene

The log site in `retry.py:classify()` emits `cmd` (the argv list, e.g. `["claude", "--print", "--output-format", "json", "--model", "sonnet", "--tools", "", "--no-session-persistence"]`) and `stderr_excerpt`. The argv list does not contain prompt content — prompt is sent on stdin only and is not present in `exc.cmd`. No `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `Bearer`, `Authorization`, `prompt=`, or `messages=` found in any modified file.

Result: clean.

### Threat item 8 — Dependency CVEs

No `pyproject.toml` or `uv.lock` changes in this task. Dependency-auditor pass not triggered per task scope; no CVE scan needed here.

### 🔴 Critical — must fix before publish/ship

None.

### 🟠 High — should fix before publish/ship

None.

### 🟡 Advisory — track; not blocking

None. The `--system-prompt` argv path carries a fixed structured string (not user free text), and the `shell=False` execution model means no shell interpretation occurs regardless. Nothing warrants even an advisory finding against the threat model for this project.

### Verdict: SHIP

## Sr. Dev review (2026-04-27)

**Files reviewed:**
- `ai_workflows/workflows/planner.py` (lines 647-707 — new tier entries + docstring)
- `ai_workflows/workflows/summarize_tiers.py` (full file — new entries + imports + module docstring)
- `ai_workflows/workflows/slice_refactor.py` (lines 1568-1608 — docstring-only)
- `tests/workflows/test_auditor_tier_configs.py` (full file — 7 tests)
- `tests/graph/test_auditor_tier_override.py` (full file — 4 tests)
- `tests/workflows/test_slice_refactor_fanout.py` (lines 393-415 — set-equality extension)
- `CHANGELOG.md` (lines 10-53)

**Skipped (out of scope):** `ai_workflows/graph/tiered_node.py` (pre-existing; read for context only — zero diff in this task). `ai_workflows/primitives/tiers.py` (spec explicitly confirms zero diff).

**Verdict:** SHIP

### BLOCK — must-fix before commit

None.

### FIX — fix-then-ship

None.

### Advisory — track but not blocking

**ADV-1 — `planner_tier_registry()` docstring first line frames "auditor pair" as part of "tiers this workflow calls" (`planner.py:648`)**

The docstring opens "Return the tiers this workflow calls plus the auditor pair." The planner workflow does not call the auditor tiers; they exist in the planner registry only so `slice_refactor` can inherit them via composition. The framing is misleading to a reader who doesn't know the cascade intent. A more accurate first line would be "Return the tier registry for the planner workflow, including the M12 auditor tiers inherited by slice_refactor via composition." This matches the idiom in `summarize_tiers.py:30` ("Return the tier registry for the summarize workflow").

Lens: Comment / docstring drift. Advisory — does not affect runtime, tests, or the AC set.

Action: Consider aligning the first-line summary with the `summarize_tier_registry()` pattern at next touch.

**ADV-2 — CHANGELOG AC-label list has a collapsed/shifted numbering (`CHANGELOG.md:49-50`)**

The CHANGELOG's ACs-satisfied list collapses AC-9 and AC-10 as "AC-9/10: Gates clean" then labels AC-11 as "CHANGELOG entry present." The spec defines AC-9 = gates, AC-10 = CHANGELOG entry, AC-11 = status surfaces. The CHANGELOG's self-description skips AC-11 (status surfaces) and misassigns the AC-10 label to what is actually the AC-11 self-referential entry. This does not affect any code path, test, or gate — the Auditor independently verified all three ACs were met. Purely a cosmetic labelling error in the CHANGELOG's own summary.

Lens: Comment / docstring drift. Advisory — no consumer parses these labels programmatically.

Action: If the CHANGELOG entry is touched again (e.g., during M12 T07 close-out docs sweep), correct to "AC-9: Gates clean" / "AC-10: CHANGELOG entry present (this entry)" / "AC-11: Status surfaces flipped."

**ADV-3 — `test_slice_refactor_tier_registry_composes_planner_tiers` uses a sealed-set assertion (`test_slice_refactor_fanout.py:406-412`)**

The set-equality check (`assert set(reg.keys()) == {...5 keys...}`) means any T03/T04/T05 Builder adding a new tier to `planner_tier_registry()` will fail this test at first run. This is intentional and defensible — the test was already a sealed-set check before M12 T01 (it just had 3 keys). The audit noted this; flagging here for the T03 Builder so they know to update this test when adding the `AuditCascadeNode` wiring (which may or may not touch `planner_tier_registry()`).

Lens: Simplification / test shape. Advisory — no action needed in T01; this is a carry-forward note for T03.

Action: T03 Builder should update the expected key set in `test_slice_refactor_tier_registry_composes_planner_tiers` if new tiers are added. No change needed at T01.

### What passed review (one-line per lens)

- Hidden bugs: None observed. `_resolve_tier` single-hop behavior is pre-existing and consistent with how the tests exercise it; the new tiers are correctly registered and the KeyError-to-NonRetryable path in `TieredNode` handles unknown tier names.
- Defensive-code creep: None. No unnecessary guards, no backwards-compat shims, no feature-flag toggles. The `or {}` fallback in `_resolve_tier:402` is pre-existing and justified by the optional nature of the state key.
- Idiom alignment: Clean. Both new registry functions follow the `<workflow>_tier_registry() -> dict[str, TierConfig]` pattern with `structlog`-free helpers (no logging needed in pure-data factories). Import surface is `workflows -> primitives` only — layer discipline maintained.
- Premature abstraction: None. No new helpers, mixins, or base classes introduced. The two new `TierConfig` entries are inline literals, matching the existing pattern.
- Comment / docstring drift: Two advisory items (ADV-1, ADV-2) — cosmetic only. No comments restating the code; the "why" paragraphs in both registry docstrings add genuine rationale (OAuth session constraint, timeout derivation).
- Simplification: None warranted. The set-equality test (ADV-3) is the right shape for a sealed-registry guard.

## Sr. SDET review (2026-04-27)

**Test files reviewed:**
- `tests/workflows/test_auditor_tier_configs.py` (new, 7 tests)
- `tests/graph/test_auditor_tier_override.py` (new, 4 tests)
- `tests/workflows/test_slice_refactor_fanout.py` (lines 393-415 — sealed key-set extension)

**Skipped (out of scope):** `tests/workflows/test_planner_synth_claude_code.py` (pre-existing, untouched by this task beyond the registry call it already makes); `tests/workflows/test_slice_refactor_e2e.py` (KDR-003 tree-wide grep, pre-existing, unmodified).

**Verdict:** SHIP

### BLOCK — tests pass for the wrong reason

None.

### FIX — fix-then-ship

None.

### Advisory — track but not blocking

**ADV-SDET-1 — Identity fall-through tests are tier-name-agnostic (`tests/graph/test_auditor_tier_override.py:50-61`)**

`test_auditor_sonnet_falls_through_to_identity_when_no_override` and `test_auditor_opus_falls_through_to_identity_when_no_override` both pass `state={}` and assert that `_resolve_tier` returns the same string it was given. This behavior is guaranteed by `_resolve_tier:408` (`return logical`) for any string whatsoever — `_resolve_tier("foobar", {}, {})` would also return `"foobar"`. The tests prove the identity-return path is reachable, but they do not probe anything specific to the auditor tier names. The Auditor already accepted these as defensible additions; this observation is informational only.

Action: No change needed at T01. If the M8 T04 `_resolve_tier` contract is ever tightened (e.g., to validate the returned tier name against a registry), these tests would become genuinely name-specific and should be updated at that point.

**ADV-SDET-2 — `TierConfig.name` field not asserted in any new test**

The `TierConfig` model carries a `name: str` field separate from the registry dict key. All new tests look up the entry by key (e.g., `registry["auditor-sonnet"]`) and assert route + concurrency + timeout, but none asserts `tier.name == "auditor-sonnet"` or `tier.name == "auditor-opus"`. A mismatch (e.g., a copy-paste where the dict key is `"auditor-sonnet"` but the `TierConfig(name="auditor-opus", ...)` object carries the wrong name string) would not be caught by any of the 7 new workflow-layer tests. In practice the `name` field is consumed by structured-logging paths and the `get_tier` helper; a mismatch would produce confusing log output at T02/T03 runtime. The AC set does not explicitly require `name` assertion, so this is advisory, not a failing gap.

Action: Consider adding `assert tier.name == "auditor-sonnet"` / `assert tier.name == "auditor-opus"` to the 4 planner/summarize shape tests (lines 35-146 of `test_auditor_tier_configs.py`) at next touch, to fully pin the constructed object.

**ADV-SDET-3 — `test_planner_existing_tiers_unchanged_after_auditor_addition` does not check `planner-synth` `max_concurrency` (`tests/workflows/test_auditor_tier_configs.py:154-167`)**

The regression guard checks `synth.route.cli_model_flag == "opus"` and `synth.per_call_timeout_s == 300` but omits `assert synth.max_concurrency == 1`. This is the same field the new auditor-tier tests assert, and it was the one value most likely to drift if someone copy-pasted a multi-concurrency tier. The existing `test_planner_synth_tier_points_at_claude_code_opus` in `test_planner_synth_claude_code.py:232-239` does assert it, so the gap is covered by the sibling file — but the T01 regression guard is incomplete on its own. Advisory only.

Action: Add `assert synth.max_concurrency == 1` to `test_planner_existing_tiers_unchanged_after_auditor_addition` at next touch.

### What passed review (one-line per lens)

- Tests-pass-for-wrong-reason: None observed. Registry lookups exercise real Pydantic construction; override tests call live `_resolve_tier` code against injected state dicts; `isinstance` narrowing is applied before accessing the discriminated union field.
- Coverage gaps: Three advisory items (ADV-SDET-1 through ADV-SDET-3); no missing-AC-coverage within scope. All 5 AC-linked test assertions (AC-1, AC-2, AC-4 shape; AC-5 override; AC-5 slice-refactor composition) are substantive.
- Mock overuse: None. Zero mocks in any of the three test files; all assertions drive real registry functions and real `_resolve_tier` logic. Correct boundary — no LLM adapter mocking needed for pure-data tier-registration tests.
- Fixture / independence: Clean. No fixtures in the two new files; `test_slice_refactor_fanout.py` extension is a standalone function with no shared state. Tests are fully order-independent.
- Hermetic-vs-E2E gating: Clean. No subprocess calls, no network I/O, no `claude` CLI invocation in any new test. The `AIW_E2E=1` gate is correctly absent.
- Naming / assertion-message hygiene: Good. Test names state the registry + tier + expected property (e.g., `test_auditor_sonnet_tier_resolves_to_cli_sonnet_in_planner`). `isinstance` assertions carry `f"Expected ClaudeCodeRoute, got {type(route).__name__}"` messages. Integer equality assertions rely on pytest's default diff output, which is sufficient for scalar comparisons.
