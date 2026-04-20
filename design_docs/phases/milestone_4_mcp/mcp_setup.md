# MCP Setup — registering `ai-workflows` with Claude Code

M4 Task 06 ships the ai-workflows MCP server as a standalone stdio process that any MCP host (Claude Code, Cursor, Zed, …) can spawn. This doc walks through registration with Claude Code — the primary target host per [KDR-002](../../architecture.md) and the solo-developer workflow.

Four tools are exposed (see [architecture.md §4.4](../../architecture.md)): `run_workflow`, `resume_run`, `list_runs`, `cancel_run`.

---

## 1. Prerequisites

- `uv sync` has been run (the console script `aiw-mcp` is resolvable — `uv run which aiw-mcp` returns a path under `.venv/bin/`).
- `GEMINI_API_KEY` is exported in the shell that will launch Claude Code. The MCP subprocess inherits the parent environment, so an unset key at launch time surfaces as a Gemini auth error on the first `run_workflow` call (see Troubleshooting §5).

No Anthropic API key is required or consulted — the ai-workflows runtime never touches the Anthropic API ([KDR-003](../../architecture.md)).

## 2. Register with Claude Code — `claude mcp add`

```bash
claude mcp add ai-workflows --scope user -- uv run aiw-mcp
```

- **Scope.** `--scope user` registers the server for every project. `--scope project` would scope it to the current repo; the solo-developer pattern is user-scope since ai-workflows is a general-purpose tool surface, not a per-project dependency.
- **Transport.** FastMCP's `server.run()` defaults to stdio — the same channel Claude Code's MCP client speaks. No flag change required.
- **Invocation.** `uv run aiw-mcp` resolves the console script registered in [pyproject.toml](../../../pyproject.toml) `[project.scripts]`. Use the full path to `uv` (e.g. `/usr/local/bin/uv`) if Claude Code's subprocess launch doesn't inherit your shell's `PATH`.

Verify registration:

```bash
claude mcp list
# expected: ai-workflows  →  uv run aiw-mcp  (stdio)
```

## 3. Alternative — `.mcp.json` (file-based registration)

For users who prefer file-based registration or need the server scoped to a specific project, drop the following into `.mcp.json` at the project root (or Claude Code's user-level config file):

```json
{
  "mcpServers": {
    "ai-workflows": {
      "command": "uv",
      "args": ["run", "aiw-mcp"],
      "env": {
        "GEMINI_API_KEY": "${GEMINI_API_KEY}"
      }
    }
  }
}
```

The `env` block is the canonical way to pass secrets through to the subprocess; `${GEMINI_API_KEY}` interpolation picks up the parent environment at spawn time.

## 4. Smoke check

From a fresh Claude Code session registered against `aiw-mcp`, ask Claude Code to call `run_workflow` against the M3 `planner`:

> "Using the `ai-workflows` MCP server, call `run_workflow` with `workflow_id='planner'`, `inputs={'goal': 'Write a release checklist'}`, and a fresh `run_id`."

Expected response shape (the `planner` pauses at the `HumanGate`):

```json
{
  "run_id": "<whatever-id-was-passed>",
  "status": "pending",
  "awaiting": "gate",
  "plan": null,
  "total_cost_usd": 0.00XX,
  "error": null
}
```

Then approve the gate:

> "Call `resume_run` with that `run_id` and `gate_response='approved'`."

Expected: `status="completed"` + populated `plan` + rolled-up `total_cost_usd`.

Round-trip verified — the MCP surface is live.

## 5. Troubleshooting

### (a) `command not found: aiw-mcp` / `command not found: uv`

Claude Code spawned the subprocess with a reduced `PATH`. Fixes:

- Pass the absolute path explicitly: `claude mcp add ai-workflows --scope user -- /usr/local/bin/uv run aiw-mcp` (substitute the output of `which uv`).
- Or, in the `.mcp.json` `command` field, use the absolute path.

### (b) Gemini auth error on first `run_workflow`

The subprocess did not inherit `GEMINI_API_KEY`. Fixes:

- **Shell registration.** Export `GEMINI_API_KEY` in the shell that launches Claude Code *before* launching it (e.g. from `~/.zshrc` / `~/.bashrc` rather than from a script that sets it after Claude Code starts).
- **`.mcp.json` registration.** Ensure the `env` block forwards the variable (as shown in §3); verify with `claude mcp list` that the env is registered.

### (c) Server starts but no tools listed

`uv sync` has not been re-run since the last `pyproject.toml` change. Run `uv sync` and re-register.

---

## Scope boundary (what this registration does **not** cover)

- **In-flight cancellation.** `cancel_run` flips the `runs` row to `cancelled`; it does **not** abort an already-running LangGraph task. The planner workflow spends almost all of its time paused at the `HumanGate`, so the flip covers the dominant case. In-flight cancellation lands at M6 T02 ([architecture.md §8.7](../../architecture.md)).
- **HTTP transport.** Stdio only at M4 — the FastMCP HTTP transport is deferred until a concrete need arises (multi-client fan-out, remote hosts). See [M4 README Non-goals](README.md).
- **Cost reporting tool.** `get_cost_report` was dropped at M4 kickoff in favour of the `total_cost_usd` field on each `RunSummary` returned by `list_runs`. See [nice_to_have.md §9](../../nice_to_have.md) for the adoption triggers that would promote a dedicated cost tool back in.
