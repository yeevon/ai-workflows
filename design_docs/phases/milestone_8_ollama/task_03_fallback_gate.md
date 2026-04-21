# Task 03 — Fallback `HumanGate` Wiring

**Status:** 📝 Planned.
**Grounding:** [milestone README §Exit criteria 3](README.md) · [architecture.md §4.2 / §8.3 / §8.4](../../architecture.md) · [KDR-001, KDR-009](../../architecture.md).

## What to Build

A graph-layer helper that builds a strict-review `HumanGate` specialised
for Ollama-outage branches. When the workflow layer routes into this
gate (because T04's `TieredNode` raised `CircuitOpen`), the user sees a
rendered prompt citing:

- The tripped tier name (e.g. `local_coder`).
- The breaker's `last_reason` (e.g. `connection_refused`, `http_503`).
- The fallback tier they can promote to (pre-declared by the workflow
  author, typically `gemini_flash`).
- Three response choices: `retry`, `fallback`, `abort`.

The gate returns a parsed enum response that the workflow layer
dispatches on — this task ships the **gate factory + response parser**,
not the workflow-level edge wiring (that lives in T04's slice-layer
plumbing so planner + slice_refactor each compose the fallback path at
their own seam).

## Deliverables

### [ai_workflows/graph/ollama_fallback_gate.py](../../../ai_workflows/graph/ollama_fallback_gate.py)

```python
class FallbackChoice(str, Enum):
    RETRY = "retry"
    FALLBACK = "fallback"
    ABORT = "abort"


def build_ollama_fallback_gate(
    *,
    gate_id: str,
    tier_name: str,
    fallback_tier: str,
) -> Callable[[GraphState, RunnableConfig], Awaitable[dict[str, Any]]]:
    """Return a strict-review human_gate node for the Ollama-outage branch.

    Prompt shape (rendered by the inner prompt_fn):

        Ollama is unavailable for tier '{tier_name}'.

        Last probe / call reason: {last_reason}
        Consecutive failures: {failure_count}

        How do you want to proceed?
          [retry]    — try the same tier again (one shot).
          [fallback] — promote this tier to '{fallback_tier}' for the rest of the run.
          [abort]    — stop the run (status='aborted').

    `last_reason` and `failure_count` are read out of the graph state
    keys the workflow layer stamps before routing to this gate:
    `state["_ollama_fallback_reason"]` and
    `state["_ollama_fallback_count"]`.

    The inner node parses the resumed response and writes a shaped
    `ollama_fallback_decision: FallbackChoice` state key so the
    workflow's conditional edge can branch on a typed value rather than
    a free-text string. Unknown responses default to RETRY — one more
    loop is safer than an accidental abort, and the gate will re-fire
    if the breaker is still open.
    """
```

Design points:

- **Strict review, no timeout.** `human_gate(..., strict_review=True)`
  — an Ollama outage is not a thing to auto-default on
  (architecture.md §8.3: strict-review gates never time out).
- **Gate ID convention.** `gate_id` is passed through so callers can
  pin a stable `(run_id, gate_id)` key. For planner and slice_refactor
  the suggested ID is `ollama_fallback` (scoped per run by the existing
  gate-persistence mechanism).
- **Prompt rendering is pure.** Reads only from `state`; no network
  calls, no fresh `probe_ollama` invocation — the breaker already
  carries the last reason.
- **Response parsing.** Case-insensitive match on the three `FallbackChoice`
  values. Unknown strings → `RETRY` (with a WARN log) so a user typo
  doesn't silently abort.
- **State key names are stable.** `_ollama_fallback_reason`,
  `_ollama_fallback_count`, and `ollama_fallback_decision` are the
  contract between T04 (writer) and this gate (reader), plus the
  workflow-layer conditional edge (consumer of the decision). Their
  names are part of this task's spec so T04 and T05 can refer to them
  without re-inventing.

### [ai_workflows/graph/__init__.py](../../../ai_workflows/graph/__init__.py)

Export `build_ollama_fallback_gate` and `FallbackChoice`.

### Tests

[tests/graph/test_ollama_fallback_gate.py](../../../tests/graph/test_ollama_fallback_gate.py):

- `test_gate_prompt_renders_tier_reason_and_fallback` — invoke the inner
  `prompt_fn` with a canned state (`_ollama_fallback_reason="timeout"`,
  `_ollama_fallback_count=3`); assert the rendered string contains
  `local_coder`, `timeout`, `3`, and `gemini_flash`.
- `test_gate_is_strict_review` — build the gate; assert the resulting
  node's forwarded interrupt payload has `timeout_s=None` and
  `default_response_on_timeout=None` (strict-review semantics).
- `test_response_parses_retry` / `_fallback` / `_abort` — feed the
  three canonical strings (upper- and lower-cased variants) into the
  response-parse path; assert each produces the corresponding
  `FallbackChoice`.
- `test_unknown_response_defaults_to_retry` — `"maybe?"` → RETRY,
  WARN log emitted (captured via `caplog`).
- `test_gate_persists_via_storage_protocol` — reuse the
  `FakeStorage` pattern already in `tests/graph/test_human_gate.py`;
  assert `record_gate(run_id, gate_id="ollama_fallback", prompt=...)`
  was called once with the rendered prompt, and `record_gate_response`
  was called once on resume with the parsed decision's `.value`.

## Acceptance Criteria

- [ ] `from ai_workflows.graph import build_ollama_fallback_gate, FallbackChoice` works.
- [ ] Gate is built with `strict_review=True` — no timeout fires under
      any code path.
- [ ] `FallbackChoice` has exactly three members: `RETRY`, `FALLBACK`,
      `ABORT`.
- [ ] Unknown responses parse to `RETRY` with a WARN log (never raise,
      never abort).
- [ ] Gate persistence goes through `StorageBackend.record_gate` /
      `record_gate_response` — no new storage primitive or migration.
- [ ] Every listed test passes under `uv run pytest tests/graph/test_ollama_fallback_gate.py`.
- [ ] `uv run lint-imports` — **4 contracts kept**.
- [ ] `uv run ruff check` clean.

## Dependencies

- [Task 01](task_01_health_check.md) / [Task 02](task_02_circuit_breaker.md)
  for the `last_reason` contract the gate prompt renders (convention
  only — the gate reads it from state, not from the breaker directly).

## Out of scope (explicit)

- Workflow-level conditional edge wiring (planner + slice_refactor).
  (T04 composes the gate into both workflows with their concrete edge
  graphs; this task is the gate factory.)
- Mid-run tier promotion mechanics (how `FallbackChoice.FALLBACK`
  actually repoints subsequent `TieredNode` calls). (T04.)
- Any periodic re-probing of Ollama while the gate is waiting. (Out of
  scope for M8 — strict-review gates wait indefinitely for a human
  response; the fallback choice is the signal, not a timer.)
