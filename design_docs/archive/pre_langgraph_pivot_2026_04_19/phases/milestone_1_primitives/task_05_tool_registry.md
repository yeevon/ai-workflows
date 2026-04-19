# Task 05 — Tool Registry and Forensic Logger

**Status:** ✅ Complete (2026-04-18) — see [issues/task_05_issue.md](issues/task_05_issue.md).

**Issues:** P-11, P-20, CRIT-04 (revises X-07)

## What to Build

Two things:

1. **`ToolRegistry`** — injected per-workflow, curates which tools are exposed to which components. pydantic-ai Agents get tools passed to them via `tools=[...]` parameter; our registry is the source.
2. **`forensic_logger`** — the renamed/rebranded former sanitizer. Logs suspicious patterns in tool outputs for POST-HOC analysis. It is NOT a security control.

## Why the Rename (CRIT-04)

The original `sanitizer.py` promised protection against prompt injection via regex pattern matching. Pattern matching does not defend against adversarial content — Simon Willison's writing is unambiguous here. Keeping it as "defense" creates false confidence.

**The real defense is already in place:**
- Tool outputs are wrapped as `tool_result` `ContentBlock` (data, not instructions)
- `run_command` has CWD restriction + allowlist + dry_run
- `HumanGate` on destructive operations
- Tool allowlists per component (via the registry you're about to build)

**What the logger actually does:** flags and records when tool outputs contain patterns like `IGNORE PREVIOUS INSTRUCTIONS`, so AFTER a bad run you can audit what the model was asked. It does NOT modify the content fed to the model.

## Deliverables

### `primitives/tools/registry.py`

```python
class ToolRegistry:
    """Injected per workflow run. Not a singleton."""

    def register(self, name: str, fn: Callable, description: str) -> None: ...

    def get_tool_callable(self, name: str) -> Callable: ...

    def build_pydantic_ai_tools(self, names: list[str]) -> list[Tool]:
        """
        Return a list of pydantic_ai.Tool instances for the given tool names.
        Used in Agent(tools=...) construction.
        """
```

**Key behavior:** `build_pydantic_ai_tools()` returns only the tools named. A Worker config declaring `tools: [read_file, grep]` gets exactly those two — never the full registry. This is per-component tool scoping (Anthropic subagent pattern).

### `primitives/tools/forensic_logger.py`

```python
INJECTION_PATTERNS = [
    r"IGNORE (PREVIOUS|ABOVE|ALL) INSTRUCTIONS",
    r"YOU ARE NOW",
    r"SYSTEM:",
    r"<\|im_start\|>",
    r"\[INST\]",
    # ...
]

def log_suspicious_patterns(
    tool_name: str,
    output: str,
    run_id: str,
) -> None:
    """
    Scan output for known injection patterns. Log matches to structlog
    with WARNING level. Does NOT modify the output.

    This is forensic logging for post-hoc analysis, NOT a security control.
    The real defense is ContentBlock tool_result wrapping, tool allowlists,
    CWD restriction, and HumanGate — all elsewhere.
    """
```

**Docstring emphasizes:** this is logging only. No stripping, no modification. Any security-critical decisions rely on the layers above.

### Tool Execution Flow

When pydantic-ai calls a tool registered via our registry:

1. pydantic-ai invokes the registered callable
2. Callable returns raw output
3. Our wrapper calls `forensic_logger.log_suspicious_patterns()` (logs only, no mutation)
4. Raw output is passed back to pydantic-ai as the tool result
5. pydantic-ai packages it into its internal message format (which maps to our `ToolResultBlock` semantics)

The `ContentBlock` `tool_result` wrapping happens by virtue of pydantic-ai's protocol — that's the actual defense.

## Acceptance Criteria

- [x] Two `ToolRegistry()` instances in the same process have zero shared state
- [x] `build_pydantic_ai_tools(["read_file"])` returns only 1 tool, not the full registry
- [x] `forensic_logger` matches and logs injection patterns without modifying output
- [x] A `WARNING` structlog event appears when output contains a known pattern
- [x] Docstrings on `forensic_logger` explicitly state it is NOT a security control

## Dependencies

- Task 01
- Task 02 (types)
