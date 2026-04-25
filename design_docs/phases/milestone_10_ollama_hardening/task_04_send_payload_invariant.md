# Task 04 — `_mid_run_tier_overrides` Send-Payload Carry Invariant Test

**Status:** 📝 Planned.
**Grounding:** [milestone README §Exit criteria 4](README.md) · [architecture.md §8.4](../../architecture.md) · [M8 T04 Send-payload carry note](../milestone_8_ollama/task_04_tiered_node_integration.md) · [M8 deep-analysis (fragility #6)](../milestone_8_ollama/README.md).

## What to Build

A hermetic regression-guard test, [tests/workflows/test_ollama_fallback_send_payload_carry.py](../../../tests/workflows/test_ollama_fallback_send_payload_carry.py),
that asserts a re-fired `Send(...)` payload post-`FALLBACK` includes
`_mid_run_tier_overrides` in its dict. The current production code
(`ai_workflows/workflows/slice_refactor.py:1350-1361`) puts the override
into the payload only when `overrides` is truthy — a future LangGraph
upgrade that changed `Send` semantics (e.g. inheriting parent state by
default, making the explicit copy a no-op) would silently regress the
fallback flow with no test catching it.

This is a **test-only** task. No production code change. The invariant
already holds in the as-shipped surface; this task makes the invariant
self-protective against `langgraph` package upgrades.

## Deliverables

### [tests/workflows/test_ollama_fallback_send_payload_carry.py](../../../tests/workflows/test_ollama_fallback_send_payload_carry.py)

A new hermetic test file. Direct router invocation (the fastest,
lowest-coupling shape — pins the invariant at the exact site where a
LangGraph `Send`-semantics regression would manifest).

The post-FALLBACK Send-emitter is
[`_route_after_fallback_dispatch_slice`](../../../ai_workflows/workflows/slice_refactor.py#L1298)
in `slice_refactor.py`. Important: the override dict is **stamped by
[`_ollama_fallback_dispatch_slice`](../../../ai_workflows/workflows/slice_refactor.py#L1245)
on FALLBACK**, not by the router itself. The test feeds the router a
hand-built post-stamp state — equivalent to having walked through the
dispatch step — without driving the graph end-to-end.

The positive test
(`test_send_payload_carries_overrides_to_subgraph`) calls
`_route_after_fallback_dispatch_slice(state)` with:

- `FALLBACK_DECISION_STATE_KEY` set to `FallbackChoice.FALLBACK`.
  Import the constant from `ai_workflows.graph.ollama_fallback_gate`
  (it lives in that module's `__all__` but is **not** re-exported at
  the `ai_workflows.graph` package level — the package's `__all__` is
  `["FallbackChoice", "build_ollama_fallback_gate"]` only).
- `slice_list` populated with two `SliceSpec` instances. Re-use the
  fixture pattern from
  [`tests/workflows/test_slice_refactor_ollama_fallback.py`](../../../tests/workflows/test_slice_refactor_ollama_fallback.py)
  — copy the minimum needed to instantiate two specs.
- `_circuit_open_slice_ids = ["slice-0", "slice-1"]`.
- `_mid_run_tier_overrides = {"slice-worker": "planner-synth"}`.

Assert:

- Return type is `list[Send]`, length 2.
- **Every** `Send.arg` dict contains
  `_mid_run_tier_overrides == {"slice-worker": "planner-synth"}` (the
  parent state's override dict survived the payload-build).
- Every `Send.arg` dict also contains `_ollama_fallback_fired=True`
  (the loop-prevention flag — already invariant in the current code,
  worth pinning here to catch a LangGraph-upgrade that changes Send
  semantics so this gets dropped too).

The negative control
(`test_payload_omits_override_when_dict_is_empty`) calls the same
router with `_mid_run_tier_overrides = {}`; asserts
`_mid_run_tier_overrides` is **not** a key in any returned `Send.arg`.
Current code (slice_refactor.py:1359-1360) skips the assignment when
the dict is falsy; if a future refactor unconditionally writes the
empty dict, that is a behaviour change the negative control catches.

### Smoke verification (Auditor runs)

```bash
uv run pytest tests/workflows/test_ollama_fallback_send_payload_carry.py -v
```

Both tests (positive carry + negative control) green.

## Acceptance Criteria

- [ ] [tests/workflows/test_ollama_fallback_send_payload_carry.py](../../../tests/workflows/test_ollama_fallback_send_payload_carry.py)
      exists with at least:
  - `test_send_payload_carries_overrides_to_subgraph` (positive case).
  - `test_payload_omits_override_when_dict_is_empty` (negative control).
- [ ] The positive test asserts every `Send.arg` in the returned list
      contains `_mid_run_tier_overrides` and the dict's contents match
      the parent state's `_mid_run_tier_overrides`.
- [ ] No production code change — diff is confined to the new test file
      (and a `CHANGELOG.md` entry).
- [ ] `uv run pytest` green; new tests run in <2s wall-clock (hermetic,
      no provider calls).
- [ ] `uv run lint-imports` reports **4 contracts kept**.
- [ ] `uv run ruff check` clean.
- [ ] `CHANGELOG.md` `[Unreleased]` gets an
      `### Added — M10 Task 04: Send-payload carry invariant test (<YYYY-MM-DD>)`
      entry naming the new test file. (`### Added` because the test
      file is new; the project's CHANGELOG vocabulary is `Added |
      Changed | Deprecated | Removed | Fixed | Security` per
      Keep-a-Changelog — `### Tests` is off-vocabulary.)

## Dependencies

- [Task 03](task_03_single_gate_invariant.md) — both M10 invariant tests
  share the `FakeStorage` + `StubLLMAdapter` patterns; sequencing T04
  after T03 lets the Builder reuse fixtures established in T03.

## Out of scope (explicit)

- **No upgrade of the underlying `langgraph` pin.** This task adds a
  guard so an upgrade *would* break loudly; it does not perform the
  upgrade.
- **No change to the per-Send payload shape.** The test pins the current
  shape; widening the payload (e.g. carrying additional state keys
  through Sends) is a separate decision.
- **No coverage of the planner workflow's payload semantics.** Planner has
  no `Send` fan-out — the invariant only matters where parallel sub-graphs
  view their own state slice (slice_refactor today; future parallel
  workflows tomorrow per T03's recipe).

## Carry-over from task analysis

- [ ] **TA-LOW-03 — `SliceSpec` minimal-fixture fields not enumerated**
      (severity: LOW, source: task_analysis.md round 4)
      The Deliverables section says "Re-use the fixture pattern from
      `tests/workflows/test_slice_refactor_ollama_fallback.py` — copy
      the minimum needed to instantiate two specs." `SliceSpec` has
      three required fields (`id: str`, `description: str`,
      `acceptance: list[str]`, with `extra='forbid'` per
      `slice_refactor.py:430–452`). The Builder will figure this out at
      first failing test, but a one-liner saves a cycle.
      **Recommendation:** Append: *"Minimal `SliceSpec` instantiation:
      `SliceSpec(id='slice-0', description='', acceptance=[])` — only
      `id` is round-tripped through `_route_after_fallback_dispatch_slice`'s
      `slice_by_id` lookup; `description` + `acceptance` are required by
      `extra='forbid'` validation."*
