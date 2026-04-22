# Task 01 — HTTP transport flag + CORS middleware + tests + doc

**Status:** 📝 Planned (drafted 2026-04-22).
**Grounding:** [milestone README](README.md) · [architecture.md §4.4](../../architecture.md) · [ai_workflows/mcp/__main__.py](../../../ai_workflows/mcp/__main__.py) · [ai_workflows/mcp/server.py](../../../ai_workflows/mcp/server.py) · [ai_workflows/cli.py](../../../ai_workflows/cli.py) (Typer pattern).

## What to Build

Extend `aiw-mcp` with a `--transport` flag. When `http` is selected, the same FastMCP server instance that stdio runs today is served over streamable-HTTP at a configurable host/port with optional permissive CORS for configured origins. Stdio remains the default; every existing host registration keeps working byte-identically.

No schema change, no new provider, no new layer. The diff is ~40 lines of Python plus tests.

## Deliverables

### [ai_workflows/mcp/__main__.py](../../../ai_workflows/mcp/__main__.py) — entry-point rewrite

Replace the argument-free `main()` with a Typer-decorated command that accepts the four flags from the milestone README exit criterion 1.

```python
from __future__ import annotations

from typing import Literal

import typer

from ai_workflows.mcp.server import build_server
from ai_workflows.primitives.logging import configure_logging

app = typer.Typer(add_completion=False, help="ai-workflows MCP server.")


@app.command()
def main(
    transport: Literal["stdio", "http"] = typer.Option(
        "stdio",
        "--transport",
        help="Transport. `stdio` (default) matches every existing MCP host. "
             "`http` serves over streamable-HTTP for browser-origin consumers.",
    ),
    host: str = typer.Option(
        "127.0.0.1",
        "--host",
        help="Bind address when --transport http. Loopback default; pass "
             "0.0.0.0 only if you own every process on the host.",
    ),
    port: int = typer.Option(
        8000,
        "--port",
        min=1,
        max=65535,
        help="TCP port when --transport http.",
    ),
    cors_origin: list[str] = typer.Option(
        None,
        "--cors-origin",
        help="Origin to permit via CORS. Repeatable. Empty (default) means "
             "same-origin only. Exact-match; no regex.",
    ),
) -> None:
    """Start the MCP server on the selected transport."""
    configure_logging(level="INFO")
    server = build_server()
    if transport == "stdio":
        server.run()
        return
    _run_http(server, host=host, port=port, cors_origins=cors_origin or [])


def _run_http(server, *, host: str, port: int, cors_origins: list[str]) -> None:
    """Attach CORS middleware (if any) and run streamable-HTTP."""
    if cors_origins:
        from starlette.middleware.cors import CORSMiddleware  # noqa: PLC0415

        server.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["*"],
        )
    server.run(transport="streamable-http", host=host, port=port)


if __name__ == "__main__":
    app()
```

- **Module docstring updated** to cover both transports and cite M14 alongside the original M4 T06 citation.
- **`app = typer.Typer(...)` pattern** matches [`ai_workflows/cli.py`](../../../ai_workflows/cli.py) exactly.
- **`_run_http` is module-private** and takes the server object as a parameter — tests import `_run_http` directly when exercising the HTTP path on an ephemeral port without going through Typer.
- **`server.add_middleware(...)` surface** — FastMCP 3.x exposes the underlying Starlette ASGI app; verify the exact attribute/method at implementation time. If the public surface is `server.app.add_middleware(...)`, use that. Spec commits to the behaviour (CORS middleware attached before `run()`), not the specific private API shape — Builder updates the line if FastMCP exposes a different accessor.
- **Import of `CORSMiddleware` stays inside `_run_http`** to keep the stdio path free of starlette import cost. The `# noqa: PLC0415` suppresses ruff's "import at top of module" rule for this intentional case.

### [ai_workflows/mcp/__init__.py](../../../ai_workflows/mcp/__init__.py) — re-export check

Confirm that `build_server` is already exported. If not, no change — the test file imports `from ai_workflows.mcp.server import build_server` directly.

### [tests/mcp/test_http_transport.py](../../../tests/mcp/test_http_transport.py) — new

Four hermetic tests (one per milestone-README exit criterion 7 bullet). Use `socket.socket` to reserve an ephemeral port; start the server in a background thread; poll the port with `httpx` until it answers; tear down.

```python
"""HTTP transport tests for aiw-mcp (M14 T01).

Exercises the streamable-HTTP path end-to-end on ephemeral localhost
ports. No live provider — tool stubbing mirrors the stdio-path fixtures
under tests/mcp/.
"""

import asyncio
import socket
import threading
from contextlib import closing

import httpx
import pytest

from ai_workflows.mcp.__main__ import _run_http
from ai_workflows.mcp.server import build_server


def _reserve_ephemeral_port() -> int:
    """Reserve a free TCP port by binding (0), releasing, returning it."""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def http_server(...):
    """Start aiw-mcp over HTTP on an ephemeral port; tear down on yield."""
    ...  # background thread + poll-until-ready + join-on-teardown
```

Test bodies assert:

1. **`test_http_transport_starts_and_serves_run_workflow`** — POST a JSON-RPC `run_workflow` call; response payload matches the stdio round-trip shape for the `planner` workflow with a stubbed tier adapter. Re-uses the stub-adapter fixture pattern from [`tests/mcp/test_run_workflow.py`](../../../tests/mcp/test_run_workflow.py).
2. **`test_http_cors_headers_present_when_origin_configured`** — server started with `cors_origins=["http://localhost:4321"]`; preflight `OPTIONS` request with `Origin: http://localhost:4321`; assert `Access-Control-Allow-Origin: http://localhost:4321` in response.
3. **`test_http_cors_headers_absent_when_origin_unconfigured`** — server started with `cors_origins=[]`; same preflight; assert no `Access-Control-Allow-Origin` header.
4. **`test_http_default_bind_is_loopback`** — start via Typer runner with `--transport http` and no `--host`; inspect the listener's bound address; assert `127.0.0.1`. Alternative if inspecting the listener is awkward: assert that a connection to `127.0.0.1` succeeds AND a connection to the machine's hostname IP fails with `ConnectionRefusedError` — but this is flaky across CI hosts, so prefer the bound-address inspection path.

**Fixture teardown.** The background thread runs uvicorn's event loop; stopping it cleanly requires signalling the server's `should_exit` attribute (uvicorn convention). If FastMCP's `server.run()` does not expose a clean stop hook, the fixture uses a daemon thread and lets pytest process teardown reap it — document the choice inline.

### [design_docs/phases/milestone_9_skill/skill_install.md](../milestone_9_skill/skill_install.md) — §5 extension

Add a new top-level section **§5 — HTTP mode for external hosts** after the existing §4 smoke section. Content:

- **One-paragraph context** — MCP stdio is the right transport for Claude Code / Cursor / Zed; HTTP is for browser-origin consumers that cannot launch subprocesses.
- **Invocation block** — the four-flag example from the milestone README Goal section.
- **Threat model paragraph** — loopback bind default; no auth; do not `--host 0.0.0.0` unless you own every process on the host.
- **Reference consumer** — *"An example browser-origin consumer is the Astro-based CS-300 notes site that drives the question-generation workflow over HTTP. The notes repo is out of scope here; the invariant is that any consumer that can speak streamable-HTTP and send JSON-RPC frames gets the same schema every stdio host gets."*
- **Cross-reference** to the M14 README.

### [tests/skill/test_doc_links.py](../../../tests/skill/test_doc_links.py) — extend

Add `test_skill_install_doc_covers_http_mode`:

- Load `skill_install.md`.
- Assert presence of the §5 heading (`## 5. HTTP mode for external hosts` or whatever the Builder names it — pin a slug, not the exact prose).
- Assert the three flags `--transport http`, `--cors-origin`, and `--host` are each referenced at least once in §5's body.

### [design_docs/architecture.md](../../architecture.md) — §4.4 sub-bullet

Add one sub-bullet under the MCP tool list, after the M11 projection bullet:

```markdown
  - *(HTTP transport, M14)* — `aiw-mcp --transport http --port <N> --cors-origin <origin>` serves the same schema over streamable-HTTP for browser-origin consumers (Astro / React / Vue / any JS runtime without subprocess access). Loopback bind default; no auth at M14 (trigger-gated for a later milestone). Skill text unchanged — stdio remains the primary host-registration path.
```

No KDR change. No ADR. Architecture.md §6 (Dependencies) is unchanged — FastMCP 3.x already bundles the HTTP-transport dependencies.

### [CHANGELOG.md](../../../CHANGELOG.md) — `[Unreleased]` entry

Under `## [Unreleased]`:

```markdown
### Added — M14 Task 01: MCP HTTP Transport (YYYY-MM-DD)

Adds the `aiw-mcp --transport http` path alongside the existing stdio default. Enables browser-origin consumers (Astro / React / Vue) to invoke the MCP surface over streamable-HTTP. Loopback bind default; optional permissive CORS for configured origins.

**Files touched:**
- `ai_workflows/mcp/__main__.py` — Typer-based entry point with `--transport`, `--host`, `--port`, `--cors-origin` flags.
- `tests/mcp/test_http_transport.py` — new 4-test hermetic suite (run+serve, CORS present, CORS absent, loopback default).
- `tests/skill/test_doc_links.py` — new `test_skill_install_doc_covers_http_mode` test.
- `design_docs/phases/milestone_9_skill/skill_install.md` — new §5 documenting the HTTP mode.
- `design_docs/architecture.md` — §4.4 sub-bullet citing M14.

**ACs satisfied:** every item in [`task_01_http_transport.md` §Acceptance Criteria](design_docs/phases/milestone_14_mcp_http/task_01_http_transport.md).

**No schema change. No new dependency. No new layer contract.**
```

## Acceptance Criteria

- [ ] `aiw-mcp` with no flags still starts over stdio and passes every existing [`tests/mcp/`](../../../tests/mcp/) stdio-path test.
- [ ] `aiw-mcp --transport http` starts an HTTP server on `127.0.0.1:8000`; `curl http://127.0.0.1:8000/mcp/` (exact path per FastMCP 3.x HTTP routing) returns a non-error response.
- [ ] `aiw-mcp --transport http --cors-origin http://localhost:4321` responds to CORS preflight from `http://localhost:4321` with `Access-Control-Allow-Origin: http://localhost:4321`.
- [ ] `aiw-mcp --transport http` **without** `--cors-origin` responds to the same preflight with **no** `Access-Control-Allow-Origin` header.
- [ ] `aiw-mcp --transport http` binds `127.0.0.1` by default. Passing `--host 0.0.0.0` binds all interfaces (documented, not tested — hermetic tests never bind 0.0.0.0).
- [ ] `aiw-mcp --transport http --port 8099` binds the chosen port.
- [ ] `tests/mcp/test_http_transport.py` — all four tests green.
- [ ] `tests/skill/test_doc_links.py::test_skill_install_doc_covers_http_mode` — green.
- [ ] `tests/mcp/` stdio-path tests — unchanged count, all green.
- [ ] `uv run pytest` — full suite green.
- [ ] `uv run lint-imports` — 4 contracts kept.
- [ ] `uv run ruff check` — clean.
- [ ] `ai_workflows/mcp/schemas.py` — byte-identical to pre-M14.
- [ ] `ai_workflows/mcp/server.py` — byte-identical to pre-M14 (no new factory; reuse `build_server()`).
- [ ] `.claude/skills/ai-workflows/SKILL.md` — unchanged (HTTP is not a skill surface; the skill uses stdio).
- [ ] [`skill_install.md`](../milestone_9_skill/skill_install.md) §5 lands with the four flags documented + threat-model paragraph + Astro reference.
- [ ] [`architecture.md`](../../architecture.md) §4.4 sub-bullet lands.
- [ ] CHANGELOG entry lands under `[Unreleased]` with the file list + ACs + "no schema change" note.

## Out-of-scope for T01

- Authentication (bearer, OAuth, API keys).
- TLS termination.
- Rate limiting / concurrency caps.
- SSE / WebSocket transports.
- A new MCP tool or resource.
- Changes to any schema under [`ai_workflows/mcp/schemas.py`](../../../ai_workflows/mcp/schemas.py).
- Changes to `.claude/skills/ai-workflows/SKILL.md` (HTTP is a non-skill surface).
- Any change to `aiw` CLI flags (M14 is MCP-only).
- Any change to workflows, graph primitives, or the evals harness.

## Risks & mitigations

- **FastMCP 3.x HTTP API may differ across patch versions.** Mitigation: pin the spec to "call `server.run(transport='streamable-http', host=..., port=...)`" which is documented public API in 3.2.x; if the Builder finds a different surface, the spec amendment lands in the T01 pre-implementation evaluation (same drill as M11 T01 did on 2026-04-22).
- **Starlette CORSMiddleware attachment point.** FastMCP 3.x may expose the ASGI app as `server.app` or via a method. Mitigation: the spec commits to the behaviour (CORS attached before `run()`); the Builder inspects the FastMCP 3.2.4 source at implementation time and updates the line with the correct accessor. No audit-level design decision depends on the exact shape.
- **Background-thread server teardown in tests.** If FastMCP / uvicorn does not expose a clean-stop hook, tests use a daemon thread and accept pytest's process teardown. Documented inline. Alternative: use `asyncio.new_event_loop()` + `loop.create_task(server.serve_async(...))` if FastMCP exposes an async entry point — Builder's call.
- **Port collisions on shared CI.** Mitigation: ephemeral port reservation (`sock.bind(0)` then release) — standard pattern, no CI-level change needed.

## Reuse (do not reinvent)

- [`ai_workflows.mcp.server.build_server()`](../../../ai_workflows/mcp/server.py) — the server factory. Untouched at M14.
- [`ai_workflows.primitives.logging.configure_logging()`](../../../ai_workflows/primitives/logging.py) — stderr-routed structured logging. Same call in both transport paths.
- Typer's `typer.Typer` + `@app.command()` + `typer.Option()` pattern — [ai_workflows/cli.py](../../../ai_workflows/cli.py) is the in-project reference.
- Stub-adapter fixture pattern in [`tests/mcp/test_run_workflow.py`](../../../tests/mcp/test_run_workflow.py) / [`tests/mcp/test_resume_run.py`](../../../tests/mcp/test_resume_run.py) — extend for the HTTP path, do not re-author.
- Existing `httpx` surface in the dev dependency tree (transitive via FastMCP). No new dependency.

## Verification checklist (Builder)

1. `uv run pytest tests/mcp/test_http_transport.py -v` — four new tests green.
2. `uv run pytest tests/mcp/ tests/skill/` — stdio + HTTP + skill-doc tests green together.
3. `uv run pytest` — full suite green.
4. `uv run lint-imports` — 4 contracts kept.
5. `uv run ruff check` — clean.
6. Manual smoke:
   - Terminal 1: `uv run aiw-mcp --transport http --port 8099 --cors-origin http://localhost:4321`.
   - Terminal 2: `curl -i -X OPTIONS http://127.0.0.1:8099/mcp/ -H 'Origin: http://localhost:4321' -H 'Access-Control-Request-Method: POST'` — confirm `Access-Control-Allow-Origin: http://localhost:4321`.
   - Terminal 2: `curl -i -X OPTIONS http://127.0.0.1:8099/mcp/ -H 'Origin: http://localhost:5000' -H 'Access-Control-Request-Method: POST'` — confirm no ACAO header (not in allow-list).
   - Terminal 2: stop-start the server without `--cors-origin`; same preflight from `http://localhost:4321` — confirm no ACAO header.
7. Existing stdio smoke from skill_install.md §4 — unchanged behaviour.
