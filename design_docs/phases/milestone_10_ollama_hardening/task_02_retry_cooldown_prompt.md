# Task 02 — RETRY Cooldown Guidance in `render_ollama_fallback_prompt`

**Status:** 📝 Planned.
**Grounding:** [milestone README §Exit criteria 2](README.md) · [architecture.md §8.4](../../architecture.md) · [M8 T03 fallback gate](../milestone_8_ollama/task_03_fallback_gate.md) · [M8 deep-analysis (fragility #4 / debt #2)](../milestone_8_ollama/README.md).

## What to Build

Extend [`render_ollama_fallback_prompt`](../../../ai_workflows/graph/ollama_fallback_gate.py)
so the operator who picks `RETRY` knows to wait at least `cooldown_s`
seconds before resuming. Today the prompt's `[retry]` line says only
"try the same tier again (one shot)" — if the breaker is still OPEN
when the user resumes, the next call re-trips the gate immediately and
the operator wonders why their retry "did nothing."

The fix is one paragraph of prompt copy that names the **actual breaker
cooldown value** (not a hard-coded 60). The breaker that tripped is the
source of truth; the gate factory grows a new optional `cooldown_s`
parameter that the workflow layer wires from the breaker's actual
configured cooldown.

This is a **code + test** task. No protocol changes, no new state keys.

## SEMVER + backward compatibility

`build_ollama_fallback_gate` and `FallbackChoice` are exported from
[`ai_workflows.graph.__init__:__all__`](../../../ai_workflows/graph/__init__.py)
— the package-level public surface of `jmdl-ai-workflows` 0.2.0.
`render_ollama_fallback_prompt`, `FALLBACK_DECISION_STATE_KEY`, and
`FALLBACK_GATE_ID` are exported from
[`ai_workflows.graph.ollama_fallback_gate.__all__`](../../../ai_workflows/graph/ollama_fallback_gate.py)
but are **not** re-exported at package level — they sit at the deeper
import path. External KDR-013 workflow modules (e.g. CS300) reach
`build_ollama_fallback_gate` via the package import; they reach
`render_ollama_fallback_prompt` only via the deeper module path. Both
import paths see the kwarg change, so both need the deprecation shim.

To preserve backward compatibility, the new `cooldown_s` kwarg is
**optional with a deprecation window**:

- Signature: `cooldown_s: float | None = None`.
- If `None`: render the prompt **without** the cooldown sentence (legacy
  shape) and emit a single `DeprecationWarning` on the first call:
  *"`cooldown_s` will be required in a future release; pass the breaker's
  actual cooldown to render the RETRY-wait guidance."*
- If a `float`: render the new prompt with the cooldown sentence.
- Internal call sites (planner.py, slice_refactor.py) **always pass
  the kwarg** so they emit no warning and render the new prompt.

This is a backward-compatible additive change — a **patch-level release
(0.2.0 → 0.2.1)**. T06 close-out runs the publish step. A future
milestone flips the kwarg to required at the next minor bump (when
external workflow migration data accumulates); this milestone does not
pre-commit a date.

## Deliverables

### [ai_workflows/graph/ollama_fallback_gate.py](../../../ai_workflows/graph/ollama_fallback_gate.py)

The deprecation shim has to fire **once per construction site**, not
once per gate invocation. Naive forwarding breaks this: if
`build_ollama_fallback_gate(cooldown_s=None)` calls
`render_ollama_fallback_prompt(..., cooldown_s=None)` from inside the
inner `_node` closure, the render function's own deprecation shim fires
on every gate invocation. The fix is a private no-warn rendering
function that the factory uses internally.

1. **Add a private helper** `_render_prompt_no_warn` that holds the
   actual rendering logic and emits **no** deprecation warning. The
   public `render_ollama_fallback_prompt` becomes a thin wrapper that
   adds the warning when `cooldown_s is None`:

   ```python
   def _render_prompt_no_warn(
       state: GraphState,
       *,
       tier_name: str,
       fallback_tier: str,
       cooldown_s: float | None,
   ) -> str:
       """Render the fallback prompt. Skip the cooldown paragraph when
       ``cooldown_s`` is ``None``. No deprecation logic — internal use only.
       """
       last_reason = state.get("_ollama_fallback_reason", "")
       failure_count = state.get("_ollama_fallback_count", 0)
       cooldown_paragraph = (
           f"\nNote: the circuit breaker for tier '{tier_name}' is in cooldown "
           f"for {cooldown_s:g}s after a trip. Choose [retry] only after at "
           f"least that long has elapsed wall-clock — otherwise the breaker "
           f"is still OPEN and the next call re-trips this gate.\n"
           if cooldown_s is not None
           else ""
       )
       return (
           f"Ollama is unavailable for tier '{tier_name}'.\n"
           f"\n"
           f"Last probe / call reason: {last_reason}\n"
           f"Consecutive failures: {failure_count}\n"
           f"{cooldown_paragraph}"
           f"\n"
           f"How do you want to proceed?\n"
           f"  [retry]    — try the same tier again (one shot).\n"
           f"  [fallback] — promote this tier to '{fallback_tier}' for the rest of the run.\n"
           f"  [abort]    — stop the run (status='aborted')."
       )


   def render_ollama_fallback_prompt(
       state: GraphState,
       *,
       tier_name: str,
       fallback_tier: str,
       cooldown_s: float | None = None,
   ) -> str:
       if cooldown_s is None:
           warnings.warn(
               "`render_ollama_fallback_prompt`'s `cooldown_s` kwarg is "
               "currently optional but will be required in a future release. "
               "Pass the breaker's actual cooldown (e.g. "
               "`circuit_breaker.cooldown_s`) so the rendered prompt can "
               "include the RETRY-wait guidance.",
               DeprecationWarning,
               stacklevel=2,
           )
       return _render_prompt_no_warn(
           state,
           tier_name=tier_name,
           fallback_tier=fallback_tier,
           cooldown_s=cooldown_s,
       )
   ```

2. **Extend `build_ollama_fallback_gate`** with the same optional
   `cooldown_s: float | None = None` kwarg. Emit one
   `DeprecationWarning` at construction time (not at invocation time)
   when the kwarg is `None`, then have the inner `_node` closure call
   `_render_prompt_no_warn` (the private helper) — **not** the public
   `render_ollama_fallback_prompt` — so the inner render does not
   re-emit the warning on every gate fire:

   ```python
   def build_ollama_fallback_gate(
       *,
       gate_id: str = FALLBACK_GATE_ID,
       tier_name: str,
       fallback_tier: str,
       cooldown_s: float | None = None,
   ) -> Callable[..., Awaitable[dict[str, Any]]]:
       if cooldown_s is None:
           warnings.warn(
               "`build_ollama_fallback_gate`'s `cooldown_s` kwarg is "
               "currently optional but will be required in a future "
               "release. Pass the breaker's `cooldown_s` so the gate's "
               "rendered prompt can include the RETRY-wait guidance.",
               DeprecationWarning,
               stacklevel=2,
           )

       async def _node(state, config):
           ...
           prompt = _render_prompt_no_warn(
               state,
               tier_name=tier_name,
               fallback_tier=fallback_tier,
               cooldown_s=cooldown_s,
           )
           ...

       return _node
   ```

   Net effect: **one warning per construction site, zero warnings per
   invocation, zero re-warnings down the inner-render path.**

### Workflow wiring sites

Locate the existing `build_ollama_fallback_gate(...)` call sites in
[planner.py](../../../ai_workflows/workflows/planner.py) and
[slice_refactor.py](../../../ai_workflows/workflows/slice_refactor.py) (one each
— see `ai_workflows/workflows/planner.py:520` and
`ai_workflows/workflows/slice_refactor.py:1508`) and add a third kwarg
sourced from the breaker:

```python
build_ollama_fallback_gate(
    tier_name=PLANNER_OLLAMA_FALLBACK.logical,
    fallback_tier=PLANNER_OLLAMA_FALLBACK.fallback_tier,
    cooldown_s=PLANNER_BREAKER_COOLDOWN_S,  # mirror of CircuitBreaker default
)
```

The breaker's `_cooldown_s` attribute is private — exposing it for the
gate factory should not require breaking encapsulation. Two acceptable
shapes (the Builder picks one and documents the choice in the task
issue file):

- **(a)** Add a public `CircuitBreaker.cooldown_s` read-only property
  (single-line `return self._cooldown_s`); both workflows read the
  breaker out of `configurable` before instantiating the graph and pass
  it through.
- **(b)** Define a module-level `PLANNER_BREAKER_COOLDOWN_S = 60.0` /
  `SLICE_REFACTOR_BREAKER_COOLDOWN_S = 60.0` constant in each workflow
  and pass *both* to `_build_ollama_circuit_breakers` and to
  `build_ollama_fallback_gate`. Defaults stay locked at the M8 T02 value
  (60.0).

Either is acceptable. **(a)** keeps the breaker as the single source of
truth; **(b)** is one extra constant per workflow but no new public API.
Picking **(a)** is the lower-coupling default — there is one breaker
per Ollama-backed tier and the gate factory call site already has the
breaker dict in scope.

### Tests

[tests/graph/test_ollama_fallback_gate.py](../../../tests/graph/test_ollama_fallback_gate.py) — extend the existing suite:

- **`test_prompt_includes_cooldown_warning`** — call
  `render_ollama_fallback_prompt(state, tier_name="local_coder",
  fallback_tier="planner-synth", cooldown_s=60.0)`; assert the rendered
  string contains *all four* tokens: the literal `60` (no `.0`), the
  word `cooldown`, the word `wall-clock`, and the tier name `local_coder`.
- **`test_prompt_cooldown_value_is_dynamic`** — same call with
  `cooldown_s=12.5`; assert `12.5` appears in the prompt and `60` does
  not. Catches a future hard-coded `60` slipping back in.
- **`test_prompt_without_cooldown_emits_deprecation_warning`** — call
  without `cooldown_s` (or pass `None`) inside
  `pytest.warns(DeprecationWarning, match="cooldown_s")`; assert the
  rendered prompt does **not** contain the word `cooldown` (legacy
  shape preserved). Closes the silent-default footgun by making the
  legacy path noisy without breaking it.
- **`test_build_gate_forwards_cooldown_to_prompt`** — build a gate with
  `cooldown_s=42.0` + a `FakeStorage`; invoke the inner node with a
  state that triggers the prompt path; assert the rendered prompt the
  storage saw contains `42`.
- **`test_build_gate_without_cooldown_emits_deprecation_warning`** —
  build a gate with no `cooldown_s` inside
  `pytest.warns(DeprecationWarning)`; assert exactly one warning is
  recorded at construction time. (Use `pytest.warns(DeprecationWarning)`
  with the `match=` kwarg to pin the warning text to the gate-factory
  message, distinguishing it from the prompt-render message.)
- **`test_gate_fire_does_not_re_emit_warning`** — the no-double-fire
  invariant. Build a gate without `cooldown_s` (catching one
  `DeprecationWarning` at construction); then drive the inner `_node`
  three times under `warnings.catch_warnings(record=True)` with
  `warnings.simplefilter("always")`; assert **zero**
  `DeprecationWarning` was recorded across the three invocations.
  This is the regression guard for the "factory uses
  `_render_prompt_no_warn` internally" design point.

[tests/workflows/test_planner_ollama_fallback.py](../../../tests/workflows/test_planner_ollama_fallback.py)
and [tests/workflows/test_slice_refactor_ollama_fallback.py](../../../tests/workflows/test_slice_refactor_ollama_fallback.py)
already exercise the fallback path under hermetic stubs. Update the
relevant assertions so the workflow's gate-build call passes
`cooldown_s` and the rendered prompt contains the new sentence. The
update should also assert that no `DeprecationWarning` fires from the
internal call sites — internal callers must always pass the kwarg.
No new test files needed.

### Smoke verification (Auditor runs)

```bash
uv run pytest \
  tests/graph/test_ollama_fallback_gate.py \
  tests/workflows/test_planner_ollama_fallback.py \
  tests/workflows/test_slice_refactor_ollama_fallback.py \
  -v
```

All five new / updated gate tests pass + both workflow suites' fallback
paths still green. The Auditor also runs:

```bash
uv run python -W error::DeprecationWarning -c \
  "from ai_workflows.workflows.planner import build_planner; \
   from ai_workflows.workflows.slice_refactor import build_slice_refactor; \
   build_planner(); build_slice_refactor(); \
   print('internal call sites pass cooldown_s')"
```

Any `DeprecationWarning` raised here fails the smoke — it would mean
an internal call site forgot to wire `cooldown_s` and the deprecation
shim caught it. (Function names verified against
[planner.py:455](../../../ai_workflows/workflows/planner.py#L455) and
[slice_refactor.py:1457](../../../ai_workflows/workflows/slice_refactor.py#L1457).)

## Acceptance Criteria

- [ ] `render_ollama_fallback_prompt` accepts an optional `cooldown_s: float | None = None`
      kwarg; passing `None` (or omitting it) emits a `DeprecationWarning`
      and renders the legacy prompt; passing a `float` renders the
      cooldown sentence.
- [ ] The new prompt paragraph names the cooldown value and instructs
      the operator to wait wall-clock time before RETRY.
- [ ] The cooldown value in the prompt matches whatever the workflow passed
      (no hard-coded `60` anywhere in `ollama_fallback_gate.py`).
- [ ] `build_ollama_fallback_gate` accepts the same optional kwarg and
      emits one `DeprecationWarning` at construction time when the kwarg
      is `None`. The inner `_node` closure calls the private
      `_render_prompt_no_warn` helper (not the public
      `render_ollama_fallback_prompt`), so no further warning fires per
      invocation. `test_gate_fire_does_not_re_emit_warning` enforces
      this.
- [ ] Both workflow wiring sites (`planner.py`, `slice_refactor.py`) pass
      the breaker's actual `cooldown_s` to the gate factory; no
      `DeprecationWarning` fires under `python -W error::DeprecationWarning`.
- [ ] No change to the existing state-key contract
      (`_ollama_fallback_reason`, `_ollama_fallback_count`,
      `ollama_fallback_decision`, `_ollama_fallback_fired`,
      `_mid_run_tier_overrides`).
- [ ] Five new / updated tests pass under `uv run pytest tests/graph/test_ollama_fallback_gate.py`.
- [ ] `uv run lint-imports` reports **4 contracts kept**.
- [ ] `uv run ruff check` clean.
- [ ] `CHANGELOG.md` `[Unreleased]` gets three entries, each following
      the project's canonical heading shape
      `### {Kind} — M10 Task 02: <descriptive title> (<YYYY-MM-DD>)`
      (see `CHANGELOG.md:10` for the convention):
      - `### Added — M10 Task 02: public breaker-cooldown access surface (<YYYY-MM-DD>)`
        naming the new `CircuitBreaker.cooldown_s` property under
        option (a) or the per-workflow `*_BREAKER_COOLDOWN_S` constants
        under option (b).
      - `### Changed — M10 Task 02: RETRY-cooldown prompt UX (<YYYY-MM-DD>)`
        citing the new cooldown sentence in
        `render_ollama_fallback_prompt`.
      - `### Deprecated — M10 Task 02: optional cooldown_s kwarg (<YYYY-MM-DD>)`
        naming the future-required kwarg on both
        `render_ollama_fallback_prompt` and `build_ollama_fallback_gate`.

## Dependencies

- [Task 01](task_01_fallback_tier_adr.md) lands first if T01 + T02 land in
  the same commit chain (T01 touches the same two workflow modules' module
  docstrings; trivial to keep separate but easier to review in T01 → T02
  order).

## Out of scope (explicit)

- **No automatic enforcement of the wait.** We do not gate `RETRY` on
  wall-clock — the breaker's HALF_OPEN logic already does that on the
  next call. The prompt warns; the breaker enforces. A "no, really, wait"
  middleware would be premature without a logged incident.
- **No periodic re-probing of Ollama while the gate waits.** Strict-review
  gates wait indefinitely; the fallback choice is the signal, not a timer
  (M8 T03 design point preserved).
- **No new `FallbackChoice` member.** Three choices stay (`RETRY` /
  `FALLBACK` / `ABORT`).
- **No telemetry on cooldown-wait duration.** Telemetry deferred to
  `nice_to_have.md` §1 (Langfuse).
- **No flip of `cooldown_s` from optional to required at this milestone.**
  The deprecation warning is the signal; the flip happens at a future
  minor bump when external workflows have had time to migrate. M10 does
  not pre-commit a removal date.

## Carry-over from task analysis

- [ ] **TA-LOW-05 — Off-by-one in workflow-wiring-sites line numbers**
      (severity: LOW, source: task_analysis.md round 4)
      The "Workflow wiring sites" paragraph cites `planner.py:520` and
      `slice_refactor.py:1508`. Live grep at task-analysis time resolved
      both to `planner.py:519` and `slice_refactor.py:1507` (off-by-one).
      Builder will find the right line via grep, but a wrong literal is
      exactly the kind of spec rot the task-analysis pass exists to catch.
      **Recommendation:** Update the literal line numbers to match what
      the live codebase reports — or drop them in favour of the grep,
      which is more robust against future drift.
