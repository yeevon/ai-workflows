# Task 04 — Cross-task iteration compaction (`iter_<N>_shipped.md` at autopilot iteration boundaries) — Audit Issues

**Source task:** [../task_04_cross_task_iteration_compaction.md](../task_04_cross_task_iteration_compaction.md)
**Audited on:** 2026-04-28
**Audit scope:** `.claude/commands/autopilot.md` (Step A read-only-latest-shipped + Step D iter-shipped emission + §Path convention), `tests/orchestrator/_helpers.py` (T04 helpers `make_iter_shipped`, `parse_iter_shipped`, `build_queue_pick_spawn_prompt`, `ITER_SHIPPED_REQUIRED_KEYS`, `ITER_SHIPPED_PROCEED_SECTIONS`), `tests/orchestrator/test_iter_shipped_emission.py` (NEW — 13 tests), `tests/orchestrator/test_cross_task_context_constant.py` (NEW — 4 tests), `tests/orchestrator/fixtures/m12_iter4_pre_t04_queue_pick_spawn_prompt.txt` (NEW — synthetic baseline), CHANGELOG, status surfaces.
**Status:** ✅ PASS

## Design-drift check

No drift detected. T04 changes are confined to `.claude/commands/autopilot.md`, `tests/orchestrator/`, `CHANGELOG.md`, and the milestone+spec markdown. Zero `ai_workflows/` touch — no new dependency, no module/layer crossing, no LLM call, no checkpoint/retry/observability code, no MCP-tool surface change, no workflow-tier rename. Layer discipline (`primitives → graph → workflows → surfaces`) untouched. None of the seven load-bearing KDRs (002/003/004/006/008/009/013) are at risk by this change. M20 milestone `Scope note` (line 5) explicitly permits `.claude/` + `CLAUDE.md` modifications at this milestone provided no `ai_workflows/` runtime change — confirmed.

## AC grading

| AC | Status | Notes |
| -- | ------ | ----- |
| 1. autopilot.md Step D writes `iter_<N>_shipped.md` per the structure above | ✅ | autopilot.md lines 173–215 (Step D #3) write `runs/autopilot-<run-timestamp>-iter<N>-shipped.md` with the canonical template (Run timestamp, Iteration, Date, Verdict from queue-pick, Task shipped, Cycles, Final commit, Files touched, Auditor verdict, Reviewer verdicts, KDR additions, Carry-over, Telemetry summary placeholder). Smoke grep `grep -qE "iter<N>-shipped\.md\|autopilot-<run-ts>-iter<N>-shipped" .claude/commands/autopilot.md` passes. |
| 2. autopilot.md Step A reads only the latest `iter_<M>_shipped.md` plus project memory; does not carry prior-iteration chat history | ✅ | autopilot.md lines 104–118 (Step A `#### Read-only-latest-shipped rule` subsection): on iter 1, no artifact; on iter N ≥ 2, ONLY the most recent `iter<N-1>-shipped.md` content + project context brief + recommendation file path. Explicit `**Do NOT** carry prior iteration chat history into this spawn` directive on line 115. |
| 3. Path naming convention `runs/autopilot-<run-ts>-iter<N>(-shipped)?.md` documented in autopilot.md per §Path convention (per L2 round-3 reword) | ✅ | autopilot.md lines 220–238 (`#### §Path convention` section): flat hyphenated form, illustrative tree, naming rule, no per-run subdirectory, no migration. Wording aligned with the L2 round-3 carry-over reword (no `runs/autopilot-<run-ts>/` subdirectory form). |
| 4. `tests/orchestrator/test_iter_shipped_emission.py` passes for the 3-iteration simulation | ✅ | 13 tests; all PASS in 0.04s. Covers: iter-1/2/3 emission, structure (required keys), verdict/SHA recorded, PROCEED sections, iter-1 unchanged after iter-2, all three coexist independently, iter-3 does NOT contain iter-1's task path (discriminating 2-part assertion: iter-3 task IS present + iter-1 task NOT present), header format, telemetry-section placeholder. |
| 5. `tests/orchestrator/test_cross_task_context_constant.py` passes — iter-5 input size within 10% of iter-1 size; iter-5 does NOT include iter-1 chat history | ⚠️ partial — see ISS-01 + ISS-02 | Tests pass (4 PASS in 0.04s). The 10% bound is applied to iter-2 vs iter-5 (both carry one artifact — structurally equivalent); iter-1 vs iter-N is bounded by a permissive 50% (documented deviation, see ISS-01). Discriminating-pattern check: Part-1 of `test_iter_5_does_not_include_iter_1_chat_history` IS discriminating (iter-4 marker IS injected via `carry_over`); Part-2 reproduces the user-arbitrated-accepted ISS-05 vacuous-phrase-never-injected pattern from T03 — see ISS-02. |
| 6. Validation re-run: re-execute fixture of M12 4-iteration autopilot run with T04's compaction; assert iter-4 orchestrator-context matches iter-1 | ⚠️ partial — see ISS-01 | `test_m12_iter4_post_t04_constant_vs_iter1` PASS — uses fixture `m12_iter4_pre_t04_queue_pick_spawn_prompt.txt` (synthetic, 192 lines representing 3 prior iteration chat transcripts pre-T04). Asserts post-T04 iter-4 within 50% of iter-1 (not the spec's 10%) AND pre-T04 fixture > 1.5× post-T04 prompt. Deviation documented; T22 baselines may revise. |
| 7. CHANGELOG.md updated under `[Unreleased]` with T04 entry | ✅ | CHANGELOG.md lines 10–78 — `### Changed — M20 Task 04: Cross-task iteration compaction (iter_<N>-shipped.md per autopilot iteration; constant cross-task orchestrator context; research brief §Lens 2.1) (2026-04-28)`. Entry covers files touched, ACs satisfied, carry-over satisfied, deviations from spec. |
| 8. Status surfaces flip together | ✅ | (a) Spec **Status:** line 3 → `✅ Done (2026-04-28)`. (b) Milestone README task table row line 109 → `✅ Done`. (c) Milestone README "Done when" exit-criterion #4 line 53 → `✅ (G1) ... [T04 Done — 2026-04-28]`. No `tasks/README.md` exists for this milestone (n/a). |
| Carry-over L3 (round 1): 10% threshold documented as heuristic | ✅ | Module docstring of `test_cross_task_context_constant.py` lines 26–43 explicitly labels the 10% bound a heuristic, cites the structural-equivalence reasoning, and notes T22 may revise. Threshold constant `_WITHIN_FRACTION = 0.10` is named (line 93). |
| Carry-over L2 (round 3): AC-3 reworded to flat-hyphenated path form per round-2 user arbitration | ✅ | Spec line 100 (AC-3) reads `Path naming convention (\`runs/autopilot-<run-ts>-iter<N>(-shipped)?.md\`) documented in autopilot.md per §Path convention.` autopilot.md `§Path convention` section content matches the reworded AC. |
| Carry-over L2 (round 4): Test descriptions use the flat hyphenated path form, not underscored shorthand | ✅ | Both new test files reference `autopilot-<run-ts>-iter<N>-shipped.md` throughout (test names + assertions + docstrings). No `iter_1_shipped.md` underscored-shorthand string appears in tests. |

## 🔴 HIGH

None.

## 🟡 MEDIUM

### M20-T04-ISS-01 — AC-5/AC-6 spec text says `within 10%`; tests use a 50% bound for iter-1 vs iter-N comparisons

**Severity:** MEDIUM — deliverable partial against literal spec text, but the deviation is explicitly documented in CHANGELOG ("Deviations from spec") and the test docstring/module docstring with sound structural rationale. Same pattern as M20-T03-ISS-04 (cycle-1 vs cycle-N comparison; user-arbitrated accepted-as-is in T03 cycle 2 commit).

**Observation.** AC-5 says "Iter 5's input-token-count ≈ iter 1's (within 10 %)" and AC-6 says "iter-4 orchestrator-context matches iter-1." Empirically, iter-1 (no prior artifact, just project brief + recommendation file path) is ~179 tokens vs iter-N≥2 (carries one iter-shipped artifact) ~304 tokens — a 70% delta on the regex-proxy. The Builder applies a tight 10% bound only to iter-2 vs iter-5 (both carry one artifact, structurally equivalent) and a permissive 50% bound to iter-1 vs iter-N. The structural rationale is sound: iter-1 has no prior-artifact payload to carry, so the comparison is structurally asymmetric. The L3 round-1 carry-over already labels the 10% threshold a heuristic awaiting T22 baselines.

**The discriminating property the AC actually wants.** Cross-task context is O(1) with respect to iteration count, not O(N). That property IS validated:
- `test_iter_2_within_10pct_of_iter_5` confirms iter-2 ≈ iter-5 at 10% (both carry one artifact — proving template bounds growth even with deliberately different content volumes).
- `test_m12_iter4_post_t04_constant_vs_iter1` confirms post-T04 iter-4 < pre-T04 iter-4 / 1.5 (compaction actually helps).
- `test_iter_5_does_not_include_iter_1_chat_history` confirms iter-1 chat content is dropped (Part 1 discriminating; Part 2 — see ISS-02).

**Action / Recommendation.** Accept-as-is and document in T22 carry-over so the empirical baseline informs the threshold. Same path as M20-T03-ISS-04 (T03 cycle-1 vs cycle-N permissive bound, user-arbitrated accepted). Forward-defer the spec-text refinement to T22 — the empirical baseline data is the natural moment to update both the spec wording and the threshold constant.

### M20-T04-ISS-02 — Part 2 of `test_iter_5_does_not_include_iter_1_chat_history` reproduces the user-arbitrated-accepted M20-T03-ISS-05 vacuous-phrase-never-injected pattern

**Severity:** MEDIUM — same pattern as M20-T03-ISS-05 which was user-arbitrated accepted-as-is in T03 cycle 3 (Path 1: discriminating Part 1 + signature-level structural guarantee + documented vacuity). The Auditor noted this risk to the Builder explicitly; the Builder reproduced the pattern with the same defensive justification.

**Observation.** Test file `tests/orchestrator/test_cross_task_context_constant.py` line 285 defines `iter1_distinctive_marker = "ITER1_DISTINCTIVE_MARKER_MUST_NOT_APPEAR_IN_ITER5"`. Per the comment on lines 291–295, the marker is **never injected** into any input passed to `build_queue_pick_spawn_prompt`. The assertion on line 341 (`assert iter1_distinctive_marker not in iter5_prompt`) is therefore vacuously true — it passes identically whether the function correctly drops prior-iteration content or admits it via some hypothetical regression. Part 1 of the same test (line 330: `assert iter4_distinctive_marker in iter5_prompt`) IS discriminating because the iter-4 marker IS injected via `carry_over` and would fail if `build_queue_pick_spawn_prompt` did not include the latest artifact.

**Why this is identical to M20-T03-ISS-05.** The T03 Builder produced the same shape: discriminating positive assertion + vacuous negative assertion + signature-level rationale ("the function's signature accepts only ONE latest artifact"). User arbitrated Path 1 (accepted-as-is) on 2026-04-28 with rationale: positive part is genuinely discriminating; structural guarantee at the function signature level is a real protection (a regression that added a multi-artifact parameter would raise `TypeError` on the test's existing call); documented acknowledgement in module + test docstring is sufficient transparency.

**T04 satisfies all three Path-1 conditions:**
1. Discriminating positive assertion — Part 1 with iter-4 marker injected.
2. Signature-level structural guarantee — `build_queue_pick_spawn_prompt` accepts only ONE `latest_iter_shipped` parameter; a regression adding multi-artifact concatenation would change the signature and surface differently.
3. Documented acknowledgement — module docstring (lines 60–64), test docstring (lines 261–280, 290–295, 336–348) all explicitly call out the single-artifact interface and the dropped-marker invariant.

**Action / Recommendation.** Accept-as-is via the same Path-1 rationale used for M20-T03-ISS-05. Explicit user concurrence is not blocking on this audit since the precedent is locked and the Builder applied the exact same defensive shape. If the user wants a stricter Path-2 pattern (a `prior_artifacts` test fixture parameter that DOES inject content the function must drop), this would need to be retroactively applied to T03 as well — surface to user only if they want to revisit.

## 🟢 LOW

### M20-T04-ISS-03 — Pre-T04 fixture is synthetic, not a real frozen pre-T04 autopilot transcript

**Severity:** LOW — the fixture is documented as a synthetic baseline; the validation re-run still demonstrates compaction (pre-T04 > 1.5× post-T04) and the iter-2-vs-iter-5 test corroborates with a different mechanism. Spec carry-over L3 (round 1) already flags T22 as the empirical-baseline owner.

**Observation.** `tests/orchestrator/fixtures/m12_iter4_pre_t04_queue_pick_spawn_prompt.txt` is a 192-line synthetic baseline constructed to represent what the pre-T04 autopilot would have assembled by carrying full chat transcripts of iters 1, 2, 3 into iter-4's queue-pick spawn. Real frozen pre-T04 transcripts of the M12 4-iteration autopilot run from 2026-04-27 (`a7f3e8f` / `fc8ef19` / `1677889`) are not used. AC-6 wording ("re-execute a fixture of the M12 4-iteration autopilot run") implies a real transcript; the synthetic fixture is a structurally faithful proxy.

**Action / Recommendation.** Forward-defer to T22 (per-cycle telemetry). T22 captures real per-cycle / per-iteration data; once T22 lands, replace the synthetic fixture with empirical pre-vs-post compaction measurements. No action on T04 — the synthetic fixture is sufficient for the structural compaction proof T04 needs to ship.

### M20-T04-ISS-04 — `tests/orchestrator/_helpers.py` module docstring header line 6 says `iter_<N>-shipped.md` (mixed underscore + hyphen) instead of pure flat hyphenated `iter<N>-shipped.md`

**Severity:** LOW — cosmetic; spec `§Path convention` is the authoritative path form and matches the test code (`autopilot-<run-ts>-iter<N>-shipped.md`). Only the module docstring header line uses the mixed `iter_<N>-shipped.md` form.

**Observation.** Line 5 of the module docstring (`Task: M20 Task 04 — Cross-task iteration compaction (iter_<N>-shipped.md at autopilot`) and the same form used in CHANGELOG entry header line 10 / spec title line 1 carry the underscored-N + hyphen-shipped form. The actual filenames in code use the pure flat-hyphenated `autopilot-<run-ts>-iter<N>-shipped.md` form (verified). The L2 round-4 carry-over is satisfied for test descriptions, but the docstring header variant is a leftover.

**Action / Recommendation.** Forward-defer to next M20 doc-touch task or address opportunistically in T28 (which references T04's iter-shipped artifacts). No T04-cycle action needed.

## Additions beyond spec — audited and justified

- `_stub_emit_iter_shipped` private test helper in `test_iter_shipped_emission.py` (line 65) — wraps `make_iter_shipped` + file write; reduces 13-test boilerplate. Justified — strictly test infrastructure, no production-code coupling.
- `ITER_SHIPPED_PROCEED_SECTIONS` constant in `_helpers.py` (line 607) covers the three section-header strings tested in `test_iter_1_shipped_has_proceed_sections`. Justified — same shape as `CYCLE_SUMMARY_REQUIRED_KEYS` introduced in T03; consistency with T03 helpers.
- `_build_iter_shipped` helper at module level in `test_cross_task_context_constant.py` (line 112) wraps `make_iter_shipped` with `_ITER_TASKS` defaults; pure test-fixture convenience.
- The CHANGELOG entry includes a "Deviations from spec" subsection (lines 72–78) — additions beyond standard CHANGELOG shape but consistent with T03's same-shape entry. Justified — explicit transparency on the iter-1-vs-iter-N permissive bound.

No additions touch `ai_workflows/`. No new dependency. No coupling-introducing module-level state.

## Gate summary

| Gate | Command | Result |
| ---- | ------- | ------ |
| pytest (full) | `AIW_BRANCH=design uv run pytest` | PASS (1 pre-existing flake, unrelated — see note) |
| pytest (T04-targeted) | `AIW_BRANCH=design uv run pytest tests/orchestrator/test_iter_shipped_emission.py tests/orchestrator/test_cross_task_context_constant.py -v` | PASS (17/17 in 0.04s) |
| lint-imports | `uv run lint-imports` | PASS (5/5 contracts kept) |
| ruff check | `uv run ruff check` | PASS (all checks passed) |
| Smoke grep — autopilot emit | `grep -qE "iter<N>-shipped\.md\|autopilot-<run-ts>-iter<N>-shipped" .claude/commands/autopilot.md` | PASS |
| Smoke grep — autopilot read | `grep -qE "iter<N>-shipped\|autopilot-<run-ts>-iter<N>-shipped" .claude/commands/autopilot.md` | PASS |

**Pre-existing flake note.** `tests/mcp/test_cancel_run_inflight.py::test_cancel_run_aborts_in_flight_task_and_flips_storage` failed in the full pytest run (1 of 1018) with `ToolError: no run found: run-inflight-cancel`. The test PASSES on isolated re-run (`pytest tests/mcp/test_cancel_run_inflight.py::test_cancel_run_aborts_in_flight_task_and_flips_storage` → 1 passed). Last touched in M6 close-out (commit `c280b93`); zero relationship to T04 (T04 changes are in `.claude/` + `tests/orchestrator/`). Treated as ordering/environment flake unrelated to this audit. **Action: forward-defer to a flake-tracking carry-over** if the same test recurs in subsequent audits; not blocking T04.

## Issue log — cross-task follow-up

| ID | Severity | Owner / next touch point | Status history |
| -- | -------- | ------------------------ | -------------- |
| M20-T04-ISS-01 | MEDIUM | T22 (per-cycle telemetry — empirical baseline data informs threshold revision) | OPEN — accepted-as-is on this audit per same Path 1 used for M20-T03-ISS-04; deferred to T22 |
| M20-T04-ISS-02 | MEDIUM | accepted-as-is per locked precedent (M20-T03-ISS-05 user-arbitrated 2026-04-28 Path 1) | OPEN — documented acceptance; same shape as T03 ISS-05 |
| M20-T04-ISS-03 | LOW | T22 (per-cycle telemetry — replace synthetic fixture with empirical data) | OPEN — deferred |
| M20-T04-ISS-04 | LOW | Opportunistic on next M20 doc-touch task or T28 | OPEN — cosmetic, deferred |

## Deferred to nice_to_have

None for T04. ISS-01 and ISS-03 forward-defer to T22 (a real spec'd task); ISS-02 is accepted-as-is per locked precedent; ISS-04 is opportunistic.

## Propagation status

No M20-T04 finding propagates to a non-existent task. Both deferrals (ISS-01 + ISS-03) target T22 — a spec'd-but-not-yet-implemented task in M20 Phase C. Per `clean-tasks` convention, T22's spec is generated when M20 reaches Phase C; the carry-over will be added to that spec at generation time. No active spec to amend now.

If the user prefers explicit carry-over wiring before T22 spec generation: add to milestone README "Carry-over from prior milestones" section. **Recommendation:** defer until T22 spec is generated — adding a free-floating carry-over note at the milestone README level introduces drift between the README's current "None at draft time" wording and the new entry. Surface to user if a different preference applies.

## Security review (2026-04-28)

### 🔴 Critical — must fix before publish/ship

None.

### 🟠 High — should fix before publish/ship

None.

### 🟡 Advisory — track; not blocking

**ADV-01 — Wheel contents: T04 files (`.claude/`, `tests/`) correctly excluded; `migrations/` present by design.**

Threat-model item: 1 (wheel-contents leakage).

The existing 0.3.1 wheel (`dist/jmdl_ai_workflows-0.3.1-py3-none-any.whl`) was inspected. T04 touches only `.claude/commands/autopilot.md` and `tests/orchestrator/` — neither directory is included in the wheel. Wheel contents: `ai_workflows/`, `migrations/`, `jmdl_ai_workflows-0.3.1.dist-info/`. The `migrations/` inclusion is intentional (runtime schema files); no `.env*`, `design_docs/`, `runs/`, `*.sqlite3`, `htmlcov/`, `.coverage`, `.pytest_cache/`, `.claude/`, `evals/`, or `.github/` entries observed.

No `.env`-shape leakage in `README.md` long description from T04 changes. No T04 action required.

**ADV-02 — iter-shipped artifact template does not define a field encouraging credential storage.**

Threat-model item: 3 (credential leakage in iter-shipped artifact structure).

The `make_iter_shipped` helper in `tests/orchestrator/_helpers.py` (lines 614–724) renders the canonical template from `autopilot.md` Step D. Fields are: run timestamp, iteration, date, verdict, task spec filename, cycle count, commit SHA, files touched list, auditor/reviewer verdicts, KDR additions flag, carry-over text, telemetry placeholder. None of these fields are defined to hold key values, OAuth tokens, or API keys. The `carry_over` free-text field accepts arbitrary strings — if a real autopilot run populated it with a log line that contained a key value, the artifact would capture it. This is the same risk class as any log field; no mitigation is added here because the orchestrator itself produces the carry-over content from locked-decision stamps, not from raw environment variables. Advisory only; no T04 action.

**ADV-03 — Path naming convention sourced from orchestrator-controlled values; no user-attacker-controlled traversal.**

Threat-model item: 4 (path injection via iter-shipped filename).

`autopilot.md` Step D names the artifact `runs/autopilot-<run-timestamp>-iter<N>-shipped.md`. Both `<run-timestamp>` (pre-flight timestamp, assembled by the orchestrator from `date -u`) and `<N>` (a monotone integer) are orchestrator-owned values, not user or external-agent input. The `runs/` directory is the flat gitignored local scratch space. No traversal vector identified. No T04 action.

**ADV-04 — Synthetic fixture contains no real credentials or `.env` values.**

Threat-model item: 3 (credential leakage via fixture).

`tests/orchestrator/fixtures/m12_iter4_pre_t04_queue_pick_spawn_prompt.txt` was inspected. It is a 192-line synthetic pre-T04 autopilot transcript simulation. Grep for `PYPI_TOKEN`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `gsk_`, `sk-`, `AIzaSy`, `Bearer`, `Authorization` all returned zero hits. Commit SHAs present are synthetic hex strings (`a1b2c3d4e5f6...`), not real repo SHAs. No action required.

### Verdict: SHIP

## Dependency audit (2026-04-28)

Dependency audit: skipped — no manifest changes. `git diff --name-only HEAD` shows neither `pyproject.toml` nor `uv.lock` was modified by T04.

## Sr. Dev review (2026-04-28)

**Files reviewed:**
- `.claude/commands/autopilot.md` — Step A read-only-latest-shipped rule, Step D iter-shipped emission, §Path convention
- `tests/orchestrator/_helpers.py` — `make_iter_shipped`, `parse_iter_shipped`, `build_queue_pick_spawn_prompt`, `ITER_SHIPPED_REQUIRED_KEYS`, `ITER_SHIPPED_PROCEED_SECTIONS`
- `tests/orchestrator/test_iter_shipped_emission.py` — 13-test 3-iteration simulation
- `tests/orchestrator/test_cross_task_context_constant.py` — 4-test cross-task context constancy
- `tests/orchestrator/fixtures/m12_iter4_pre_t04_queue_pick_spawn_prompt.txt` — synthetic baseline

**Skipped (out of scope):** None — T04 touched no `ai_workflows/` runtime code; all changes in `.claude/`, `tests/orchestrator/`, `CHANGELOG.md`, milestone markdown.

**Verdict:** SHIP

### 🔴 BLOCK — must-fix before commit

None.

### 🟠 FIX — fix-then-ship

None.

### 🟡 Advisory — track but not blocking

**ADV-SR-01 — `build_queue_pick_spawn_prompt` (N ≥ 2) omits `milestone_scope` as a discrete field; `build_roadmap_selector_spawn_prompt` (N == 1) includes it as a top-level line.**

`tests/orchestrator/_helpers.py:379` (`build_roadmap_selector_spawn_prompt`) emits `f"Milestone scope: {milestone_scope}\n"` as the second line of the prompt. `tests/orchestrator/_helpers.py:774` (`build_queue_pick_spawn_prompt`) has no `milestone_scope` parameter; the scope is expected to arrive embedded in `project_context_brief`. In the test constant `_PROJECT_CONTEXT_BRIEF` (line 73), the milestone scope appears as a template placeholder string `Milestone scope: <from $ARGUMENTS, or "all open">`, not the actual runtime value. In production the orchestrator embeds the real scope in the brief it passes to both functions, so no runtime bug exists. However, the asymmetry means a future caller of `build_queue_pick_spawn_prompt` could pass a context brief that omits the scope field and the test would still pass — the N ≥ 2 helper provides no reminder that scope must be present. Lens: idiom alignment / simplification.
Action: When T22 or a future M20 task touches these helpers, consider adding `milestone_scope: str` to `build_queue_pick_spawn_prompt` so both iter-1 and iter-N helpers have the same signature shape. Not blocking — the production autopilot.md Step A instructs the orchestrator to include the milestone list in the context brief on every iteration.

**ADV-SR-02 — `test_iter_1_shipped_unchanged_after_iter_2` uses `st_mtime` equality as an independence check; `read_text()` equality is the real guard.**

`tests/orchestrator/test_iter_shipped_emission.py:309` asserts both content equality (`read_text() == original_text`) and mtime equality (`st_mtime == original_mtime`). On filesystems with 1-second mtime granularity (e.g. ext3, some CI tmpfs mounts), both writes can land in the same second, making the mtime assertion vacuously true regardless of whether a write occurred. The `read_text()` assertion is the actually discriminating check. Lens: hidden bugs that pass tests.
Action: Remove the `st_mtime` assertion or gate it with a note. The content-equality check alone is sufficient and unambiguous. Low-urgency — the content equality is already present and correct.

**ADV-SR-03 — `<run-timestamp>` and `<run-ts>` are used interchangeably for the same placeholder within `autopilot.md` across lines 23, 41, 113, 129, 176 vs. 233–236.**

The §Path convention section (line 233) uses `<run-ts>`, defining it as "the pre-flight timestamp." Lines 23, 41, 113, 129, 176, and 270 use `<run-timestamp>`. Both refer to the same value. The §Path convention was introduced by T04 (adding the `<run-ts>` shorthand) without normalising the existing `<run-timestamp>` references. Lens: comment / docstring drift.
Action: Opportunistic cleanup — normalise to one form (either is fine; `<run-ts>` is more compact) when autopilot.md is next touched. Not blocking.

### What passed review (one-line per lens)

- Hidden bugs: `st_mtime` check in test_iter_1_shipped_unchanged_after_iter_2 is weaker than it looks (see ADV-SR-02); no production-code bug found.
- Defensive-code creep: none observed — no defensive shims or impossible-scenario guards introduced.
- Idiom alignment: T04 helpers follow the same shape as T03's `CYCLE_SUMMARY_REQUIRED_KEYS` / `make_cycle_summary` / `parse_cycle_summary` — clean reuse; minor signature asymmetry noted (ADV-SR-01).
- Premature abstraction: none — `_stub_emit_iter_shipped` and `_build_iter_shipped` are private test helpers with multiple callers within their own files; `ITER_SHIPPED_PROCEED_SECTIONS` mirrors `CYCLE_SUMMARY_REQUIRED_KEYS` exactly as the Auditor justified.
- Comment / docstring drift: `<run-timestamp>` vs `<run-ts>` inconsistency across autopilot.md sections (ADV-SR-03); module docstring header uses mixed `iter_<N>-shipped.md` form (already ISS-04 in Auditor log).
- Simplification: none warranted — helpers are appropriately lean; no two-line delegation chains or single-field dataclasses observed.

## Sr. SDET review (2026-04-28)

**Test files reviewed:**
- `tests/orchestrator/_helpers.py` — T04 extensions: `make_iter_shipped`, `parse_iter_shipped`, `build_queue_pick_spawn_prompt`, `ITER_SHIPPED_REQUIRED_KEYS`, `ITER_SHIPPED_PROCEED_SECTIONS`
- `tests/orchestrator/test_iter_shipped_emission.py` — NEW; 13 tests
- `tests/orchestrator/test_cross_task_context_constant.py` — NEW; 4 tests
- `tests/orchestrator/fixtures/m12_iter4_pre_t04_queue_pick_spawn_prompt.txt` — NEW; synthetic baseline

**Skipped (out of scope):** None — all files are within the T04-defined test scope.

**Verdict:** FIX-THEN-SHIP

### 🔴 BLOCK — tests pass for the wrong reason

None.

### 🟠 FIX — fix-then-ship

**FIX-SDET-01 — `make_iter_shipped` `NEEDS-CLEAN-TASKS` and `HALT-AND-ASK` verdict branches are not exercised by any test; a regression to either section would be undetected.**

Lens: Coverage gap (Lens 2).

`tests/orchestrator/_helpers.py:614` (`make_iter_shipped`) has three verdict branches: `PROCEED` (lines 674–692), `NEEDS-CLEAN-TASKS` (lines 694–703), and `HALT-AND-ASK` (lines 705–714). Every call in `test_iter_shipped_emission.py` uses `verdict="PROCEED"` (lines 149, 166, 189, 207, 260, 270, 299, 324, 334, 376, 415, 428, 434, 469, 489 — all via `_stub_emit_iter_shipped` which defaults to PROCEED or receives it explicitly). The cross-task context test also exclusively uses `verdict="PROCEED"` (via `_build_iter_shipped` and the direct `make_iter_shipped` call in `test_iter_5_does_not_include_iter_1_chat_history` at line 298).

The spec template (task_04 lines 32–41) defines both alternative sections as required structure for their respective verdicts. `ITER_SHIPPED_PROCEED_SECTIONS` (tested in `test_iter_1_shipped_has_proceed_sections`) is the only verdict-specific section constant; no equivalent constant or test covers `## Milestone work (if NEEDS-CLEAN-TASKS)` or `## Halt (if HALT-AND-ASK)`. A regression that silently dropped the `NEEDS-CLEAN-TASKS` branch body (e.g. a stray `elif` removal in `make_iter_shipped`) would produce an artifact that still parses the four `ITER_SHIPPED_REQUIRED_KEYS` correctly (those keys are emitted unconditionally in lines 665–671) and would pass all 13 emission tests and all 4 context-constancy tests.

Action: Add two tests to `test_iter_shipped_emission.py`:
1. `test_iter_shipped_needs_clean_tasks_structure` — call `_stub_emit_iter_shipped` (or `make_iter_shipped` directly) with `verdict="NEEDS-CLEAN-TASKS"`, read the artifact text, assert `"## Milestone work (if NEEDS-CLEAN-TASKS)"` is in text and that a `clean_tasks_milestone` value appears in the body.
2. `test_iter_shipped_halt_and_ask_structure` — call `make_iter_shipped` with `verdict="HALT-AND-ASK"` and a `halt_reason`, assert `"## Halt (if HALT-AND-ASK)"` is in text and the halt reason string appears.

Both tests are hermetic (pure string construction + assertion), consistent with the existing pattern, and would catch the unexercised branches.

### 🟡 Advisory — track but not blocking

**ADV-SDET-01 — `test_iter_1_prompt_is_baseline` (line 175) asserts only `count > 50`; the test name implies a baseline measurement but the assertion is a weak sanity check.**

Lens: Naming / assertion-message hygiene (Lens 6).

`tests/orchestrator/test_cross_task_context_constant.py:175` — the test name `test_iter_1_prompt_is_baseline` implies it's anchoring a measurable baseline. The body only checks `count > 50`, which passes for any non-trivial string. If the project context brief were accidentally truncated to a few words (e.g. by a caller passing an empty brief), the test would still pass as long as the result is longer than ~38 characters. The test is documented as a "sanity check" in its docstring (line 185), so the intent is clear — but the name overpromises.
Action: Consider renaming to `test_iter_1_prompt_is_non_trivially_sized` or adding a realistic lower bound (e.g. `> 100`) with an assertion message. Advisory — no impact on correctness of the other tests.

**ADV-SDET-02 — `test_iter_3_shipped_does_not_contain_iter_1_task` Part 2 (line 454) shares the ISS-02 structural vacuity shape for the emission-test context.**

Lens: Tests pass for wrong reason (Lens 1) — but the pattern is the same user-arbitrated ISS-02 precedent.

`tests/orchestrator/test_iter_shipped_emission.py:454` asserts `iter1_task_marker not in iter3_text`. `iter3_text` is produced by `_stub_emit_iter_shipped(iteration=3, task_shipped=iter3_task_marker)`. The function `make_iter_shipped` only renders its own `task_shipped` argument in the output; it has no accumulation mechanism. The negative assertion is structurally guaranteed to pass regardless of whether any future caller were to add an accumulation path in `make_iter_shipped`. Part 1 (line 447) is genuinely discriminating. This is the emission-test analogue of ISS-02 (the cross-task context test). The same Path-1 rationale applies: (1) discriminating positive assertion present; (2) signature-level structural guarantee (the function has one `task_shipped` parameter, not a list); (3) the test's own docstring notes the per-iteration independence property. Treat as accepted-as-is per the ISS-02 precedent.
Action: No action required. Noted for completeness.

### What passed review (one-line per lens)

- Tests-pass-for-wrong-reason: no BLOCK-level case found; Part-2 negative assertions in both test files share the user-arbitrated ISS-02 vacuous-phrase pattern (structural guarantee accepted per locked precedent); noted as ADV-SDET-02.
- Coverage gaps: `NEEDS-CLEAN-TASKS` and `HALT-AND-ASK` verdict branches of `make_iter_shipped` unexercised — FIX-SDET-01 above.
- Mock overuse: none — tests use real `make_iter_shipped` / `parse_iter_shipped` / `build_queue_pick_spawn_prompt` helpers (no mocks); file I/O uses real `tmp_path`.
- Fixture / independence: `runs_dir` fixture correctly scoped to method via `tmp_path`; no module-level state mutation; tests are order-independent.
- Hermetic-vs-E2E gating: fully hermetic — no network calls, no subprocess, no `AIW_E2E` skip needed; correct for the orchestrator-simulation scope.
- Naming / assertion-message hygiene: names are largely descriptive; `test_iter_1_prompt_is_baseline` overpromises vs. a `> 50` check (ADV-SDET-01); assertion messages throughout are helpful and debuggable.

## Locked team decisions (cycle 1 → cycle 2 carry-over)

Per `/auto-implement` Step T4 #2 (auditor-agreement bypass on FIX-THEN-SHIP). One FIX with single clear recommendation; loop-controller concurs against KDRs + spec; no scope expansion or future-task deferral.

- **Locked team decision (loop-controller + sr-sdet concur, 2026-04-28)** — FIX-SDET-01: Add two hermetic tests to `tests/orchestrator/test_iter_shipped_emission.py` covering the unexercised `make_iter_shipped` verdict branches:
  1. `test_iter_shipped_needs_clean_tasks_structure` — call `make_iter_shipped` with `verdict="NEEDS-CLEAN-TASKS"` + a `clean_tasks_milestone` value; assert the artifact text contains `"## Milestone work (if NEEDS-CLEAN-TASKS)"` and the milestone string appears in the body.
  2. `test_iter_shipped_halt_and_ask_structure` — call `make_iter_shipped` with `verdict="HALT-AND-ASK"` + a `halt_reason`; assert the artifact text contains `"## Halt (if HALT-AND-ASK)"` and the halt reason string appears.

  Both are pure string-construction tests; consistent with the existing 13-test pattern; would catch a regression that silently dropped either alternative-verdict branch.

Advisories (ADV-SR-01, -02, -03 from sr-dev; ADV-SDET-01, -02 from sr-sdet) are not in cycle-2 carry-over — tracked for future follow-up. The 2 MEDIUMs (ISS-01, ISS-02) remain user-arbitrated-precedent acceptance per T03 ISS-04 / ISS-05; no further action.

## Cycle 2 audit (2026-04-28)

**Verdict:** ✅ PASS — locked-team-decision FIX-SDET-01 satisfied; no scope creep; gates green.

**Scope of cycle-2 review:** `tests/orchestrator/test_iter_shipped_emission.py` — two new tests added:

1. `test_iter_shipped_needs_clean_tasks_structure` (line 508) — calls `make_iter_shipped` with `verdict="NEEDS-CLEAN-TASKS"` + `clean_tasks_milestone="milestone_15_mcp_surface"`; asserts `"## Milestone work (if NEEDS-CLEAN-TASKS)"` section header AND the milestone string both appear in the body.
2. `test_iter_shipped_halt_and_ask_structure` (line 538) — calls `make_iter_shipped` with `verdict="HALT-AND-ASK"` + a `halt_reason`; asserts `"## Halt (if HALT-AND-ASK)"` section header AND the halt reason string both appear in the body.

Both tests are pure string-construction (no file I/O), hermetic, and consistent with the existing 13-test pattern. Test class membership preserved (added under `TestIterShippedEmission`).

**Discrimination verification (Auditor-run regression injection).**

The Auditor independently verified each new test would catch a regression in its target branch:

1. Replaced `elif verdict == "NEEDS-CLEAN-TASKS":` (line 694 of `_helpers.py`) with `elif False:`. Result: `test_iter_shipped_needs_clean_tasks_structure` FAILS with `AssertionError: NEEDS-CLEAN-TASKS artifact must contain '## Milestone work (if NEEDS-CLEAN-TASKS)' section header.` All 14 other tests still pass — proving the regression is silent without these tests. Restored.
2. Replaced `elif verdict == "HALT-AND-ASK":` (line 704 of `_helpers.py`) with `elif False:`. Result: `test_iter_shipped_halt_and_ask_structure` FAILS with `AssertionError: HALT-AND-ASK artifact must contain '## Halt (if HALT-AND-ASK)' section header.` All 14 other tests still pass. Restored.

Both tests are genuinely discriminating against the target regression class FIX-SDET-01 was raised against. The locked team decision is fully satisfied.

**Scope discipline.** Cycle 2 modified ONLY `tests/orchestrator/test_iter_shipped_emission.py`. No other source / spec / `_helpers.py` / CHANGELOG / autopilot.md changes. Verified via `git status --short` and `git diff --stat HEAD`. No scope creep.

**Cycle-1 ACs re-verified.** AC-1 through AC-8 + carry-over L3 / L2-r3 / L2-r4 still PASS as graded in the cycle-1 audit table above (status surfaces unchanged, all spec-required helpers + tests + autopilot.md edits + CHANGELOG entry + path convention all intact).

**Cycle-2 gate summary.**

| Gate | Command | Result |
| ---- | ------- | ------ |
| pytest (T04 emission tests) | `AIW_BRANCH=design uv run pytest tests/orchestrator/test_iter_shipped_emission.py -v` | PASS (15/15 in 0.03s — was 13, now 13 + 2 new) |
| pytest (full orchestrator dir) | `AIW_BRANCH=design uv run pytest tests/orchestrator/` | PASS (82/82 in 0.10s) |
| pytest (full repo) | `AIW_BRANCH=design uv run pytest` | PASS (1021 passed, 7 skipped, 22 warnings — 46.01s) |
| lint-imports | `uv run lint-imports` | PASS (5/5 contracts kept) |
| ruff check | `uv run ruff check` | PASS (all checks passed) |
| Discriminating-property check (NEEDS-CLEAN-TASKS) | manual regression injection on `_helpers.py:694` | New test FAILS → discriminating |
| Discriminating-property check (HALT-AND-ASK) | manual regression injection on `_helpers.py:704` | New test FAILS → discriminating |

**Pre-existing flake.** The cycle-1 flake `tests/mcp/test_cancel_run_inflight.py::test_cancel_run_aborts_in_flight_task_and_flips_storage` did NOT recur in this cycle's full pytest run (1021/1021 passed without that failure). Confirms it as an environment / ordering flake unrelated to T04.

**Open MEDIUMs unchanged.** ISS-01 (10% threshold deferral to T22) and ISS-02 (Path-1 vacuous-phrase precedent) remain accepted-as-is per cycle-1 disposition; no cycle-2 action.

**Open LOWs unchanged.** ISS-03 (synthetic fixture deferred to T22) and ISS-04 (`iter_<N>-shipped.md` mixed underscore-hyphen docstring header) unchanged; opportunistic / forward-deferred.

**Overall verdict:** ✅ PASS. Cycle 2 satisfies the locked team decision with no scope creep and all gates green. Ready for autopilot orchestrator commit + push to `workflow_optimization` branch (user-approved override of `design_branch` per session brief).

## Security review — cycle 2 re-check (2026-04-28)

**Scope:** Incremental re-check of two tests added in cycle 2 (`tests/orchestrator/test_iter_shipped_emission.py` lines 508–566 — `test_iter_shipped_needs_clean_tasks_structure` and `test_iter_shipped_halt_and_ask_structure`). Cycle-1 section preserved verbatim above.

### 🔴 Critical — must fix before publish/ship

None.

### 🟠 High — should fix before publish/ship

None.

### 🟡 Advisory — track; not blocking

None. All three cycle-2 check items are clean:

1. **Wheel-contents leakage (threat-model item 1).** Both new tests live in `tests/orchestrator/`, which is excluded from the wheel per existing build configuration (confirmed cycle-1 ADV-01). No new file added outside `tests/`. No `pyproject.toml` or build-config change. Wheel-contents status unchanged.

2. **No new credentials / subprocess / env-var reads (threat-model items 2, 6).** Both tests are pure in-memory calls to `make_iter_shipped` — no `subprocess`, no `os.environ`, no `shell=True`, no fixed-path file I/O, no API-key reads. The helper was already reviewed in cycle 1 with zero subprocess or credential surface.

3. **Test inputs are placeholder-only (threat-model item 1 / logging hygiene).** `clean_tasks_milestone="milestone_15_mcp_surface"` (fixture name), `halt_reason="Architect returned two options without a recommendation."` (plain prose), `run_timestamp="20260427T152243Z"` (synthetic, cycle-1 reviewed), `date="2026-04-28"` (fixture date). Grep for `PYPI_TOKEN`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `gsk_`, `sk-`, `AIzaSy`, `Bearer`, `Authorization` in the two new tests: zero hits.

### Verdict: SHIP

## Sr. Dev review — cycle 2 re-check (2026-04-28)

**Files reviewed:**
- `tests/orchestrator/test_iter_shipped_emission.py` — two new tests added for `NEEDS-CLEAN-TASKS` and `HALT-AND-ASK` verdict branches (lines 508–566)

**Skipped (out of scope):** All source / agent / command files — cycle 2 is test-only per locked team decision FIX-SDET-01; no `.claude/`, `ai_workflows/`, or `_helpers.py` changes in cycle 2.

**Verdict:** SHIP

### 🔴 BLOCK — must-fix before commit

None.

### 🟠 FIX — fix-then-ship

None.

### 🟡 Advisory — track but not blocking

None new. Cycle-1 advisories (ADV-SR-01, -02, -03) unchanged and tracked for future M20 tasks.

### What passed review (one-line per lens)

- Hidden bugs: none — both tests call `make_iter_shipped` with no file I/O; optional parameters have safe defaults; no off-by-one or silent-catch risk introduced.
- Defensive-code creep: none — no new guards or shims; tests are minimal string-construction assertions.
- Idiom alignment: both tests match the existing `TestIterShippedEmission` pattern exactly (no `runs_dir` fixture needed since these exercise the return value directly, consistent with the function's in-memory return path).
- Premature abstraction: none — no new helpers; tests inline their inputs.
- Comment / docstring drift: docstrings accurately describe the branch under test and cite the `_helpers.py` line range; no restatement of obvious code.
- Simplification: no opportunities — tests are already at minimum viable assertion count (two assertions each: section header + payload string).

## Sr. SDET review — cycle 2 re-check (2026-04-28)

**Test files reviewed:**
- `tests/orchestrator/test_iter_shipped_emission.py` — two new tests (lines 508–566): `test_iter_shipped_needs_clean_tasks_structure`, `test_iter_shipped_halt_and_ask_structure`
- `tests/orchestrator/_helpers.py` — `make_iter_shipped` verdict branches (lines 694–714) as the code under test

**Skipped (out of scope):** `test_cross_task_context_constant.py` — not touched in cycle 2; cycle-1 verdict unchanged.

**Verdict:** SHIP

### 🔴 BLOCK — tests pass for the wrong reason

None.

### 🟠 FIX — fix-then-ship

None. FIX-SDET-01 is fully satisfied.

### 🟡 Advisory — track but not blocking

None new. ADV-SDET-01 and ADV-SDET-02 from cycle 1 remain open and tracked; they were not addressed in cycle 2 per the locked-team-decision carry-over (advisories explicitly excluded from cycle-2 scope). No additional advisory raised.

### Discrimination verification (Sr. SDET independent read)

**`test_iter_shipped_needs_clean_tasks_structure` (line 508).**
Calls `make_iter_shipped` directly with `verdict="NEEDS-CLEAN-TASKS"` and `clean_tasks_milestone="milestone_15_mcp_surface"`. Asserts two things: (1) `"## Milestone work (if NEEDS-CLEAN-TASKS)"` appears in the output — this string is emitted solely by the `elif verdict == "NEEDS-CLEAN-TASKS":` branch at `_helpers.py:696`; (2) the milestone string itself appears — emitted at `_helpers.py:697` via `f"- **Milestone:** {clean_tasks_milestone or 'unknown'}"`. Both assertions would fail if the branch were dropped or muted. The Auditor's regression injection (`elif False:`) corroborates. Genuinely discriminating.

**`test_iter_shipped_halt_and_ask_structure` (line 538).**
Calls `make_iter_shipped` with `verdict="HALT-AND-ASK"` and `halt_reason="Architect returned two options without a recommendation."`. Asserts: (1) `"## Halt (if HALT-AND-ASK)"` in text — emitted at `_helpers.py:706`; (2) the halt reason string in text — emitted at `_helpers.py:707` via `f"- **Halt reason:** {halt_reason or 'unspecified'}"`. Both would fail on branch removal or muting. Genuinely discriminating.

**Fixture and independence.** Both new tests are bare methods (no `runs_dir` fixture) operating purely on the in-memory string returned by `make_iter_shipped`. This is intentional and correct; the docstrings state "No file I/O needed." No order dependence, no shared mutable state. The test class method pattern is consistent with the existing 13-test suite.

**Input leak risk.** `milestone = "milestone_15_mcp_surface"` is a spec fixture name, not a credential. `halt_reason` is plain prose. `_RUN_TIMESTAMP = "20260427T152243Z"` is the same synthetic constant reviewed in cycle 1 (security cycle 2 ADV verified zero credential strings). No leak risk.

**Cycle-1 advisories still tracked.** ADV-SDET-01 (`test_iter_1_prompt_is_baseline` overpromising name / weak `> 50` bound) and ADV-SDET-02 (emission-test `iter1_task_marker not in iter3_text` structural vacuity, ISS-02 precedent) remain in the cycle-1 Sr. SDET section unchanged. The locked-team-decision block (lines 269–279) explicitly excludes advisories from cycle-2 carry-over. Both are visible in the open issue log; no re-raise warranted.

### What passed review (one-line per lens)

- Tests-pass-for-wrong-reason: both new tests are genuinely discriminating against the regression class FIX-SDET-01 was raised for; no case identified where a test would pass while the target code is wrong.
- Coverage gaps: FIX-SDET-01 (NEEDS-CLEAN-TASKS and HALT-AND-ASK branches unexercised) is now closed; no new gap identified within cycle-2 scope.
- Mock overuse: none — both tests call the real `make_iter_shipped` helper with no mocks; the function is pure string construction with no external dependencies to mock.
- Fixture / independence: tests are bare methods with no fixture dependency; pure in-memory; order-independent; consistent with the existing class pattern.
- Hermetic-vs-E2E gating: fully hermetic — no network, no subprocess, no env-var gate needed; no `AIW_E2E=1` skip required or omitted.
- Naming / assertion-message hygiene: test names accurately describe the verdict branch under test; assertion messages include the expected string and context sufficient for debugging on failure.
