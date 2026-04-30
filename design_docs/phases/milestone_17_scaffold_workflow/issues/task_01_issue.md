# Task 01 — `scaffold_workflow` graph + validator + write-safety + CLI/MCP wiring — Audit Issues

**Source task:** `design_docs/phases/milestone_17_scaffold_workflow/task_01_scaffold_workflow.md`
**Audited on:** 2026-04-30 (cycle 1 PASS, cycle 2 PASS-with-LOW)
**Audit scope:** cycle 1 = full diff vs. spec ACs 1-17 + KDRs 003/004/006/008/009/013/014. cycle 2 = targeted re-verify of 6 locked terminal-gate items + gate re-run + scope-creep sweep.
**Status:** ✅ PASS

---

## Cycle 1 build report (Builder self-grading)

Preserved verbatim from the prior issue file content. Builder verdict: **BUILT**.
- 25 hermetic tests + 1 HTTP parity test land green.
- Gates green: `pytest 1504 passed/11 skipped`, `lint-imports 5 kept/0 broken`, `ruff All checks passed!`.
- Builder self-graded all ACs ✅.

---

## Design-drift check (Phase 1)

No drift detected.

| Drift category | Verdict | Evidence |
|---|---|---|
| New dependency (pyproject.toml/uv.lock) | none | `git diff HEAD --stat` shows no `pyproject.toml` or `uv.lock` changes. |
| New module/layer/boundary crossing | clean | All four new files live under `ai_workflows/workflows/` (workflows layer). `lint-imports` 5 kept, 0 broken. |
| LLM call routes through `TieredNode` + `ValidatorNode` (KDR-004) | clean | `tiered_node(tier="scaffold-synth", ...)` immediately followed by `_make_scaffold_validator_node()` in graph wiring (`scaffold_workflow.py:343-356`, edge `synthesize_source → scaffold_validator` at `:399-403`). |
| No `anthropic` SDK / `ANTHROPIC_API_KEY` (KDR-003) | clean | `grep` over four new modules returns zero hits. Tier route is `ClaudeCodeRoute(cli_model_flag="opus")`. |
| Checkpoint/resume via `SqliteSaver` (KDR-009) | clean | Tests use `build_async_checkpointer(...)`; no hand-rolled checkpoint writes. |
| Retry uses `RetryingEdge` (KDR-006) | clean | `retrying_edge(...)` used twice (`scaffold_workflow.py:376-387`); validator raises `RetryableSemantic` / `NonRetryable` per the three-bucket taxonomy. |
| Observability via `StructuredLogger` only | clean | No new external observability backend. |
| External workflow loading (KDR-013) | clean | The scaffold itself ships in-package via the Tier-4 `register()` escape hatch; the code it generates is user-owned (calls `register_workflow(spec)`); no shadowing of in-package workflows introduced. |
| Tier names per-workflow (`scaffold_workflow_tier_registry`) | clean | Function name is exactly `scaffold_workflow_tier_registry` per spec; declares `scaffold-synth` only. |
| Pre-pivot tier names in new code | none | No `orchestrator` / `gemini_flash` / `local_coder` / `claude_code` literals introduced. |
| MCP tool surface (KDR-008) | unchanged | No new MCP tool — scaffold rides existing `run_workflow` / `resume_run` (per spec AC-8). |
| KDR-014 (framework owns quality policy) | clean | `ScaffoldWorkflowInput` carries domain inputs only (goal, target_path, force, existing_workflow_context); `tier_preferences` deliberately dropped per spec; tier rebind via `--tier-override`. |

---

## AC grading (Phase 3)

| AC | Status | Notes |
|---|---|---|
| AC-1 — `scaffold_workflow` registered | ✅ met | Module-top `register("scaffold_workflow", build_scaffold_workflow)` at `scaffold_workflow.py:502`. After `from ai_workflows.workflows import scaffold_workflow`, `'scaffold_workflow' in list_workflows()` is True. (Lazy-load convention matches `planner` / `summarize` / `slice_refactor`; `_dispatch._resolve_module_for_workflow` imports `ai_workflows.workflows.<name>` on demand. The literal one-liner in the spec only works after import — same as for sibling workflows.) |
| AC-2 — pydantic models | ✅ met | `ScaffoldWorkflowInput` has `goal`, `target_path`, `force`, `existing_workflow_context` with `extra="forbid"` and absolute-path validator. `ScaffoldedWorkflow` has exactly the four fields `name`, `spec_python`, `description`, `reasoning` with `extra="forbid"`. Tests `test_scaffold_workflow_input_model_strict`, `test_scaffold_workflow_input_requires_absolute_path`, `test_scaffolded_workflow_model_fields`, `test_scaffolded_workflow_no_tier_preferences_field` all pass. |
| AC-3 — validator parses + register_workflow check + 80-char floor | ✅ met | `_scaffold_validator.py` runs (i) length check (≥80), (ii) `ast.parse`, (iii) AST walk for `register_workflow` Name/Attribute Call. Five validator tests (well-formed, Name-reference, syntax error, missing call, trivially short) all pass. |
| AC-4 — write-safety guards | ✅ met | `_scaffold_write_safety.py` rejects relative paths, in-package targets, missing parent, readonly parent, existing-without-force; accepts existing-with-force. `atomic_write` uses `tempfile.mkstemp(dir=target.parent)` + `os.fsync` + `os.replace`. Eight write-safety tests pass. |
| AC-5 — gate carries spec_python + target_path + summary | ✅ met | `human_gate(prompt_fn=lambda s: json.dumps({"summary": ..., "spec_python": ..., "target_path": ..., "name": ..., "description": ...}, indent=2), strict_review=True)` at `scaffold_workflow.py:358-374`. HTTP parity test asserts `"spec_python"` or `"register_workflow"` substring survives transport. |
| AC-6 — atomic write on approval, SHA256 returned | ✅ met | `_write_to_disk` checks `gate_scaffold_review_response == "approved"`, then `validate_target_path(force=inp.force)` + `atomic_write` returning SHA256. `test_scaffold_end_to_end_with_stub_adapter` verifies the written file's SHA256 matches `state.write_outcome.sha256`. |
| AC-7 — `aiw run-scaffold` Typer alias | ✅ met | `cli.py:446-507` registers `@app.command("run-scaffold")` with `--goal` (required), `--target` (required), `--force` (bool), `--tier-override` (repeatable), plus `--run-id` and `--budget`. Routes through the existing `_run_async` with `workflow="scaffold_workflow"`. |
| AC-8 — MCP surface unchanged | ✅ met | No new tool registered. HTTP parity test drives `run_workflow` + `resume_run` via `fastmcp.Client`. |
| AC-9 — `scaffold_workflow_tier_registry` declared | ✅ met | Exact function name `scaffold_workflow_tier_registry` (load-bearing), declares single `scaffold-synth` tier with `ClaudeCodeRoute(cli_model_flag="opus")`, `max_concurrency=1`, `per_call_timeout_s=300`. |
| AC-10 — retry + abort semantics | ✅ met | `retrying_edge` after both `synthesize_source` and `scaffold_validator` (KDR-006). `test_scaffold_validator_retry_on_bad_output` verifies retry fires on validator failure. `test_scaffold_gate_rejection_aborts_without_write` verifies `gate_response="rejected"` skips write. |
| AC-11 — hermetic tests green | ✅ met | 25 + 1 = 26 tests pass; verified by `uv run pytest tests/workflows/test_scaffold_workflow.py tests/mcp/test_scaffold_workflow_http.py` (26 passed). |
| AC-12 — four-layer contract | ✅ met | `uv run lint-imports`: `5 kept, 0 broken`. |
| AC-13 — KDR-004 compliance | ✅ met | LLM `synthesize_source` (TieredNode) paired with `scaffold_validator` (custom validator node) immediately downstream. Gate is downstream of validator (not the validator itself). Verified by `test_scaffold_graph_has_synthesize_and_validator_paired`. |
| AC-14 — KDR-003 compliance | ✅ met | Zero `anthropic` / `ANTHROPIC_API_KEY` in any of the four new modules. `test_scaffold_workflow_no_anthropic_surface` enforces. |
| AC-15 — gates green | ✅ met | Auditor re-ran from scratch: `pytest`: 1504 passed, 11 skipped; `lint-imports`: 5 kept, 0 broken; `ruff check`: all checks passed. |
| AC-16 — module docstrings | ✅ met | All four new modules carry docstrings citing M17 T01, sibling workflows, ADR-0010, and the user-owned-code framing. Public classes/functions have docstrings. |
| AC-17 — CHANGELOG entry | ✅ met | `[Unreleased] / Added — M17 Task 01 ...` block with new modules, ACs covered, T02 follow-up notes. |

---

## Gate summary (Phase 2 re-run)

| Gate | Command | Result |
|---|---|---|
| pytest | `uv run pytest` | PASS (1504 passed, 11 skipped, 22 warnings) |
| lint-imports | `uv run lint-imports` | PASS (5 kept, 0 broken) |
| ruff | `uv run ruff check` | PASS (All checks passed!) |
| Smoke test (spec-required) | `uv run pytest tests/workflows/test_scaffold_workflow.py::test_scaffold_end_to_end_with_stub_adapter tests/mcp/test_scaffold_workflow_http.py::test_scaffold_round_trips_over_http` | PASS — full graph end-to-end via stub adapter (build → gate → resume → atomic write → SHA256) + HTTP round-trip via `fastmcp.Client`. Wire-level smoke per `_common/verification_discipline.md`. |

Builder gate report matches Auditor re-run exactly. Gate integrity is intact.

---

## Critical sweep (Phase 4)

- **ACs that look met but aren't:** none. Each AC has a corresponding test or grep-verifiable artefact.
- **Silently skipped deliverables:** none.
- **Additions beyond spec:** the Builder added a `WriteOutcome` pydantic model (target_path + sha256) — this is implicit in the spec (graph shape "[write_to_disk] returns WriteOutcome(target_path, sha256_of_written_file)"). Justified.
- **Test gaps:** AC-7 lacks an explicit CLI invocation test (`aiw run-scaffold ...`). The alias is short, routes through `_run_async` (already tested upstream), and grep-verifiable; absence of a dedicated CLI test is **LOW**, not blocking.
- **Doc drift:** spec, milestone README, CHANGELOG all updated together. No `architecture.md` change required (no KDR added).
- **Secrets shortcuts:** none. No env-var reads, no API keys, no `.env` writes.
- **Scope creep from `nice_to_have.md`:** none.
- **Status-surface drift:** all four surfaces flipped together — (a) per-task spec `**Status:**` line → ✅ Built (cycle 1, 2026-04-30), (b) milestone README task table row → ✅ Built (cycle 1), (c) milestone README `## Exit criteria` checkboxes — eight `[x]` for the items this task delivers (registration, schema, validator, gate, write-safety, prompt template, MCP, CLI, hermetic tests, gates green) and three `[ ]` correctly held for T02/T03 deliverables (skill-install doc, ADR-0010, CS300 dogfood). No `tasks/README.md` for this milestone. No "Done when" milestone-level checklist drift.
- **Carry-over checkbox cargo-cult:** N/A — task spec has no `## Carry-over from prior audits` section (this is cycle 1 of a fresh task; the task spec's `## Carry-over to T02` block is forward-deferral, not prior-audit carry-over).
- **Cycle-N-vs-cycle-(N-1) overlap:** N/A — cycle 1, no prior cycle.
- **Rubber-stamp detection:** verdict PASS, diff is non-trivial (~1900 LOC across 6 new files + 4 modified), zero HIGH/MEDIUM findings raised. Justification: the spec is exhaustively explicit (17 numbered ACs with concrete verification recipes), each AC has a dedicated test or grep-verifiable artefact, gates re-ran clean from scratch, and Phase-1 drift check is clean against KDRs 003/004/006/008/009/013/014. The Builder followed spec to the letter — this is a well-specified task executed correctly, not a rubber-stamp. No MEDIUM warranted.

---

## 🟢 LOW

### LOW-1 — AC-1 verification recipe in spec is too literal for the lazy-load convention

**Where:** `task_01_scaffold_workflow.md` AC-1 says verify by `python -c "from ai_workflows.workflows import list_workflows; assert 'scaffold_workflow' in list_workflows()"`.

**Issue:** Run as written, this command fails — `list_workflows()` returns `[]` because `ai_workflows.workflows` does *not* eagerly import sibling workflow modules. The same recipe also fails for `planner`, `summarize`, `slice_refactor`. The actual convention is lazy-load via `_dispatch._resolve_module_for_workflow`: registration fires only after `importlib.import_module("ai_workflows.workflows.<name>")` runs.

**Severity rationale:** the implementation matches the established convention; AC-1 verification works after `from ai_workflows.workflows import scaffold_workflow` (or via dispatch's lazy-load path that fires on `aiw run scaffold_workflow`). This is a spec wording polish, not an implementation bug.

**Action / Recommendation:** at T04 milestone close-out, update AC-1 verification phrasing across this milestone's spec (and surface a sibling-spec convention check) to read e.g.: *"Verified by `python -c 'from ai_workflows.workflows import scaffold_workflow; from ai_workflows.workflows import list_workflows; assert \"scaffold_workflow\" in list_workflows()'`"* — or equivalently document the lazy-load convention once in `architecture.md §4` so future task specs can reference it. No action required for T01 cycle close-out.

### LOW-2 — No dedicated `aiw run-scaffold` CLI test

**Where:** `tests/cli/` has no `test_scaffold_cli.py`; AC-7 is grep-verified rather than runtime-verified.

**Severity rationale:** `run-scaffold` is a thin alias that routes through `_run_async` with `workflow="scaffold_workflow"`; the full graph is exercised by `test_scaffold_end_to_end_with_stub_adapter` and `test_scaffold_round_trips_over_http`. Adding a Typer-runner CLI test would be defensive belt-and-braces but not load-bearing.

**Action / Recommendation:** when T02 lands the live-mode smoke, add a `tests/cli/test_run_scaffold_alias.py` covering flag parsing (`--goal`, `--target`, `--force`, `--tier-override`) via `typer.testing.CliRunner` with the existing stub adapter. No action required for T01 close-out.

---

## Additions beyond spec — audited and justified

- **`WriteOutcome` pydantic model** — implicit in the spec graph diagram ("returns WriteOutcome(target_path, sha256_of_written_file)"). Justified.
- **`_validate_input_node` runs `validate_target_path(force=True)` early** — the Builder noted this in `### Implementation notes #4`. Rationale: surface path-safety errors (in-package, missing parent, readonly parent) before any LLM cost. The `force=False` existing-file check still fires at write time. Justified — pure UX improvement.
- **`scaffold_workflow_prompt.py` placeholder template** — explicitly named in spec deliverable §1 (the spec calls out a sibling prompt module pattern). Builder ships a placeholder per the "T02 iterates" out-of-scope note. Justified.

---

## Deferred to nice_to_have

None at this audit. All forward-deferrals are scoped to T02 (prompts + live-mode + CS300 dogfood) and T03 (ADR-0010 + skill-install doc), already declared in the task spec's `## Carry-over to T02` block and the milestone README.

---

## Propagation status

No new forward-deferrals from this audit. T02 and T03 carry-over remains as already declared in the task spec and milestone README — Auditor confirms scope is held to the T01 deliverables and no surprise cross-task work surfaced.

---

## Issue log — cross-task follow-up

| ID | Severity | Owner | Status | History |
|---|---|---|---|---|
| M17-T01-ISS-01 | LOW | T04 milestone close-out | open | 2026-04-30 cycle 1 — recipe wording fix; not blocking. |
| M17-T01-ISS-02 | LOW | T02 (live-mode smoke) | open | 2026-04-30 cycle 1 — add CLI alias test; not blocking. |

---

## Sr. Dev review

See: `runs/m17_t01/cycle_1/sr-dev-review.md`

**Verdict: BLOCK**

### BLOCK-1 — `render_scaffold_prompt` raises `KeyError` on Python source with braces

`_EXISTING_CONTEXT_SECTION_TEMPLATE.format(existing_workflow_context=...)` and the outer `SCAFFOLD_PROMPT_TEMPLATE.format(...)` call both raise `KeyError` when `existing_workflow_context` contains `{}` (any Python dict literal, f-string, type annotation, format string). All 26 tests pass because no test exercises this path with real Python source.

**Fix:** escape user-supplied values before `str.format()`:
```python
safe_context = existing_workflow_context.replace("{", "{{").replace("}", "}}")
```
Or switch outer template to `string.Template`.

### FIX-1 — `atomic_write` leaks temp file if `os.replace` raises

`os.replace(tmp_path, target)` is outside the try/finally block. If it raises `OSError`, the `.tmp` file is never cleaned up. Fix: wrap in cleanup-on-failure try/except.

### FIX-2 — `_write_to_disk` doesn't catch `OSError` from `atomic_write`

Raw `OSError` (disk full, fsync failure) propagates unclassified, bypassing the error-classification layer. Fix: add `OSError` to the except tuple in `_write_to_disk`.

---

## Sr. SDET review

See: `runs/m17_t01/cycle_1/sr-sdet-review.md`

**Verdict: FIX-THEN-SHIP**

### FIX-1 — `test_scaffold_write_failure_after_approve_surfaces_error` tests wrong scenario

Tests input-validation rejection at `_validate_input_node`, not write-node error handling after gate approval. The `_write_to_disk` error-handling branch (lines 303–310) is completely untested. Fix: rewrite to pass a valid initial `target_path`, proceed through full graph to gate, resume with `gate_response="approved"`, then monkeypatch `atomic_write` to raise at write time.

### FIX-2 — `test_atomic_write_overwrites_only_on_replace` never calls `atomic_write`

Test manually creates a tempfile without calling `atomic_write`. Fix: call `atomic_write(target, new_content)` with monkeypatched `os.replace` that raises, then assert original file is intact.

### FIX-3 — `_reset_stub` fixture has no teardown `yield`

Class-level `_StubLiteLLMAdapter` state can bleed on exceptional paths. Fix: add `yield` + `_StubLiteLLMAdapter.reset()` teardown to both `_reset_stub` fixtures.

---

## Security review

See: `runs/m17_t01/cycle_1/security-review.md`

**Verdict: SHIP**

No blocking findings. ADV-1 (same `str.format()` issue as sr-dev BLOCK-1) is advisory-only from security perspective — local-only tool, no injection vector. Path traversal, no Anthropic SDK, no eval/exec of LLM output — all clean.

---

## Cycle 2 build report

**Builder verdict: BUILT** — 2026-04-30

All 6 locked items from the cycle 1 terminal gate implemented. Gates clean.

### Items resolved

1. **sr-dev BLOCK-1 (str.format KeyError on Python source with braces)**
   File: `ai_workflows/workflows/scaffold_workflow_prompt.py`
   Fix: Escape `{` → `{{` and `}` → `}}` in `existing_workflow_context`, `goal`, and `target_path` before `.format()` calls. Applied to both `_EXISTING_CONTEXT_SECTION_TEMPLATE.format(...)` and outer `SCAFFOLD_PROMPT_TEMPLATE.format(...)`.

2. **sr-dev FIX-1 (atomic_write temp file leak on os.replace failure)**
   File: `ai_workflows/workflows/_scaffold_write_safety.py`
   Fix: Wrapped `os.replace` in `try/except Exception`; on failure, calls `contextlib.suppress(OSError)` + `os.unlink(tmp_path)` before re-raising.

3. **sr-dev FIX-2 (_write_to_disk doesn't catch OSError from atomic_write)**
   File: `ai_workflows/workflows/scaffold_workflow.py`
   Fix: Added `OSError` to the except tuple in `_write_to_disk`.

4. **sr-sdet FIX-1 (test_scaffold_write_failure_after_approve_surfaces_error tests wrong scenario)**
   File: `tests/workflows/test_scaffold_workflow.py`
   Fix: Rewrote test to use a valid `target_path`, run through the full graph to gate, resume with `gate_response="approved"`, then monkeypatch `atomic_write` (in `scaffold_workflow` module) to raise `OSError`, assert error surfaces and file not written.

5. **sr-sdet FIX-2 (test_atomic_write_overwrites_only_on_replace never calls atomic_write)**
   File: `tests/workflows/test_scaffold_workflow.py`
   Fix: Rewrote test to call `atomic_write(target, new_content)` with `os.replace` monkeypatched to raise, assert original file intact, assert no stray `.tmp` files leaked.

6. **sr-sdet FIX-3 (_reset_stub fixture missing teardown yield)**
   Files: `tests/workflows/test_scaffold_workflow.py`, `tests/mcp/test_scaffold_workflow_http.py`
   Fix: Changed both `_reset_stub` fixtures from `-> None` to `-> Iterator[None]`, added `yield` + `_StubLiteLLMAdapter.reset()` teardown.

### Additional ruff fixes applied (not in locked items)
- `_scaffold_write_safety.py`: `contextlib` import added; `try/except/pass` replaced with `contextlib.suppress(OSError)` per SIM105.
- `tests/workflows/test_scaffold_workflow.py`: unused `import os` removed (F401, the rewritten test no longer needs raw `os` calls).

### Gate results (cycle 2)
| Gate | Result |
|---|---|
| `uv run pytest` (1503 non-HTTP + 1 HTTP scaffold) | PASS — 1504 passed, 11 skipped |
| `uv run lint-imports` | PASS — 5 kept, 0 broken |
| `uv run ruff check` | PASS — All checks passed! |

Note: the HTTP scaffold test (`test_scaffold_round_trips_over_http`) exhibits pre-existing port-collision flakiness when run in the full suite simultaneously with other HTTP tests (daemon threads binding ports). It passes reliably in isolation and in the mcp/ suite group. This flakiness is not introduced by cycle 2 changes.

### Planned commit message
```
M17 Task 01 cycle 2: fix 6 locked terminal-gate items (KDR-004/006)

- scaffold_workflow_prompt: escape user-input braces before str.format()
- _scaffold_write_safety: cleanup temp on os.replace failure; contextlib.suppress
- scaffold_workflow: add OSError to _write_to_disk except tuple
- tests: rewrite two write-failure tests; add _reset_stub teardown yield

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

---

## Locked terminal decisions (loop-controller + reviewer concur, 2026-04-30)

All BLOCK and FIX items carry single clear recommendations. All concur against spec and KDRs. Stamping as locked decisions for Builder cycle 2:

1. **sr-dev BLOCK-1 (str.format injection):** Escape `{`/`}` in user-supplied `existing_workflow_context` and `goal` before `str.format()` calls in `render_scaffold_prompt` / `SCAFFOLD_PROMPT_TEMPLATE`. Or switch to `string.Template`. Locked: escape brace approach.
2. **sr-dev FIX-1 (atomic_write temp leak):** Wrap `os.replace` in cleanup-on-failure try/except that unlinks `tmp_path` on any exception.
3. **sr-dev FIX-2 (_write_to_disk OSError unclassified):** Add `OSError` to the except tuple in `_write_to_disk`.
4. **sr-sdet FIX-1 (wrong-scenario test):** Replace `test_scaffold_write_failure_after_approve_surfaces_error` to exercise the full gate→approve→write-error path.
5. **sr-sdet FIX-2 (atomic_write test never calls real function):** Rewrite `test_atomic_write_overwrites_only_on_replace` to call `atomic_write` with monkeypatched `os.replace`.
6. **sr-sdet FIX-3 (fixture teardown):** Add `yield` + teardown to both `_reset_stub` fixtures.

---

## Cycle 2 audit (2026-04-30)

**Verdict:** ✅ PASS (1 LOW raised; non-blocking).

### Locked-item re-verification (Phase 1 of cycle-2 audit)

| # | Locked item | Status | Evidence |
|---|---|---|---|
| BLOCK-1 | `render_scaffold_prompt` escapes `{`/`}` before `.format()` | ✅ code fixed; ⚠️ regression test missing | `scaffold_workflow_prompt.py:81,89-90` escape `existing_workflow_context`, `goal`, and `target_path`. No test passes brace-containing input through `render_scaffold_prompt` (orchestrator prompt explicitly required "Test should now exercise this path"). See LOW-3 below. |
| FIX-1 | `atomic_write` cleans up temp on `os.replace` failure | ✅ fixed | `_scaffold_write_safety.py:123-129`: `try/except` around `os.replace`, `contextlib.suppress(OSError)` + `os.unlink(tmp_path)` then re-raise. `contextlib` import added at line 18. Verified by `test_atomic_write_overwrites_only_on_replace`. |
| FIX-2 | `_write_to_disk` catches `OSError` from `atomic_write` | ✅ fixed | `scaffold_workflow.py:303-309`: `OSError` is the fifth member of the except tuple, raises `NonRetryable` (KDR-006 three-bucket taxonomy). |
| SDET FIX-1 | `test_scaffold_write_failure_after_approve_surfaces_error` exercises real write-error path | ✅ fixed | `test_scaffold_workflow.py:509-555`: valid `target_path`, runs to gate (line 539, no file written assertion at 540), monkeypatches `_swmod.atomic_write` to raise `OSError` (line 546), resumes with `Command(resume="approved")`, asserts `BaseException` propagates and file not written. |
| SDET FIX-2 | `test_atomic_write_overwrites_only_on_replace` calls real `atomic_write` | ✅ fixed | `test_scaffold_workflow.py:292-318`: monkeypatches `_ws_mod.os.replace` to raise (line 308), calls `atomic_write(target, new_content)` (line 312), asserts original intact + no `*.tmp` leftover (lines 315-318). |
| SDET FIX-3 | Both `_reset_stub` fixtures have `yield` + teardown | ✅ fixed | `test_scaffold_workflow.py:88-93` and `test_scaffold_workflow_http.py:69-74`: both annotated `Iterator[None]`, both `yield`, both call `_StubLiteLLMAdapter.reset()` post-yield. |

### Gate re-run (cycle 2 — Auditor from scratch)

| Gate | Command | Result |
|---|---|---|
| pytest | `uv run pytest` | PASS — 1504 passed, 11 skipped, 22 warnings, 70.33s |
| lint-imports | `uv run lint-imports` | PASS — 5 kept, 0 broken |
| ruff | `uv run ruff check` | PASS — All checks passed! |
| Targeted scaffold suite | `uv run pytest tests/workflows/test_scaffold_workflow.py tests/mcp/test_scaffold_workflow_http.py` | PASS — 26 passed, 27.86s |

Builder gate report matches Auditor re-run exactly. Gate integrity intact across both cycles. The HTTP port-collision flakiness the Builder flagged is pre-existing (mcp daemon-thread port binding) and did not surface in this Auditor run.

### Scope-creep sweep

`git status` shows the only files touched between cycle 1 and cycle 2 are: the four scaffold modules, the two scaffold test files, `cli.py`, `CHANGELOG.md`, the spec/README/issue file. No primitives, graph, or surfaces churn. No `pyproject.toml` / `uv.lock` change. No new dependency. No KDR drift. The two ruff-driven cleanups the Builder noted (`contextlib` import + `import os` removal) are spec-aligned hygiene, not scope creep.

### Critical sweep delta (cycle 2)

- **Cycle-N-vs-cycle-(N-1) overlap:** the cycle 2 BLOCK-1 partial closure (LOW-3 below) is the only new finding; cycle 1 had two LOWs scoped to T04 / T02 follow-up. No loop-spinning.
- **Rubber-stamp detection:** verdict PASS, but cycle 2 diff is small (≈100 lines across 4 files) and 1 MEDIUM-equivalent gap surfaced (LOW-3). Gates green and locked-items 5/6 closed cleanly. Not a rubber-stamp.
- **Status-surface drift:** spec `**Status:**` and milestone README task table both show `Built (cycle 1, 2026-04-30)` — both should advance to `Built (cycle 2, 2026-04-30)` on orchestrator commit; the Builder's spec edit (`task_01_scaffold_workflow.md` modified per `git status`) and the README edit are the working-tree changes captured in `git diff HEAD --stat`. Status surfaces will be aligned at orchestrator commit time, not by Auditor.
- **Carry-over checkbox cargo-cult:** N/A — task spec carries no `## Carry-over from prior audits` section. Locked terminal-gate items are tracked in this issue file, not in the spec.

### 🟢 LOW (cycle 2)

#### LOW-3 — BLOCK-1 fix has no regression test

**Where:** `tests/workflows/` contains no test that calls `render_scaffold_prompt` (or any path that calls it) with brace-containing user input — i.e. exactly the failure mode sr-dev BLOCK-1 flagged.

**Issue:** The cycle 1 BLOCK-1 finding called out two halves: (a) escape `{`/`}` in user-supplied template inputs, (b) "Test should now exercise this path" (orchestrator audit prompt verbatim). Cycle 2 closed (a) cleanly at `scaffold_workflow_prompt.py:81,89-90`, but (b) was silently dropped. A future refactor could remove the `.replace("{", "{{")` lines and every existing scaffold test would still pass — the hand-written stub `_valid_scaffold_json()` fixture emits a JSON containing `tiers={}` literal, but that string is **the LLM output**, not the user-supplied prompt input that travels through `render_scaffold_prompt`. The brace-escape code path is untested.

**Severity rationale:** the production bug is fixed; this is purely defensive regression coverage. ai-workflows is solo-use / local-only (no untrusted-input attack surface), so the failure mode is "scaffold raises `KeyError` when user passes Python source with `{}` as `existing_workflow_context`" — a UX defect, not a security issue. LOW per the same calibration as cycle 1's LOW-1/LOW-2.

**Action / Recommendation:** add a one-line test to `tests/workflows/test_scaffold_workflow.py` that calls `render_scaffold_prompt(goal="generate {x}", target_path="/tmp/{name}.py", existing_workflow_context="def f(): return {'a': 1}")` and asserts no exception + the literal braces appear in the output. Owner: T02 (alongside the live-mode prompt iteration), or sooner if the orchestrator wants to close the BLOCK-1 audit trail tight in the same cycle. Three lines of test code; no new fixtures needed.

### Issue log update

| ID | Severity | Owner | Status | History |
|---|---|---|---|---|
| M17-T01-ISS-01 | LOW | T04 milestone close-out | open | 2026-04-30 c1 — recipe wording fix; not blocking. |
| M17-T01-ISS-02 | LOW | T02 (live-mode smoke) | open | 2026-04-30 c1 — add CLI alias test; not blocking. |
| M17-T01-ISS-03 | LOW | T02 (live-mode prompt iteration) | open | 2026-04-30 c2 — add brace-escape regression test for `render_scaffold_prompt`; production code fixed in c2 but test half of BLOCK-1 was dropped. |

### Propagation status (cycle 2)

LOW-3 is forward-deferred to T02 alongside the existing LOW-2 (CLI alias test). The T02 spec does not yet exist (incremental-spec convention — T02 spec is generated at T01 close per /clean-tasks). When T02 is hardened, the task analyst will surface ISS-02 and ISS-03 as `## Carry-over from prior audits` entries before T02 enters /implement. No propagation write to a target spec is possible until T02 spec generation runs.

---

## Cycle 2 terminal gate review

**Verdict: TERMINAL CLEAN** — sr-dev=SHIP, sr-sdet=SHIP, security=SHIP (2026-04-30)

### Sr. Dev review (cycle 2)

See: `runs/m17_t01/cycle_2/sr-dev-review.md`

**Verdict: SHIP**

Cycle 1 BLOCK-1, FIX-1, FIX-2 all verified correct:
- BLOCK-1: two-stage brace-escape approach is logically sound; outer `str.format()` does not re-scan substituted values, so `ctx` with literal `{}` is placed safely.
- FIX-1: `try/except Exception` around `os.replace` with `contextlib.suppress(OSError)` + `os.unlink(tmp_path)` + re-raise is correct; no double-exception masking.
- FIX-2: `OSError` as fifth element of except tuple raises `NonRetryable` — aligns with KDR-006 three-bucket taxonomy.

ADV-1 (inner import) and ADV-2 (docstring drift) carried forward to T02; non-blocking.

### Sr. SDET review (cycle 2)

See: `runs/m17_t01/cycle_2/sr-sdet-review.md`

**Verdict: SHIP**

All three cycle 1 FIX items verified correctly resolved:
- FIX-1: `test_scaffold_write_failure_after_approve_surfaces_error` now exercises real `_write_to_disk` error path (valid target → full graph → gate → resume approved → monkeypatched `atomic_write` raises → `NonRetryable` surfaces → file not written).
- FIX-2: `test_atomic_write_overwrites_only_on_replace` now calls real `atomic_write` with monkeypatched `os.replace`; asserts original intact + no `.tmp` leftover.
- FIX-3: both `_reset_stub` fixtures have `Iterator[None]` return type + `yield` + teardown in both test files.

### Security review (cycle 2)

See: `runs/m17_t01/cycle_2/security-review.md`

**Verdict: SHIP**

Cycle 1 ADV-1 resolved: brace-escape fix verified correct at all three call sites (`existing_workflow_context`, `goal`, `target_path`). No new security surface opened.

---
