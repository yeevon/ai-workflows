# Task 05 — OTel Observability via Logfire (NEW)

**Issues:** IMP-02

## What to Build

Wire `logfire.instrument_anthropic()` and `logfire.instrument_openai()`. Every LLM call made through pydantic-ai's models emits OpenTelemetry GenAI spans automatically. No adapter code changes.

## Why This Matters

OTel GenAI semantic conventions are the interoperability layer between every observability/eval tool (Langfuse, Phoenix, Braintrust, Logfire itself). Emitting these spans costs two lines and buys integration with all of them for free.

## Deliverables

### `primitives/logging.py` Update

Extend `configure_logging()`:

```python
def configure_logging(level: str = "INFO", run_id: str | None = None) -> None:
    logfire.configure(
        service_name="ai_workflows",
        send_to_logfire=os.getenv("LOGFIRE_TOKEN") is not None,
    )
    logfire.instrument_anthropic()
    logfire.instrument_openai()        # covers OpenAI, DeepSeek, Ollama (same client)
    logfire.instrument_httpx()         # tool HTTP calls

    # structlog setup as before
    ...
```

### Spans Emitted Automatically

For every `agent.run()`:

```text
gen_ai.operation.name=chat
gen_ai.request.model=claude-sonnet-4-6
gen_ai.usage.input_tokens=1523
gen_ai.usage.output_tokens=847
gen_ai.usage.cache_read_input_tokens=1200
gen_ai.response.model=claude-sonnet-4-6
gen_ai.response.finish_reason=end_turn
```

Plus nested spans for each tool call made during the agent's turns.

### Export Destinations

Three export options, selected by env var:

- `LOGFIRE_TOKEN=xxx` → Logfire cloud (Pydantic's hosted observability)
- `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318` → self-hosted OTel collector (Phoenix, Jaeger, Grafana)
- Neither → spans emit to stderr as readable console output (local dev)

### Verification

```python
async def test_otel_spans_emitted():
    """After an agent.run(), exactly one gen_ai span exists with expected attrs."""
    with logfire.capture() as captured:
        await agent.run("test", deps=deps)
    assert any(
        s.attributes.get("gen_ai.operation.name") == "chat"
        for s in captured.spans
    )
```

### Surfacing in `aiw inspect`

Extend `aiw inspect <run_id>` to print a "GenAI spans" section when span data is available:

```text
GenAI Spans:
  14:32:10  chat  claude-sonnet-4-6   1523 in / 847 out / 1200 cached  $0.08
  14:32:18  chat  claude-haiku-4-5    432 in / 156 out / 0 cached      $0.00
  ...
```

This is a joined query between the `llm_calls` table and a new `otel_spans` table (or Logfire's API if using cloud).

## Acceptance Criteria

- [ ] `logfire.instrument_anthropic()` called during `configure_logging()`
- [ ] A real agent.run() emits a `gen_ai.operation.name=chat` span
- [ ] Span attributes include input_tokens, output_tokens, cache_read_tokens
- [ ] Tool calls within the agent emit nested spans
- [ ] `OTEL_EXPORTER_OTLP_ENDPOINT=...` routes spans to that collector (test with a local receiver)
- [ ] `LOGFIRE_TOKEN` unset → no network calls to logfire.dev

## Dependencies

- M1 Task 11 (logging base)
- M1 Task 03 (model factory)
