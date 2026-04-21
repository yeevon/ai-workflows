# Task 02 — `CircuitBreaker` Primitive

**Status:** 📝 Planned.
**Grounding:** [milestone README §Exit criteria 2](README.md) · [architecture.md §8.4](../../architecture.md) · [KDR-006](../../architecture.md).

## What to Build

A process-local circuit-breaker state machine that `TieredNode` (T04)
consults before every Ollama-routed provider call. Trips after N
consecutive failures within a cooldown window; once open, subsequent
`allow()` calls short-circuit with a stable signal so the workflow
layer can route to the fallback gate (T03) without waiting for a
per-call timeout.

The breaker is **process-local**, not Storage-backed. Restart semantics
match M6's `_ACTIVE_RUNS` registry: the breaker is reset on process
boot; an operator restarting the CLI/MCP server after fixing Ollama
gets a clean slate. This is the correct trade-off — persisting the
breaker across restarts would require a new migration + race against
`cancel_run` + extra audit surface for M8's modest incremental scope.

## Deliverables

### [ai_workflows/primitives/circuit_breaker.py](../../../ai_workflows/primitives/circuit_breaker.py)

```python
class CircuitState(str, Enum):
    CLOSED = "closed"          # normal; allow() returns True
    OPEN = "open"              # tripped; allow() returns False
    HALF_OPEN = "half_open"    # cooldown elapsed; single probe permitted


class CircuitOpen(Exception):
    """Raised by callers that prefer to raise rather than branch on `allow()`.

    Carries the breaker's tier name and `last_reason` so the workflow
    layer can render the fallback gate prompt (T03) without re-probing.
    """

    def __init__(self, *, tier: str, last_reason: str) -> None: ...


class CircuitBreaker:
    """Per-tier circuit-breaker state machine — process-local.

    Thread / task safety: guarded by an `asyncio.Lock` so the three
    parallel `slice-worker` branches in `slice_refactor` cannot race on
    the consecutive-failure counter.

    Parameters
    ----------
    tier:
        Logical tier name (e.g. "local_coder"). Stamped into
        `CircuitOpen` and surfaced in structured log lines.
    trip_threshold:
        Consecutive failures that flip CLOSED → OPEN. Default 3 —
        matches the three-bucket retry taxonomy's transient-attempt
        budget so one exhausted RetryingEdge loop (which already means
        `max_transient_attempts` failures in a row on the same call)
        is enough to trip the breaker.
    cooldown_s:
        Wall-clock seconds the breaker stays OPEN before transitioning
        to HALF_OPEN. Default 60.0.
    """

    def __init__(
        self,
        *,
        tier: str,
        trip_threshold: int = 3,
        cooldown_s: float = 60.0,
    ) -> None: ...

    @property
    def state(self) -> CircuitState: ...

    @property
    def last_reason(self) -> str: ...

    async def allow(self) -> bool:
        """Return True if a call is permitted. Transitions OPEN → HALF_OPEN
        when cooldown has elapsed; in HALF_OPEN, only the *first* caller
        that asks receives True until record_* is called."""

    async def record_success(self) -> None:
        """Zero the counter; transition any non-CLOSED state back to CLOSED."""

    async def record_failure(self, *, reason: str) -> None:
        """Increment the counter; transition to OPEN when threshold reached
        or when HALF_OPEN receives a failure. Stamps `reason` for later
        `CircuitOpen`/gate rendering."""
```

Structured-log convention (module-level logger, keyed `ai_workflows.circuit_breaker`):

- State transitions log at INFO with `event="circuit_state"`,
  `tier=<tier>`, `from=<state>`, `to=<state>`, `reason=<reason>`.
- `allow()` denials log at DEBUG with `event="circuit_short_circuit"`
  — a successful trip already logged the transition at INFO.

### [ai_workflows/primitives/__init__.py](../../../ai_workflows/primitives/__init__.py)

Export `CircuitBreaker`, `CircuitOpen`, `CircuitState` alongside the
existing primitives.

### Tests

[tests/primitives/test_circuit_breaker.py](../../../tests/primitives/test_circuit_breaker.py):

- `test_starts_closed` — fresh breaker: `state == CLOSED`, `allow()` → True.
- `test_trips_open_after_threshold_failures` — three `record_failure`
  calls flip state to OPEN; next `allow()` → False.
- `test_success_resets_counter_mid_streak` — fail, fail, success, fail:
  state stays CLOSED, counter is zero after the success.
- `test_half_open_after_cooldown` — trip, `monkeypatch` time source +60s,
  `allow()` → True, `state == HALF_OPEN`; a *second* `allow()` without
  a record → False (single-probe semantics).
- `test_half_open_success_closes` — in HALF_OPEN, `record_success` →
  state goes back to CLOSED.
- `test_half_open_failure_reopens` — in HALF_OPEN, `record_failure` →
  state goes back to OPEN and the cooldown clock resets.
- `test_concurrent_branches_do_not_double_trip` — fire ten concurrent
  `record_failure` calls via `asyncio.gather`; counter goes to 10 but
  the state transition logs at INFO exactly **once** (the threshold
  crossing), not on every increment.
- `test_last_reason_survives_trip` — record three failures with
  distinct reasons; `last_reason` equals the most-recent one. Assert
  that a `CircuitOpen(tier=..., last_reason=breaker.last_reason)`
  round-trips cleanly.

Tests use `freezegun` or a monkeypatched `time.monotonic` — **no real
sleep** (one existing convention in the repo; confirm in `tests/primitives/`
before adding a new dependency). If `freezegun` is not already pinned,
inject a `time_source: Callable[[], float] = time.monotonic` constructor
argument and stub it in tests rather than pulling in a new dep.

## Acceptance Criteria

- [ ] `from ai_workflows.primitives import CircuitBreaker, CircuitOpen, CircuitState` works.
- [ ] `CircuitState` transitions: CLOSED → (N failures) → OPEN → (cooldown)
      → HALF_OPEN → (success) → CLOSED **or** → (failure) → OPEN with
      cooldown reset.
- [ ] `allow()` in HALF_OPEN lets through exactly one probe until the
      next `record_*` call.
- [ ] All operations are `asyncio.Lock`-guarded; concurrent branches do
      not double-count past the threshold.
- [ ] State transitions log at INFO **exactly once per transition**
      (not once per increment).
- [ ] Every listed test passes under
      `uv run pytest tests/primitives/test_circuit_breaker.py`.
- [ ] `uv run lint-imports` — **4 contracts kept**.
- [ ] `uv run ruff check` clean.
- [ ] No new runtime dependency. If `freezegun` is chosen for time
      manipulation, it is a dev-dep only, pinned in
      `[tool.uv.dev-dependencies]` — not in `[project.dependencies]`.

## Dependencies

- [Task 01](task_01_health_check.md) (for the `HealthResult.reason`
  strings the breaker's `last_reason` ends up mirroring — not a hard
  code dependency, just a convention alignment).

## Out of scope (explicit)

- Storage-backed breaker state. (Process-local is intentional for M8;
  see design note above.)
- Per-run breaker isolation. The breaker is shared across runs on the
  same tier — one process, one breaker per tier. The slice_refactor
  parallel fan-out in M6 deliberately shares the semaphore at the
  same granularity.
- Breaker-reset CLI command (`aiw circuit reset <tier>`). (Not on the
  punch list; operators restart the process.)
- Integration with `TieredNode`. (T04.)
