# Task 22 — Per-cycle token telemetry per agent — Audit Issues

**Source task:** [../task_22_per_cycle_telemetry.md](../task_22_per_cycle_telemetry.md)
**Audited on:** 2026-04-28
**Audit scope:** cycle 1 — `scripts/orchestration/{telemetry.py, check_task_response_fields.py}`, `tests/orchestrator/test_telemetry_{record,aggregation}.py`, 5 spawning slash commands, retrofit of 3 iter-shipped artifacts, milestone README + spec status surfaces, CHANGELOG.
**Status:** ✅ PASS

---

## Design-drift check (Phase 1 — mandatory)

| Check | Result | Notes |
| --- | --- | --- |
| KDR-003 — zero `anthropic` SDK imports | ✅ Clean | `grep -nE "anthropic\|ANTHROPIC_API_KEY" scripts/orchestration/*.py tests/orchestrator/test_telemetry_*.py` → 0 hits. |
| KDR-003 — zero `ANTHROPIC_API_KEY` reads | ✅ Clean | No env-var reads of any kind; CLI args only. |
| Four-layer rule | N/A by design | T22 lives under `scripts/orchestration/`, **outside** `ai_workflows/`. M20 README §Scope-note explicitly preserves the runtime-vs-orchestration-infra boundary. `lint-imports` re-run unaffected (5/5 contracts KEPT). |
| `pyproject.toml` / `uv.lock` untouched | ✅ Clean | `git diff HEAD -- pyproject.toml uv.lock` empty. Stdlib-only (`argparse`, `json`, `tempfile`, `datetime`, `pathlib`). No dep-auditor invocation needed. |
| KDR-008 (MCP tool surface) | N/A | T22 ships no MCP tool. |
| KDR-009 (LangGraph SqliteSaver checkpointing) | N/A | T22 records are telemetry-side artifacts, not LangGraph checkpoints. |
| KDR-013 (user code is user-owned) | N/A | T22 captures orchestration-side spawn metadata, not user-workflow internals. |

**No drift detected.**

---

## Phase 2 — Gate re-run (from scratch)

| Gate | Command | Result |
| --- | --- | --- |
| pytest (full) | `AIW_BRANCH=design uv run pytest -q` | **1089 passed, 7 skipped** in 43.48s |
| pytest (T22 targeted) | `AIW_BRANCH=design uv run pytest tests/orchestrator/test_telemetry_record.py tests/orchestrator/test_telemetry_aggregation.py -v` | **28 passed** in 0.10s |
| lint-imports | `uv run lint-imports` | 5 contracts KEPT, 0 broken |
| ruff | `uv run ruff check` | All checks passed |
| Spec smoke test (lines 134–155) | `mkdir → spawn → complete → assert` | **SMOKE-OK** — record lands; fields verified; no `quota_consumption_proxy` field |

Builder's reported gate results match the auditor's re-run.

---

## Phase 3 — AC grading

| AC | Status | Notes |
| --- | --- | --- |
| 1 — `telemetry.py` exists with `spawn` + `complete` subcommands | ✅ Met | `argparse` with `add_subparsers(required=True)`; both subcommands have full required-arg gating verified by tests. |
| 2 — Per-cycle JSON records include all 14 captured fields | ✅ Met | `cmd_spawn` writes the full schema with completion fields nulled; `cmd_complete` merges (does NOT overwrite spawn fields — verified by `test_complete_preserves_spawn_fields`). |
| 3 — 5 spawning slash commands describe the convention | ✅ Met | Confirmed in `auto-implement.md`, `autopilot.md`, `clean-implement.md`, `clean-tasks.md`, `queue-pick.md`. Each has a callable `python scripts/orchestration/telemetry.py spawn …` block tied to the spawn surface. |
| 4 — Aggregation hook reads telemetry into `iter_<N>_shipped.md` | ✅ Met | `aggregate_cycle_records()` + `format_telemetry_table()` exported from `telemetry.py`; `_helpers.ITER_SHIPPED_PROCEED_SECTIONS` already included `## Telemetry summary` (T04 forward-thinking). 3 pre-existing iter-shipped artifacts (iter5/6/7) retrofitted with the table-header stub + "no records — T22 was not yet active" placeholder. |
| 5 — `test_telemetry_record.py` passes | ✅ Met | 14/14 tests pass — spawn, complete, atomic-write under 8-thread concurrency, idempotent retry, missing-arg exits non-zero, smoke flow. |
| 6 — `test_telemetry_aggregation.py` passes | ✅ Met | 14/14 tests pass — 3×5 fixture → 15 records, sorting, missing-dir empty-list, corrupt-JSON skip, cache-hit % math (40%/100%/0%/null→`—`), no-quota-proxy assertion. |
| 7 — `runs/` in `.gitignore`; records local-only | ✅ Met | `.gitignore` line 30 `runs/*`; line 31 `!runs/.gitkeep`. |
| 8 — CHANGELOG entry written | ✅ Met | `CHANGELOG.md` line 10 — verbatim match against spec AC-8 wording (raw token capture + cache-* + T06/T07/T23/T27 + #52502 link). |
| 9 — Status surfaces flip together | ✅ Met | (a) spec `**Status:** ✅ Done (2026-04-28)`; (b) milestone README task table row (line 123) `✅ Done`; (c) milestone README G7 exit criterion (line 61) `✅ **(G7)** … **[T22 Done — 2026-04-28]**`. No `tasks/README.md` exists for M20 — N/A surface. |
| **Carry-over L1 round 2** — surface-check helper extensible to T27 | ✅ Met | `check_task_response_fields.py` `FIELDS_TO_PROBE` registry has 4 T22 entries + 2 T27 entries (`context_management.edits`, `clear_tool_uses_20250919_strategy_available`). T28 explicitly DEFERRED in module docstring + report body per `nice_to_have.md §24`. |
| **Carry-over L1 round 4** — out-of-scope reword | ✅ Met | spec line 159 now reads "T22's raw-count records (input/output/cache-* tokens) plus T06's analysis-script proxy aggregation are the local-best-estimate; reconciliation would require Anthropic API surface that doesn't exist." Matches the L1 round-4 suggestion verbatim. |

**All 9 ACs + both carry-over items met.**

---

## Phase 4 — Critical sweep

| Check | Result |
| --- | --- |
| Atomic-write semantics genuinely atomic | ✅ Yes — `tempfile.NamedTemporaryFile(dir=path.parent, delete=False)` + `Path.replace()` is the canonical write-temp + same-FS rename pattern. POSIX `rename(2)` atomicity holds. Stress-tested by `test_concurrent_spawns_do_not_corrupt_each_other` (8 threads). |
| Bad-input error messages clean (not Python tracebacks) | ✅ Yes — argparse handles missing/invalid args (`SystemExit(2)` with usage line); `cmd_complete` write errors print one-line `telemetry complete: write error — <OSError>` to stderr and `sys.exit(1)`. No raw tracebacks. |
| `complete` correctly merges into spawn record (not overwrite) | ✅ Yes — `_read_record(path)` first, then `record.update({…})` on completion fields only. `test_complete_preserves_spawn_fields` asserts `spawn_ts/model/effort` survive. |
| Cache-hit % handles divide-by-zero | ✅ Yes — `format_telemetry_table` checks `if total_cache > 0` before dividing; falls back to `"0.0%"` when both are zero, `"—"` when both are null. Three explicit tests cover the edge cases. |
| Surface-check helper genuinely extensible (not T22-specific) | ✅ Yes — `FIELDS_TO_PROBE` is a tuple list with `category` discriminator; report builder iterates without hard-coding T22 columns. T27 fields already registered. T28 explicitly out-of-scope per DEFER. |
| L1 round-4 spec reword landed | ✅ Yes — spec line 159 matches the suggested wording. |
| Test gaps | None found. Every AC has a corresponding pytest assertion (or, for AC-7/8/9, a verifiable filesystem/document check the auditor re-ran). |
| Doc drift | None. Module docstrings cite the task and downstream consumers (T06/T07/T23/T27); CHANGELOG, milestone README, and spec stay in lock-step. |
| Scope creep / `nice_to_have.md` adoption | None. T28 explicitly deferred to `nice_to_have.md §24`; T22 stays raw-counts-only per the round-2 H1 fix (no quota-proxy column). |
| Silent additions beyond spec | One — `aggregate_cycle_records()` + `format_telemetry_table()` are exported from `telemetry.py` rather than living in a separate aggregation script. Spec §Aggregation hook describes "T22's aggregation script" as a unit; co-locating with the spawn/complete CLI is reasonable (single-import contract for T04's `_helpers.make_iter_shipped()`). Transparency note — not a finding. |
| Status-surface drift | None — three surfaces present, three flipped. No `tasks/README.md` to flip. |

---

## Additions beyond spec — audited and justified

1. **`aggregate_cycle_records()` + `format_telemetry_table()` co-located in `telemetry.py`** — spec §Aggregation hook is silent on script location. Co-location reduces import surface for T04's `_helpers.make_iter_shipped()` and matches the one-helper-per-concern pattern of `bench_terminal_gate.py`. Justified.
2. **Fallback `cmd_complete` path when no spawn record exists** — spec is silent on this case; Builder added a stderr warning + null-`spawn_ts` stub. Defensive but matches the atomic-write + idempotent-retry intent. Justified.

No drive-by refactors. No `nice_to_have.md` adoption.

---

## Gate summary

| Gate | Command | Pass/Fail |
| --- | --- | --- |
| pytest | `AIW_BRANCH=design uv run pytest -q` | PASS (1089 passed, 7 skipped) |
| pytest (targeted) | `uv run pytest tests/orchestrator/test_telemetry_*.py -v` | PASS (28/28) |
| lint-imports | `uv run lint-imports` | PASS (5/5 contracts KEPT) |
| ruff | `uv run ruff check` | PASS |
| Spec smoke test | spec lines 134–155 (spawn → complete → assert) | PASS |

---

## Issue log — cross-task follow-up

*(none — no findings)*

---

## Deferred to nice_to_have

*(none — T28 was deferred to `nice_to_have.md §24` before T22's land time; T22 honoured the boundary by carrying T28 as DEFERRED in the surface-check docstring rather than probing)*

---

## Propagation status

*(no forward-deferred findings — no propagation needed)*

---

## Cycle 1 audit appendix — `runs/m20_t22/cycle_1/summary.md` inline equivalent

(Per cycle-1 T05/T21 precedent; harness blocks `.md` writes outside the issue file.)

- **State as of audit close:** all 9 ACs + both carry-over items met; all gates green; smoke test passed; status surfaces aligned.
- **Files touched (Builder cycle 1):** see issue body above + `git status`.
- **Open items:** none.
- **Decisions made:** Builder's choice to co-locate aggregation helpers with the spawn/complete CLI is justified (transparency note, not a finding).
- **Files NOT touched:** `pyproject.toml`, `uv.lock`, `ai_workflows/**` (KDR-003 + scope-note compliance).

---

**Auditor verdict:** ✅ PASS — cycle 1 closes T22.

---

## Sr. SDET review (2026-04-28)

**Test files reviewed:**
- `tests/orchestrator/test_telemetry_record.py` (14 tests — spawn, complete, atomic-write, smoke)
- `tests/orchestrator/test_telemetry_aggregation.py` (14 tests — aggregate_cycle_records, format_telemetry_table, iter-shipped section)

**Skipped (out of scope):** all other `tests/orchestrator/` files

**Verdict:** BLOCK

### BLOCK — tests pass for the wrong reason

**Finding B1 — Lens 1: Concurrency test does not exercise atomic-write semantics**

`tests/orchestrator/test_telemetry_record.py:306` — `TestAtomicWrite.test_concurrent_spawns_do_not_corrupt_each_other`

The test launches 8 threads, each writing to a DIFFERENT file (`agent_0.usage.json` through `agent_7.usage.json`). No two threads share a file path. There is no write-contention across threads. The only shared resource is the directory, and `mkdir(parents=True, exist_ok=True)` is already thread-safe. The `_write_record_atomic` function's `NamedTemporaryFile + replace()` path is entirely bypassed — replacing it with a bare `open(path, "w"); json.dump(record, fh)` would leave this test green. The test confirms that 8 different agents can each write their own file without error; it does NOT confirm that concurrent writes to the SAME file are atomic.

The production risk this AC is meant to guard: an orchestrator retries `complete` for agent `auditor` concurrently with a prior in-flight `complete` call. That race is not exercised.

Cited source: `scripts/orchestration/telemetry.py:75-99` (`_write_record_atomic`). Spec AC-2 + Tests section: "Atomic-write semantics: simulated concurrent invocations don't lose records."

Action: Add a test where multiple threads call `complete` on the SAME `(task, cycle, agent)` triple concurrently. Assert the resulting JSON is parseable and contains one of the expected `input_tokens` values (last writer wins, no corruption/truncation).

### FIX — fix-then-ship

**Finding F1 — Lens 2: `total_cache == 0` branch (divide-by-zero guard) not covered**

`tests/orchestrator/test_telemetry_aggregation.py:173` — `TestFormatTelemetryTable.test_cache_hit_pct_zero_percent`

Uses `cache_creation=800, cache_read=0`. `total_cache = 800 > 0` so the `if total_cache > 0` formula branch executes. The `else: cache_pct_str = "0.0%"` branch at `scripts/orchestration/telemetry.py:303-304` (when BOTH fields are integer 0, not null) is never exercised. If the condition were incorrectly inverted or the else branch deleted, all tests would still pass.

Action: Add `test_cache_hit_pct_zero_when_both_zero` with `cache_creation=0, cache_read=0` asserting `"0.0%"` in the table output.

### Advisory — track but not blocking

- **A1** — Smoke test (`test_telemetry_record.py:390`) passes `--cache-creation 80 --cache-read 20` but does not assert those values in the written record. Low risk (covered elsewhere), but the spec smoke test would not catch a regression where cache fields are silently dropped on `complete`.
- **A2** — Test name `test_concurrent_spawns_do_not_corrupt_each_other` implies same-file corruption testing; after the B1 fix, rename to clarify that the existing test covers directory-creation safety for different agents.
- **A3** — `_load_telemetry_module` helper is duplicated verbatim in both test files; could move to `_helpers.py`.

### What passed review (one line per lens)

- Tests-pass-for-wrong-reason: BLOCK — B1 (concurrency test covers directory creation, not write atomicity).
- Coverage gaps: F1 (total_cache == 0 branch uncovered); A1 (smoke test omits cache field check).
- Mock overuse: none — module loaded directly via importlib, no mocks.
- Fixture / independence: clean — monkeypatch.chdir reverts; tmp_path is per-test; no module-level state.
- Hermetic-vs-E2E gating: clean — no network, no subprocess, no provider calls.
- Naming / assertion-message hygiene: A2 (misleading test name), A3 (helper duplication).

---

## Sr. Dev review (2026-04-28)

**Verdict:** SHIP

(Stitched from `runs/m20_t22/cycle_1/sr-dev-review.md`.)

No BLOCK / no FIX. Four advisories tracked:
- **A1 (track-only):** dead `else` branch in `telemetry.py::main()` — argparse `add_subparsers(required=True)` exits before reaching it. Drop in cleanup pass.
- **A2 (track-only):** `_load_telemetry_module` duplicated verbatim across the two new test files; consolidate into `tests/orchestrator/conftest.py` as a fixture in a future cleanup.
- **A3 (track-only):** misleading comment in `aggregate_cycle_records` (`"orchestrator logs the error"` — actually no caller logs). Reword to `# Skip corrupt files silently — callers detect via shorter record count.`
- **A4 (track-only):** `check_task_response_fields.py` writes non-atomically. Acceptable since it's a one-shot human-invoked tool, not a concurrent-write surface.

Cycle-1 lenses (hidden bugs / defensive-code creep / idiom alignment / premature abstraction / docstring drift / simplification / KDR-003 / extensibility / test idiom) all clean.

---

## Security review (2026-04-28)

**Verdict:** SHIP

(Stitched from `runs/m20_t22/cycle_1/security-review.md`.)

No Critical / High. Three advisories tracked:
- **ADV-1 (track-only):** `--task` and `--agent` CLI args are joined into the `runs/<task>/cycle_<N>/<agent>.usage.json` path without `..`-segment guard. Theoretical write-path traversal under hostile invocation; current callers are hardcoded `m<MM>_t<NN>` shorthands. Hygiene fix possible (`assert resolved.is_relative_to(Path("runs").resolve())`); not blocking under solo-use threat model.
- **ADV-2 (track-only):** `check_task_response_fields.py --output` accepts arbitrary write paths. Single-user, single-machine — no remote attacker can supply this. Help string already documents the default.
- **ADV-3 (track-only):** `scripts/orchestration/` not in sdist exclude block; will appear in next sdist. Files are stdlib-only, no secrets — developer-tooling exposure rather than credential leak. Tracking for awareness; defensive-enumeration deferred until a future task adds sensitive content under `scripts/orchestration/`.

KDR-003 clean: zero `import anthropic`, zero `ANTHROPIC_API_KEY` references. Wheel surface clean: `[tool.hatch.build.targets.wheel] packages = ["ai_workflows"]` strictly limits wheel to `ai_workflows/`. No `subprocess`, `eval`, `exec`, `shell=True` in either new script. JSON via `json.dump`, not string interpolation.

---

## Locked decisions — terminal-gate BLOCK + FIX bypass (2026-04-28)

Per `/auto-implement` Step T4 TEAM BLOCKER: BLOCK from sr-sdet (test-passes-for-wrong-reason lens) requires another Builder → Auditor cycle targeting the finding. The BLOCK + FIX both carry single clear recommendations, no KDR conflict, no scope expansion, no deferral to non-existent task. sr-dev and security reviewers' specialised lenses don't conflict with sr-sdet's BLOCK — sr-dev SHIP'd on code-quality grounds (atomic-write semantics genuinely correct), and the BLOCK is on test-discrimination (sr-sdet's lens). Loop controller concurs with sr-sdet's reasoning. Stamp + re-loop with the two below as carry-over ACs for Builder cycle 2.

- **Locked decision (loop-controller + sr-sdet concur, 2026-04-28):** Rewrite `tests/orchestrator/test_telemetry_record.py::TestAtomicWrite::test_concurrent_spawns_do_not_corrupt_each_other` to exercise SAME-triple write contention. N threads call `complete` on the same `(task="m20_t22_atomic", cycle=1, agent="auditor")` triple concurrently with distinct `--input-tokens` values. After `join()`, assert exactly one parseable JSON record exists at the expected path, and its `input_tokens` value is one of the expected per-thread values (last-writer-wins; no truncation/interleaving/corruption). The original different-files-per-thread test is acceptable as a SECOND test for directory-creation safety — keep it but rename to `test_concurrent_spawns_for_different_agents_create_distinct_records` per sr-sdet A2. Verify discriminating-positive: replacing `_write_record_atomic` with bare `open()+json.dump()` would race-corrupt the same-triple test.
- **Locked decision (loop-controller + sr-sdet concur, 2026-04-28):** Add `test_cache_hit_pct_when_both_cache_fields_zero` to `tests/orchestrator/test_telemetry_aggregation.py` exercising the `else: cache_pct_str = "0.0%"` divide-by-zero guard at `telemetry.py:303-304`. Fixture: a single record with `cache_creation=0, cache_read=0` (both integer 0, neither null). Assert `"0.0%"` appears in the formatted table. Verify discriminating-positive: removing the `else` branch would crash on this fixture instead of returning `0.0%`.
- **Locked carry-over (loop-controller, 2026-04-28):** sr-sdet A1/A2/A3 + sr-dev A1/A2/A3/A4 + security ADV-1/ADV-2/ADV-3 all remain track-only — none are promoted to carry-over. Future cleanup sweep (likely M21 hygiene task) consolidates them.

**Cycle 2 expected diff:** small — one test rewrite + one new test. No production code changes; the production atomic-write logic is correct (sr-dev confirmed) and the divide-by-zero guard is correct (sr-sdet confirmed) — only test discrimination is being added.

---

## Cycle 2 audit (2026-04-28)

**Audit scope:** the two locked-decision deltas only — `tests/orchestrator/test_telemetry_record.py::TestAtomicWrite` (rename + new same-triple test) and `tests/orchestrator/test_telemetry_aggregation.py::TestFormatTelemetryTable` (new both-zero divide-by-zero test). Plus regression sweep across all cycle-1 ACs to confirm no drift.

**Status:** ✅ PASS

### Phase 1 — Drift check (compact)

| Check | Result |
| --- | --- |
| Production code (`scripts/orchestration/`, `ai_workflows/`) untouched cycle 2 | ✅ `git diff HEAD --stat -- scripts/ ai_workflows/ pyproject.toml uv.lock` empty |
| KDR-003 — zero `anthropic` SDK / `ANTHROPIC_API_KEY` in 2 cycle-2-touched test files + production `telemetry.py` | ✅ `grep -nE "anthropic\|ANTHROPIC_API_KEY"` → 0 hits |
| Four-layer rule | N/A (test files only) |
| `pyproject.toml` / `uv.lock` untouched | ✅ |

**No drift.** Cycle 2's diff is two test files only — production atomic-write logic + divide-by-zero guard remain unchanged (sr-dev + sr-sdet cycle-1 confirmed correct).

### Phase 2 — Gate re-run (from scratch)

| Gate | Command | Result |
| --- | --- | --- |
| pytest (full) | `AIW_BRANCH=design uv run pytest -q` | **1091 passed, 7 skipped** in 44.82s (+2 vs cycle 1's 1089 — the 2 new tests) |
| pytest (T22 targeted) | `AIW_BRANCH=design uv run pytest tests/orchestrator/test_telemetry_record.py tests/orchestrator/test_telemetry_aggregation.py -v` | **30 passed** in 0.12s (+2 vs cycle 1's 28) |
| lint-imports | `uv run lint-imports` | 5 contracts KEPT, 0 broken |
| ruff | `uv run ruff check` | All checks passed |
| Spec smoke test (lines 134–155) | `mkdir → spawn → complete → assert` | **SMOKE-OK** |

Builder cycle-2 reported 1091/7/30 — matches auditor re-run exactly. Gate integrity intact.

### Phase 3 — Cycle-2 carry-over AC grading (locked decisions only)

Per Auditor procedure: re-graded ONLY the two locked-decision carry-over ACs, not the original 9.

| Carry-over AC | Status | Notes |
| --- | --- | --- |
| **LD-1** — Original `test_concurrent_spawns_do_not_corrupt_each_other` renamed to `test_concurrent_spawns_for_different_agents_create_distinct_records`; NEW `test_concurrent_completes_for_same_triple_are_atomic` exercises N-thread same-triple `complete` calls and asserts single-parseable record + `input_tokens` ∈ expected per-thread values | ✅ Met | Rename landed at `test_telemetry_record.py:306` (verified docstring NOTE explicitly disclaims same-file contention coverage and points to the new test). New test at `test_telemetry_record.py:354` uses N=8 threads, distinct `input_tokens` (0..700), spawns base record once, then 8 concurrent `complete` calls with no artificial backoffs. Asserts `record_path.exists()`, `json.load()` succeeds (no JSONDecodeError on truncation), and `rec["input_tokens"] in expected_input_tokens` (catches non-atomic interleaving where mid-write produces a token value that's neither old nor new). |
| **LD-2** — NEW `test_cache_hit_pct_when_both_cache_fields_zero` with `cache_creation=0, cache_read=0` (both int 0) asserting `"0.0%"` appears | ✅ Met | New test at `test_telemetry_aggregation.py:179`. Fixture record uses int 0 (not None) for both fields. Asserts `"0.0%" in table`. Production guard at `telemetry.py:303-304` (`else: cache_pct_str = "0.0%"`) is the path under test — confirmed by source inspection: with both cache fields not-None and total_cache==0, the `if total_cache > 0` branch is False, the else fires. |
| **Optional** — CHANGELOG cycle-2 parenthetical amendment | ✅ Met | `CHANGELOG.md:10` ends with `(cycle 2 follow-up: rewrote concurrency test for same-triple contention + added zero-cache divide-by-zero guard test)`. |

### Phase 4 — Discriminating-positive verification

**LD-1 — would the test fail if `_write_record_atomic` were replaced with bare `open() + json.dump()`?**

Yes. Eight concurrent threads writing to the same path via non-atomic `open(path, "w")` would hit one of three failure modes intermittently:
1. Mid-write truncation → `json.load(fh)` raises `JSONDecodeError` → assertion `not errors` after `do_complete` would still pass (errors are caught inside the thread fn and listed), but the outer `with record_path.open() as fh: rec = json.load(fh)` (line 425) would raise — test fails with uncaught `JSONDecodeError`.
2. Interleaved bytes from two threads producing valid-looking but corrupt JSON whose `input_tokens` is not in `[0, 100, 200, ..., 700]` → membership assertion at line 428 fails.
3. Last-writer-wins is the expected outcome under atomic rename (test passes); under bare `open()`, last-writer-wins is also possible (lucky scheduling), so the test is probabilistic. Mitigation: 8 threads with no backoff and read-modify-write across ~14 fields per record creates a wide enough race window that repeated CI runs would catch a regression.

The contention level (8 threads, no `time.sleep`, immediate join) is acceptable. Documented as "discriminating-positive" in the test docstring (line 367-374). **Verified.**

**LD-2 — would the test fire (`ZeroDivisionError` or `KeyError`) if the production `else: cache_pct_str = "0.0%"` branch were removed?**

Yes. With both cache fields integer 0, `cache_read is not None and cache_creation is not None` → True, enters the outer block. `total_cache = 0 + 0 = 0`. `if total_cache > 0` → False. If the `else: cache_pct_str = "0.0%"` line were removed, `cache_pct_str` would be **unbound** when referenced at line 309-310 (`f"... | {cache_pct_str} | ..."`) → `UnboundLocalError: cannot access local variable 'cache_pct_str' where it is not associated with a value`. Test would crash.

Alternative: if the condition were inverted (`if total_cache <= 0` accidentally), with cache=600/400 the existing `test_cache_hit_pct_computed_correctly` would fall into the wrong branch and miss "40.0%" — that older test would fail first. So this test specifically guards the both-zero case the older tests structurally cannot reach.

The test docstring at line 187-194 explicitly documents the discriminating-positive reasoning. **Verified.**

### Phase 5 — sr-sdet A2 absorption check (rename happened correctly)

sr-sdet cycle-1 advisory A2: "Test name `test_concurrent_spawns_do_not_corrupt_each_other` implies same-file corruption testing; after the B1 fix, rename to clarify that the existing test covers directory-creation safety for different agents."

LD-1 stamps absorbed A2: "The original different-files-per-thread test is acceptable as a SECOND test for directory-creation safety — keep it but rename to `test_concurrent_spawns_for_different_agents_create_distinct_records` per sr-sdet A2."

Verified: original test at `test_telemetry_record.py:306` is now named `test_concurrent_spawns_for_different_agents_create_distinct_records`. Docstring updated to clarify scope ("directory-creation safety under concurrent access"). Explicit cross-reference to the new same-triple test at line 318 ("This test does NOT exercise same-file write contention — that case is covered by `test_concurrent_completes_for_same_triple_are_atomic`."). A2 absorption is clean.

### Phase 6 — Status surfaces (verify, do NOT re-flip)

| Surface | Cycle-1 state | Cycle-2 state | Drift? |
| --- | --- | --- | --- |
| (a) spec `**Status:**` line | `✅ Done (2026-04-28).` | `✅ Done (2026-04-28).` | ✅ Stable |
| (b) milestone README task table row 123 | `✅ Done` | `✅ Done` | ✅ Stable |
| (c) milestone README G7 exit (line 61) | `**[T22 Done — 2026-04-28]**` | `**[T22 Done — 2026-04-28]**` | ✅ Stable |
| (d) `tasks/README.md` row | N/A (no M20 tasks/README) | N/A | ✅ Stable |

**No surface drift.** Cycle-2 did not (and should not have) re-touched status surfaces; cycle-1 set them and they remain consistent.

### Phase 7 — Critical sweep

| Check | Result |
| --- | --- |
| Production code unchanged (sr-dev + sr-sdet cycle-1 confirmed semantics correct) | ✅ Confirmed via `git diff HEAD --stat -- scripts/ ai_workflows/` empty |
| Cycle-2 scope limited to 2 test files | ✅ Confirmed: only `tests/orchestrator/test_telemetry_record.py` + `tests/orchestrator/test_telemetry_aggregation.py` + `CHANGELOG.md` parenthetical |
| Test count delta matches expectation: 28 → 30 (1 new in each file) | ✅ Confirmed |
| Total pytest delta: 1089 → 1091 (+2) | ✅ Confirmed |
| Discriminating-positive documented in test docstrings | ✅ Both new tests carry explicit "Discriminating-positive: …" docstring notes (`test_telemetry_record.py:367-374` + `test_telemetry_aggregation.py:187-194`) |
| sr-sdet A1/A3, sr-dev A1-A4, security ADV-1/ADV-2/ADV-3 — all locked as track-only by loop controller; not re-promoted | ✅ Confirmed (per locked-decision section line 221) |
| Status-surface drift | None |
| Doc drift | None — CHANGELOG cycle-2 parenthetical present; spec/README untouched cycle-2 (correct) |

### Gate summary (cycle 2)

| Gate | Command | Pass/Fail |
| --- | --- | --- |
| pytest (full) | `AIW_BRANCH=design uv run pytest -q` | PASS (1091 passed, 7 skipped) |
| pytest (targeted T22) | `AIW_BRANCH=design uv run pytest tests/orchestrator/test_telemetry_*.py -v` | PASS (30/30) |
| lint-imports | `uv run lint-imports` | PASS (5/5 contracts KEPT) |
| ruff | `uv run ruff check` | PASS |
| Spec smoke test | spec lines 134–155 | PASS (SMOKE-OK) |

### Cycle-2 audit appendix — `runs/m20_t22/cycle_2/summary.md` inline equivalent

(Per cycle-1 T05/T21 precedent; harness blocks `.md` writes outside the issue file.)

- **State as of cycle 2 close:** both LD-1 + LD-2 carry-over ACs cleanly applied; CHANGELOG parenthetical present; all gates green; new tests verified discriminating-positive; status surfaces stable from cycle 1.
- **Files touched (Builder cycle 2):** `tests/orchestrator/test_telemetry_record.py` (rename + new same-triple atomic test), `tests/orchestrator/test_telemetry_aggregation.py` (new both-zero divide-by-zero test), `CHANGELOG.md` (cycle-2 parenthetical).
- **Files NOT touched (correctly):** `scripts/orchestration/telemetry.py` + all production code — sr-dev confirmed atomic-write semantics correct, sr-sdet confirmed divide-by-zero guard correct; only test discrimination needed.
- **Open items:** none.
- **Forward-deferred:** none — sr-sdet A1/A3, sr-dev A1-A4, security ADV-1/ADV-2/ADV-3 remain track-only per cycle-1 lock.

---

**Auditor verdict (cycle 2):** ✅ PASS — both locked decisions cleanly applied, new tests are discriminating, all gates green, status surfaces stable, no drift detected. T22 ready to ship from cycle 2.

---

## Sr. Dev review (2026-04-28) — cycle 2 terminal gate

**Verdict:** SHIP

(Stitched from `runs/m20_t22/cycle_2/sr-dev-review.md`.)

No BLOCK / no FIX. Cycle-2 test additions structurally sound: threading + join + assertion order correct on the same-triple atomic test; rename clean (no orphan references); zero-cache test specific. KDR-003 cross-check still clean.

---

## Sr. SDET review (2026-04-28) — cycle 2 terminal gate

**Verdict:** SHIP

(Stitched from `runs/m20_t22/cycle_2/sr-sdet-review.md`.)

LD-1 (B1 fix) confirmed discriminating: SAME-triple write contention exercised; ≥ 8 threads; no artificial backoffs; bare `open()+json.dump()` would race-corrupt. LD-2 (F1 fix) confirmed discriminating: both `cache_creation` and `cache_read` are integer 0 (not null); removing the `else` branch would `ZeroDivisionError`. Rename clean. A1/A3 advisories correctly remain track-only.

---

## Security review (2026-04-28) — cycle 2 terminal gate

**Verdict:** SHIP

(Stitched from `runs/m20_t22/cycle_2/security-review.md`.)

Cycle 2 test-only — `tmp_path` isolated; no subprocess outside script under test; no out-of-repo reads; no credential/API-key references. KDR-003 still clean. Concurrency test thread cleanup correct (`.join()` before assertions). No new threat surface.

---

## Cycle 2 terminal gate — TERMINAL CLEAN

All three reviewers verdict SHIP. Per T05's precedence rule: TERMINAL CLEAN. dependency-auditor not spawned (no manifest change in this task). Proceed to commit ceremony.

**Final task close-out summary**
- Cycles run: 2 (cycle 1 BUILT/PASS → terminal gate cycle 1 returned BLOCK + FIX from sr-sdet → bypass + 2 locked decisions → cycle 2 BUILT/PASS → terminal gate cycle 2 TERMINAL CLEAN).
- Auditor verdict: PASS (cycles 1 + 2).
- Reviewer verdicts (cycle 2): sr-dev SHIP, sr-sdet SHIP, security SHIP, dependency = N/A.
- KDR additions: none.
- Open issues at close: 10 track-only advisories (sr-sdet A1/A3 + sr-dev A1/A2/A3/A4 + security ADV-1/ADV-2/ADV-3) — all deferred to a future hygiene sweep.
