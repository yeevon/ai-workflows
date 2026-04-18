# Task 08 — Stdlib Tools: Filesystem

**Issues:** P-16

## What to Build

The filesystem stdlib tools. Language-agnostic — no AST parsing, no file-type assumptions. Summarization of file content is a Worker-level concern driven by prompts, not these tools.

## Deliverables

### `primitives/tools/fs.py`

**`read_file(path: str, max_chars: int | None = None) -> str`**
- Reads file at `path`, returns content as string
- If `max_chars` is set, truncates and appends `\n[TRUNCATED at {max_chars} chars]`
- Raises `FileNotFoundError` with the path in the message if file doesn't exist
- No encoding assumption — try UTF-8, fall back to latin-1 with a note in the output

**`write_file(path: str, content: str) -> str`**
- Writes `content` to `path`, creating parent dirs if needed
- Returns `"Written {len(content)} chars to {path}"`
- Does NOT overwrite without warning — if file exists, log a structlog info event

**`list_dir(path: str, pattern: str | None = None) -> str`**
- Lists directory contents, one path per line
- `pattern` is an optional glob (e.g., `"**/*.py"`)
- Returns relative paths from `path`
- Caps at 500 entries, appends `[{N} more entries not shown]` if over cap

**`grep(pattern: str, path: str, max_results: int = 100) -> str`**
- Regex search in files under `path`
- Returns `file:line_number: matched_line` format, one per line
- Caps at `max_results`, appends count of additional matches

**Registration:**
```python
def register_fs_tools(registry: ToolRegistry) -> None:
    registry.register(ToolSpec(name="read_file", ...), read_file)
    registry.register(ToolSpec(name="write_file", ...), write_file)
    registry.register(ToolSpec(name="list_dir", ...), list_dir)
    registry.register(ToolSpec(name="grep", ...), grep)
```

## Acceptance Criteria

- [ ] `read_file` truncates correctly at `max_chars`
- [ ] `read_file` handles binary files gracefully (doesn't crash)
- [ ] `list_dir` with glob pattern returns only matching files
- [ ] `grep` caps results and reports additional count
- [ ] All tools return strings (never raise unhandled exceptions — return error description as string so LLM can react)

## Dependencies

- Task 07 (tool registry)
