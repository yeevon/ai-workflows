# Task 03 — Single-Gate-Per-Run Pattern Docs + Cross-Workflow Invariant Test

**Status:** 📝 Planned.
**Grounding:** [milestone README §Exit criteria 3](README.md) · [architecture.md §8.4](../../architecture.md) · [M8 T04 spec](../milestone_8_ollama/task_04_tiered_node_integration.md) · [M8 deep-analysis (fragility #5)](../milestone_8_ollama/README.md).

## What to Build

Three artefacts that together promote the **single-gate-per-run**
invariant for parallel-fan-out workflows from "implementation detail of
slice_refactor" to "named pattern with a regression-guard test, backed
by public reducers":

1. A small refactor of slice_refactor.py to **promote two reducers from
   private to public surface**:
   - `_merge_ollama_fallback_fired` → `merge_ollama_fallback_fired`
   - `_merge_mid_run_tier_overrides` → `merge_mid_run_tier_overrides`

   Reasoning: the cross-workflow invariant test (artefact 3) imports
   these reducers because they ARE the regression target. The
   architecture.md recipe (artefact 2) names them in load-bearing docs
   that future workflow authors are expected to consume. Naming them in
   public docs while keeping them private is incoherent — leading
   underscore says "implementation detail not part of the contract,"
   which is the opposite of what the recipe + invariant test claim.
   Promotion is the right disposition.

2. A new architecture.md §8.4 subsection — *"Composing the fallback
   path into a new parallel workflow"* — that names the sticky-OR
   `_ollama_fallback_fired` state key + the `_route_before_aggregate`
   router pattern, cites the invariant test as the regression guard,
   and points future workflow authors at the public reducers from
   artefact 1.

3. A new hermetic test, [tests/workflows/test_ollama_fallback_single_gate_invariant.py](../../../tests/workflows/test_ollama_fallback_single_gate_invariant.py),
   that builds a minimal three-branch `Send`-based workflow agnostic of
   slice_refactor's domain shape (no `SliceSpec`, no
   `_circuit_open_slice_ids`, no `slice_list`), imports the now-public
   reducers from `ai_workflows.workflows.slice_refactor`, and asserts
   that N parallel `CircuitOpen` emissions in a single super-step
   result in exactly **one** `record_gate('ollama_fallback', ...)` call.

This is a **small refactor + doc + test** task. The refactor is
mechanical (rename + `__all__` add + internal call-site updates); the
doc + test work is the bulk.

## Deliverables

### [ai_workflows/workflows/slice_refactor.py](../../../ai_workflows/workflows/slice_refactor.py) — reducer rename

Rename two functions to drop their leading underscores and add them to
the module's `__all__` list:

| Before | After |
| --- | --- |
| `_merge_ollama_fallback_fired` | `merge_ollama_fallback_fired` |
| `_merge_mid_run_tier_overrides` | `merge_mid_run_tier_overrides` |

Update every internal call site within
[slice_refactor.py](../../../ai_workflows/workflows/slice_refactor.py)
(the `Annotated[..., _merge_*]` reducer references on
[lines 604-607](../../../ai_workflows/workflows/slice_refactor.py#L604-L607)
are the load-bearing call sites; there are no other consumers in-tree).

Add both names to `slice_refactor`'s `__all__` so they are part of the
documented public surface — the M8 T04 contract that this task's
invariant test pins.

Bump the docstring on each function to acknowledge they are now public:
*"Promoted to public at M10 T03 because the cross-workflow invariant
test [`tests/workflows/test_ollama_fallback_single_gate_invariant.py`](../../../tests/workflows/test_ollama_fallback_single_gate_invariant.py)
imports them as part of the M8 T04 contract surface."*

No behaviour change — pure rename. The module's existing reducer
behaviour is what the invariant test verifies; promoting the symbols to
public does not change their semantics.

### [design_docs/architecture.md](../../architecture.md) §8.4 expansion

Add a new subsection **after** the existing "Single-gate-per-run invariant
for parallel fan-out" paragraph (currently around line 220), titled
*"Composing the fallback path into a new parallel workflow"*. The subsection
documents the four-step recipe a future workflow author follows:

1. **Declare the sticky-OR state key.** Add `_ollama_fallback_fired:
   Annotated[bool, merge_ollama_fallback_fired]` to the workflow's
   `TypedDict` state shape. Import `merge_ollama_fallback_fired` from
   `ai_workflows.workflows.slice_refactor` — it's the canonical
   OR-reducer for this state key (`lambda old, new: bool(old) or
   bool(new)`; idempotent, safe under parallel fan-in).
2. **Declare the override-merge state key.** Add `_mid_run_tier_overrides:
   Annotated[dict[str, str], merge_mid_run_tier_overrides]` (canonical
   dict-merge reducer, also imported from
   `ai_workflows.workflows.slice_refactor`).
3. **Add a `_route_before_aggregate` router.** Before the parallel fan-in
   node, insert a router that:
   - returns the gate-stamp node name when `_ollama_fallback_fired` is
     already `True` *or* when `_circuit_open_<branch>_ids` is non-empty
     on the current super-step;
   - otherwise returns the workflow's normal aggregate node.
   This is what guarantees the gate-stamp node fires **once** even when
   N branches each emit `CircuitOpen` in parallel.
4. **Compose `build_ollama_fallback_gate`.** Build the gate with
   `tier_name`, `fallback_tier`, and `cooldown_s` (the M10 T02 kwarg),
   wire its `FALLBACK_DECISION_STATE_KEY` output to a conditional edge
   that branches on `FallbackChoice.{RETRY, FALLBACK, ABORT}`, and stamp
   `_mid_run_tier_overrides[tier_name] = fallback_tier` in the
   FALLBACK-branch terminal node.

The subsection ends with a **bold callout**:

> **Regression guard:** [`tests/workflows/test_ollama_fallback_single_gate_invariant.py`](../../tests/workflows/test_ollama_fallback_single_gate_invariant.py)
> drives a three-branch parallel fan-out through the recipe and asserts
> the single-gate invariant holds. Regressions in the gate factory or
> the two reducers fail this test.

The four-step recipe lives in architecture.md (load-bearing, reviewed by
the Auditor) so it does not rot inside one workflow's docstring.

### [tests/workflows/test_ollama_fallback_single_gate_invariant.py](../../../tests/workflows/test_ollama_fallback_single_gate_invariant.py)

A new hermetic test file. Builds a deliberately-minimal LangGraph
`StateGraph` independent of slice_refactor's domain-specific shape
(`SliceSpec`, `_circuit_open_slice_ids`, etc.). The test:

- Defines a fresh `TypedDict` state.
- Imports `merge_ollama_fallback_fired` and `merge_mid_run_tier_overrides`
  from `ai_workflows.workflows.slice_refactor` — those reducers **are**
  the regression target. After the artefact-1 rename, both are part of
  slice_refactor's `__all__` and are appropriate to import from a sibling
  test module.
- Defines two `branch_<i>` nodes that each call a stub `TieredNode`
  configured to raise `CircuitOpen(tier='local_coder',
  last_reason='timeout')` immediately. (`CircuitOpen` import comes from
  `ai_workflows.primitives.circuit_breaker`.)
- Implements a `_route_before_aggregate` router per the architecture
  recipe (in-test; the router is the unit under test, not a slice_refactor
  import).
- Wires a `build_ollama_fallback_gate(...)` instance with
  `cooldown_s=60.0` (post-M10 T02).
- Uses a `FakeStorage` that records every `record_gate` call.

The positive test (`test_three_branch_parallel_fanout_records_one_gate`)
fans out **three** parallel `Send("branch_<i>", ...)` payloads in one
super-step; resumes the gate with `FallbackChoice.ABORT` to terminate
cleanly; and asserts:

- `record_gate` was called **exactly once** with `gate_id="ollama_fallback"`.
- `record_gate_response` was called **exactly once** with the resumed
  decision string.
- `_ollama_fallback_count` ended at `1` (not `3` — sticky-OR + the
  router make the count idempotent across parallel branches).

The negative control (`test_invariant_fails_without_router`) is a
**plain test that passes when the broken code is broken** — proving the
positive test detects something real. Concrete mechanics:

- Build the **same** state graph nodes (the three `branch_<i>` nodes,
  the gate-stamp node, the `build_ollama_fallback_gate(...)` instance,
  the `FakeStorage`) — but wire each `branch_<i>`'s edge directly to
  the `ollama_fallback_stamp` node, **bypassing** `_route_before_aggregate`.
  That is the wiring slice_refactor *would* have if M8 T04's invariant
  guard had not been built; it lets each parallel branch hit the
  gate-stamp node independently.
- Drive the same three-branch fan-out and resume the gate.
- Assert `fake_storage.record_gate.call_count > 1` — without the
  router, the broken workflow does call `record_gate` once per branch.

No `pytest.xfail` involved. A passing negative control demonstrates the
positive test detects something real (the router is what enforces the
invariant). If a future refactor of the gate factory or reducers makes
the broken-wiring composition somehow stop calling `record_gate`
multiple times, the negative control fails — surfacing that the
positive test's "exactly one" assertion is suddenly trivial.

### Smoke verification (Auditor runs)

```bash
uv run pytest tests/workflows/test_ollama_fallback_single_gate_invariant.py -v
```

Both tests (positive invariant + negative control) report green.

## Acceptance Criteria

- [ ] `merge_ollama_fallback_fired` and `merge_mid_run_tier_overrides`
      exist as public symbols in
      `ai_workflows.workflows.slice_refactor` (no leading underscore;
      both in the module's `__all__`); their docstrings cite M10 T03
      as the promotion point.
- [ ] No `_merge_ollama_fallback_fired` / `_merge_mid_run_tier_overrides`
      references remain anywhere in the codebase
      (`grep -rn "_merge_ollama_fallback_fired\|_merge_mid_run_tier_overrides" ai_workflows tests`
      returns nothing).
- [ ] All existing `tests/workflows/test_slice_refactor*.py` and
      `tests/workflows/test_planner_ollama_fallback.py` suites pass
      against the renamed symbols.
- [ ] `architecture.md` §8.4 has a new subsection
      *"Composing the fallback path into a new parallel workflow"* with
      the four-step recipe and the bold regression-guard callout. The
      recipe references `merge_ollama_fallback_fired` and
      `merge_mid_run_tier_overrides` by their public names.
- [ ] [tests/workflows/test_ollama_fallback_single_gate_invariant.py](../../../tests/workflows/test_ollama_fallback_single_gate_invariant.py)
      exists with both `test_three_branch_parallel_fanout_records_one_gate`
      (positive, asserts one gate call) and `test_invariant_fails_without_router`
      (negative control, asserts the broken workflow does call the gate
      multiple times — plain test, no `xfail`).
- [ ] The negative control's broken wiring is documented in a comment:
      *"each `branch_<i>` edge wires directly to `ollama_fallback_stamp`,
      bypassing `_route_before_aggregate` — recreates the pre-M8-T04
      shape."*
- [ ] The synthetic workflow does not depend on slice_refactor's
      domain-specific shape (`SliceSpec`, `_circuit_open_slice_ids`,
      `slice_list`). Importing the two public reducers from
      slice_refactor is fine — they are the regression target.
- [ ] Outside the reducer imports, the test imports only from
      `ai_workflows.graph.ollama_fallback_gate`,
      `ai_workflows.primitives.circuit_breaker`, and `langgraph.*`.
- [ ] `uv run pytest` green.
- [ ] `uv run lint-imports` reports **4 contracts kept** (no new layer
      contract; the test stays under `tests/workflows/` which is allowed
      to import from any layer).
- [ ] `uv run ruff check` clean.
- [ ] `CHANGELOG.md` `[Unreleased]` gets an
      `### Added — M10 Task 03: cross-workflow single-gate invariant test + reducer promotion (<YYYY-MM-DD>)`
      entry naming the new invariant test + the two reducer-promotion
      symbols (`merge_ollama_fallback_fired` /
      `merge_mid_run_tier_overrides`). (`### Added` because the public
      reducer surface is new and the test file is new; the project's
      CHANGELOG vocabulary is `Added | Changed | Deprecated | Removed |
      Fixed | Security` per Keep-a-Changelog — `### Tests` is
      off-vocabulary.)

## Dependencies

- [Task 02](task_02_retry_cooldown_prompt.md) lands first — the gate
  factory's new `cooldown_s` kwarg is required to build the gate in the
  invariant test.

## Out of scope (explicit)

- **No refactor of the sticky-OR pattern into `build_ollama_fallback_gate`'s
  surface.** Deferred to `nice_to_have.md` §26 (T05). The trigger is "a
  third parallel-fan-out workflow lands"; M10 documents the pattern + adds
  the invariant test, the refactor is premature.
- **No change to slice_refactor's existing wiring.** The four-step recipe
  is the documentation of slice_refactor's *current* shape, not a rewrite.
- **No coverage for the linear (non-parallel) planner workflow** in the
  cross-workflow test. Planner has no parallel fan-out, so the
  single-gate invariant is trivially satisfied; testing it would be
  redundant. Planner's own test suite already exercises the gate path.

## Carry-over from task analysis

- [ ] **TA-LOW-04 — Recipe step 4 doesn't name the canonical `cooldown_s` source**
      (severity: LOW, source: task_analysis.md round 4)
      The architecture.md recipe's step 4 says "Build the gate with
      `tier_name`, `fallback_tier`, and `cooldown_s` (the M10 T02 kwarg)…"
      — but a future workflow author following the recipe needs to know
      the source of truth for `cooldown_s` (the per-tier
      `CircuitBreaker.cooldown_s` under T02 option (a), or a workflow-local
      constant under option (b)).
      **Recommendation:** Append a half-sentence after "the M10 T02 kwarg":
      *"…wire it from the per-tier `CircuitBreaker.cooldown_s` so the
      rendered prompt names the breaker's actual cooldown — not a
      hard-coded literal."*
