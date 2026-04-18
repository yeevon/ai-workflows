# Task 11 — Logging (structlog + logfire)

**Issues:** P-42, P-43, P-44

## What to Build

Configure `structlog` for structured logging + `logfire` for OTel GenAI observability. OTel `instrument_anthropic()` wiring happens in M3 (task IMP-02) — at M1, we just configure both so the hooks exist.

## Deliverables

### `primitives/logging.py`

```python
import structlog
import logfire

def configure_logging(level: str = "INFO", run_id: str | None = None) -> None:
    """
    Configure structlog + logfire once at CLI startup.

    - structlog emits JSON to ~/.ai-workflows/runs/<run_id>/run.log
    - structlog emits console output for DEBUG mode
    - logfire.configure() sets up OTel exporter
    - In M1, logfire is configured but no adapters are instrumented
    - In M3, add logfire.instrument_anthropic() / instrument_openai()
    """
    logfire.configure(
        send_to_logfire=False,  # local only by default; can flip via env var
        service_name="ai_workflows",
        pydantic_plugin=logfire.PydanticPlugin(record="all"),
    )

    # structlog setup
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    if level == "DEBUG":
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level)
        ),
    )

    if run_id:
        # Add per-run file sink
        _add_run_file_handler(run_id)
```

### Log Levels

- **INFO**: run lifecycle (start, finish, failure), cost summaries, HumanGate events, retries, sanitizer hits (forensic)
- **DEBUG**: full LLM inputs/outputs, tool call inputs/outputs, token counts per call
- **WARNING**: forensic_logger pattern hits, model not in pricing, rate limit retries, cache misses on static prompts
- **ERROR**: unrecoverable failures, BudgetExceeded, SecurityError, HumanGate rejections

### Two Sinks

1. **stderr** — human-readable in DEBUG, JSON in INFO+
2. **per-run file** — `~/.ai-workflows/runs/<run_id>/run.log` — JSON always. One file per run. No rotation needed because each run is a fresh file.

### What Happens in M3

When `logfire.instrument_anthropic()` and `logfire.instrument_openai()` are added in M3:

- Every LLM call automatically emits an OTel GenAI span with: `gen_ai.operation.name`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.response.model`
- Spans are sent to Logfire (or any OTel backend via `OTEL_EXPORTER_OTLP_ENDPOINT`)
- Zero change to adapter code — pydantic-ai's models use the underlying SDK clients which logfire has already instrumented

## Acceptance Criteria

- [ ] `configure_logging("INFO")` suppresses DEBUG
- [ ] `configure_logging("DEBUG")` produces human-readable console output
- [ ] JSON output validates as JSON
- [ ] Per-run log file is created at `runs/<run_id>/run.log` when `run_id` is provided
- [ ] `logfire.configure()` does not attempt to send to logfire.dev unless `LOGFIRE_TOKEN` is set
- [ ] `structlog.get_logger()` works from any module after `configure_logging()` is called

## Dependencies

- Task 01 (scaffolding)
