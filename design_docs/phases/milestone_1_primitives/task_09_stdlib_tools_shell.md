# Task 09 — Stdlib Tools: Shell

**Issues:** P-13, P-14, P-15

## What to Build

The `run_command` tool with CWD restriction, executable allowlist, and dry-run mode. This is the highest-risk stdlib tool — small LLMs can make unexpected calls.

## Deliverables

### `primitives/tools/shell.py`

**`run_command(command: str, working_dir: str, dry_run: bool = False) -> str`**

**Guards (enforced before execution):**
1. **CWD restriction:** `working_dir` must be within the declared project root (set at workflow run start via `RunContext`). Reject any `..` traversal. Raise `SecurityError` with the attempted path.
2. **Executable allowlist:** First token of `command` (the executable name) must appear in the workflow's `allowed_executables` list. If empty list: all executables blocked. Raise `ExecutableNotAllowedError` with the executable name and the allowlist.
3. **Dry run:** If `dry_run=True`, log `[DRY RUN] Would execute: {command}` and return that string without executing.

**Execution:**
- `subprocess.run()` with `timeout` (configurable, default 300s)
- Capture stdout + stderr combined
- Return `"Exit {code}\n{output}"` — LLM sees both exit code and output
- Timeout raises `CommandTimeoutError` with the command and timeout value

**`RunContext` for allowlist:** The workflow injects `allowed_executables: list[str]` into a `RunContext` object that `run_command` reads. This is set at workflow load time, not per-call.

## Acceptance Criteria

- [ ] `..` traversal in `working_dir` raises `SecurityError`
- [ ] Command not in allowlist raises `ExecutableNotAllowedError`
- [ ] `dry_run=True` returns the would-execute string without running anything
- [ ] Timeout raises `CommandTimeoutError` (use a short timeout in tests with a `sleep` command)
- [ ] Exit code and stdout/stderr both appear in the returned string

## Dependencies

- Task 07 (tool registry)
