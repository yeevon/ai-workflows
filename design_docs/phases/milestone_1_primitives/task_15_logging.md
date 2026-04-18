# Task 15 — Logging Setup

**Issues:** P-42, P-43

## What to Build

Configure `structlog` once at process startup. All other modules import and use `structlog.get_logger()` — no configuration in individual modules.

## Deliverables

### `primitives/logging.py`

```python
import structlog

def configure_logging(level: str = "INFO") -> None:
    """
    Call once at CLI startup. Sets up structlog with:
    - JSON output for INFO and above (machine-readable run logs)
    - Console output for DEBUG (human-readable dev output)
    - Bound context: run_id, workflow_id, component (if set)
    """
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer() if level == "DEBUG"
            else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level)
        ),
    )
```

**Log levels by event type:**
- `INFO`: run started/finished, task state transitions, cost summaries, HumanGate events
- `DEBUG`: full LLM inputs and outputs (can be very large), tool call inputs/outputs
- `WARNING`: sanitizer hits, rate limit retries, model not found in pricing
- `ERROR`: hard failures, validation errors, unrecoverable states

**Log file:** In addition to stderr, write JSON logs to `~/.ai-workflows/runs/<run_id>/run.log` via a file handler added in `configure_logging()` when `run_id` is known.

## Acceptance Criteria

- [ ] `configure_logging("INFO")` suppresses DEBUG events
- [ ] `configure_logging("DEBUG")` shows DEBUG events with console formatting
- [ ] JSON output is valid JSON (parse in tests)
- [ ] `structlog.get_logger()` works from any module after `configure_logging()` is called once

## Dependencies

- Task 01 (scaffolding)
