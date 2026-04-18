# Task 10 — Stdlib Tools: HTTP and Git

**Issues:** P-17, P-18, P-19

## What to Build

HTTP fetch tool (single tool, not two) and git inspection/apply tools.

## Deliverables

### `primitives/tools/http.py`

**`http_fetch(url: str, method: str = "GET", max_chars: int = 50000) -> str`**
- Single HTTP tool (replaces the `http_get` / `http_fetch` ambiguity from the design doc — `http_fetch` is the name)
- Supports GET and POST (`method` param)
- Returns response body as string, truncated at `max_chars`
- Returns `"HTTP {status_code}\n{body}"` so the LLM sees the status
- Timeout: 30s default
- On network error: return error description as string (don't raise — LLM should be able to react)

---

### `primitives/tools/git.py`

**`git_diff(repo_path: str, ref: str = "HEAD") -> str`**
- Returns `git diff {ref}` output for the repo at `repo_path`
- Caps at 100K chars, appends `[TRUNCATED]` if over

**`git_log(repo_path: str, max_entries: int = 20) -> str`**
- Returns last N commits: `{hash} {date} {author}: {message}`, one per line

**`git_apply(repo_path: str, diff_content: str, dry_run: bool = False) -> str`**
- Applies a unified diff to the repo
- **Safety check first:** calls `git status --porcelain`. If output is non-empty (dirty working tree), raise `DirtyWorkingTreeError` with the status output — do not apply.
- `dry_run=True`: runs `git apply --check` (validates without applying)
- Returns `"Applied successfully"` or `"Failed: {error}"`

## Acceptance Criteria

- [ ] `http_fetch` returns status code in response string
- [ ] `http_fetch` truncates at `max_chars`
- [ ] `git_apply` with dirty working tree raises `DirtyWorkingTreeError`
- [ ] `git_apply` with `dry_run=True` validates without modifying files
- [ ] All tools return strings on error (no unhandled exceptions)

## Dependencies

- Task 07 (tool registry)
