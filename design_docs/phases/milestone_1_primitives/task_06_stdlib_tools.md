# Task 06 — Stdlib Tools (fs, shell, http, git)

**Issues:** P-13, P-14, P-15, P-16, P-17, P-18, P-19

## What to Build

The stdlib tool implementations. Language-agnostic. Returned as strings (LLM-reactable), never raised exceptions. Registered into the `ToolRegistry` at workflow load time.

## Deliverables

### `primitives/tools/fs.py`

- `read_file(path, max_chars=None)` — full content; optional truncation marker
- `write_file(path, content)` — creates parent dirs; logs overwrite
- `list_dir(path, pattern=None)` — glob-aware; caps at 500 entries
- `grep(pattern, path, max_results=100)` — regex search; caps output

All accept a `RunContext[WorkflowDeps]` parameter (pydantic-ai convention) — not shown above but always first param in the actual function signature. Gives every tool access to `run_id`, `allowed_executables`, `project_root`.

### `primitives/tools/shell.py`

`run_command(ctx, command, working_dir, dry_run=False, timeout_seconds=300)`:

**Guards (in order):**
1. **CWD containment** — `working_dir` must be under `ctx.deps.project_root`. `..` traversal → `SecurityError`.
2. **Executable allowlist** — first token of `command` must appear in `ctx.deps.allowed_executables`. Empty list = all blocked. → `ExecutableNotAllowedError`.
3. **Dry run** — returns `[DRY RUN] Would execute: {command}` without invoking subprocess.
4. **Timeout** — `subprocess.run(timeout=timeout_seconds)`; timeout → `CommandTimeoutError`.

Returns `"Exit {code}\n{output}"` on success or structured error string on failure. Never raises to the LLM.

### `primitives/tools/http.py`

`http_fetch(ctx, url, method="GET", max_chars=50_000, timeout=30)`:

Single HTTP tool (no separate `http_get`). Returns `"HTTP {code}\n{body}"` with body truncated at `max_chars`. Network errors return error description as string, don't raise.

### `primitives/tools/git.py`

- `git_diff(ctx, repo_path, ref="HEAD")` — 100K char cap
- `git_log(ctx, repo_path, max_entries=20)` — formatted one-per-line
- `git_apply(ctx, repo_path, diff_content, dry_run=False)` — **checks `git status --porcelain` first** and raises `DirtyWorkingTreeError` if non-empty. `dry_run=True` uses `git apply --check`.

### Registration

```python
def register_stdlib_tools(registry: ToolRegistry) -> None:
    registry.register("read_file", fs.read_file, "...")
    registry.register("write_file", fs.write_file, "...")
    # ... all tools registered here
```

Called at workflow run start, before `ToolRegistry` is passed to Components.

## Acceptance Criteria

- [ ] `read_file` handles UTF-8 and latin-1 fallback gracefully
- [ ] `..` in `working_dir` raises `SecurityError` with the attempted path
- [ ] Executable not in allowlist raises `ExecutableNotAllowedError`
- [ ] `dry_run=True` never invokes subprocess
- [ ] `git_apply` refuses on dirty working tree
- [ ] All tools return strings on error paths (test each failure mode returns str, not raises)
- [ ] Tools pull `allowed_executables` and `project_root` from `RunContext[WorkflowDeps]`

## Dependencies

- Task 02 (types)
- Task 05 (registry)

## Carry-over from prior audits

Forward-deferred items owned by this task. Treat each entry like an
additional acceptance criterion and tick it when the corresponding test or
change lands.

- [ ] **M1-T05-ISS-01** — End-to-end test that a real `pydantic_ai.Agent.run()`
  call routes a registered tool's output through
  `forensic_logger.log_suspicious_patterns()`. Use
  `pydantic_ai.models.test.TestModel` so no API key is needed. Register a
  tool whose output contains an `INJECTION_PATTERNS` marker; assert a
  `tool_output_suspicious_patterns` WARNING is emitted when the agent
  invokes it. The Task 05 tests call `tools[0].function(...)` directly —
  this carry-over pins the wrapper is still in the path under pydantic-ai's
  internal call protocol.
  Source: [issues/task_05_issue.md](issues/task_05_issue.md) — LOW.
  Alternative owner: M2 Task 02 (Worker).
- [ ] **M1-T05-ISS-03** — Standardise how non-string tool outputs reach the
  forensic scanner. The Task 05 wrapper calls `str(result)`, which is a
  no-op for the stdlib tools landing here (`read_file`, `grep`,
  `run_command` all return `str`). Either keep all stdlib tools returning
  `str` (recommended; document the convention in the module docstring) or
  wrap the value with pydantic-ai's JSON serialiser so the forensic scan
  sees the exact bytes the model receives. Pick one and pin it in code
  review.
  Source: [issues/task_05_issue.md](issues/task_05_issue.md) — LOW,
  informational. Alternative owner: M2 Task 02 (Worker), only if Worker
  introduces structured-output tools before this task closes.
