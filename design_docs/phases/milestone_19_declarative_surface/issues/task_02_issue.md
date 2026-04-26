# Task 02 — Spec → `StateGraph` compiler — Audit Issues

**Source task:** [../task_02_compiler.md](../task_02_compiler.md)
**Audited on:** 2026-04-26 (cycle 1) · re-audited 2026-04-26 (cycle 2)
**Audit scope:** `ai_workflows/workflows/_compiler.py` (new), `ai_workflows/workflows/spec.py` (modified — `Step.compile()` default + `register_workflow()` real-builder wiring), `ai_workflows/workflows/__init__.py` (cycle 2 — `_reset_for_tests()` extension), `tests/workflows/test_compiler.py` (new — 23 hermetic tests after cycle 2; 20 in cycle 1), `tests/workflows/test_spec.py` (two tests updated to reflect T02 behaviour), `CHANGELOG.md` `[Unreleased]` entry. Cross-referenced against ADR-0008, `architecture.md` §3 + §4.2 + §6 + §9 (KDR-002/003/004/006/008/009/013), the cited graph primitives (`tiered_node`, `validator_node`, `human_gate`, `retrying_edge`, `error_handler`, `checkpointer`), `_dispatch.py` lines 540–602 (compile site) + 245–290 (resolution helpers), the T01 issue file (predecessor), Builder's cycle-1 + cycle-2 reports, and the three task gates re-run from scratch on each cycle.
**Status:** ✅ PASS (cycle 2 — MEDIUM-1 + MEDIUM-2 + LOW-1 + LOW-3 resolved; LOW-2 + LOW-4 remain open as documented out-of-scope deferrals)

## Design-drift check

**Cycle 2 (2026-04-26 re-audit):** No new drift. The cycle-2 changes are scoped to the same `_compiler.py` + `__init__.py` files inside the workflows layer; no surface or eval imports added; no MCP wire shape change; no anthropic SDK touched; no hand-rolled retry loop introduced (MEDIUM-1 fix went *via* the existing `retrying_edge` factory — KDR-006 strengthened, not weakened); no hand-rolled checkpoint write (KDR-009 unchanged); user-owned-code boundary unchanged (KDR-013). One extra import-linter dependency (`RetryPolicy` from `ai_workflows.primitives.retry`) — `primitives → workflows` is a downward read-only direction, the same direction `RetryPolicy` was already imported in `__init__.py`. `lint-imports` reports `4 contracts kept, 0 broken` with 104 dependencies (one more than cycle 1's 103).

**Cycle 1 baseline:** No drift detected against the seven load-bearing KDRs or the four-layer rule.

- **Four-layer rule.** `_compiler.py` imports stdlib + `pydantic` + `langgraph` + `ai_workflows.graph.*` (`error_handler`, `human_gate`, `retrying_edge`, `tiered_node`, `validator_node`) + a `TYPE_CHECKING`-guarded import of `spec.py`. Lives in the workflows layer; `workflows → graph` is the permitted direction. No surface or evals imports. `lint-imports` reports 4 contracts kept, 0 broken (re-run from scratch this audit).
- **`spec.py` stays graph-free at import time.** The `_compiler` import inside `register_workflow()`'s function body is lazy — verified by `tests/workflows/test_registry.py::test_workflows_module_does_not_import_langgraph` (still green) and the new `tests/workflows/test_compiler.py::test_spec_module_does_not_import_graph_at_top_level`.
- **KDR-002 / KDR-008 (MCP wire surface).** No MCP imports added; no schema changes. `WorkflowSpec` remains pure data; the compiler emits a standard LangGraph `StateGraph` that flows through the existing `RunWorkflowOutput` shape unchanged.
- **KDR-003 (no Anthropic API).** No `anthropic` SDK import; no `ANTHROPIC_API_KEY` reference. `grep -rn "anthropic\|ANTHROPIC_API_KEY" ai_workflows/workflows/_compiler.py ai_workflows/workflows/spec.py` returns zero hits.
- **KDR-004 (validator pairing — by construction).** `_compile_llm_step` always emits two nodes (`<id>_call` + `<id>_validate`) and an unconditional edge between them. `_assert_kdr004_invariant` runs at compile time and raises `ValueError` if any `LLMStep`-emitted `CompiledStep` does not have exactly two nodes with distinct entry/exit ids. Verified by `test_compile_llm_step_pairs_validator_by_construction` and `test_kdr004_invariant_raises_if_llmstep_subclass_drops_validator`.
- **KDR-006 (three-bucket retry via `RetryingEdge`).** `LLMStep.retry` (a primitives-layer `RetryPolicy`, not a parallel class — Q1 lock preserved) is passed verbatim to `retrying_edge(policy=...)`. No bespoke try/except retry loops in the compiler. `wrap_with_error_handler` wraps both call and validate nodes so bucket exceptions become state writes the edge can route on.
- **KDR-009 (LangGraph `SqliteSaver` checkpoints).** The synthesised `StateGraph` compiles via `builder().compile(checkpointer=...)` at `_dispatch.py:554` unchanged. Verified by `test_compiled_stategraph_compiles_with_checkpointer` (compiles against a real `AsyncSqliteSaver` from `build_async_checkpointer`). No hand-rolled checkpoint writes; no checkpoint-format changes.
- **KDR-013 (user code is user-owned).** `TransformStep.fn` and custom `Step.execute()` bodies are wrapped without inspection. `_compile_transform_step` and `_compile_custom_step` simply `await step.fn(state)` / `await step.execute(state)`.
- **External workflow loading + register-time collision check.** Unchanged. `register_workflow()` defers to `register(spec.name, builder)`; the existing collision guard fires.
- **Workflow tier names.** `WorkflowSpec.tiers` is required and provided per-spec; no pre-pivot tier names appear in `_compiler.py`.
- **MCP tool surface.** Unchanged.

ADR-0008 §Step taxonomy + §Extension model: all five built-in step types compile; the locked Q4 default `compile()` (delegates to `_default_step_compile` / `_compile_custom_step`) ships, so Tier 3 custom steps that only override `execute()` get a working compile path.

## AC grading

| AC | Status | Notes |
| -- | ------ | ----- |
| AC-1 — `_compiler.py` exposes `compile_spec`, `CompiledStep`, `GraphEdge` | ✅ PASS | All three are exported via `__all__` and importable. `CompiledStep` is a dataclass with `entry_node_id`, `exit_node_id`, `nodes`, `edges`. `GraphEdge` is a dataclass with `source`, `target`, `condition`, plus an addition-beyond-spec `fanout_targets: list[str]` field needed for `add_conditional_edges` Send-pattern wiring (justified — see Additions). `compile_spec(spec) -> Callable[[], StateGraph]` matches the existing `WorkflowBuilder` shape. Verified by `test_compiler_public_surface_importable`. |
| AC-2 — every built-in step type implements `Step.compile()` returning a non-empty `CompiledStep` | ✅ PASS | `_compile_llm_step`, `_compile_validate_step`, `_compile_gate_step`, `_compile_transform_step`, `_compile_fan_out_step` all return a `CompiledStep` with at least one node + correct entry/exit ids. The `Step` base-class `compile()` default (delegates to `_default_step_compile` → `_compile_custom_step`) ships per locked Q4 so custom Tier 3 steps that override only `execute()` work. Tests `test_compile_llm_step_pairs_validator_by_construction`, `test_compile_gate_step_emits_terminal_gate_id`, `test_compile_transform_step_runs_callable`, `test_compile_fan_out_step_dispatches_per_element`, `test_compile_custom_step_default_compile_wraps_execute` all green. |
| AC-3 — KDR-004 enforced by construction; `_assert_kdr004_invariant` runs at compile time | ✅ PASS | `_compile_llm_step` returns a `CompiledStep` with exactly 2 nodes; `_assert_kdr004_invariant` runs in `compile_spec`'s builder closure and raises on shape violations (wrong node count, entry == exit). Both happy + failure paths covered by `test_compile_llm_step_pairs_validator_by_construction` and `test_kdr004_invariant_raises_if_llmstep_subclass_drops_validator`. |
| AC-4 — KDR-006 retry semantics preserved; `RetryPolicy` plumbed without translation | ✅ PASS | `_compile_llm_step` passes `step.retry` directly to `retrying_edge(policy=...)` — no wrapping, no translation. `validator_node`'s `max_attempts` is set from `step.retry.max_semantic_attempts` (TA-LOW-07 — primitives' field name preserved; "deterministic" terminology absent from `_compiler.py`). `test_compile_llm_step_with_retry_wires_retrying_edge` exercises a deterministic-retry round-trip (invalid → valid stub script; asserts 2 LLM calls fired and workflow completes). See **MEDIUM-1** below for a related doc/code mismatch that does not affect AC verification but should be fixed in this cycle. |
| AC-5 — synthesised `StateGraph` compiles via `builder().compile(checkpointer=...)` unchanged | ✅ PASS | `test_compiled_stategraph_compiles_with_checkpointer` constructs a real `AsyncSqliteSaver` via `build_async_checkpointer(...)` and compiles the synthesised builder — succeeds. End-to-end smoke `test_compile_minimal_validate_only_spec` round-trips through `_dispatch.run_workflow` (which invokes line 554's `builder().compile(checkpointer=...)`) and reports `status="completed"`. |
| AC-6 — state class merges input + output schemas; output wins on collision | ✅ PASS | `_derive_state_class` collects `input_schema.model_fields` first, then `output_schema.model_fields` (overwriting on collision), then framework-internal keys (`run_id`, `last_exception`, `_retry_counts`, `_non_retryable_failures`, `_mid_run_tier_overrides`), then per-`LLMStep` intermediate `*_output` + `*_output_revision_hint` keys, then `Annotated[list, _append_reducer]` channels for any `FanOutStep.merge_field`. `test_compile_state_class_merges_input_and_output_schemas` exercises the collision rule (output `int` wins over input `str`). |
| AC-7 — `initial_state(run_id, inputs)` synthesised correctly | ✅ PASS | `compile_spec` defines `initial_state` as a closure: instantiates `spec.input_schema(**inputs)`, dumps to `state`, seeds `run_id`, then sets every `output_schema` field to `None` via `setdefault`. Attached to the synthetic module under `sys.modules["ai_workflows.workflows._compiled_<name>"]` so `_dispatch._build_initial_state` finds it via `getattr(module, "initial_state")`. `test_compile_initial_state_hook_signature` covers the full shape. |
| AC-8 — `FINAL_STATE_KEY` resolved as first field of `output_schema`; empty schema raises | ✅ PASS | `compile_spec` reads `list(spec.output_schema.model_fields)[0]`. Empty-output guard raises `ValueError("…has no fields…")` at compile-time (which is registration time because `register_workflow` calls `compile_spec` synchronously). Both paths covered: `test_compile_final_state_key_is_first_output_field` + `test_compile_empty_output_schema_raises`. |
| AC-9 — `FanOutStep` Send-pattern wiring (dispatch → branch → merge) | ✅ PASS *(with caveat)* | `_compile_fan_out_step` emits three nodes (`<id>_dispatch`, `<id>_branch`, `<id>_merge`) and a `Send`-based `add_conditional_edges` wiring (the `fanout_targets` field on `GraphEdge` is what plumbs the third positional arg to `add_conditional_edges`). Sub-graph compiled from `sub_steps` runs per branch via `compiled_sub.ainvoke(state)` inside `_branch_node`; results accumulate via the `merge_field` `Annotated[list, _append_reducer]` channel on the parent state. `test_compile_fan_out_step_dispatches_per_element` exercises a 3-element fan-out end-to-end. The unknown-iter-field warning path is covered by `test_compile_unknown_field_in_fan_out_iter_field_warns`. **Caveat:** the spec defers M8/M10 fault-tolerance overlay (`_mid_run_tier_overrides` carry, `CircuitOpen` routing, hard-stop terminal) per locked Q5; T02's basic Send-pattern is correct for the M19 scope. |
| AC-10 — `register_workflow(spec)` wires the compiler; end-to-end smoke succeeds | ✅ PASS | `register_workflow` calls `compile_spec(spec)` (lazy import) and registers the resulting builder. `test_compile_minimal_validate_only_spec` is the smoke: registers a `WorkflowSpec` with one `ValidateStep`, dispatches via `_dispatch.run_workflow`, asserts `status="completed"`. |
| AC-11 — layer rule preserved; `lint-imports` 4 contracts kept | ✅ PASS | `uv run lint-imports` reports `Contracts: 4 kept, 0 broken` (re-run from scratch). `_compiler.py` imports `ai_workflows.graph.*` per the permitted `workflows → graph` direction. The lazy `_compiler` import inside `register_workflow()` keeps `spec.py` graph-free for callers that only need the data classes — verified by `test_workflows_module_does_not_import_langgraph` (full import graph runs with `langgraph` masked to `None`) and `test_spec_module_does_not_import_graph_at_top_level`. |
| AC-12 — all `tests/workflows/test_compiler.py` green; <2s wall-clock | ✅ PASS | 20 tests pass in **1.42 s** (re-measured this audit). Hermetic — uses `_StubLiteLLMAdapter` monkey-patched onto `tiered_node_module.LiteLLMAdapter`, plus `tmp_path` + `AIW_CHECKPOINT_DB` / `AIW_STORAGE_DB` env redirects so no filesystem leakage. Registry isolation autouse fixture wraps each test. |
| AC-13 — existing register(name, build_fn) workflows unaffected; zero regression | ✅ PASS | `tests/workflows/test_planner_graph.py` + `tests/workflows/test_slice_refactor_e2e.py` re-run cleanly (12 passed in 1.78 s). Full workflow test directory: 210 passed, 0 failed. The two `test_spec.py` updates (custom-step compile returns `CompiledStep`; `register_workflow` builder returns `StateGraph`) are minimal and justified — see "Additions beyond spec". `test_existing_register_escape_hatch_unaffected` covers the Tier 4 path explicitly. |
| AC-14 — module + class/function docstrings cite M19 T02 + ADR-0008 + KDR-004/006/009 | ✅ PASS | `_compiler.py` module docstring cites M19 T02, ADR-0008, KDR-004, KDR-006 (with explicit `max_semantic_attempts` field-name note per Q1 + TA-LOW-07), KDR-009. Public class docstrings (`CompiledStep`, `GraphEdge`) document role + extension-model context. `compile_spec` docstring documents the builder contract + KDR-009 reference + raise condition. Per-helper docstrings document each step type's compile shape. |
| AC-15 — CHANGELOG entry under `[Unreleased]` matches Deliverable 9 | ✅ PASS | `### Added — M19 Task 02: Spec → StateGraph compiler (2026-04-26)` under `[Unreleased]` lists the three required bullets (compiler module + responsibilities, per-step `compile()` implementations, `register_workflow` wiring) plus the test bullet. KDR citations included. Carry-over absorption (TA-LOW-07 + TA-LOW-10) noted in the entry. Keep-a-Changelog vocabulary only. |
| AC-16 — gates green on both branches | ✅ PASS (on `design_branch`; T08 owns the `main` propagation) | Cycle 2 re-run: `uv run pytest`: 682 passed, 9 skipped, 0 failed in 29.46s (3 new tests vs. cycle 1; total compiler tests now 23). `uv run lint-imports`: 4 contracts kept, 0 broken. `uv run ruff check`: all checks passed. Cycle-1 transient flake (LOW-2) did not reproduce on the cycle-2 run. Cross-branch propagation to `main` is T08's release ceremony job. |
| Carry-over TA-LOW-07 — "deterministic" terminology aligned with `max_semantic_attempts` | ✅ PASS | `grep -n "deterministic" ai_workflows/workflows/_compiler.py` returns zero hits. The retry path uses `step.retry.max_semantic_attempts` consistently. Module docstring + helper docstrings explicitly cite `max_semantic_attempts` per primitives' field naming. |
| Carry-over TA-LOW-10 — `_dispatch.run_workflow` reference (no leading underscore on the function) | ✅ PASS | `_compiler.py:38` cites `_dispatch.run_workflow` (correct) and `_dispatch.py:554` (the actual line number for `builder().compile(checkpointer=...)`). The synthetic-module pattern is consistent with how `_dispatch._import_workflow_module` resolves builder modules via `sys.modules[builder.__module__]`. |

**Cycle 2:** 16 ACs PASS (AC-16 flipped to PASS on `design_branch`; the cross-branch piece is T08's release ceremony). All cycle-1-graded ACs remain met functionally; cycle-2 fixes addressed the four findings inside their scope (MEDIUM-1, MEDIUM-2, LOW-1, LOW-3 → RESOLVED) without regressing any ACs. LOW-2 + LOW-4 remain open as documented out-of-scope deferrals (orchestrator-confirmed).

## 🔴 HIGH

*None.* The compiler is functionally correct for the M19 in-scope step taxonomy + Q1–Q4 locks; KDR-004/006/009/013 are upheld; layer rule preserved; smoke green.

## 🟡 MEDIUM

### MEDIUM-1 — `LLMStep.retry=None` doc/code mismatch: docstring says "default `RetryPolicy()`", compiler skips `retrying_edge` entirely — RESOLVED 2026-04-26 (cycle 2)

**Cycle 2 status — RESOLVED.** User locked Option 1 (default-on retry). Builder edits verified at `ai_workflows/workflows/_compiler.py:436-459`:

```python
policy: RetryPolicy = step.retry if step.retry is not None else RetryPolicy()

call_node = tiered_node(...)
validator_node(
    ...,
    max_attempts=policy.max_semantic_attempts,
)
...
edge_fn = retrying_edge(
    on_transient=call_node_id,
    on_semantic=call_node_id,
    on_terminal=END,
    policy=policy,
)
```

The `retrying_edge` is now **always** wired (no `if step.retry is not None` guard); when `step.retry is None`, the compiler instantiates `RetryPolicy()` whose primitives-layer defaults are `max_transient_attempts=3, max_semantic_attempts=3` (verified at `ai_workflows/primitives/retry.py:114-115`). `validator_node.max_attempts` reads from `policy.max_semantic_attempts` so the two budgets agree (no split-brain). Docstring on `spec.py:188-189` (*"Optional per-step retry budget. When `None` the compiler uses the default `RetryPolicy()`."*) is now factually correct.

**Regression test:** `test_compile_llm_step_with_retry_none_wires_default_retry_policy` (cycle-2 addition) registers a spec with `retry=None`, scripts the stub adapter to emit invalid JSON then valid JSON, and asserts both `_StubLiteLLMAdapter.call_count == 2` (semantic retry consumed once) and `result["status"] == "completed"`. Re-ran the test in isolation post-audit: PASSED in 0.10 s.

**Cycle-1 finding text preserved below for audit history.**

---

**Where (cycle 1):**
- Docstring claim: `ai_workflows/workflows/spec.py:188-189` — *"Optional per-step retry budget. When `None` the compiler uses the default `RetryPolicy()`."*
- Actual compiler behaviour: `ai_workflows/workflows/_compiler.py:442-459` — `if step.retry is not None: …; else: <no retrying_edge>`. The `validator_node` constructor receives `max_attempts=3` (its own default) only when `step.retry is None`, but the `retrying_edge` is **not** wired, so transient `RetryableTransient` exceptions raised by `tiered_node` propagate as workflow errors instead of looping back via the policy's `max_transient_attempts`.

**Why it matters:** A spec author reading the docstring on `LLMStep.retry` would expect that omitting `retry=` still gets them the default three-bucket retry behaviour (consistent with KDR-006 framing). The current behaviour gives them a one-shot LLM call with semantic-only retry through `validator_node`'s built-in `max_attempts=3` exhaustion path — transient retries are silent no-ops. For solo-dev use against Gemini's free tier (frequent 429s), the missing transient retry is a real UX regression vs. the `register(name, build_fn)` escape hatch where authors hand-wire `retrying_edge` explicitly.

**Two reasonable fixes (option 1 locked by user 2026-04-26):**
1. **Match the docstring:** in `_compile_llm_step`, when `step.retry is None`, instantiate `RetryPolicy()` (default) and wire `retrying_edge` with it. Then update `validator_node`'s `max_attempts` to read from `policy.max_semantic_attempts` so the two budgets agree. This is the more spec-faithful path.
2. **Match the code:** edit the docstring on `LLMStep.retry` to read *"Optional per-step retry budget. When `None`, no `RetryingEdge` is wired — `ValidatorNode`'s built-in `max_attempts=3` provides semantic-retry exhaustion, but transient (`RetryableTransient`) failures propagate without retry. Set `retry=RetryPolicy(...)` to enable three-bucket retry semantics."* This is the more honest path; less convenient for spec authors.

**Action / Recommendation (cycle-1 framing — superseded by cycle-2 resolution):** Stop and ask the user; user picked option 1. Cycle 2 implemented option 1.

### MEDIUM-2 — `_resolve_tier_registry` lookup mismatch breaks workflows with hyphenated names — RESOLVED 2026-04-26 (cycle 2)

**Cycle 2 status — RESOLVED.** Builder edit verified at `ai_workflows/workflows/_compiler.py:241-250`:

```python
# MEDIUM-2 fix: store under the *raw* spec.name (not a sanitised variant)
# because _dispatch._resolve_tier_registry does:
#   getattr(module, f"{workflow}_tier_registry", None)
# where `workflow` is the registry key verbatim — e.g. "my-workflow" not
# "my_workflow".  setattr/getattr work on any string key, even ones that
# are not valid Python identifiers, so hyphens are fine here.
setattr(_synth_module, f"{spec.name}_tier_registry", _tier_registry_helper)
```

The previous `_safe_name = spec.name.replace("-", "_")` line is gone; the helper is now stored under the raw `spec.name` so `_dispatch._resolve_tier_registry`'s `getattr(module, f"{workflow}_tier_registry", None)` (`_dispatch.py:252`) resolves the helper for any registry key — including ones that are not valid Python identifiers. Re-verified by grepping `_compiler.py` for `_safe_name`: zero hits.

**Regression test:** `test_compile_workflow_name_with_hyphen_resolves_tier_registry` (cycle-2 addition) registers `WorkflowSpec(name="hyphen-name", steps=[LLMStep(tier="t", …)], tiers={"t": _tier()})`, scripts the stub adapter, dispatches via `run_workflow(workflow="hyphen-name", …)`, and asserts `result["status"] == "completed"` (would surface `NonRetryable("unknown tier")` if the tier registry weren't resolved). Re-ran the test in isolation post-audit: PASSED in 0.05 s.

**Cycle-1 finding text preserved below for audit history.**

---

**Where (cycle 1):**
- Compiler stores helper under sanitised name: `ai_workflows/workflows/_compiler.py:242-243` — `_safe_name = spec.name.replace("-", "_"); setattr(_synth_module, f"{_safe_name}_tier_registry", _tier_registry_helper)`.
- Dispatch reads under raw name: `ai_workflows/workflows/_dispatch.py:252` — `helper = getattr(module, f"{workflow}_tier_registry", None)` (uses the registry key verbatim, no sanitisation).

**Why it matters:** A spec author registering `WorkflowSpec(name="my-workflow", …)` (perfectly valid — `WorkflowSpec` does not validate name shape; `register()` accepts any string as a registry key) would have:
- Compiler stores helper as `my_workflow_tier_registry` (sanitised)
- Dispatch looks up `my-workflow_tier_registry` (not a valid Python identifier; `getattr` returns the default `None`)
- `_resolve_tier_registry` falls through to `return {}`, losing the spec's `tiers=` content
- Any `LLMStep` in the workflow then fails at `tiered_node` resolution with `NonRetryable(f"unknown tier: …")` because the empty tier-registry dict has no keys

The bug is silent at registration time and surfaces only on first dispatch.

## 🟢 LOW

### LOW-1 — `prompt_template` Tier 1 sugar synthesises an empty user-message list, sending the rendered prompt as `system` only — RESOLVED 2026-04-26 (cycle 2)

**Cycle 2 status — RESOLVED.** Builder edit verified at `ai_workflows/workflows/_compiler.py:420-434`:

```python
def _prompt_fn(state: dict) -> tuple[str | None, list[dict]]:
    """Synthesised prompt_fn from prompt_template (Tier 1 sugar).

    LOW-1 fix: returning ``(rendered, [])`` (system-only, no user
    message) causes Gemini's chat-completions API to reject the
    request ("at least one user message is required").  The correct
    shape is ``(None, [{"role": "user", "content": rendered}])``.
    """
    rendered = template.format(**state)
    return None, [{"role": "user", "content": rendered}]
```

`system=None` because the Tier 1 sugar template carries the entire user-facing instruction; authors who need an explicit system prompt drop to `prompt_fn=...` Tier 2 (verified by `test_compile_llm_step_prompt_fn_passthrough` still passing — Builder did not touch the escape-hatch path).

**Regression test:** `test_compile_llm_step_with_prompt_template_synthesizes_prompt_fn` (cycle-2 rewrite — old test asserted only the `CompiledStep` shape; new test asserts the synthesised prompt_fn's tuple shape directly). Asserts `system_val is None`, `len(messages) == 1`, `msg["role"] == "user"`, `msg["content"] == "hello world"`. Re-ran the test in isolation post-audit: PASSED in 0.04 s. The integration test `test_compile_llm_step_prompt_template_renders_at_invoke_time` still asserts the rendered string `"hello world"` reaches the stub adapter via the user-role message (the stub captures `messages[0]["content"]` first, falling back to `system` only when no user message is present — `tests/workflows/test_compiler.py:80-87`).

**Cycle-1 finding text preserved below for audit history.**

---

**Where (cycle 1):** `ai_workflows/workflows/_compiler.py:407-414` — the synthesised `_prompt_fn` returns `(rendered, [])`. Down at `tiered_node`, this becomes `system=rendered, messages=[]`; the LiteLLM adapter prepends `{"role": "system", "content": rendered}` and sends `messages=[{"role": "system", …}]` with no user-role message.

**Why it matters:** Gemini's chat-completions API rejects requests with no user message ("at least one user message is required").

### LOW-2 — One transient flake on the very first full pytest run (test isolation pollution from a sibling timing-dependent test) — STILL OPEN (out-of-scope deferral; not addressed in cycle 2 per orchestrator instruction)

**Cycle 2 status:** unchanged. Per orchestrator instruction LOW-2 was explicitly out of scope for cycle 2. The cycle-2 audit's full-suite `uv run pytest` invocation (run from scratch after the cycle-2 changes landed) reported `682 passed, 9 skipped, 0 failed in 29.46s` — no flake observed on this audit's run, but the underlying timing race in `tests/mcp/test_cancel_run_inflight.py` is unchanged. Continues to track as a flaky-test follow-up outside T02 scope.

**Where (cycle 1):** `tests/mcp/test_cancel_run_inflight.py::test_cancel_run_aborts_in_flight_task_and_flips_storage` failed once on the auditor's first `uv run pytest` invocation with the M19 T02 changes loaded; passed cleanly on three subsequent full-suite runs and on isolated invocation.

**Symptom (first run):** `fastmcp.exceptions.ToolError: no run found: run-inflight-cancel` — the cancel arrived before the dispatcher inserted the `runs` row.

**Why orthogonal to T02:** The test is a known timing race — it polls `_ACTIVE_RUNS` for 50 × 20 ms = 1 s waiting for the dispatcher to register, then races a cancel against the dispatcher's row insertion. Under load (the previous 670-test suite ran before this one), the registration sometimes lags. T02 changes are isolated to `_compiler.py` (new), `spec.py` (modified), `test_compiler.py` (new), `test_spec.py` (two minor edits), and (cycle 2) `__init__.py` (`_reset_for_tests` extension) + `CHANGELOG.md` — none of these modify dispatch, MCP, or the in-flight cancel path.

**Action / Recommendation:** Track separately as a flaky-test issue — not a T02 cycle-2 fix. The test could tighten its readiness check by polling for the storage row's existence (not just the `_ACTIVE_RUNS` entry) before firing the cancel. Owner: separate follow-up; not blocking T02 audit. Filed here for visibility because it surfaced during the T02 gate re-run.

### LOW-3 — Synthetic modules in `sys.modules["ai_workflows.workflows._compiled_*"]` accumulate across tests; `_reset_for_tests()` does not clear them — RESOLVED 2026-04-26 (cycle 2)

**Cycle 2 status — RESOLVED.** Builder edit verified at `ai_workflows/workflows/__init__.py:152-171`:

```python
def _reset_for_tests() -> None:
    """Clear the registry and any synthetic compiled-spec modules.

    LOW-3 fix: ...  We match conservatively: only keys with the exact
    ``_compiled_`` prefix inside our package namespace are removed, so unrelated
    ``sys.modules`` entries are never touched.
    """
    import sys

    _REGISTRY.clear()
    prefix = "ai_workflows.workflows._compiled_"
    stale = [k for k in sys.modules if k.startswith(prefix)]
    for key in stale:
        del sys.modules[key]
```

The pattern matches conservatively — only `sys.modules` keys with the exact `ai_workflows.workflows._compiled_` prefix are removed. The full prefix string (including the package namespace) makes accidental collisions with unrelated modules effectively impossible (no other ai-workflows module follows the `_compiled_*` naming). Materialised the matching key list before iterating so the loop doesn't mutate the dict it's iterating over.

**Regression test:** `test_reset_for_tests_clears_synthetic_compiled_modules` (cycle-2 addition) registers a spec, asserts `ai_workflows.workflows._compiled_cleanup_test_wf` is in `sys.modules`, calls `workflows._reset_for_tests()` explicitly (the autouse fixture also calls it but the explicit call exercises the contract), then asserts the key is gone. Re-ran the test in isolation post-audit: PASSED in 0.04 s.

**Spot-check on potential side effects:** the autouse `_reset_registry` fixture in `tests/workflows/test_compiler.py` (and `tests/workflows/test_spec.py`) calls `_reset_for_tests()` before AND after each test. The cycle-2 extension means `sys.modules` is now also pruned twice per test — full suite ran 682 passed / 9 skipped with no regression, confirming no test depends on a synthetic module surviving across the test boundary.

**Cycle-1 finding text preserved below for audit history.**

---

**Where (cycle 1):** `ai_workflows/workflows/_compiler.py:233-249` injects `sys.modules[f"ai_workflows.workflows._compiled_{spec.name}"]` on every `compile_spec` call. `ai_workflows/workflows/__init__.py:152-154` clears `_REGISTRY` only.

**Why LOW:** Today, test names are unique per spec (`validate_smoke`, `llm_kdr004`, `retry_test`, …) so the modules don't collide across tests. The accumulation is a small memory footprint and a debugging-confusion vector if a future test (or a real consumer's interactive session) reuses a workflow name.

### LOW-4 — `GateStep.compile` does not expose `strict_review` to the spec author — STILL OPEN (deferred; not addressed in cycle 2 per orchestrator instruction)

**Where:** `ai_workflows/workflows/_compiler.py:528-531` calls `human_gate(gate_id=step.id, prompt_fn=_prompt_fn)` without forwarding `strict_review`. The `human_gate` factory defaults `strict_review=False, timeout_s=1800` (per `ai_workflows/graph/human_gate.py:53-55`).

**Why LOW:** The architecture's gate semantics (§8.3) describe both strict and non-strict review with explicit policy choices. The current `GateStep` schema (in `spec.py`) does not surface a `strict_review` field, so all spec-authored gates inherit the non-strict default — different from the planner's `gate_review` (which uses strict review explicitly). Spec authors who need strict-review semantics (no timeout; only resume clears the gate) cannot get them through the spec API today; they must drop to the Tier 4 escape hatch.

**Why LOW (not MEDIUM):** No spec author has requested strict-review yet (`summarize` in T04 doesn't gate; CS-300 doesn't expose gates through the spec API). Surfaces only when the third-or-later in-tree-shape workflow lands.

**Action / Recommendation:** Defer to a future T01 spec-amendment or to the Q5 + H2 re-open trigger ("a second external workflow with conditional routing or sub-graph composition wants to use the spec API"). Add `strict_review: bool = False` (default matches today's compiled behaviour; non-breaking) to `GateStep` when a downstream consumer needs it. Owner: future M19+ task; not in T02 scope.

## Additions beyond spec — audited and justified

1. **`GraphEdge.fanout_targets: list[str]` field** (above the spec's `source / target / condition`). Required by LangGraph's `add_conditional_edges(source, condition, [target_list])` Send-pattern signature. Without this third arg, LangGraph cannot resolve the per-`Send` packet target. The compiler routes through `_add_edge_to_graph` which dispatches on `fanout_targets` populated → list-form `path_map`. Implementation detail of the fan-out path; no public-surface impact.
2. **`_default_step_compile` helper** in `_compiler.py:749-764` (additive to spec's "step types implement `compile()`"). The Q4 lock requires a default `compile()` body on `Step`; the spec mandates it but doesn't name an exact implementation. The Builder factored it into a helper so `Step.compile()`'s lazy `_compiler` import has a stable target. Minor refactor; no scope creep.
3. **`wrap_with_error_handler` integration on call + validate nodes** (spec mentions it implicitly via "preserves the existing wrap" but does not call it out as a deliverable). Required for the three-bucket taxonomy to ride state-channel writes through `RetryingEdge`'s router. Existing graph-layer pattern; not an addition-of-new-machinery, just a wiring choice.
4. **Per-`LLMStep` `*_output` + `*_output_revision_hint` annotations on the synthesised state class** (`_compiler.py:852-858`). Required because LangGraph's TypedDict-based reducer drops undeclared keys. `tiered_node` writes `f"{node_name}_output"` and the validator reads it; both keys must be declared. The spec describes the state-class derivation in terms of input/output schemas; the LLM intermediate-key declarations are a downstream necessity discovered at compile time.
5. **Two `tests/workflows/test_spec.py` updates** (custom-step `compile()` returns `CompiledStep`; `register_workflow` builder returns `StateGraph`). Both are minimal, targeted edits — they update assertions that pinned the T01 stub behaviour ("`NotImplementedError("compiler lands in M19 T02")`") to verify the now-real T02 contract. Coverage equal-or-better; T01's pre-condition assertions are no longer checked because that pre-condition no longer holds. Justified.
6. **`arbitrary_types_allowed=True` was already on `WorkflowSpec`** (T01). T02 inherits; no addition.
7. **Synthetic-module injection pattern** (`sys.modules[f"ai_workflows.workflows._compiled_{spec.name}"]`). Spec asks for `initial_state` + `FINAL_STATE_KEY` to be on "the synthesized workflow module" — this concretises that to a runtime-injected `types.ModuleType` with the right `__module__` stamping. Necessary to satisfy `_dispatch._import_workflow_module`'s `sys.modules[builder.__module__]` lookup contract (M16 T01 path for external workflows; same path used here for spec-compiled workflows). The pattern is unconventional but correct given the existing dispatch resolution.

All seven additions are within the spec's intent. No drive-by refactors; no scope creep into `nice_to_have.md` items.

## Gate summary

### Cycle 2 (2026-04-26 re-run)

| Gate | Command | Result |
| -- | ------ | ----- |
| Pytest (full suite, cycle-2 fresh run) | `uv run pytest` | **682 passed, 9 skipped, 0 failed in 29.46 s.** Three more tests than cycle 1 (regression coverage for MEDIUM-1, MEDIUM-2, LOW-3; LOW-1 swapped a shape-only test for a tuple-shape assertion). LOW-2 transient flake did not reproduce on this run. |
| Pytest (compiler tests only) | `uv run pytest tests/workflows/test_compiler.py -v` | 23 passed in 1.67 s. Still under the spec's <2 s target. |
| Import-linter | `uv run lint-imports` | `Contracts: 4 kept, 0 broken`. Analyzed 41 files, 104 dependencies (one extra dependency vs. cycle 1 — `RetryPolicy` import added to `_compiler.py` for the MEDIUM-1 default-on path). No new layer crossings. |
| Ruff | `uv run ruff check` | All checks passed. |
| MEDIUM-1 regression | `uv run pytest tests/workflows/test_compiler.py::test_compile_llm_step_with_retry_none_wires_default_retry_policy -v` | PASSED in 0.10 s. Stub fired twice (invalid → semantic-retry → valid); workflow completed. Default-on retry confirmed. |
| MEDIUM-2 regression | `uv run pytest tests/workflows/test_compiler.py::test_compile_workflow_name_with_hyphen_resolves_tier_registry -v` | PASSED in 0.05 s. Hyphenated `WorkflowSpec(name="hyphen-name")` dispatches without `NonRetryable("unknown tier")`. |
| LOW-1 regression | `uv run pytest tests/workflows/test_compiler.py::test_compile_llm_step_with_prompt_template_synthesizes_prompt_fn -v` | PASSED in 0.04 s. Synthesised prompt_fn returns `(None, [{"role": "user", "content": "hello world"}])` — the user-role message Gemini's API requires. |
| LOW-3 regression | `uv run pytest tests/workflows/test_compiler.py::test_reset_for_tests_clears_synthetic_compiled_modules -v` | PASSED in 0.04 s. Synthetic module `ai_workflows.workflows._compiled_cleanup_test_wf` removed from `sys.modules` after `_reset_for_tests()`. |
| Existing cycle-1 retry test (no regression) | `uv run pytest tests/workflows/test_compiler.py::test_compile_llm_step_with_retry_wires_retrying_edge -v` | PASSED. Cycle-2 default-on retry refactor did not regress the explicit-`RetryPolicy()` path. |
| Existing cycle-1 prompt_fn passthrough (no regression) | `uv run pytest tests/workflows/test_compiler.py::test_compile_llm_step_prompt_fn_passthrough -v` | PASSED. Tier 2 escape-hatch `prompt_fn=` path unchanged by LOW-1's Tier 1 sugar fix. |
| `grep -rn "_safe_name" ai_workflows/workflows/_compiler.py` | MEDIUM-2 backstop | Zero hits — sanitisation removed. |
| `grep -rn "anthropic\|ANTHROPIC_API_KEY" ai_workflows/workflows/_compiler.py ai_workflows/workflows/__init__.py` | KDR-003 backstop | Zero hits. |
| `grep -rn "deterministic" ai_workflows/workflows/_compiler.py` | TA-LOW-07 carry-over check | Zero hits. Terminology still aligned with `max_semantic_attempts`. |

All cycle-2 gates green. No new findings introduced by the cycle-2 changes.

### Cycle 1 (2026-04-26 first audit)

| Gate | Command | Result |
| -- | ------ | ----- |
| Pytest (full suite, cycle-1 first run) | `uv run pytest` | 678 passed, 9 skipped, **1 failed** (`test_cancel_run_inflight::test_cancel_run_aborts_in_flight_task_and_flips_storage`) in 29.32 s. **Pre-existing flaky timing race** — see LOW-2. Not introduced by T02; verified by three subsequent clean runs. |
| Pytest (full suite, runs 2–4) | `uv run pytest` | 679 passed, 9 skipped, 0 failed in 29.09–29.87 s. Clean. |
| Pytest (compiler tests only) | `uv run pytest tests/workflows/test_compiler.py -v` | 20 passed in 1.42 s. Under the spec's <2s target. |
| Pytest (workflow tests only) | `uv run pytest tests/workflows/` | 210 passed, 0 failed in 10.30 s. No regression on planner / slice_refactor tests. |
| Pytest (planner + slice_refactor regression spot-check) | `uv run pytest tests/workflows/test_planner_graph.py tests/workflows/test_slice_refactor_e2e.py` | 12 passed in 1.78 s. |
| Import-linter | `uv run lint-imports` | `Contracts: 4 kept, 0 broken`. Analyzed 41 files, 103 dependencies. |
| Ruff | `uv run ruff check` | All checks passed. |
| KDR-004 invariant assertion | Manual: read `_compile_llm_step` + `_assert_kdr004_invariant`; run `test_kdr004_invariant_raises_if_llmstep_subclass_drops_validator` | Invariant fires on shape violations; verified. |
| KDR-006 retry round-trip | Manual: run `test_compile_llm_step_with_retry_wires_retrying_edge` | Stub script `[invalid, valid]`; 2 LLM calls fired; workflow completed. Three-bucket taxonomy preserved. |
| KDR-009 checkpointer compose | Manual: run `test_compiled_stategraph_compiles_with_checkpointer` | Real `AsyncSqliteSaver` from `build_async_checkpointer`; `graph.compile(checkpointer=cp)` succeeds. |
| KDR-013 user-code boundary | Manual: read `_compile_transform_step` + `_compile_custom_step` | No body inspection; `await step.fn(state)` / `await step.execute(state)` only. |
| End-to-end smoke (Deliverable 8) | `uv run pytest tests/workflows/test_compiler.py::test_compile_minimal_validate_only_spec -v` | PASSED in 0.11 s. `register_workflow` → `_dispatch.run_workflow` → `status="completed"`. |
| Layer-rule isolation: spec.py stays graph-free | `uv run pytest tests/workflows/test_registry.py::test_workflows_module_does_not_import_langgraph` | PASSED. The `_compiler` import is correctly lazy. |
| `grep -rn "anthropic\|ANTHROPIC_API_KEY" ai_workflows/workflows/_compiler.py` | KDR-003 backstop | Zero hits. |
| `grep -rn "deterministic" ai_workflows/workflows/_compiler.py` | TA-LOW-07 carry-over check | Zero hits. Terminology aligned with `max_semantic_attempts`. |

All cycle-1 gates green. The single first-run pytest failure (LOW-2) is a pre-existing flaky timing race documented separately.

## Issue log — cross-task follow-up

| ID | Severity | Owner / next touch point | Status |
| -- | -------- | ------------------------ | ------ |
| M19-T02-ISS-01 | MEDIUM | T02 cycle-2 Builder — `LLMStep.retry=None` doc/code mismatch (MEDIUM-1). User locked Option 1 (default-on retry); cycle 2 wired `RetryPolicy()` defaults when `retry=None`. | RESOLVED 2026-04-26 (cycle 2) — `_compiler.py:436-459`; regression `test_compile_llm_step_with_retry_none_wires_default_retry_policy`. |
| M19-T02-ISS-02 | MEDIUM | T02 cycle-2 Builder — `_resolve_tier_registry` lookup mismatch with hyphenated workflow names (MEDIUM-2). Cycle 2 stored helper under raw `spec.name`. | RESOLVED 2026-04-26 (cycle 2) — `_compiler.py:241-250`; regression `test_compile_workflow_name_with_hyphen_resolves_tier_registry`. |
| M19-T02-ISS-03 | LOW | T02 cycle-2 Builder — Tier 1 sugar `prompt_template` synthesises empty `messages` list (LOW-1). Cycle 2 returned `(None, [user-role-message])`. | RESOLVED 2026-04-26 (cycle 2) — `_compiler.py:420-434`; regression `test_compile_llm_step_with_prompt_template_synthesizes_prompt_fn` (rewritten from cycle 1's shape-only test). |
| M19-T02-ISS-04 | LOW | Separate flaky-test issue — `test_cancel_run_inflight::test_cancel_run_aborts_in_flight_task_and_flips_storage` timing race (LOW-2). Not in T02 scope. | OPEN — orthogonal; cycle 2 explicitly out of scope per orchestrator. Did not reproduce on cycle-2 run. |
| M19-T02-ISS-05 | LOW | T02 cycle-2 Builder — `sys.modules` synthetic-module accumulation (LOW-3). Cycle 2 extended `_reset_for_tests` to prune `_compiled_*` keys. | RESOLVED 2026-04-26 (cycle 2) — `__init__.py:152-171`; regression `test_reset_for_tests_clears_synthetic_compiled_modules`. |
| M19-T02-ISS-06 | LOW | Future M19+ task — `GateStep.strict_review` not exposed (LOW-4). Defer. | DEFERRED — no current owner; cycle 2 explicitly out of scope per orchestrator. |

## Deferred to nice_to_have

*Not applicable.* No findings naturally map to `nice_to_have.md` entries. MEDIUM-1 and MEDIUM-2 were concrete defects in T02-cycle-1 source (now resolved); LOW-1 was a correctness fix for T02 (now resolved); LOW-3/LOW-4 are within the M19 spec API surface (LOW-3 resolved, LOW-4 deferred to a future M19+ task); LOW-2 is a sibling-test flake. None match an existing nice_to_have §.

## Propagation status

**Cycle 2 close-out (2026-04-26):** No findings forward-deferred to a specific future task by this audit. M19-T02-ISS-06 (LOW-4 — `GateStep.strict_review`) has no committed M19+ owner and remains DEFERRED with the original cycle-1 framing intact (re-open trigger: "a second external workflow with conditional routing or sub-graph composition wants to use the spec API" — the same Q5 + H2 trigger T07 records in `nice_to_have.md`). M19-T02-ISS-04 (LOW-2 — flaky `test_cancel_run_inflight`) is sibling-test housekeeping outside the M19 scope. No carry-over edits to other task specs are required by either OPEN finding.

**MEDIUM-1 user decision recorded (2026-04-26):** User locked Option 1 (default-on retry — `RetryPolicy()` defaults instantiated when `LLMStep.retry is None`). Cycle 2 implemented the chosen path. T05's `writing-a-workflow.md` rewrite documents the convenient default behaviour; CS-300 + future spec authors get retry-on-by-default. The Tier 4 `register(name, build_fn)` escape hatch retains its hand-wired-retry posture; the spec API is more forgiving than the escape hatch by design (KDR-006 framing — three-bucket retry is the path, and it's now wired by default for spec-authored workflows).

**Cycle 1 propagation footer preserved below for audit history.**

---

*Cycle 1 propagation footer:* Not applicable for this cycle. No findings forward-deferred to a specific future task. The other five issues all land on T02 cycle-2 (or are orthogonal) so no carry-over edits to other task specs are required.

---

## Security review (2026-04-26)

Reviewed against the threat model in `.claude/agents/security-reviewer.md`. Scope: `ai_workflows/workflows/_compiler.py`, `ai_workflows/workflows/spec.py`, `ai_workflows/workflows/__init__.py` (T02 additions only), `tests/workflows/test_compiler.py`. Built wheel + sdist from `uv build` and inspected contents. Ran targeted greps for all eight threat-model checks.

### Threat model check results

**1. Wheel contents** — `unzip -l dist/jmdl_ai_workflows-0.2.0-py3-none-any.whl` shows T02's additions (`_compiler.py`, updated `spec.py`, updated `__init__.py`) land under `ai_workflows/workflows/` as intended. No `.env*`, no `design_docs/`, no `runs/`, no `*.sqlite3`, no `.claude/`, no `.github/` in the wheel. The `ai_workflows/evals/` sub-package and `migrations/` are pre-existing wheel content (evals is shipped as runtime API per M7; migrations are force-included per M13 T01 note in `pyproject.toml`) — not introduced by T02 and outside this review's scope.

Sdist (`tar tzf dist/jmdl_ai_workflows-0.2.0.tar.gz`): `.env.example`, `.claude/`, `design_docs/` (including M19 phase docs), and `.github/` are present. These are the pre-existing T01 HIGH-1 leakage items already folded to T08. T02 added M19 phase spec/issue files to the sdist (via `design_docs/phases/milestone_19_declarative_surface/`) but introduced no new secrets and no new categories of leakage. The `.env.example` contains only placeholder values (`GEMINI_API_KEY=` with no value). T02 does not change the leakage surface.

**2. KDR-003 / no Anthropic API** — `grep -rn "ANTHROPIC_API_KEY|import anthropic|anthropic\." _compiler.py spec.py __init__.py` returns zero hits. T02 is pure in-memory compilation; no LLM provider surface is touched.

**3. Subprocess / network surface** — `grep -rn "subprocess|shell=True|os.system|Popen|requests.|httpx.|urllib|socket." _compiler.py` returns zero hits. No subprocess or network calls introduced.

**4. Format-string injection via `prompt_template`** — The synthesised `_prompt_fn` at `_compiler.py:433` calls `template.format(**state)`. The `prompt_template` is set by the workflow author at registration time in a frozen pydantic model (`LLMStep.model_config = frozen=True`). The trust boundary is the same as `prompt_fn`: a workflow author who can set `prompt_template` can already set `prompt_fn` to do arbitrarily worse things. There is no end-user-supplied prompt template at dispatch time. A malicious `prompt_template` (e.g. `"{__class__.__init__.__globals__}"`) would be authored by the workflow developer, who already has full Python access — this is the KDR-013 user-owned-code boundary. No new escalation beyond what `prompt_fn` already permits.

**5. `sys.modules` synthetic-module injection** — `_compiler.py:234` sets `_module_name = f"ai_workflows.workflows._compiled_{spec.name}"`. The `spec.name` value comes from the workflow author's `WorkflowSpec` construction. Python's `types.ModuleType` accepts arbitrary strings as the module name, but the module is injected under a namespaced key that includes the full package prefix. The `setattr`/`getattr` pattern at line 250 works on any string key (including those with hyphens or other non-identifier characters) and has no filesystem side-effect. A pathological `spec.name` such as `../../../foo` results in a `sys.modules` key of `"ai_workflows.workflows._compiled_../../../foo"` — a valid dict key that no legitimate module would collide with, but not a valid Python import path. Python's import system ignores it for `import` statements; only `sys.modules[key]` lookups (which `_dispatch._import_workflow_module` performs by `builder.__module__`) use it. There is no path traversal since `sys.modules` is a plain dict, not a filesystem operation. The `register()` collision guard (in `__init__.py:121-129`) fires at the `spec.name` level before `compile_spec` is called, meaning two specs with the same name cannot silently shadow each other.

**6. State-key reserved-prefix discipline (`_mid_run_*`)** — `_derive_state_class` at `_compiler.py:860-875` writes schema fields first (input, then output, with output winning on collision), then writes framework-internal keys *after* (`run_id`, `last_exception`, `_retry_counts`, `_non_retryable_failures`, `_mid_run_tier_overrides`). Because Python dict assignment is last-write-wins, the framework-internal keys always overwrite any identically-named user schema fields. A workflow author who declares `_mid_run_tier_overrides` in their `output_schema` would have their annotation silently replaced by `Any` — the framework key wins. This is safe: the framework can never be spoofed via a schema field collision. The compiler does not actively reject `_mid_run_*` field names in input/output schemas — it silently overwrites them. This is the correct side of the boundary (framework wins) but authors who accidentally use `_mid_run_*` as a schema field name will get surprising behaviour (their field annotation is overwritten). No security issue; noted as an advisory.

**7. `_reset_for_tests()` prefix safety** — `__init__.py:168` uses the prefix `"ai_workflows.workflows._compiled_"` (23 characters including full package namespace). The `startswith` check is conservative: no unrelated module in a typical `sys.modules` would begin with that exact prefix. Confirmed `_reset_for_tests` is only called from test fixtures (`tests/workflows/test_compiler.py:124,126`, and 14 other test files) — not reachable from `ai_workflows/cli.py` or `ai_workflows/mcp/`. Zero production-code callsites.

**8. Test hermeticity** — `test_compiler.py` uses three autouse fixtures: stub adapter (monkeypatched), registry isolation (`_reset_for_tests()`), and SQLite path redirect (`AIW_CHECKPOINT_DB` + `AIW_STORAGE_DB` pointed to `tmp_path`). No subprocess calls, no network calls, no filesystem writes outside `tmp_path`. The `build_async_checkpointer` call in `test_compiled_stategraph_compiles_with_checkpointer` uses an explicit `tmp_path`-scoped path, not the default `~/.ai-workflows/` path.

### 🔴 Critical — must fix before publish/ship

None.

### 🟠 High — should fix before publish/ship

None.

### 🟡 Advisory — track; not blocking

**ADV-1 — No active rejection of `_mid_run_*` field names in input/output schemas.**
File: `ai_workflows/workflows/_compiler.py:860-875` (threat model item 6).
The compiler silently overwrites any `_mid_run_*` field from a user schema with `Any`. This is the safe outcome (framework wins), but a workflow author who accidentally names an output field `_mid_run_tier_overrides` will lose their declared type annotation without any warning at registration time. The actual runtime behaviour is correct (the framework field takes precedence), but the silent overwrite is a debugging trap. A future improvement could emit a `UserWarning` at registration time if any `input_schema` or `output_schema` field name starts with `_mid_run_` or matches another reserved key (`run_id`, `last_exception`, `_retry_counts`, `_non_retryable_failures`). No security impact; the framework-side invariant is correct. Action: optionally add a reserved-name check in `_validate_llm_step_tiers` / `register_workflow` in a future M19+ task; not blocking T02.

**ADV-2 — Sdist leakage of `.claude/`, `design_docs/`, `.env.example` (pre-existing; inherited from T01 HIGH-1, folded to T08).**
File: `pyproject.toml` (no `[tool.hatch.build.targets.sdist]` exclude block). T02 adds M19 phase spec files to the sdist but introduces no new secret content. The `.env.example` contains only placeholder values. This is the same finding as T01 HIGH-1, already tracked as a T08 release-ceremony item. Action: no action in T02; T08 owns the sdist exclusion block.

### Verdict: SHIP

T02's compiler is in-memory synthesis with no subprocess, network, or filesystem side-effects. KDR-003 is clean (zero Anthropic API hits). The synthetic-module injection pattern is safe (namespaced dict key, no filesystem touch, no import-system shadowing of real modules). The `prompt_template` format-string path is within the workflow-author trust boundary (same as `prompt_fn`). The `_mid_run_*` reserved-key ordering correctly ensures framework keys always win. The `_reset_for_tests()` prefix is conservative and test-only. Wheel contents are clean. The two advisories (ADV-1: silent reserved-key overwrite with no warning; ADV-2: sdist leakage) are pre-existing or low-impact and do not block shipment.

## Dependency audit (2026-04-26)

**Skipped — no manifest changes.** T02 cycles 1+2 modified `ai_workflows/workflows/_compiler.py` (new), `ai_workflows/workflows/spec.py`, `ai_workflows/workflows/__init__.py`, `tests/workflows/test_compiler.py` (new), `tests/workflows/test_spec.py`, and `CHANGELOG.md` only. Neither `pyproject.toml` nor `uv.lock` was touched, so the dependency-auditor pass is not triggered per /clean-implement S2.
