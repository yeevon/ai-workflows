# Task 06 — stdio Transport + `claude mcp add` Setup Docs

**Status:** 📝 Planned.

## What to Build

Make the MCP server runnable as a standalone process over stdio, and document how to register it with Claude Code. Stdio is the only transport M4 ships ([README.md Non-goals](README.md) — HTTP deferred). Fulfils [README.md exit criterion 3](README.md) — a documented `claude mcp add` invocation registers the server and the server answers a live `run_workflow` call against the M3 planner.

Aligns with [architecture.md §4.4](../../architecture.md), KDR-002, KDR-008.

## Deliverables

### `ai_workflows/mcp/__main__.py` — entry point

```python
"""Run the ai-workflows MCP server over stdio.

Invoked as ``python -m ai_workflows.mcp`` or via the console script
``aiw-mcp`` (registered in pyproject.toml).
"""
from __future__ import annotations

from ai_workflows.mcp.server import build_server
from ai_workflows.primitives.logging import configure_logging


def main() -> None:
    """stdio-mode entry point for the MCP server."""
    configure_logging(level="INFO")
    server = build_server()
    server.run()  # FastMCP's default transport is stdio


if __name__ == "__main__":
    main()
```

### `pyproject.toml` — console script

Add under `[project.scripts]`:

```toml
aiw-mcp = "ai_workflows.mcp.__main__:main"
```

Verify `uv sync` regenerates the lock and `uv run aiw-mcp` resolves.

### `design_docs/phases/milestone_4_mcp/mcp_setup.md` — setup doc

A short how-to covering:

1. **Prerequisites.** `GEMINI_API_KEY` exported; `uv sync` run.
2. **Register with Claude Code.** The exact `claude mcp add` command, e.g.:

   ```bash
   claude mcp add ai-workflows --scope user -- uv run aiw-mcp
   ```

   Confirm the scope choice (`--scope user` vs `--scope project`) matches the solo-developer pattern.
3. **Alternative: MCP JSON config.** Equivalent snippet for `.mcp.json` / Claude Code's config file, for users who prefer a file-based registration. Show the exact structure FastMCP's stdio transport expects.
4. **Smoke check.** One-line invocation the user can run from a fresh Claude Code session to prove the server answered: e.g. ask Claude Code to call `run_workflow` against the `planner` with a short goal, observe the returned `{run_id, awaiting: "gate"}`, then `resume_run` it.
5. **Troubleshooting.** The two realistic failure modes: (a) binary not on `PATH` → `command not found`; (b) `GEMINI_API_KEY` not inherited by the Claude Code subprocess → Gemini auth error in the first `run_workflow`. Fixes for each.

### `README.md` (root) — one-line pointer

Add a line to the root README `## Getting started` (or a new `## MCP server` subsection) pointing at the setup doc. Do not duplicate the content — the doc is the canonical source.

### Tests

`tests/mcp/test_entrypoint.py`:

- `python -m ai_workflows.mcp --help` (or equivalent FastMCP CLI introspection) runs without error.
- `from ai_workflows.mcp.__main__ import main` imports cleanly.
- The console script `aiw-mcp` is resolvable via `importlib.metadata.entry_points` (pins the `pyproject.toml` entry).

Live stdio transport is exercised by [Task 07](task_07_mcp_smoke.md)'s in-process smoke test + manual validation of the `claude mcp add` loop (not automated — manual verification only, captured in the T08 close-out CHANGELOG entry).

## Acceptance Criteria

- [ ] `ai_workflows/mcp/__main__.py` exists; `python -m ai_workflows.mcp` starts the server over stdio.
- [ ] `aiw-mcp` console script resolves post-`uv sync`.
- [ ] `mcp_setup.md` documents the exact `claude mcp add` invocation + the MCP JSON config alternative.
- [ ] A fresh Claude Code session registered against `aiw-mcp` can invoke `run_workflow` against `planner` and receive `{run_id, awaiting: "gate"}` (manual — record the tested command + output in the T08 CHANGELOG entry).
- [ ] `uv run pytest tests/mcp/test_entrypoint.py` green.
- [ ] `uv run lint-imports` 3 / 3 kept; `uv run ruff check` clean.

## Dependencies

- [Tasks 01–05](README.md) — all four tools must be wired before stdio registration is meaningful.
- `fastmcp>=0.2` — already in [pyproject.toml](../../../pyproject.toml).
- Claude Code CLI available on the developer's `PATH` (for the manual verification step).
