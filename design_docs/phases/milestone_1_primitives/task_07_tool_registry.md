# Task 07 — Tool Registry

**Issues:** P-11, P-20

## What to Build

An injected `ToolRegistry` instance per workflow run. Stdlib tools are registered at startup. Workflow-specific custom tools are registered before the workflow executes. No global singleton.

## Deliverables

### `primitives/tools/registry.py`

```python
class ToolRegistry:
    def register(self, spec: ToolSpec, fn: Callable) -> None: ...
    def get(self, name: str) -> tuple[ToolSpec, Callable]: ...
    def get_specs(self, names: list[str]) -> list[ToolSpec]: ...
    def execute(self, name: str, input: dict) -> str: ...
```

**Key behaviors:**

- `register()`: associates a `ToolSpec` (name + description + JSON schema) with a callable. Raises `DuplicateToolError` if a name is already registered.
- `get_specs(names)`: returns only the `ToolSpec`s for the listed tool names. This is what callers pass to `generate(tools=...)`. Never passes the full registry to the LLM.
- `execute(name, input)`: calls the registered function with validated inputs, runs the result through `sanitize_tool_output()`, returns a clean string.
- `@tool` decorator (convenience): registers a function into a given registry instance. Not a global decorator — takes a `registry` parameter.

**Workflow usage pattern:**
```python
registry = ToolRegistry()
register_stdlib_tools(registry)          # fs, shell, http, git
register_custom_tools(registry, workflow_dir)  # from custom_tools.py
```

**Test isolation:** Each test creates its own `ToolRegistry()`. No shared state between tests.

## Acceptance Criteria

- [ ] `register()` + `execute()` round-trip works for a simple tool
- [ ] `get_specs(["read_file", "grep"])` returns only those two specs
- [ ] `DuplicateToolError` raised on name collision
- [ ] `execute()` output is sanitized (verify sanitizer is called)
- [ ] Two registries in the same process have no shared state

## Dependencies

- Task 02 (shared types — `ToolSpec`)
- Task 06 (sanitizer)
