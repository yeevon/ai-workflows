# M12 Task 06 — Eval Harness Fixture Convention — Issue Log

**Task:** Eval harness fixture convention for cascade author/auditor node pairs
**Status:** ✅ PASS — cycle 2 close (sr-sdet FIX resolved; all gates clean)
**Spec:** `task_06_eval_harness_fixture_convention.md`
**Audit scope:** evals/README.md, .claude/skills/ai-workflows/SKILL.md, three new test files,
CHANGELOG.md, milestone README + spec status flips. KDR-003/004/009/011/013 drift check.

---

## Cycle 1 — Audit (2026-04-29)

**Source task:** `task_06_eval_harness_fixture_convention.md`
**Audited on:** 2026-04-29
**Audit scope:** as above; 6 new tests run from scratch; 3 gates re-run from scratch.

### Design-drift check

No drift detected. T06 ships documentation + golden tests only — no production code change
(verified via `git diff --stat ai_workflows/ pyproject.toml uv.lock` → empty).

- **KDR-003** (no Anthropic API): `grep -n "anthropic\|ANTHROPIC_API_KEY"` across all 4 new
  files → 0 hits. PASS.
- **KDR-004** (validator pairing): T06 explicitly carves out cascade-fixture replay through
  `EvalRunner._resolve_node_scope` because cascade nodes register `<cascade_name>_validator`
  rather than `<cascade_name>_primary_validator` / `<cascade_name>_auditor_validator`. The
  carve-out is documented in `evals/README.md` and forward-deferred to `nice_to_have.md`.
  No new pairing needed — T06 adds no production LLM call. PASS.
- **KDR-009** (SqliteSaver checkpoints): T06 writes JSON fixtures under `evals/` (read by
  the test); checkpointers built per test via `build_async_checkpointer`. No hand-rolled
  persistence. PASS.
- **KDR-011** (audit cascade): T06 documents the cascade's eval-fixture surface. No
  behaviour change. PASS.
- **KDR-013** (user-owned external workflows): convention applies free to any external
  cascade-using workflow via the `name=` kwarg's role-suffix derivation. PASS.

### AC grading

| AC | Status | Notes |
|----|--------|-------|
| 1 — `evals/README.md` with both sections + literals | met | `## Layout reference` + `## Cascade fixture convention (M12 T06)` both present; tables enumerate `planner_explorer_audit_*` / `slice_worker_audit_*` paths; verdict-node-no-fixture rule documented (line 49-50); `EvalRunner` carve-out documented (line 52-58) with KDR-004 reference; `TokenUsage.role` vs `state['cascade_role']` distinction documented (line 60-67) with `audit_cascade.py:313, 349` references — **verified against production lines 313 and 349 — both match `role="author"` and `role="auditor"` factory bindings**. |
| 2 — SKILL.md cross-reference bullet | met | Bullet added at SKILL.md:96-101 under §Primary surface — MCP, names both `<cascade_name>` literals (`planner_explorer_audit`, `slice_worker_audit`). |
| 3 — `tests/evals/test_cascade_fixture_convention.py` 4 tests pass | met | All 4 tests pass; test 4 uses `load_case` only (no `EvalRunner` invocation per spec carve-out); inline cascade construction via `audit_cascade_node()` confirmed. |
| 4 — `tests/workflows/test_planner_cascade_fixture_golden.py` passes | met | Single test passes; `CASCADE_NAME = "planner_explorer_audit"` matches `planner.py:570`; primary path `planner/planner_explorer_audit_primary/`, auditor path `planner/planner_explorer_audit_auditor/`; both fixtures load via `load_case`; `tracker.by_role(run_id)` contains both `"author"` and `"auditor"` keys. |
| 5 — `tests/workflows/test_slice_refactor_cascade_fixture_golden.py` passes | met | Single test passes; `CASCADE_NAME = "slice_worker_audit"` matches `slice_refactor.py:1053`; correct paths; `skip_terminal_gate=True` mirrors production (`slice_refactor.py:1054`); both role keys present. |
| 6 — All 3 test files use inline-cascade construction | met | All 3 use `audit_cascade_node()` directly + own their `CostTracker` instance; none import or call `run_workflow`; all use `tmp_path` for fixture roots. |
| 7 — No diff to `ai_workflows/` production code | met | `git diff --stat ai_workflows/` → empty. |
| 8 — No `pyproject.toml` / `uv.lock` diff | met | `git diff --stat pyproject.toml uv.lock` → empty. |
| 9 — KDR-003 guardrail still passes; gates clean | met | Independent gate re-run: `uv run pytest` (1477 passed, 11 skipped), `uv run lint-imports` (5 contracts kept), `uv run ruff check` (clean). |
| 10 — CHANGELOG entry under [Unreleased] cites KDR-011 + KDR-004 | met | CHANGELOG.md:10-46 entry under `[Unreleased]`; cites KDR-011 (line 39) + KDR-004 carve-out (line 40-42); notes "documentation + golden tests only" (line 44). |
| 11 — Status surfaces flipped | met (4-canonical) / see LOW-01 | (a) spec `**Status:**` ✅ Complete (2026-04-29); (b) milestone README task-table row 06 ✅ Complete (2026-04-29); (c) milestone README §Exit-criteria #9 `[x]` ticked; (d) `tasks/README.md` N/A (M12 has no per-task subdirectory README — confirmed via `ls`). All four canonical surfaces flipped. See LOW-01 for non-canonical AC-checkbox observation. |
| Carry-over TA-LOW-01 (audit_cascade.py:313/349 line refs) | met | Verified production lines 313 and 349 carry `role="author"` and `role="auditor"` — README references match. |
| Carry-over TA-LOW-02 (canonical stub adapter reuse) | met | All 3 test files use the canonical `_StubClaudeCodeAdapter` shape from `tests/graph/test_audit_cascade.py:107`. No fallback to `test_slice_refactor_cascade_enable.py` was needed. |

### 🟢 LOW-01 — Per-AC checkboxes inside spec block remain `[ ]`

The spec's own `## Acceptance Criteria` block (lines 187-200) shows `[ ]` for every AC,
and the `## Carry-over from task analysis` block (lines 230-231) shows `[ ]` for both
TA-LOW-01 and TA-LOW-02 — even though the issue file's "Carry-over items resolved"
section confirms both as resolved.

The four canonical status-surfaces (per AC #11) are flipped correctly. The per-AC
checkboxes inside the spec are convention, not in AC #11's scope, but ticking them
matches the convention used by other completed tasks (e.g. T05's spec).

**Action / Recommendation:** Auditor flips the per-AC checkboxes in the spec (12 ACs +
2 carry-over items) to `[x]` as part of this audit close. Non-blocking; cosmetic
status-surface tidy. Same edit could be done by Builder on next cycle if there is one,
but since verdict is PASS there will be no Builder cycle.

### Additions beyond spec — audited and justified

- `slice_refactor` golden test passes `skip_terminal_gate=True` to `audit_cascade_node()`.
  This mirrors production wiring at `slice_refactor.py:1054` (T08 amendment) and is
  spec-conformant per the spec's "mirrors production wiring" framing. Justified — no
  drift.

### Gate summary

| Gate | Command | Result |
|------|---------|--------|
| pytest (full suite) | `uv run pytest` | PASS (1477 passed, 11 skipped, 0 failures) |
| pytest (T06 new tests only) | `uv run pytest tests/evals/test_cascade_fixture_convention.py tests/workflows/test_planner_cascade_fixture_golden.py tests/workflows/test_slice_refactor_cascade_fixture_golden.py -v` | PASS (6 passed) |
| lint-imports | `uv run lint-imports` | PASS (5 contracts kept) |
| ruff | `uv run ruff check` | PASS (all checks passed) |
| KDR-003 grep guardrail | `grep -rn "anthropic\|ANTHROPIC_API_KEY" tests/evals/test_cascade_fixture_convention.py tests/workflows/test_*cascade_fixture_golden.py evals/README.md` | PASS (0 hits) |

### Issue log — cross-task follow-up

- `M12-T06-LOW-01` — per-AC spec-checkboxes not ticked. Severity LOW. Owner: this audit
  (cosmetic close-out fix). Status: open at audit start; resolved by auditor in this
  audit close (see Phase-6 actions below).

### Deferred to nice_to_have

- **`EvalRunner` cascade-fixture replay** — `_resolve_node_scope` enforces a
  `<node>_validator` pair-lookup (KDR-004) that the cascade graph's
  `<cascade_name>_validator` (single-segment) registration does not satisfy. Adding
  cascade-aware lookup is an engine change with KDR/ADR implications. Trigger:
  "an operator wants to replay a captured cascade fixture through `EvalRunner`
  end-to-end". Add to `nice_to_have.md` at M12 close-out (T07).
- **External-workflow cascade fixture convention** — KDR-013 user-owned workflows get
  this for free. If external workflows want a different layout (e.g. flat the per-node
  directory split), they would author a custom `CaptureCallback`. Flag for
  `nice_to_have.md` if a CS300 or other external user requests it.
- **Multi-tier cascade fixture layout** — when single-tier audit verdicts prove unstable
  and multi-tier cascading lands as a future task, the directory convention extends from
  `<cascade_name>_auditor/` to per-tier sub-paths. No T06 deliverable.
- **`<cascade_name>_verdict` capture** — currently no fixture (verdict is pure-parse);
  future LLM-graded verdict node would extend the convention naturally. No T06 deliverable.

### Propagation status

- **EvalRunner cascade-fixture replay** — DEFERRED to `nice_to_have.md`. To be added at
  M12 T07 close-out (M12 T07 is doc-only; bundles the four ADR-0004 amendments + this
  `nice_to_have.md` entry). No carry-over needed in T07's spec because T07 is
  milestone-close-out (not yet drafted); the M12 README §Propagation status block
  already flags forward-deferrals from M12.

No carry-over needed in any sibling task spec — all deferrals are framework-wide and
flow through `nice_to_have.md` rather than a specific future task.

### Auditor close-out actions

1. Tick all 12 AC checkboxes in the spec from `[ ]` to `[x]`.
2. Tick both TA-LOW-01 and TA-LOW-02 carry-over checkboxes from `[ ]` to `[x]`.
3. Issue file is the durable artefact for this audit (this file).
4. Cycle summary written at `runs/m12_t06/cycle_1/summary.md`.

---

## Terminal gate — Cycle 1 (2026-04-29)

**Verdicts:** sr-dev=SHIP · sr-sdet=FIX-THEN-SHIP · security=SHIP

**Locked terminal decision (loop-controller + sr-sdet concur, 2026-04-29):**
All tests pass `root=tmp_path` to `CaptureCallback`, which bypasses the `dataset_name`-append logic in `CaptureCallback.__init__:108`. The production path that exercises `evals/<dataset>/<workflow>/<node>/` layout (the `root=None` branch) is untested. Add one test in `tests/evals/test_cascade_fixture_convention.py` that instantiates `CaptureCallback` with `root=None` and `monkeypatch.setenv("AIW_EVALS_ROOT", str(tmp_path))`, drives `on_node_complete` with a stub cascade result, and asserts the fixture lands at `tmp_path / dataset_name / workflow_id / node_name / *.json`. This fixes the coverage gap against the core `evals/README.md` convention without production-code changes.

**sr-dev advisories (non-blocking, no cycle required):**
- A1: Test docstrings claim `<dataset>/...` path prefix but `root=tmp_path` bypasses it. Update docstrings to note the bypass. (Will be fixed in cycle 2 alongside the sr-sdet FIX.)
- A2: `calls` class attribute tracked but never asserted in new test files. Advisory only; no obligation.

**Carry-over to cycle 2 Builder:**
1. Add `test_capture_callback_root_none_uses_dataset_segment` to `tests/evals/test_cascade_fixture_convention.py`: uses `root=None` + `monkeypatch.setenv("AIW_EVALS_ROOT", str(tmp_path))`, calls `on_node_complete` with a stub node result, asserts fixture at `tmp_path / "<dataset_name>" / "<workflow_id>" / "<node_name>" / "*.json"`.
2. Update docstrings in tests 1–4 of `test_cascade_fixture_convention.py` to add one-liner: "Note: `root=tmp_path` bypasses the dataset-name prefix; on-disk path is `<root>/<workflow>/<node>/`." (sr-dev A1).

---

## Cycle 1 — Implementation (2026-04-29)

### Carry-over items resolved

**TA-LOW-01 (Round 1):** Verified that the `evals/README.md` cascade-fixture-convention
block lands with the correct role-tag paragraph distinguishing `state['cascade_role']`
(debug-only) from `TokenUsage.role` (persistent telemetry). The `audit_cascade.py:313, 349`
references were confirmed against the production file at implementation time — both line
numbers match the factory-time `role="author"` and `role="auditor"` bindings on `tiered_node`.
**Resolved.**

**TA-LOW-02 (Round 1):** `_StubClaudeCodeAdapter` from `tests/graph/test_audit_cascade.py:107`
was used as the canonical reuse target for all three test files. The same stub shape
(FIFO script, independent from `_StubLiteLLMAdapter`) was reproduced in each test module.
No fallback to `tests/workflows/test_slice_refactor_cascade_enable.py` was needed — the
`SliceResult` schema works cleanly with the standard stub shape.
**Resolved.**

### Deliverables shipped

- `evals/README.md` — created with `## Layout reference` + `## Cascade fixture convention
  (M12 T06)` sections as specified. Cascade-convention section enumerates explicit paths
  for planner (`planner_explorer_audit_primary/`, `planner_explorer_audit_auditor/`) and
  slice_refactor (`slice_worker_audit_primary/`, `slice_worker_audit_auditor/`), documents
  the verdict-node no-fixture rule, the `EvalRunner` replay carve-out, and the
  `TokenUsage.role` vs `state['cascade_role']` distinction.
- `.claude/skills/ai-workflows/SKILL.md` — one-bullet cascade fixture layout cross-reference
  added under §Primary surface — MCP (before the `run_audit_cascade` section).
- `tests/evals/test_cascade_fixture_convention.py` — 4 hermetic tests: (1) primary+auditor
  fixture emission at deterministic paths, (2) primary fixture provenance + "author" role,
  (3) auditor fixture provenance + "auditor" role, (4) independent `load_case` loadability.
- `tests/workflows/test_planner_cascade_fixture_golden.py` — 1 golden test for
  `planner_explorer_audit` cascade with `ExplorerReport` schema.
- `tests/workflows/test_slice_refactor_cascade_fixture_golden.py` — 1 golden test for
  `slice_worker_audit` cascade with `SliceResult` schema; uses `skip_terminal_gate=True`
  to mirror production wiring (`slice_refactor.py:1054`).
- `CHANGELOG.md` — entry under `[Unreleased]` citing KDR-011 + KDR-004 constraint carve-out.

### Gate results (cycle 1)

- `uv run pytest` — 1475 passed, 11 skipped (AIW_E2E gates), 0 failures.
- `uv run lint-imports` — 5 contracts kept, 0 broken.
- `uv run ruff check` — all checks passed.

### Deviations from spec

- None. The spec stated "no diff to production code" and none was made.
- `skip_terminal_gate=True` was added to the slice_refactor golden test to mirror the
  production wiring at `slice_refactor.py:1054`. The spec says "mirrors production wiring"
  which implies this flag; adding it is spec-conformant.

### Propagation status

Forward-deferrals as anticipated:

1. **`EvalRunner` cascade-fixture replay** — `_resolve_node_scope` enforces `<node>_validator`
   pair lookup not satisfied by cascade nodes. Deferred to `nice_to_have.md`.
2. **`<cascade_name>_verdict` capture** — verdict node is pure parse, no LLM call. If a future
   task adds an LLM verdict, the convention naturally extends.
3. **External-workflow cascade fixture convention** — KDR-013 workflows get this for free.
4. **Multi-tier cascade fixture layout** — deferred to a future task.

---

## Sr. Dev review (2026-04-29)
**Files reviewed:** `tests/evals/test_cascade_fixture_convention.py`, `tests/workflows/test_planner_cascade_fixture_golden.py`, `tests/workflows/test_slice_refactor_cascade_fixture_golden.py`, `evals/README.md`, `.claude/skills/ai-workflows/SKILL.md` | **Skipped:** `CHANGELOG.md`, `design_docs/` status flips (doc-only; Auditor already verified) | **Verdict:** SHIP

No BLOCK or FIX findings. Two advisories (A1: misleading docstring about dataset path bypass; A2: unused `calls` tracking in stub adapters). A1 being addressed in cycle 2 alongside the sr-sdet FIX.

---

## Sr. SDET review (2026-04-29)
**Test files reviewed:** `tests/evals/test_cascade_fixture_convention.py`, `tests/workflows/test_planner_cascade_fixture_golden.py`, `tests/workflows/test_slice_refactor_cascade_fixture_golden.py` | **Verdict:** FIX-THEN-SHIP

FIX: Dataset path segment untested — `root=tmp_path` bypasses `dataset_name`-append in `CaptureCallback.__init__:108`. The `root=None` production path is unexercised. Fix: add `test_capture_callback_root_none_uses_dataset_segment`. Bypass applied (locked decision above).

---

## Security review (2026-04-29)
T06 is documentation + hermetic tests only. No production code changed. All security checks passed (KDR-003, subprocess safety, no credential disclosure, wheel contents clean). **Verdict:** SHIP

---

## Cycle 2 — Audit (2026-04-29)

**Source task:** `task_06_eval_harness_fixture_convention.md`
**Audited on:** 2026-04-29
**Audit scope:** cycle 2 delta only — single-file change to `tests/evals/test_cascade_fixture_convention.py` addressing the terminal-gate sr-sdet FIX (root=None coverage gap) plus sr-dev advisory A1 (docstring bypass note).

### Design-drift check

No drift detected. Cycle 2 adds one hermetic test + four docstring tweaks; zero production code touched.

- `git status --short` → only `tests/evals/test_cascade_fixture_convention.py` differs from cycle 1 (still untracked since cycle 1 created it; net delta = +1 test + 4 docstring updates).
- `git diff --stat ai_workflows/ pyproject.toml uv.lock` → empty.
- KDR-003: no `anthropic` / `ANTHROPIC_API_KEY` introduction (verified via grep on the new test). PASS.
- KDR-004/009/011/013: no behaviour change; cycle 2 only widens hermetic test coverage. PASS.

### AC grading (cycle 2 delta)

| AC | Status | Notes |
|----|--------|-------|
| Terminal-gate FIX (sr-sdet, locked decision) | met | New test `test_capture_callback_root_none_uses_dataset_segment` instantiates `CaptureCallback` without `root=` (triggers `capture_callback.py:107-109` `root = default_evals_root() / dataset_name` branch); monkeypatches `AIW_EVALS_ROOT` (the env-var read by `storage.py:default_evals_root` line 41-47); calls `on_node_complete(...)`; asserts `result_path.is_relative_to(tmp_path / dataset / workflow / node)` — all four path segments pinned. Loads via `load_case` and pins `node_name`, `workflow_id`, `captured_from_run_id`. Test passes. |
| sr-dev advisory A1 (docstring bypass note) | met | Tests 1-4 each carry a one-liner: "Note: `root=tmp_path` bypasses the dataset-name prefix; on-disk path is `<root>/<workflow>/<node>/`" (lines 287-289, 344-346, 387-389, 438-440). Existing descriptions intact. |
| Spec AC #3 (4 hermetic tests pass) — superset coverage | met | Cycle 2 raises the file from 4 → 5 tests; original 4 still pass; the extra test is a strict superset of the documented `evals/README.md` convention. The spec text "4 hermetic tests" is not literally re-amended, but the issue file is the authoritative amendment per CLAUDE.md ("Issue file is authoritative amendment to spec") and the locked terminal-gate decision documented above mandates the addition. |
| Scope discipline | met | `git status` confirms ONLY `tests/evals/test_cascade_fixture_convention.py` was touched in cycle 2. No production code, no other test files, no docs, no spec, no CHANGELOG. |
| Gates clean | met | `uv run pytest` → 1478 passed (was 1477 in cycle 1; exactly +1 from new test), 11 skipped, 0 failures. `uv run lint-imports` → 5 contracts kept. `uv run ruff check` → all checks passed. |

### Critical sweep

- **Path correctness end-to-end traced:** `CaptureCallback(dataset_name=dataset, workflow_id=workflow, run_id=run_id)` (no `root` kwarg) → `capture_callback.py:107-109` `root = default_evals_root() / dataset_name`. With `monkeypatch.setenv("AIW_EVALS_ROOT", str(tmp_path))`, `default_evals_root()` returns `tmp_path` → `_root = tmp_path / dataset`. `_resolve_unique_path` calls `fixture_path(self._root, workflow_id, node_name, case_id)` → `tmp_path / dataset / workflow / node / case_id.json`. Test assertion is tight against this exact path.
- **Env-var alignment:** `AIW_EVALS_ROOT` is the canonical env-var read by `default_evals_root()`. No drift.
- **No status-surface drift:** spec `**Status:**` line, milestone README task-table row, and milestone README §Exit-criteria #9 all remain `✅ Complete (2026-04-29)` from cycle 1 close. No re-flip needed (cycle 2 is a coverage-only fix, not a re-completion).
- **Rubber-stamp check:** cycle 2 diff is ~50 lines (1 new test ~40 lines + 4 docstring tweaks ~10 lines); PASS verdict with zero HIGH/MEDIUM findings is appropriate — the locked terminal-gate decision was specific and the implementation matches verbatim.
- **Cycle-overlap check:** cycle 1 LOW-01 (cosmetic spec checkboxes) was resolved by Auditor at cycle 1 close; terminal-gate sr-sdet FIX is the only carry-over to cycle 2 and is now resolved. Zero finding-overlap; no loop spinning.

### Gate summary

| Gate | Command | Result |
|------|---------|--------|
| pytest (full suite) | `uv run pytest` | PASS (1478 passed, 11 skipped, 0 failures) |
| pytest (T06 file) | `uv run pytest tests/evals/test_cascade_fixture_convention.py -v` | PASS (5 passed) |
| lint-imports | `uv run lint-imports` | PASS (5 contracts kept) |
| ruff | `uv run ruff check` | PASS (all checks passed) |

### Findings

None. Cycle 2 cleanly resolves the cycle-1 terminal-gate FIX with no new issues introduced.

### Auditor close-out actions

1. Status flipped to `✅ PASS` at the top of this issue file.
2. Cycle 2 summary written at `runs/m12_t06/cycle_2/summary.md`.
3. No spec edits needed (status surfaces already at `✅ Complete (2026-04-29)` from cycle 1 close).
4. No new propagation entries — all cycle-1 forward-deferrals (`EvalRunner` cascade-replay → `nice_to_have.md` at M12 T07 close-out, etc.) remain on track.
