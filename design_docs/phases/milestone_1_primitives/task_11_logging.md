# Task 11 — Logging (structlog + logfire)

**Status:** ✅ Complete (2026-04-19)

**Issues:** P-42, P-43, P-44 (resolves carry-overs M1-T05-ISS-02, M1-T01-ISS-08)

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

- [x] `configure_logging("INFO")` suppresses DEBUG
  — pinned by `tests/primitives/test_logging.py::test_info_level_suppresses_debug`
  and `::test_warning_level_suppresses_debug_and_info` (reinforcement)
  and `::test_level_is_case_insensitive`.
- [x] `configure_logging("DEBUG")` produces human-readable console output
  — `::test_debug_level_emits_human_readable_console` asserts the
  event name, key, value, and bracketed `[debug` token are all
  present; `::test_debug_console_output_is_not_json` asserts the
  first line fails `json.loads`.
- [x] JSON output validates as JSON
  — `::test_info_level_emits_valid_json_per_line` parses each stderr
  line via `json.loads` and asserts the `event`, user kwargs,
  `level`, and `timestamp` fields.
- [x] Per-run log file is created at `runs/<run_id>/run.log` when `run_id` is provided
  — `::test_per_run_file_is_created_when_run_id_given`,
  `::test_per_run_file_receives_json_lines`,
  `::test_per_run_file_is_always_json_even_in_debug_mode`,
  `::test_no_per_run_file_when_run_id_missing` (negative coverage).
- [x] `logfire.configure()` does not attempt to send to logfire.dev unless `LOGFIRE_TOKEN` is set
  — `::test_logfire_configure_receives_if_token_present` patches
  `logfire.configure` and asserts the kwarg is
  `send_to_logfire="if-token-present"` (the SDK's documented knob
  for "send iff env has LOGFIRE_TOKEN");
  `::test_logfire_pydantic_instrumentation_is_invoked` pins the
  modern `instrument_pydantic(record="all")` call path.
- [x] `structlog.get_logger()` works from any module after `configure_logging()` is called
  — `::test_get_logger_works_from_arbitrary_module_name` (two
  arbitrary module names), `::test_get_logger_with_no_name_works`.

## Dependencies

- Task 01 (scaffolding)

## Carry-over from prior audits

Forward-deferred items owned by this task. Treat each entry like an
additional acceptance criterion and tick it when the corresponding test or
change lands.

- [x] **M1-T01-ISS-08** — Optional hardening for the `secret-scan` CI check.
  Today `tests/test_scaffolding.py::test_secret_scan_regex_matches_known_key_shapes`
  hard-codes the `sk-ant-[A-Za-z0-9_-]+` pattern so a narrower CI regex
  can drift undetected. Option-2 from the Task 01 audit: parse
  `.github/workflows/ci.yml` at test time and extract the live regex so
  the test and CI always agree. Nice-to-have, not required.
  Source: [issues/task_01_issue.md](issues/task_01_issue.md) — LOW.
  Resolved by M1 Task 11 — `_extract_ci_secret_scan_regex()` in
  `tests/test_scaffolding.py` greps the live `grep -E '<regex>'`
  invocation out of `ci.yml` and feeds it to the regex-shape test;
  `::test_secret_scan_regex_is_extracted_from_ci_yml` guards the
  extractor itself.
- [x] **M1-T05-ISS-02** — Smoke test that a forensic `WARNING` emitted by
  `ai_workflows.primitives.tools.forensic_logger.log_suspicious_patterns()`
  survives the production structlog processor chain configured here.
  Call the function through the real pipeline and assert the event lands
  in the expected sink with `level=warning` and the four expected keys
  (`tool_name`, `run_id`, `patterns`, `output_length`). Task 05's unit
  tests reconfigure structlog themselves; this carry-over pins the
  behaviour under the *real* configuration.
  Source: [issues/task_05_issue.md](issues/task_05_issue.md) — LOW.
  Resolved by M1 Task 11 —
  `tests/primitives/test_logging.py::test_forensic_warning_survives_production_pipeline`
  drives `log_suspicious_patterns` through `configure_logging(...,
  run_id=..., run_root=tmp_path)` and asserts the event lands in
  `run.log` with `level=warning`, `event=tool_output_suspicious_patterns`,
  `tool_name`, `run_id`, `patterns` (non-empty list), and
  `output_length > 0`.
