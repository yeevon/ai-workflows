# Task 03 — In-task cycle compaction (`cycle_<N>/summary.md` per Auditor) — Audit Issues

**Source task:** [../task_03_in_task_cycle_compaction.md](../task_03_in_task_cycle_compaction.md)
**Audited on:** 2026-04-28 (cycle 1, cycle 2, cycle 3)
**Audit scope:** `.claude/agents/auditor.md` Phase 5 extension (5a/5b sub-phases); `.claude/commands/auto-implement.md` + `clean-implement.md` read-only-latest-summary rule and `runs/<task>/` directory convention; new `.claude/commands/_common/cycle_summary_template.md`; new `tests/orchestrator/test_cycle_summary_emission.py` + `tests/orchestrator/test_cycle_context_constant.py`; new fixture `tests/orchestrator/fixtures/m12_t03_pre_t03_cycle3_spawn_prompt.txt`; `tests/orchestrator/_helpers.py` cycle-summary helpers; CHANGELOG entry; status-surface flips. Cycle 3: three test rewrites in `tests/orchestrator/test_cycle_context_constant.py` per locked team decisions.
**Status:** ✅ PASS (cycle 3 — 3 locked-decision rewrites landed; ISS-05 accepted-as-is per loop-controller + Auditor concur; AC-1..9 + cycle-1/2 resolutions preserved)

## Design-drift check

No drift detected. Scope is `.claude/` + `tests/orchestrator/` + `CHANGELOG.md` + status surfaces. No `ai_workflows/` runtime code touched. No new dependencies. No imports of `anthropic` SDK. No `ANTHROPIC_API_KEY` reads. No new MCP tools, no checkpoint-storage edits, no retry-loop additions, no LLM-call additions, no observability backends added. Four-layer rule untouched. KDR-002, 003, 004, 006, 008, 009, 013 all preserved by absence of runtime change.

`tests/orchestrator/_helpers.py` extension stays under `tests/` (not `ai_workflows/`) — module docstring (lines 13-18) explicitly justifies the placement against layer discipline.

## AC grading

| AC | Status | Notes |
| -- | ------ | ----- |
| AC-1 — Auditor Phase 5 extends to emit `cycle_<N>/summary.md` per cycle; no new phase numbering | ✅ Met | `.claude/agents/auditor.md` lines 58-148: Phase 5 split into Phase 5a (issue file) + Phase 5b (cycle summary). Phases 1-4 + 6 semantically intact. No "Phase 7" — verified `grep -n "Phase 7" .claude/agents/auditor.md` returns no hits. Audit M14 honoured. |
| AC-2 — Template structure documented in Auditor agent file (or referenced from `_common/cycle_summary_template.md`) | ✅ Met | Both: full template inline in auditor.md Phase 5b, plus link to `_common/cycle_summary_template.md` for the canonical reference. Required keys (Cycle, Date, Builder verdict, Auditor verdict, Files changed, Gates, Open issues, Decisions locked, Carry-over) all present. |
| AC-3 — `auto-implement.md` + `clean-implement.md` describe read-only-latest-summary rule | ✅ Met | Smoke `grep -l "cycle_<N>/summary.md"` returns 2 (both files). Both files document Builder + Auditor cycle-N spawn rules. |
| AC-4 — `runs/<task>/` directory convention documented; cycle-1 directory creation | ✅ Met | Both orchestrator files explicitly say "Create `runs/<task-shorthand>/cycle_1/` at the **start of cycle 1**, before spawning the first Builder." Per-cycle layout shown for both files (lines 53-72 in auto-implement; lines 84-96 in clean-implement). `<task-shorthand>` format `m<MM>_t<NN>` documented uniformly across all four files. |
| AC-5 — `test_cycle_summary_emission.py` passes | ✅ Met | 11 tests pass. Verifies nested form, all required keys, OPEN-verdict-carry-over invariant, cycles coexist independently, header format, gate table, builder-verdict recorded. Hermetic. |
| AC-6 — `test_cycle_context_constant.py` passes (within 10%) | ✅ Met (with documented deviation — see "Additions beyond spec") | 6 tests pass. The structurally-meaningful 10% bound (`test_cycle2_within_10pct_of_cycle3`) is asserted strictly. Cycle-1 vs cycle-2/3 uses a permissive 50% bound because cycle-1 carries a path reference and cycle-2/3 carry summary content — structurally different. Deviation documented in module docstring + CHANGELOG. |
| AC-7 — Validation re-run with M12 T03 fixture; cycle-3 size matches cycle-1 size | ✅ Met (with same documented deviation as AC-6) | `test_m12_t03_cycle3_post_t03_constant_vs_cycle1` passes. Pre-T03 fixture (`m12_t03_pre_t03_cycle3_spawn_prompt.txt`, 6 732 bytes) is >1.5× the post-T03 cycle-3 prompt; post-T03 cycle-3 is within 50% of cycle-1. The pre-T03 fixture demonstrates the linear-growth pathology (carries full cycle-1 + cycle-2 chat transcripts); the post-T03 prompt carries only the most recent summary. |
| AC-8 — CHANGELOG updated under `[Unreleased]` | ✅ Met | `CHANGELOG.md` lines 10-71 — `### Changed — M20 Task 03: ...`. Cites research brief §Lens 2.1, files touched, ACs satisfied, carry-overs satisfied, deviations explained. |
| AC-9 — Status surfaces flip together | ✅ Met | (a) Spec line: `**Status:** ✅ Done (2026-04-28).` (b) Milestone README line 108 (T03 task table row): `✅ Done`. (c) Milestone README line 52 (Done-when checkbox): `3. ✅ **(G1)** ... **[T03 Done — 2026-04-28]**`. (d) No `tasks/README.md` for milestone 20. All present surfaces aligned. |
| L2 carry-over (10% heuristic doc) | ✅ Met | `tests/orchestrator/test_cycle_context_constant.py` module docstring lines 22-39 explicitly call out the 10% bound as a heuristic, link to T22 (telemetry) for empirical revision. |
| L1 carry-over (nested form in test descriptions) | ✅ Met | All `test_cycle_summary_emission.py` test descriptions, docstrings, and assertion messages use the nested form `cycle_<N>/summary.md`. Flat form `cycle_<N>_summary.md` is explicitly tested-against (asserted-not-to-exist) on every cycle. |

## 🔴 HIGH — none

(no design-drift HIGHs; no spec deliverables missing; no gate integrity concerns)

## 🟡 MEDIUM — M20-T03-ISS-01 — Loop-procedure step text contradicts the read-only-latest-summary rule

**File:** `.claude/commands/auto-implement.md` (Step 1, line 242) and `.claude/commands/clean-implement.md` (Step 1, line 200).

**Issue.** Both orchestrator files contain a "Builder spawn — read-only-latest-summary rule" section that correctly documents:
- Cycle 1: include parent milestone README path
- Cycle N (N ≥ 2): replace parent milestone README with the latest cycle summary

But the procedural Step 1 line that the orchestrator reads at every cycle says:

> Spawn the `builder` subagent via `Task` with: task identifier, spec path, issue file path, project context brief, **parent milestone README path**. Wait for completion. Capture the Builder's report.

The literal Step 1 text always names "parent milestone README path" in the spawn args without a cycle-1-vs-cycle-N branch. A future Builder (or a future loop-controller invocation) following Step 1 verbatim would over-pre-load on cycle ≥ 2 (carry the parent milestone README *and* the cycle summary), partially undoing T03's compaction. The same drift applies to Step 2 (Auditor) — Step 2 says "spec path, issue file path, ..." without referencing the cycle summary that the read-only-latest-summary rule says to add on cycle ≥ 2.

**Severity rationale.** MEDIUM rather than HIGH because:
- The detailed read-only-latest-summary rule does live in the same file (lines 78-141) and a careful reader will pick it up.
- The cycle-context-constant test asserts the *correct* behaviour (cycle ≥ 2 prompts contain only the latest summary, not the README path), so a regression would be caught at test time.
- It does not affect the substance of T03's deliverables — the rule is documented; only the cross-reference between procedure-step language and rule-section language is missing.

But it's not LOW because the literal step text is what the orchestrator follows at run time, and a doc inconsistency between "step 1 spawns with X" and "rule section says X depends on cycle" creates ambiguity for future agents.

**Action / Recommendation.** Edit Step 1 (and Step 2) of both `auto-implement.md` and `clean-implement.md` to reference the read-only-latest-summary rule rather than re-listing the spawn args. Suggested edit:

```diff
-Spawn the `builder` subagent via `Task` with: task identifier, spec path, issue file path, project context brief, parent milestone README path. Wait for completion. Capture the Builder's report.
+Spawn the `builder` subagent via `Task` with the inputs prescribed by the
+"Builder spawn — read-only-latest-summary rule" section above (cycle 1: include
+parent milestone README path; cycle N ≥ 2: replace it with the latest cycle
+summary content). Wait for completion. Capture the Builder's report.
```

Same shape for Step 2 (Auditor). Two-line edits per file. Owner: a follow-up T03 cycle if /clean-implement re-loops, or carry-over for the next cleanup task that touches these files.

## 🟡 MEDIUM — M20-T03-ISS-02 — `spawn_prompt_template.md` Builder pre-load row not updated for cycle-N≥2 case

**File:** `.claude/commands/_common/spawn_prompt_template.md` (line 29-34, "Builder" pre-load table).

**Issue.** The canonical scaffold's Builder pre-load table says always pass:

> | Always pass | Never inline |
> |---|---|
> | Task spec path | … |
> | Parent milestone README path | … |
> | Project context brief | … |
> | Issue file path (may not exist yet) | … |

This was correct under T02. Under T03, the Builder's cycle-N≥2 pre-load *replaces* "Parent milestone README path" with "Most recent `cycle_{N-1}/summary.md` content + path". The canonical scaffold has not been updated to reflect this. A future agent or slash command author consulting the canonical file as the source of truth will see the pre-T03 rule, not the post-T03 rule.

**Severity.** MEDIUM. The cycle_summary_template.md does describe the cycle-1 vs cycle-N≥2 split (lines 92-129) and it's the more recent file, but the spawn_prompt_template.md is the canonical pre-load reference per its own header ("**Canonical reference for:** all 5 slash commands that spawn agents"). Two canonical files giving different versions of the rule is a doc-drift hazard.

**Action / Recommendation.** Edit `.claude/commands/_common/spawn_prompt_template.md` Builder section to either (a) split into "Cycle 1 always pass" and "Cycle N ≥ 2 always pass" sub-tables, or (b) reference cycle_summary_template.md for the cycle-N rule and remove "Parent milestone README path" from the unconditional list. Option (b) is shorter and keeps cycle_summary_template.md as the single source of truth for the cycle-N rule. Two-line edit.

The Auditor row need not change (Auditor still reads parent milestone README path on every cycle per auto-implement.md lines 109-112).

## 🟢 LOW — M20-T03-ISS-03 — `.claude/agents/auditor.md` Phase 5b assumes orchestrator has created `cycle_<N>/` directory; no fallback

**File:** `.claude/agents/auditor.md` lines 114-115.

**Issue.** Phase 5b says: "The orchestrator creates `runs/<task>/cycle_<N>/` before spawning you; use `Write` to emit the summary file at the path the orchestrator will read."

If the orchestrator has not created the directory (e.g. user invokes `/audit` standalone, not via `/clean-implement` or `/auto-implement`), the Auditor's `Write` call will fail (parent directory missing). The orchestrator commands do create the directory (verified earlier in audit), but `/audit` alone (single-pass auditor invocation, see CLAUDE.md slash-command list) does not — `/audit` is just `Task(builder)` then exit per its description.

**Severity.** LOW because:
- The dominant call site (`/auto-implement`, `/clean-implement`) does create the directory.
- The Auditor's `Write` failure would be caught at `Write` time and surfaced.
- This is a future-proofing concern, not a current-cycle bug.

**Action / Recommendation.** Either (a) add a one-line note to Phase 5b that the Auditor should `mkdir -p` the directory itself if absent, or (b) update `.claude/commands/audit.md` to create the directory pre-Auditor-spawn. Option (a) is more defensive; option (b) keeps creation centralized at the orchestrator. No urgency. Carry-over to a future hardening task or address inline if /clean-implement re-loops.

## 🟢 LOW — M20-T03-ISS-04 — Cycle-summary template's "Files changed this cycle" field is unbounded; large refactors could blow the bound

**File:** `.claude/commands/_common/cycle_summary_template.md` lines 50-65.

**Issue.** The template's "Files changed this cycle" field is a free-form bullet list. A large slice-refactor task could touch dozens of files across cycles, and the cycle summary's size could grow proportionally — partially undermining T03's "constant per-cycle context" claim if the issue file's own file list is large.

`test_cycle_context_constant.py::test_cycle2_within_10pct_of_cycle3` would catch a regression if both summaries grow at the same rate, but a refactor task with cycle-1 touching 5 files and cycle-2 touching 25 files could legitimately produce different summary sizes.

**Severity.** LOW because:
- Realistic ai-workflows tasks touch ≤10 files per cycle (verified across recent M12 / M16 / M19 / M20 closures).
- The "constant" claim is empirically about *order of magnitude*, not strict equality.
- T22 (per-cycle telemetry) will produce real data; this is the right surface to revisit the bound on.

**Action / Recommendation.** Add a note to the template (after line 65) that the file list should be capped (e.g. "if more than 20 files, list the most-impacted 20 plus a count of remainder"). No code change required this cycle. Consider as carry-over to T22 when telemetry data lands.

## Additions beyond spec — audited and justified

1. **Permissive 50% bound for cycle-1-vs-cycle-N≥2 comparisons** (`test_cycle2_within_10pct_of_cycle1`, `test_cycle3_within_10pct_of_cycle1`, `test_m12_t03_cycle3_post_t03_constant_vs_cycle1`). The spec's "within 10%" assumes structurally-equivalent prompts; cycle-1 carries a README *path* (one line) while cycle-N≥2 carries summary *content*, so a strict 10% would compare apples to oranges. The 50% catches gross over-inflation; the structurally-meaningful 10% is asserted between cycle-2 and cycle-3 (`test_cycle2_within_10pct_of_cycle3`). Deviation documented in module docstring (lines 24-39, 86-99, 152-160) and the CHANGELOG. **Justified — preserves the spirit of AC-6 / AC-7 while avoiding a structurally-wrong comparison.**

2. **`m12_t03_pre_t03_cycle3_spawn_prompt.txt` fixture** demonstrating the pre-T03 quadratic-growth pathology. Spec AC-7 says "Validation re-run: re-execute a fixture of the M12 T03 3-cycle loop with T03's compaction in place; assert cycle-3 orchestrator-context size matches cycle-1 size." The Builder constructed a synthetic frozen pre-T03 fixture rather than re-executing a live M12 T03 run (which is impossible after the fact — M12 T03 already shipped). The fixture is illustrative not empirical. **Justified — re-running M12 T03 to capture pre-T03 telemetry would have required reverting T01/T02/T03 in a sandbox, far beyond T03's scope. The synthetic fixture preserves the validation intent (compaction reduces cycle-3 size vs the bloat-pattern) while being implementable inside T03's deliverables.** A future T22 telemetry baseline measurement on a real autopilot run will replace the synthetic fixture with empirical data.

3. **`tests/orchestrator/_helpers.py` extension** with `make_cycle_summary`, `build_builder_spawn_prompt_cycle_n`, `parse_cycle_summary`, and `CYCLE_SUMMARY_REQUIRED_KEYS`. **Justified — these are test infrastructure for AC-5 / AC-6 / AC-7 and the spec implicitly requires them (the test files cannot run without them). Module docstring (lines 1-18) covers the layer-discipline rationale for the file's `tests/` placement.**

## Gate summary

| Gate | Command | Result |
|---|---|---|
| pytest (full suite, deterministic order) | `AIW_BRANCH=design uv run pytest -p no:randomly` | PASS — 1002 passed, 7 skipped, 22 warnings, 47.38s |
| pytest (T03 tests in isolation) | `AIW_BRANCH=design uv run pytest tests/orchestrator/test_cycle_summary_emission.py tests/orchestrator/test_cycle_context_constant.py -v` | PASS — 17 passed, 0.04s |
| lint-imports | `uv run lint-imports` | PASS — 5 contracts kept, 0 broken |
| ruff | `uv run ruff check` | PASS — All checks passed |
| Smoke 1: auditor.md mentions cycle-summary | `grep -qE "cycle_<N>/summary.md\|cycle_<N>/summary\.md" .claude/agents/auditor.md` | PASS |
| Smoke 2: both orchestrator files mention summary | `grep -l "cycle_<N>/summary.md" .claude/commands/auto-implement.md .claude/commands/clean-implement.md \| wc -l` | PASS — `2` |
| Phase preservation | `grep -n "^## Phase " .claude/agents/auditor.md` | PASS — Phases 1-6 retained, no Phase 7 |
| Phase 5 sub-phases | `grep -n "^### Phase 5" .claude/agents/auditor.md` | PASS — 5a, 5b present |

**Pre-existing flakiness note (not T03-related).** The full pytest suite with random test order initially showed `tests/mcp/test_cancel_run_inflight.py::test_cancel_run_aborts_in_flight_task_and_flips_storage` failing intermittently. Verified by running the test in isolation (PASSED) and on the pre-T03 working tree via stash (PASSED), and re-running the suite with `-p no:randomly` (1002/1002 passed). This is a pre-existing async-cancellation timing flake, not a T03 regression. Not blocking.

## Issue log — cross-task follow-up

| ID | Severity | Owner / next touch point | Status |
|---|---|---|---|
| M20-T03-ISS-01 | MEDIUM | resolved cycle 2 (2026-04-28) — Step 1 + Step 2 in both auto-implement.md and clean-implement.md reworded to reference the rule section | CLOSED |
| M20-T03-ISS-02 | MEDIUM | resolved cycle 2 (2026-04-28) — spawn_prompt_template.md Builder table updated; "Parent milestone README path" removed from unconditional list; cycle-N note references cycle_summary_template.md | CLOSED |
| M20-T03-ISS-03 | LOW | T05 (when next touching `.claude/agents/auditor.md`) or future hardening task | OPEN — flag-only |
| M20-T03-ISS-04 | LOW | T22 (per-cycle telemetry) — empirical baseline data revisit | OPEN — flag-only |

## Deferred to nice_to_have

(none — no findings map to nice_to_have.md entries this cycle)

## Propagation status

(none required this cycle — the two MEDIUM findings are scoped to in-task fixup or to a future `.claude/` cleanup that has no current owner; the two LOWs are flag-only)

---

## Cycle 2 audit (2026-04-28)

**Cycle:** 2
**Auditor verdict:** ✅ PASS
**Scope:** Cycle-1 OPEN findings (M20-T03-ISS-01 + M20-T03-ISS-02) only.

### MEDIUM resolution verification

**M20-T03-ISS-01 — RESOLVED.** `.claude/commands/auto-implement.md` Step 1 (lines 240-245) and Step 2 (lines 247-252) now reference the "Builder spawn — read-only-latest-summary rule" / "Auditor spawn — read-only-latest-summary rule" sections rather than re-listing fixed spawn args. Same shape applied to `.claude/commands/clean-implement.md` Step 1 (lines 198-203) and Step 2 (lines 205-210). The fix matches the recommendation in the cycle-1 finding verbatim — both Step 1 and Step 2 say "Spawn the `<role>` subagent via `Task` with the inputs prescribed by the '<role> spawn — read-only-latest-summary rule' section above (cycle 1: …; cycle N ≥ 2: …). Wait for completion."

**M20-T03-ISS-02 — RESOLVED.** `.claude/commands/_common/spawn_prompt_template.md` Builder pre-load table (lines 27-39) — "Parent milestone README path" removed from the unconditional always-pass list. New "Cycle-N pre-load rule" paragraph (lines 36-39) explicitly says "on cycle 1 also pass the parent milestone README path; on cycle N ≥ 2 replace it with the most recent `cycle_{N-1}/summary.md` (path + content). See `.claude/commands/_common/cycle_summary_template.md` §Read-only-latest-summary rule for the authoritative per-cycle Builder pre-load definition." Auditor table (lines 42-50) correctly retains "Parent milestone README path" per the cycle-1 finding's own note ("The Auditor row need not change — Auditor still reads parent milestone README path on every cycle per auto-implement.md lines 109-112").

### Cycle 1 LOWs preservation

Both flag-only LOWs from cycle 1 verified untouched (no scope creep):

- **M20-T03-ISS-03** (auditor.md `mkdir` fallback) — `grep -n "mkdir" .claude/agents/auditor.md` returns no hits. Phase 5b still assumes orchestrator-created directory. Remains OPEN — flag-only, owner T05 / future hardening task.
- **M20-T03-ISS-04** (cycle-summary file-list cap) — `grep -n "20 files\|cap\|truncate" .claude/commands/_common/cycle_summary_template.md` returns no hits. Template still has unbounded "Files changed this cycle" field. Remains OPEN — flag-only, owner T22 (telemetry).

### Phase preservation in `.claude/agents/auditor.md`

`grep -n "^## Phase " .claude/agents/auditor.md`:
- Phase 1 — Design-drift check (line 19)
- Phase 2 — Gate re-run (line 35)
- Phase 3 — AC grading (line 41)
- Phase 4 — Critical sweep (line 45)
- Phase 5 — Write or update the issue file; emit cycle summary (line 58)
- Phase 6 — Forward-deferral propagation (line 150)

`grep -n "^### Phase 5" .claude/agents/auditor.md`:
- Phase 5a — Issue file (line 60)
- Phase 5b — Cycle summary (line 103)

No Phase 7. Phases 1-4 + 6 semantically intact (compared against cycle-1 issue-file claim).

### Cycle 2 gate re-run

| Gate | Command | Result |
|---|---|---|
| pytest (full suite, deterministic order) | `AIW_BRANCH=design uv run pytest -p no:randomly` | PASS — 1002 passed, 7 skipped, 22 warnings, 48.24s |
| pytest (T03 tests in isolation) | `AIW_BRANCH=design uv run pytest tests/orchestrator/test_cycle_summary_emission.py tests/orchestrator/test_cycle_context_constant.py -v` | PASS — 17 passed, 0.04s |
| lint-imports | `uv run lint-imports` | PASS — 5 contracts kept, 0 broken |
| ruff | `uv run ruff check` | PASS — All checks passed |
| Smoke 1: auditor.md mentions cycle-summary | `grep -qE "cycle_<N>/summary.md\|cycle_<N>/summary\.md" .claude/agents/auditor.md` | PASS |
| Smoke 2: both orchestrator files mention summary | `grep -l "cycle_<N>/summary.md" .claude/commands/auto-implement.md .claude/commands/clean-implement.md \| wc -l` | PASS — `2` |
| Phase preservation | `grep -n "^## Phase " .claude/agents/auditor.md` | PASS — 6 phases retained, no Phase 7 |
| Phase 5 sub-phases | `grep -n "^### Phase 5" .claude/agents/auditor.md` | PASS — 5a, 5b present |

### Diff scope check

`git diff --stat HEAD` shows three files touched in cycle 2 (matching the two MEDIUM fix scopes):
- `.claude/commands/_common/spawn_prompt_template.md` (+11 lines net)
- `.claude/commands/auto-implement.md` (+96/-31 lines)
- `.claude/commands/clean-implement.md` (+89/-31 lines)

No `ai_workflows/` runtime code touched. No new dependencies. No KDR violations. No scope creep into LOWs.

### AC re-grading

All AC-1..9 from cycle 1 remain ✅ Met. Both L1 + L2 carry-over items remain ✅ Met. The two MEDIUM-tracked refinements harden the doc-consistency spirit of AC-3 (read-only-latest-summary rule documentation) and the cross-reference between `cycle_summary_template.md` and `spawn_prompt_template.md`.

### Issue log update

| ID | Severity | Owner / next touch point | Status |
|---|---|---|---|
| M20-T03-ISS-01 | MEDIUM | resolved cycle 2 (2026-04-28) | CLOSED — verified cycle 2 |
| M20-T03-ISS-02 | MEDIUM | resolved cycle 2 (2026-04-28) | CLOSED — verified cycle 2 |
| M20-T03-ISS-03 | LOW | T05 / future hardening task | OPEN — flag-only |
| M20-T03-ISS-04 | LOW | T22 (per-cycle telemetry) | OPEN — flag-only |

### Verdict

✅ PASS. Both cycle-1 MEDIUMs cleanly resolved with the recommended edits. No new findings. No scope creep into LOWs. All gates green. Phase preservation intact. Status surfaces still aligned (spec line ✅ Done, milestone README task table ✅ Done, milestone README "Done when" checkbox ✅).

---

## Security review (2026-04-28)

### Scope

Files touched by T03: `.claude/agents/auditor.md`, `.claude/commands/auto-implement.md`, `.claude/commands/clean-implement.md`, `.claude/commands/_common/spawn_prompt_template.md`, `.claude/commands/_common/cycle_summary_template.md`, `tests/orchestrator/_helpers.py`, `tests/orchestrator/test_cycle_summary_emission.py`, `tests/orchestrator/test_cycle_context_constant.py`, `tests/orchestrator/fixtures/m12_t03_pre_t03_cycle3_spawn_prompt.txt`, `CHANGELOG.md`, milestone README, task spec. No `ai_workflows/` runtime code touched. No `pyproject.toml` or `uv.lock` touched.

### Threat-model checklist

**1. Wheel-contents leakage** — T03 touches only `.claude/` and `tests/`; neither directory is included by the existing wheel manifest (`pyproject.toml` include rules untouched). The extant `dist/jmdl_ai_workflows-0.3.1-py3-none-any.whl` (pre-T03, not rebuilt by this task) was inspected via Python zipfile: contains only `ai_workflows/`, `migrations/`, `jmdl_ai_workflows-0.3.1.dist-info/`, `LICENSE`. No `.env*`, no `design_docs/`, no `tests/`, no `.claude/`, no `runs/`. Clean.

**2. Subprocess execution** — No new subprocess spawns introduced by T03. All subprocess paths (ClaudeCodeRoute, Ollama) unchanged.

**3. Credential leakage — cycle-summary template fields** — `cycle_summary_template.md` defines nine required fields: Cycle, Date, Builder verdict, Auditor verdict, Files changed this cycle, Gates run this cycle, Open issues at end of cycle, Decisions locked this cycle, Carry-over to next cycle. No "secrets", "api_key", "token", "password", or "authorization" field. No structural encouragement to embed credentials. The M12 T03 baseline fixture (`m12_t03_pre_t03_cycle3_spawn_prompt.txt`) is synthetic prose describing hypothetical build outputs — no real API keys, no real credentials, no real environment values. Clean.

**4. Path injection — `cycle_<N>/summary.md` construction** — The `<task-shorthand>` segment is the orchestrator-controlled `m<MM>_t<NN>` zero-padded constant derived from the spec ID (not runtime user input). The cycle counter N is an integer incremented by the orchestrator loop. Neither is user-attacker-controlled. No injection surface.

**5. KDR-003 boundary** — `grep -rn "ANTHROPIC_API_KEY" ai_workflows/` returns zero hits. The single occurrence of the string in `auditor.md` is a negative-assertion instruction ("does not import `anthropic` SDK or read `ANTHROPIC_API_KEY` — either violation is HIGH"), not a live credential reference. KDR-003 preserved.

**6. Logging hygiene** — No new `StructuredLogger` calls introduced (T03 is `.claude/` + `tests/` only). No API keys, OAuth tokens, or env values in any new file.

### 🔴 Critical — must fix before publish/ship

None.

### 🟠 High — should fix before publish/ship

None.

### 🟡 Advisory — track; not blocking

None.

### Verdict: SHIP

## Dependency audit (2026-04-28)

Dependency audit: skipped — no manifest changes. `git diff --name-only HEAD` shows neither `pyproject.toml` nor `uv.lock` was modified by T03.

---

## Sr. Dev review (2026-04-28)

**Files reviewed:**
- `.claude/agents/auditor.md`
- `.claude/commands/auto-implement.md`
- `.claude/commands/clean-implement.md`
- `.claude/commands/_common/spawn_prompt_template.md`
- `.claude/commands/_common/cycle_summary_template.md`
- `tests/orchestrator/_helpers.py`
- `tests/orchestrator/test_cycle_summary_emission.py`
- `tests/orchestrator/test_cycle_context_constant.py`

**Skipped (out of scope):** `tests/orchestrator/fixtures/m12_t03_pre_t03_cycle3_spawn_prompt.txt` (fixture content; no logic to review)

**Verdict:** SHIP

### 🔴 BLOCK — must-fix before commit

None.

### 🟠 FIX — fix-then-ship

None.

### 🟡 Advisory — track but not blocking

**Advisory-1 — `make_cycle_summary` does not enforce the OPEN+carry_over invariant it documents**

File: `tests/orchestrator/_helpers.py`, line 434 (`make_cycle_summary`) and line 462 (docstring).

The function docstring states "Must be non-empty when `auditor_verdict` is `OPEN` (invariant from the template)." The function body does not enforce this: calling `make_cycle_summary(auditor_verdict="OPEN", carry_over=[])` silently renders `Carry-over to next cycle: none` — a spec-violation summary that passes all structural tests. The test suite tests the PASS+empty-carry-over case (`test_cycle_3_pass_carry_over_empty`, line 280) but has no test that asserts the OPEN+empty-carry-over case is rejected or flagged. In production, an LLM Auditor that erroneously emits an OPEN verdict with empty carry-over would produce a summary the orchestrator reads without error, silently skipping the next Builder's target ACs.

This is not a hidden bug in production paths (the Auditor is instructed to populate carry-over; the `auditor.md` invariant is clear). It is a gap in the test harness: the guard that should make the invariant machine-checkable is missing. Advisory because the production path is prose-instructed, not code-executed.

Action: Add a `ValueError` guard at the top of `make_cycle_summary` — `if auditor_verdict == "OPEN" and not carry_over: raise ValueError(...)` — and add a corresponding test `test_open_verdict_requires_carry_over` asserting the guard fires. Two-line code change; two-line test. Consider as carry-over to T05 (next task touching `_helpers.py`) or a standalone cleanup pass.

**Advisory-2 — `_stub_auditor_emit_summary` references "audit M11" — stale milestone citation**

File: `tests/orchestrator/test_cycle_summary_emission.py`, line 65 (function docstring) and line 144 (assertion message): "nested form `cycle_<N>/summary.md` is authoritative per audit M11."

M11 does not exist in this repo's milestone sequence (current range is M12–M20). The reference appears to be a placeholder or copy-paste artefact. The assertion message on line 213 ("per audit M11") and line 277 ("per audit M11") repeat the same stale citation. This does not affect test correctness but will confuse a future reader trying to trace the provenance.

Action: Replace "audit M11" with the correct source ("T03 spec" or "cycle_summary_template.md §Directory layout"). Three-line find-replace across the file.

**Advisory-3 — Harness-write Advisory (from invoker brief) — not a runtime correctness risk**

The invoker brief notes a concern that the Claude Code default-prompt rule "NEVER create documentation files (*.md)" may block the Auditor's `Write` call at runtime. After reviewing `auditor.md` lines 1-6 (front matter declares `tools: Read, Write, Edit, Bash, Grep, Glob`) and Phase 5b (line 114: "use `Write` to emit the summary file"):

The `tools:` front matter in a `Task`-spawned agent's system prompt is the operative permission grant for that agent's invocation. The interactive-Claude-Code "NEVER create documentation" default applies to the main assistant session, not to `Task`-spawned agents whose system prompt explicitly authorises `Write`. Phase 5b's instruction "use `Write` to emit the summary file at the path the orchestrator will read" is a direct override of any default-mode documentation-creation restriction for that agent invocation. This is not a runtime correctness risk.

The genuine (pre-existing) risk in this area is LOW-3 (M20-T03-ISS-03): if the orchestrator has not created the `runs/<task>/cycle_<N>/` directory, the `Write` call will fail because the parent directory is absent. This remains correctly tracked as OPEN/flag-only. No new finding.

### What passed review (one-line per lens)

- Hidden bugs: No runtime hidden bugs; one test-harness invariant gap in `make_cycle_summary` (Advisory-1 above).
- Defensive-code creep: None observed — Phase 5b and template are lean; no gratuitous guards.
- Idiom alignment: All four files consistent on Builder/Auditor cycle-N rules; Auditor pre-load correctly retains README path on all cycles per cycle-2 resolution.
- Premature abstraction: None introduced by T03; `extract_kdr_sections` pre-dates T03 (T02 scope).
- Comment / docstring drift: Stale "audit M11" citation in test docstrings and assertion messages (Advisory-2); otherwise docstrings are appropriate and cite the task correctly.
- Simplification: No simplification opportunities identified; `parse_cycle_summary` complexity is warranted and scoped to test infrastructure with appropriate caveat in its docstring.

---

## Sr. SDET review (2026-04-28)

**Test files reviewed:**
- `tests/orchestrator/_helpers.py` (cycle-summary additions: `make_cycle_summary`, `build_builder_spawn_prompt_cycle_n`, `parse_cycle_summary`, `CYCLE_SUMMARY_REQUIRED_KEYS`)
- `tests/orchestrator/test_cycle_summary_emission.py` (11 tests)
- `tests/orchestrator/test_cycle_context_constant.py` (6 tests)
- `tests/orchestrator/fixtures/m12_t03_pre_t03_cycle3_spawn_prompt.txt`

**Skipped (out of scope):** `.claude/agents/auditor.md`, `.claude/commands/auto-implement.md`, `.claude/commands/clean-implement.md` — prose only, no test logic.

**Verdict:** BLOCK

### 🔴 BLOCK — tests pass for the wrong reason

**BLOCK-1 — `test_cycle3_does_not_include_cycle1_builder_report` asserts a string the test never injects (tautological assertion)**

File: `tests/orchestrator/test_cycle_context_constant.py:300-328`
Lens: 1 (passes for the wrong reason)

The test defines `distinctive_cycle1_phrase = "Cycle 1 Builder report (FULL CHAT — pre-T03 pattern)"` and then asserts `distinctive_cycle1_phrase not in cycle3_prompt`. The `cycle3_prompt` is built by `build_builder_spawn_prompt_cycle_n()` with parameters `task_spec_path`, `issue_file_path`, `project_context_brief`, `latest_cycle_summary`, and `cycle_summary_path`. None of these parameters contains the distinctive phrase; none of the function's internal string literals contain it either. The assertion is therefore vacuously true — it passes identically whether the function correctly drops prior cycle context or not.

The AC this test is supposed to pin (spec AC-6 / spec §Tests para 3: "The orchestrator does **not** include cycle 1's Builder report in cycle 3's spawn prompt") requires demonstrating that the function's interface does not admit prior-cycle chat content. The meaningful test would call `build_builder_spawn_prompt_cycle_n()` with a `latest_cycle_summary` that contains a known marker phrase, then assert the marker IS present (the summary is carried), and separately call a hypothetical pre-T03 function that additionally accepts prior Builder chat and assert the marker from prior cycles is NOT present in the post-T03 variant. As written, the assertion proves only that `build_builder_spawn_prompt_cycle_n()` does not inject a string that was never passed to it — which is true of any pure function regardless of its implementation.

The source it was supposed to pin: `_helpers.py:507-553` (`build_builder_spawn_prompt_cycle_n`), which correctly implements the rule but whose correctness the tautological assertion does not prove.

Action / Recommendation: Replace the tautological negative assertion with a two-part discriminating test:
1. Assert that content from `latest_cycle_summary` (a known marker phrase embedded in the summary) IS present in `cycle3_prompt` (proves the summary is carried).
2. Assert that additional content passed to a `build_builder_spawn_prompt_cycle_n_pre_t03` (or equivalent model with a `prior_context` parameter) would appear in the pre-T03 prompt but NOT in the post-T03 prompt — demonstrating the compaction. Alternatively, simply assert that the prompt length equals the expected length (spec path + issue path + project brief + single summary) and that no second-summary content appears when two different summaries are available.

### 🟠 FIX — fix-then-ship

**FIX-1 — `test_cycle2_within_10pct_of_cycle3` is nearly tautological: both summaries are constructed from the same factory with near-identical inputs**

File: `tests/orchestrator/test_cycle_context_constant.py:174-212`
Lens: 2 (coverage gap hiding under a passing test)

`summary_1 = _build_cycle_summary(cycle_number=1, auditor_verdict="OPEN")` and `summary_2 = _build_cycle_summary(cycle_number=2, auditor_verdict="OPEN")` differ by exactly one character in their rendered output (the cycle number digit in the header `# Cycle 1 summary` vs `# Cycle 2 summary`, plus `cycle_1` vs `cycle_2` in the `cycle_summary_path` arg). `_build_cycle_summary()` hardcodes `files_changed`, `gates`, `open_issues`, `decisions_locked`, and `carry_over` to the same values for both calls. The resulting token counts differ by at most 2 tokens (one digit in the summary, one digit in the path string). A 10% bound on counts of ~200+ tokens will never be violated by a 2-token difference.

The test is supposed to prove that the O(1) constant-context property holds: that cycle-2 and cycle-3 prompts stay near the same size even as real-world issue content accumulates. The current construction proves only that two prompts built from the same factory with integer-differing inputs have similar sizes — which is true by construction regardless of the template's actual bounding behaviour.

A meaningful test would construct `summary_1` with minimal content (e.g. 1 carry-over item, 3 files, no decisions) and `summary_2` with a realistic larger content (e.g. 5 carry-over items, 8 files, 2 decisions locked, a multi-item open-issues string) and assert the resulting prompts still fall within a bound. That would validate that the template structure actually bounds growth. The current test validates nothing the factory's interface doesn't already guarantee.

Action / Recommendation: Construct `summary_1` and `summary_2` with meaningfully different content volumes (different `files_changed` list lengths, different `carry_over` list lengths, different `open_issues` lengths). The test should still pass (the template is bounded by design), but it would become discriminating: if someone modified `make_cycle_summary` to include unbounded raw text, the test would catch it.

**FIX-2 — `test_cycle2_within_10pct_of_cycle1` and `test_cycle3_within_10pct_of_cycle1` test names promise 10% but bodies use 50%**

File: `tests/orchestrator/test_cycle_context_constant.py:214-259` and `261-298`
Lens: 6 (naming hygiene) + Lens 2 (the actual 10% bound from the spec is never asserted for cycles 1 vs 2/3)

Both test names say `within_10pct_of_cycle1` but both use `permissive_bound = 0.50`. The spec AC-6 states "within 10%" for all cycles vs cycle 1. The documented deviation (50% bound for cycle-1-vs-cycle-N because of structural difference: path reference vs content) is in the module docstring and the Auditor accepted it. However the test name actively misdirects a reader and future maintainer into believing the 10% assertion is in force. Naming a test `test_cycle2_within_10pct_of_cycle1` when the actual bound in the body is `0.50` is a Lens 6 finding that borders on misleading.

Additionally, since the spec's stated requirement is "within 10% of cycle 1" for all N, and no test enforces the 10% bound against cycle-1 (the strict 10% test only covers cycle-2-vs-cycle-3), the spec's "within 10%" claim is not covered by any test for the cycle-1 baseline.

Action / Recommendation: Rename both tests to `test_cycle2_within_50pct_of_cycle1` and `test_cycle3_within_50pct_of_cycle1` to match the actual assertion. In the module docstring or a comment, explicitly note that the spec's 10% claim for cycle-1 vs cycle-N is deferred to T22 when empirical baselines land. This is a two-line rename (one per test) with no logic change.

### 🟡 Advisory — track but not blocking

**Advisory-SDET-1 — No negative test for OPEN-verdict + empty carry-over in `test_cycle_summary_emission.py`**

File: `tests/orchestrator/test_cycle_summary_emission.py` (no test present for this case)
Lens: 2 (coverage gap)

`make_cycle_summary()` documents "Must be non-empty when `auditor_verdict` is `OPEN`" but does not enforce it. `test_cycle_1_open_carry_over_populated` only tests the happy path (OPEN + non-empty carry-over). No test asserts that calling with `auditor_verdict="OPEN"` and `carry_over=[]` is rejected or flagged. This was already flagged by Sr. Dev as Advisory-1 (the guard is missing from the helper). The SDET lens adds: even if the guard is added, there is currently no test pinning it. Both the guard and the test for the guard are missing.

Action: Add `test_open_verdict_requires_carry_over` asserting `pytest.raises(ValueError)` when `make_cycle_summary(auditor_verdict="OPEN", carry_over=[])` is called (after adding the guard per Sr. Dev Advisory-1 recommendation). One test, two lines of assertion.

**Advisory-SDET-2 — Stale "audit M11" citation in test docstrings and assertion messages (eight occurrences)**

File: `tests/orchestrator/test_cycle_summary_emission.py` lines 8, 65, 144, 215, 277, 323
Lens: 6 (assertion-message hygiene)

"nested form `cycle_<N>/summary.md` is authoritative per audit M11" — M11 does not exist in the milestone sequence (M12 is the earliest active milestone). Already flagged by Sr. Dev Advisory-2. Surfacing here too: the stale citation appears in six assertion failure messages, meaning a failing test would output misleading provenance.

Action: Replace "audit M11" with the canonical source reference: `"cycle_summary_template.md §Directory layout"` or `"T03 spec §Deliverables"`. Six occurrences (find-replace across the file).

**Advisory-SDET-3 — `test_cycle_1_summary_exists` and similar tests assert `flat.exists() == False` without verifying the directory was not created at all**

File: `tests/orchestrator/test_cycle_summary_emission.py:140-145`, `215-218`, `274-278`, `317-322`
Lens: 4 (fixture hygiene / assertion granularity)

The flat-form assertions check `assert not flat.exists()` where `flat = runs_dir / "cycle_1_summary.md"`. Since `_stub_auditor_emit_summary` creates `cycle_dir = runs_dir / "cycle_1"` and writes `cycle_dir / "summary.md"`, the flat path `runs_dir / "cycle_1_summary.md"` is in a different directory and will never be created by the current implementation. The assertion is true by construction. A stronger assertion would also verify that `runs_dir / "cycle_1_summary.md"` does not exist *because* the correct nested path does exist (i.e., `assert (runs_dir / "cycle_1" / "summary.md").exists() and not (runs_dir / "cycle_1_summary.md").exists()`). The positive side already has a dedicated assertion; these are fine as defense-in-depth.

No action required — this is a documentation note, not a functional gap.

### What passed review (one-line per lens)

- Tests-pass-for-wrong-reason: BLOCK-1 — `test_cycle3_does_not_include_cycle1_builder_report` is tautological (phrase never injected; assertion cannot fail).
- Coverage gaps: FIX-1 — `test_cycle2_within_10pct_of_cycle3` uses near-identical factory inputs; Advisory-SDET-1 — no negative test for OPEN+empty-carry-over.
- Mock overuse: None — no mocks in scope; pure Python string construction throughout.
- Fixture / independence: Clean — `runs_dir` fixture is function-scoped; no cross-test state; tests in `TestCycleSummaryEmission` are independent.
- Hermetic-vs-E2E gating: Clean — no network calls, no subprocess, no real LLM spawns, no `AIW_E2E` gating needed.
- Naming / assertion-message hygiene: FIX-2 — two test names say "10pct" but bodies assert 50%; Advisory-SDET-2 — stale "audit M11" citation in six assertion messages.

## Locked team decisions (cycle 2 → cycle 3 carry-over)

User-arbitrated 2026-04-28 after team-gate divergence (sr-dev SHIP, sr-sdet BLOCK). User concurred with sr-sdet's reading and stamped all three findings as locked decisions for Builder cycle 3:

- **Locked decision (loop-controller + sr-sdet concur, 2026-04-28)** — BLOCK-1: Replace `test_cycle3_does_not_include_cycle1_builder_report` with a discriminating two-part assertion. (1) Assert `latest_cycle_summary` marker IS present in the cycle-3 prompt (proves the summary is carried). (2) Assert a prior-cycle marker passed via a `prior_context` test fixture parameter is NOT present in the post-T03 prompt (proves prior-cycle chat content is dropped). The current vacuous "phrase not in prompt" assertion does not pin AC-6 because the phrase is never injected into any input. File: `tests/orchestrator/test_cycle_context_constant.py:300-328`.

- **Locked decision (loop-controller + sr-sdet concur, 2026-04-28)** — FIX-1: Vary content volumes meaningfully across the within-10%-bound test fixtures (`test_cycle2_within_10pct_of_cycle3`). Current inputs differ by 1 character (cycle number digit), making the bound trivially unreachable. Pick distinctive content volumes — e.g. summary 1 with minimal content (1 carry-over item, 3 files, no decisions) and summary 2 with realistic larger content (5 carry-over items, 8 files, 2 decisions locked, multi-item open-issues). Test should still pass (template is bounded by design) but become discriminating: a regression that introduced unbounded raw text would be caught. File: `tests/orchestrator/test_cycle_context_constant.py:174-212`.

- **Locked decision (loop-controller + sr-sdet concur, 2026-04-28)** — FIX-2: Rename `test_cycle{2,3}_within_10pct_of_cycle1` → `test_cycle{2,3}_within_50pct_of_cycle1` to match the body's actual 50% assertion. The 50% is the documented heuristic for cycle-1-vs-cycle-N≥2 structural-difference comparisons; the names should agree with the bodies. The strict 10% claim for cycle-1 baseline remains deferred to T22's empirical telemetry. Two-line rename per file. Files: `tests/orchestrator/test_cycle_context_constant.py:214-259` + `261-298`.

Out of scope for cycle 3: Advisory-SDET-1, -2, -3 + the cycle-2 LOWs (LOW-3, LOW-4) — tracked but not in cycle-3 carry-over. Cycle 3 should converge fast (three test rewrites, no production code changes).

---

## Cycle 3 audit (2026-04-28)

**Cycle:** 3
**Auditor verdict:** ✅ PASS (with one cycle-3 MEDIUM observation — see below)
**Scope:** Three locked-decision test rewrites in `tests/orchestrator/test_cycle_context_constant.py` + CHANGELOG cycle-3 note. No production-code changes expected.

### Diff scope check (cycle 3 in isolation)

The cycle-3 carry-over scoped changes to `tests/orchestrator/test_cycle_context_constant.py` (test rewrites) and CHANGELOG (notes). The working tree (post-cycle-3) shows the cumulative T03 working-tree state (no commits yet on T03; cycles 1, 2, 3 all live as uncommitted changes). To isolate cycle-3 deltas, I cross-checked each named locked-decision change against the file's current state:

- `tests/orchestrator/test_cycle_context_constant.py` — three named rewrites land (BLOCK-1 / FIX-1 / FIX-2; details below).
- `CHANGELOG.md` — appended a "Cycle 3 test rewrites (2026-04-28)" subsection at lines 84-99 documenting the three locked-decision changes. No production-block additions.
- All other files in the cumulative working tree (`.claude/agents/auditor.md`, `.claude/commands/auto-implement.md`, `.claude/commands/clean-implement.md`, `.claude/commands/_common/spawn_prompt_template.md`, `.claude/commands/_common/cycle_summary_template.md`, `tests/orchestrator/_helpers.py`, `tests/orchestrator/test_cycle_summary_emission.py`, `tests/orchestrator/fixtures/m12_t03_pre_t03_cycle3_spawn_prompt.txt`, milestone README, task spec) are unchanged vs the cycle-2 audit close — verified by inspection of the named regions referenced in cycle-1 / cycle-2 issue-file findings.

No `ai_workflows/` runtime code touched. No new dependencies. No `pyproject.toml` / `uv.lock` touched. Scope discipline held.

### Locked-decision verification

#### BLOCK-1 — Discriminating two-part replacement (`test_cycle3_carries_summary_drops_prior_chat`)

**File:** `tests/orchestrator/test_cycle_context_constant.py:360-424`

Test renamed from `test_cycle3_does_not_include_cycle1_builder_report` (line 360). The new test embeds `summary_marker = "DISTINCTIVE_SUMMARY_MARKER_FOR_CYCLE_2"` inside the cycle-2 summary's carry-over field (line 390) and runs two assertions:

- **Part 1 (line 407): `assert summary_marker in cycle3_prompt`** — DISCRIMINATING. If `build_builder_spawn_prompt_cycle_n` regressed to drop `latest_cycle_summary` from the prompt assembly (e.g. the f-string at `_helpers.py:545-553` lost the summary line), this assertion would fail. Procedure-step-3 thought experiment confirmed: the assertion would fail under any regression that breaks summary forwarding.

- **Part 2 (line 418): `assert prior_chat_marker not in cycle3_prompt`** — STILL VACUOUS in the strict sense. `prior_chat_marker = "DISTINCTIVE_PRIOR_CYCLE_BUILDER_CHAT_MARKER"` is defined at line 384 but never injected into any input. The assertion would be true regardless of `build_builder_spawn_prompt_cycle_n`'s implementation. The docstring (lines 372-375, 414-416) acknowledges the structural guarantee comes from the function's signature ("the function's interface itself cannot admit prior-cycle chat content"), not from the assertion's discriminating power.

  Procedure-step-3 thought experiment for part 2: if the function were modified to concatenate `prior_context` via a new parameter, the test's existing call (no `prior_context` kwarg) would raise `TypeError` — caught indirectly. But if the function were modified to read prior context from a global / file / process state and inject it, the assertion `prior_chat_marker not in cycle3_prompt` would still pass vacuously — NOT caught.

**Verdict:** Partial fix. Part 1 substantially improves AC-6 coverage and is genuinely discriminating; the test as a whole is much stronger than the cycle-2 version. Part 2 reproduces the same vacuous-phrase-never-injected pattern that the locked decision explicitly flagged as the failure mode ("the current vacuous 'phrase not in prompt' assertion does not pin AC-6 because the phrase is never injected into any input"). See M20-T03-ISS-05 below.

#### FIX-1 — Meaningfully different content volumes in `test_cycle2_within_10pct_of_cycle3`

**File:** `tests/orchestrator/test_cycle_context_constant.py:174-268`

Both summaries are now constructed inline (no longer using `_build_cycle_summary` helper) with different content:
- `summary_1` (line 194-209): 3 files, "1 MEDIUM" open_issues, 0 decisions, 1 carry-over → 119.6 tokens
- `summary_2` (line 225-247): 5 files, "2 MEDIUM (...)" open_issues, 1 decision (~75 chars), 2 carry-overs → 153.4 tokens

Empirical verification (run via inline Python invocation against the live module):
- summary_1 → cycle2_prompt = 393.9 tokens
- summary_2 → cycle3_prompt = 427.7 tokens
- ratio = 8.58% (under the 10% bound, ~14% margin)
- A regression injecting unbounded raw text (10× 200-char carry-overs simulated) would shift the ratio by enough to blow the 10% bound

**Deviation from locked-decision suggested values.** The locked decision suggested "5 carry-over items, 8 files, 2 decisions locked, multi-item open-issues" for summary_2; the Builder used 2 carry-overs / 5 files / 1 decision. The locked decision text used "e.g." (suggestive), and the achieved 14% margin is sufficient to discriminate. Acceptable.

**Verdict:** Fix landed and is genuinely discriminating. The 8.58% / 10% margin demonstrates the bound is tight enough that real-world summary content fits, but a template regression that admitted unbounded text would fail the test.

#### FIX-2 — Rename `test_cycle{2,3}_within_10pct_of_cycle1` → `test_cycle{2,3}_within_50pct_of_cycle1`

**File:** `tests/orchestrator/test_cycle_context_constant.py:270` (renamed `test_cycle2_within_50pct_of_cycle1`) and line 317 (renamed `test_cycle3_within_50pct_of_cycle1`).

Verified via `grep -n "def test_cycle" tests/orchestrator/test_cycle_context_constant.py`:
- Line 162: `test_cycle1_prompt_is_baseline` (unchanged)
- Line 174: `test_cycle2_within_10pct_of_cycle3` (FIX-1 target)
- Line 270: `test_cycle2_within_50pct_of_cycle1` (was `_10pct_`)
- Line 317: `test_cycle3_within_50pct_of_cycle1` (was `_10pct_`)
- Line 360: `test_cycle3_carries_summary_drops_prior_chat` (BLOCK-1 target)

Both renamed test bodies use `permissive_bound = 0.50` (lines 307, 350), agreeing with their new names. Docstrings updated (lines 271-282, 318-329) to note that the strict 10% bound for cycle-1 baseline is deferred to T22.

**Verdict:** Clean rename. Names + bodies + docstrings all agree.

### Cycle 3 gate re-run (Auditor; from scratch — not relying on Builder report)

| Gate | Command | Result |
|---|---|---|
| pytest (T03 tests in isolation) | `AIW_BRANCH=design uv run pytest tests/orchestrator/test_cycle_summary_emission.py tests/orchestrator/test_cycle_context_constant.py -v` | PASS — 17 passed, 0.04s |
| pytest (full suite, deterministic order) | `AIW_BRANCH=design uv run pytest -p no:randomly` | PASS — 1002 passed, 7 skipped, 22 warnings, 47.48s |
| lint-imports | `uv run lint-imports` | PASS — 5 contracts kept, 0 broken |
| ruff | `uv run ruff check` | PASS — All checks passed |
| Test-name agreement | `grep -n "def test_cycle" tests/orchestrator/test_cycle_context_constant.py` | PASS — both `_50pct_` names match `permissive_bound = 0.50` bodies |
| Status surfaces | spec line + milestone README task table + Done-when checkbox | PASS — all aligned at "✅ Done (2026-04-28)" |

### Cycle 1 + 2 ACs preservation

All AC-1..9 from cycle 1 remain ✅ Met. Cycle-2 MEDIUM resolutions (M20-T03-ISS-01, M20-T03-ISS-02) remain ✅ Met. Cycle-1 LOWs (M20-T03-ISS-03, M20-T03-ISS-04) remain OPEN — flag-only as previously tracked. L1 + L2 carry-over items remain ✅ Met. AC-9 status surfaces remain aligned.

### 🔴 HIGH — none

(no design-drift HIGHs; no scope creep beyond test files + CHANGELOG; no gate integrity concerns)

### 🟡 MEDIUM — M20-T03-ISS-05 — BLOCK-1 part 2 retains the vacuous-phrase-never-injected pattern the locked decision flagged

**File:** `tests/orchestrator/test_cycle_context_constant.py:418-424` (part 2 of `test_cycle3_carries_summary_drops_prior_chat`).

**Issue.** The locked decision (cycle 2 → cycle 3 carry-over) explicitly identified the failure mode of the cycle-2 BLOCK-1 test:

> "The current vacuous 'phrase not in prompt' assertion does not pin AC-6 because the phrase is never injected into any input."

The cycle-3 rewrite split the test into two parts and made part 1 (`summary_marker in cycle3_prompt`) genuinely discriminating, but part 2 (`prior_chat_marker not in cycle3_prompt`) reproduces the exact pattern the locked decision flagged: the marker `"DISTINCTIVE_PRIOR_CYCLE_BUILDER_CHAT_MARKER"` is defined at line 384 but never passed to any function or injected into any input. The assertion at line 418 is true by construction regardless of `build_builder_spawn_prompt_cycle_n`'s implementation.

The Builder's docstring (lines 372-375, 414-416) acknowledges this and argues the structural guarantee comes from the function's signature ("the function's interface itself cannot admit prior-cycle chat content"). This is a reasonable defence — the function genuinely cannot accept prior context via its current parameter list, so a regression would require a signature change which would break the test's existing call. But this is a *signature-level* guarantee captured by Python's type-checking, not an *assertion-level* guarantee captured by the test's negative assertion.

The locked decision text offered an alternative path: "Alternatively, simply assert that the prompt length equals the expected length (spec path + issue path + project brief + single summary) and that no second-summary content appears when two different summaries are available." The Builder did not take this alternative path.

**Severity rationale.** MEDIUM rather than HIGH because:
- Part 1 IS genuinely discriminating and substantially improves AC-6 coverage vs the cycle-2 version. The test as a whole is meaningfully stronger.
- The function signature DOES structurally prevent prior-context injection, so the vacuity reflects a real structural property — it's just not captured by the assertion itself.
- Test-only scope, no production-code risk.
- Cycle-3 already converged on the other two locked decisions; reopening this for a third cycle would cost more orchestrator context than the marginal coverage improvement justifies (FIX-1 already discriminates against unbounded-text regressions; BLOCK-1 part 1 already discriminates against summary-drop regressions).

But it's not LOW because the locked decision text explicitly named the vacuous-phrase-never-injected pattern as the failure mode and the Builder's part 2 reproduces that pattern verbatim with a different distinct phrase.

**Action / Recommendation.** Two paths:

1. **(Defer / accept as-is)** — Stamp the cycle-3 part-2 form as locked-decision-acceptance (loop-controller concur) on the grounds that the signature constraint + part-1 discrimination + cycle-2 docstring acknowledgement of the structural guarantee together cover the spirit of the locked decision. The vacuity is well-documented in the test's own docstring. Tracked here as MEDIUM/flag-only; not blocking.

2. **(Future cleanup)** — Add a third assertion that constructs two distinct summaries (e.g. summary_1 with marker_a, summary_2 with marker_b) and asserts that when `build_builder_spawn_prompt_cycle_n` is called with summary_2 as `latest_cycle_summary`, marker_a does NOT appear in the prompt — discriminating against any regression that retains prior-summary content. This is the "two-different-summaries" alternative the locked decision named. One additional inline call + two assertions in the same test.

Pending user / loop-controller decision between path 1 (accept) and path 2 (carry-over to a future test-cleanup task).

**Locked decision (loop-controller + Auditor concur + user arbitration, 2026-04-28):** Path 1 accepted. The cycle-3 BLOCK-1 part-2 vacuity is documented as known and acknowledged in the test docstring. The signature-level structural guarantee (`build_builder_spawn_prompt_cycle_n` cannot accept `prior_context` via its current parameter list) + part-1's positive-discriminating assertion + the test as a whole being meaningfully stronger than the cycle-2 version together cover the spirit of the original locked decision. The two-different-summaries discrimination alternative (path 2) is deferred — if a future task touches `tests/orchestrator/test_cycle_context_constant.py` it may add the third assertion as a coverage hardening; not blocking T03 ship.

### Issue log update

| ID | Severity | Owner / next touch point | Status |
|---|---|---|---|
| M20-T03-ISS-01 | MEDIUM | resolved cycle 2 (2026-04-28) | CLOSED — verified cycle 2 + 3 (no regression) |
| M20-T03-ISS-02 | MEDIUM | resolved cycle 2 (2026-04-28) | CLOSED — verified cycle 2 + 3 (no regression) |
| M20-T03-ISS-03 | LOW | T05 / future hardening task | OPEN — flag-only |
| M20-T03-ISS-04 | LOW | T22 (per-cycle telemetry) | OPEN — flag-only |
| M20-T03-ISS-05 | MEDIUM | accepted-as-is (loop-controller + Auditor concur + user-arbitrated 2026-04-28; path 1) | ✅ CLOSED — documented acceptance |

### Cycle 3 verdict

✅ PASS with one MEDIUM observation (M20-T03-ISS-05). All three locked-decision rewrites landed. Two of three are genuinely discriminating (FIX-1 + BLOCK-1 part 1); one reproduces the cycle-2 vacuity pattern (BLOCK-1 part 2) but is paired with a discriminating positive assertion and a signature-level structural guarantee. All gates green. No scope creep. Status surfaces aligned.

The cycle-3 MEDIUM is a candidate for loop-controller-concur-and-stamp under the auditor-agreement bypass mechanic (CLAUDE.md `/clean-implement` semantics): the recommendation is clear (path 1 accept OR path 2 add two-summary discrimination), neither expands scope nor conflicts with KDRs. Surface to the user / loop-controller for arbitration before closing this audit cycle.

---

## Security review — cycle 3 re-check (2026-04-28)

**Scope:** Cycle-3 incremental diff only — three test rewrites in `tests/orchestrator/test_cycle_context_constant.py` and a CHANGELOG cycle-3 subsection. No production code touched. Cycle-1 security review (lines 236-268) is preserved verbatim and applies in full.

### Threat-model checklist (cycle-3 delta)

**1. Wheel-contents leakage** — No manifest changes. `pyproject.toml` and `uv.lock` untouched. The cycle-3 diff adds no new files; the three rewrites are in-place edits to an existing file under `tests/`, which is excluded from the wheel by the pre-existing manifest rules. No leakage surface introduced.

**2. Subprocess / env reads** — `tests/orchestrator/test_cycle_context_constant.py` contains no `subprocess` calls, no `os.environ` reads, no `ANTHROPIC_API_KEY` references, no `GEMINI_API_KEY` references. Confirmed via grep returning zero hits.

**3. Test marker strings** — The two new marker constants (`"DISTINCTIVE_SUMMARY_MARKER_FOR_CYCLE_2"` at line 379; `"DISTINCTIVE_PRIOR_CYCLE_BUILDER_CHAT_MARKER"` at line 384) are syntactically unambiguous placeholder strings. Neither has the shape of a real credential, token, API key, or environment variable value. No leakage risk.

**4. CHANGELOG entry** — The cycle-3 subsection at `CHANGELOG.md` line 84 is prose description of test-rewrite rationale. No secrets, no real credentials, no env values embedded.

**5. KDR-003 boundary** — No new `ANTHROPIC_API_KEY` reads. No new `anthropic` SDK imports. KDR-003 unaffected by the cycle-3 diff.

### 🔴 Critical — must fix before publish/ship

None.

### 🟠 High — should fix before publish/ship

None.

### 🟡 Advisory — track; not blocking

None.

### Verdict: SHIP

---

## Sr. Dev review — cycle 3 re-check (2026-04-28)

**Files reviewed:** `tests/orchestrator/test_cycle_context_constant.py` (cycle-3 rewrites: BLOCK-1 / FIX-1 / FIX-2), `CHANGELOG.md` (cycle-3 note)
**Skipped (out of scope):** `.claude/agents/auditor.md`, `.claude/commands/auto-implement.md`, `.claude/commands/clean-implement.md`, `.claude/commands/_common/*.md`, `tests/orchestrator/_helpers.py`, `tests/orchestrator/test_cycle_summary_emission.py` — cycle-3 diff did not touch these files; cycle-2 Sr. Dev review covers them.
**Verdict:** SHIP

### Scope-creep check (source/agent/command lane)

The invoker brief specifies that cycle 3 is test-only. Verified: none of `.claude/agents/`, `.claude/commands/`, or `ai_workflows/` files appear in the cycle-3 diff. The only changed files are `tests/orchestrator/test_cycle_context_constant.py` and `CHANGELOG.md`. No scope creep.

### 🔴 BLOCK — must-fix before commit

None.

### 🟠 FIX — fix-then-ship

None.

### 🟡 Advisory — track but not blocking

**Advisory-C3-1 — `test_cycle2_within_10pct_of_cycle3` name still contains `10pct` while FIX-2 renamed the cycle-1-vs-N tests to `50pct`**

File: `tests/orchestrator/test_cycle_context_constant.py:174`

The two tests renamed by FIX-2 (`test_cycle2_within_50pct_of_cycle1`, `test_cycle3_within_50pct_of_cycle1`) now accurately reflect their `0.50` bound. The structurally-different test `test_cycle2_within_10pct_of_cycle3` (line 174) correctly asserts `_WITHIN_FRACTION = 0.10` and the name matches the body — no bug. This is Advisory only because FIX-2's rename of the sibling tests briefly creates a reader pause: two tests with `_50pct_` and one with `_10pct_`; a reader must understand the two measure structurally different comparisons. The module docstring and per-test docstrings explain this clearly.

Action: None required. If a future task touches this file, consider adding a comment in the class docstring noting the intentional asymmetry.

### What passed review (one-line per lens)

- Hidden bugs: None — BLOCK-1 part 1 is genuinely discriminating (summary marker present in cycle-3 prompt); BLOCK-1 part 2 vacuity is accepted-as-is per ISS-05 user-arbitrated Path 1; FIX-1 / FIX-2 are pure test-quality improvements with no correctness risk.
- Defensive-code creep: None observed — test rewrites are lean; no gratuitous guards added.
- Idiom alignment: Consistent with neighbouring test files in `tests/orchestrator/`; `make_cycle_summary` helper usage and `token_count_proxy` pattern unchanged.
- Premature abstraction: None — cycle-3 removes `_build_cycle_summary` delegation in favour of inline construction in `test_cycle2_within_10pct_of_cycle3`, a simplification not an abstraction.
- Comment / docstring drift: FIX-1 and FIX-2 docstrings updated to match changed assertion logic; cycle-3 adds clear T22-deferral notes consistent with cycle-1/2 docstrings.
- Simplification: FIX-1 inline construction is a net simplification vs the prior two-call `_build_cycle_summary` delegation it replaced.

---

## Sr. SDET review — cycle 3 re-check (2026-04-28)

**Test files reviewed:**
- `tests/orchestrator/test_cycle_context_constant.py` (lines 360-424 renamed/rewritten — BLOCK-1; lines 174-268 rewritten — FIX-1; lines 270 + 317 renamed — FIX-2)
- `tests/orchestrator/test_cycle_summary_emission.py` (spot-checked for advisory regression)
- `tests/orchestrator/_helpers.py` (no cycle-3 changes; re-checked for context)

**Skipped (out of scope):** `.claude/agents/auditor.md`, `.claude/commands/auto-implement.md`, `.claude/commands/clean-implement.md`, `CHANGELOG.md` cycle-3 subsection — prose only.

**Verdict:** SHIP

### Locked-decision re-verification (three items from cycle 2 to cycle 3)

**BLOCK-1 — `test_cycle3_carries_summary_drops_prior_chat` (lines 360-424)**

Part 1 (`assert summary_marker in cycle3_prompt`, line 407): genuinely discriminating. `summary_marker = "DISTINCTIVE_SUMMARY_MARKER_FOR_CYCLE_2"` is embedded in the carry-over field of `summary_2` (line 390) which is passed as `latest_cycle_summary` to `build_builder_spawn_prompt_cycle_n`. Any regression that dropped the `{latest_cycle_summary}` interpolation from `_helpers.py:549` would cause this assertion to fail. Lens-1 concern from cycle 2 is resolved for part 1.

Part 2 (`assert prior_chat_marker not in cycle3_prompt`, line 418): the vacuity is intact and documented in the test docstring (lines 372-375, 414-416). The marker is defined at line 384 but never injected into any input — the assertion is tautologically true. User-arbitrated Path 1 (accepted-as-is, 2026-04-28) governs; not re-raised here. Locked decision reference: ISS-05 in issue log.

**FIX-1 — `test_cycle2_within_10pct_of_cycle3` (lines 174-268)**

`summary_1` (lines 194-209): 3 files changed, 1 carry-over item, 0 decisions, 1 MEDIUM open issue. `summary_2` (lines 225-247): 5 files changed, 2 carry-over items, 1 decision locked (~75 chars), 2 MEDIUM open issues. The two summaries have meaningfully different content volumes as the locked decision required. The Auditor verified empirically: ratio = 8.58% (under the 10% bound; ~14% margin to the limit). A regression injecting unbounded raw text would shift the ratio beyond 10% — the test is now genuinely discriminating. Lens-2 finding from cycle 2 is resolved.

**FIX-2 — Rename `test_cycle{2,3}_within_10pct_of_cycle1` to `test_cycle{2,3}_within_50pct_of_cycle1`**

Line 270: `def test_cycle2_within_50pct_of_cycle1`. Line 317: `def test_cycle3_within_50pct_of_cycle1`. Both bodies use `permissive_bound = 0.50` (lines 307 and 350). Both docstrings updated (lines 271-282, 318-329) to note that the strict 10% bound for cycle-1 baseline is deferred to T22's empirical telemetry. Names + bodies + docstrings agree. Lens-6 / Lens-2 finding from cycle 2 is resolved.

### Advisory regression check

**ADV-SDET-1** (no negative test for OPEN+empty-carry-over): still absent from `test_cycle_summary_emission.py` — no `test_open_verdict` function and no `pytest.raises` in scope. Advisory was marked out of scope for cycle 3; no regression, no new finding.

**ADV-SDET-2** (stale "audit M11" citation): still present at `test_cycle_summary_emission.py` lines 8, 65, 144, 217, 277, 321. Advisory was marked out of scope for cycle 3; no regression, no new finding.

**ADV-SDET-3** (nested-vs-flat path assertion granularity): assertions at `test_cycle_summary_emission.py:140-145` and peer locations unchanged from cycle 2. Advisory was marked out of scope for cycle 3; no regression, no new finding.

### 🔴 BLOCK — tests pass for the wrong reason

None. The cycle-2 BLOCK-1 tautology is partially resolved by part 1; part 2 vacuity is user-arbitrated accepted per ISS-05 locked decision — not re-raisable.

### 🟠 FIX — fix-then-ship

None. Both cycle-2 FIX findings are resolved.

### 🟡 Advisory — track but not blocking

None new. Cycle-2 advisories (ADV-SDET-1, ADV-SDET-2, ADV-SDET-3) carry forward unchanged; no regression observed.

### What passed review (one-line per lens)

- Tests-pass-for-wrong-reason: Part 1 of `test_cycle3_carries_summary_drops_prior_chat` is genuinely discriminating; part-2 vacuity is user-arbitrated ISS-05 (Path 1 accepted) — not re-raisable.
- Coverage gaps: `test_cycle2_within_10pct_of_cycle3` now uses meaningfully different content volumes; ADV-SDET-1 (OPEN+empty-carry-over negative test) deferred, out of scope for cycle 3, no regression.
- Mock overuse: None — no mocks in scope; pure Python string construction throughout.
- Fixture / independence: Unchanged from cycle 2; clean function-scoped fixtures, no cross-test state.
- Hermetic-vs-E2E gating: No network calls, no subprocess, no `AIW_E2E` gating needed or added.
- Naming / assertion-message hygiene: FIX-2 resolved — test names now agree with actual assertion bounds; ADV-SDET-2 (stale M11 citation) carries forward as advisory, out of scope for cycle 3, no regression.
