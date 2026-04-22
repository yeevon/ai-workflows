# ADR-0005 — FastMCP HTTP middleware accessor

**Status:** Accepted (2026-04-22).
**Decision owner:** [M14 Task 01](../phases/milestone_14_mcp_http/task_01_http_transport.md) (implementation) + [M14 Task 02](../phases/milestone_14_mcp_http/task_02_milestone_closeout.md) (this ADR lands at close-out).
**References:** [architecture.md §4.4](../architecture.md) · KDR-002 · KDR-008 · [task_01_http_transport.md §Risks](../phases/milestone_14_mcp_http/task_01_http_transport.md#risks--mitigations) · [task_01 audit issue file](../phases/milestone_14_mcp_http/issues/task_01_issue.md) · [deep_analysis.md](../phases/milestone_14_mcp_http/deep_analysis.md).
**Supersedes:** nothing. First ADR on the MCP-transport surface.

## Context

[M14 Task 01](../phases/milestone_14_mcp_http/task_01_http_transport.md)
added `aiw-mcp --transport http` with optional `--cors-origin` flags.
The task spec prescribed the CORS attachment as:

```python
server.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)
```

**This call does not match FastMCP 3.2.4's API.** FastMCP 3.2.4's
[`server.add_middleware`](../../.venv/lib/python3.13/site-packages/fastmcp/server/server.py)
takes a **FastMCP-internal `Middleware` instance**, not the Starlette
`CORSMiddleware` class. Passing the Starlette class raises
`TypeError` at server construction. The Builder had to pick an
alternate accessor at implementation time.

Task spec [§Risks #2](../phases/milestone_14_mcp_http/task_01_http_transport.md#risks--mitigations)
explicitly pre-authorised the Builder to amend:

> *"Starlette CORSMiddleware attachment point. FastMCP 3.x may expose
> the ASGI app as `server.app` or via a method. Mitigation: the spec
> commits to the behaviour (CORS attached before `run()`); the
> Builder inspects the FastMCP 3.2.4 source at implementation time
> and updates the line with the correct accessor. No audit-level
> design decision depends on the exact shape."*

The T01 audit ([issues/task_01_issue.md](../phases/milestone_14_mcp_http/issues/task_01_issue.md))
passed clean with the amendment recorded in `_run_http`'s docstring,
the audit issue file's "Deviation from spec" section, and the
CHANGELOG entry — but no ADR captured the **reasoning** behind the
chosen accessor over its alternatives. The M14 deep-analysis pass
([deep_analysis.md §M14-DA-04](../phases/milestone_14_mcp_http/deep_analysis.md))
flagged the gap: the next FastMCP minor bump will force the next
Builder — including future-you — to re-derive the trade-off from
scratch without knowing *why* the current shape was picked.

This ADR codifies that reasoning so that the next maintenance pass
has the context.

## Decision

**Attach Starlette's `CORSMiddleware` by passing a Starlette
`Middleware` list through FastMCP's transport-level `middleware=`
kwarg.** Concretely, in
[`ai_workflows/mcp/__main__.py::_run_http`](../../ai_workflows/mcp/__main__.py):

```python
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
] if cors_origins else None

server.run(transport="http", host=host, port=port, middleware=middleware)
```

The `middleware=` kwarg flows through FastMCP's `run_http_async` →
`http_app(middleware=...)` → `create_streamable_http_app(middleware=...)`
(see [`fastmcp/server/mixins/transport.py:235, 310`](../../.venv/lib/python3.13/site-packages/fastmcp/server/mixins/transport.py)).
`ASGIMiddleware` is an alias for `starlette.middleware.Middleware`
([`fastmcp/server/mixins/transport.py:13`](../../.venv/lib/python3.13/site-packages/fastmcp/server/mixins/transport.py)) —
so the Starlette import is the intended public shape, not a private
back-door.

The imports of `Middleware` + `CORSMiddleware` stay **inside**
`_run_http` (pinned with `# noqa: PLC0415`) so the stdio transport
path never pays the starlette import cost.

## Rejected alternatives

### A. `server.http_app(middleware=[...]) + uvicorn.run(app, host, port)`

Construct the ASGI app via `http_app(...)` and run it through
`uvicorn.run` directly. Gives full control over uvicorn settings at
the cost of **re-deriving FastMCP's uvicorn config**:
`timeout_graceful_shutdown=2`, `lifespan="on"`,
`ws="websockets-sansio"`, `log_level` routing, and any future flags
FastMCP layers on. Every minor FastMCP version that tunes its uvicorn
defaults becomes a potential drift surface for this code path.

**Rejected because:** M14's deployment shape is loopback / solo-use /
single-machine (see [project memory `project_local_only_deployment.md`]).
There is no need for uvicorn-level knobs (`proxy_headers`,
`forwarded_allow_ips`, per-worker config) that would justify the
re-derivation cost. The Builder path pays one line; the uvicorn-first
path pays ongoing tracking of FastMCP's defaults.

### B. `server.add_middleware(CORSMiddleware, ...)`

The call prescribed by the original task spec. Fails at runtime —
FastMCP 3.2.4's `add_middleware` accepts a FastMCP-internal
`Middleware` instance (a distinct class in `fastmcp.server.middleware`),
not Starlette's `Middleware` or a Starlette middleware class.

**Rejected because:** `TypeError` at construction. Task spec Risks §2
authorised the amendment explicitly.

### C. Fork to a Starlette-first pattern

Wrap FastMCP's ASGI app inside a hand-rolled Starlette application:

```python
app = Starlette(
    routes=[Mount("/", app=server.http_app())],
    middleware=[Middleware(CORSMiddleware, ...)],
)
uvicorn.run(app, host=host, port=port, ...)
```

Maximum flexibility — the operator owns the full Starlette surface
(custom routes, request middleware, exception handlers, lifespan
management).

**Rejected because:** doubles the line count, couples the M14 entry
point to Starlette's Mount / lifespan / routing model *more tightly*
than the chosen path, and reproduces the uvicorn-config re-derivation
cost from alternative A. No current or anticipated consumer needs
the extra knobs. Solo-use default is the smallest surface that works.

## Consequences

- **Implicit coupling to FastMCP's uvicorn defaults.** The chosen
  path inherits whatever uvicorn config FastMCP chooses
  (`timeout_graceful_shutdown=2`, `lifespan="on"`,
  `ws="websockets-sansio"`, etc.). If a future FastMCP minor tunes
  these in a way that affects M14's behaviour, the impact surfaces
  at version-bump time via the existing test suite
  (`tests/mcp/test_http_transport.py` — four tests pinning the HTTP
  round-trip + CORS + loopback invariants, plus the parity /
  regression tests landing in [M14 T02](../phases/milestone_14_mcp_http/task_02_milestone_closeout.md)).
- **No uvicorn-level knob at M14.** If the operator needs
  `proxy_headers`, `forwarded_allow_ips`, custom lifespan handlers,
  or per-worker config, none of them are reachable through this
  accessor. Adding any of them flips the decision to alternative A
  (http_app + uvicorn.run) and the ADR gets superseded. Under the
  committed local-only / solo-use threat model, none of these knobs
  are load-bearing.
- **Starlette becomes a "first-party" transitive dependency** — not
  listed in `pyproject.toml` directly, but imported explicitly in
  `_run_http` (`from starlette.middleware import Middleware`,
  `from starlette.middleware.cors import CORSMiddleware`). Starlette
  is already a transitive of FastMCP and uvicorn, so no new pin is
  required; the explicit import just makes the dependency legible
  at the call site. A hypothetical FastMCP 4.x that replaces
  Starlette with another ASGI framework would break this import and
  force a re-decision — acceptable signal at version-bump time.
- **No KDR change.** This ADR is local to the M14 transport surface;
  it refines how M14 wires CORS, not an architectural rule. KDR-002
  (skill packaging-only, stdio-primary) and KDR-008 (FastMCP public
  schema contract) are both preserved.
- **Auditor rule.** Any future task that modifies `_run_http`'s
  middleware attachment point must either preserve this decision or
  supersede this ADR with an explicit successor. Documented in the
  [M14 T02](../phases/milestone_14_mcp_http/task_02_milestone_closeout.md)
  acceptance criteria.
- **Re-visit trigger.** Flip to alternative A (http_app + uvicorn.run)
  if and only if: (a) a deployment-shape change requires uvicorn-
  level config (the project commits to a non-loopback host or a
  reverse-proxy layer — not on any committed roadmap through M15+),
  *or* (b) FastMCP removes the `middleware=` transport kwarg in a
  major bump. Both triggers are version-bump-visible via the existing
  test suite.

## References

- [architecture.md §4.4](../architecture.md) — MCP surface, HTTP
  transport sub-bullet (M14).
- KDR-002 — skill packaging-only, stdio-primary. Preserved:
  `.claude/skills/ai-workflows/SKILL.md` is untouched at M14; HTTP
  is a second surface documented separately.
- KDR-008 — FastMCP is the MCP server implementation. Preserved:
  `ai_workflows/mcp/schemas.py` + `ai_workflows/mcp/server.py` are
  byte-identical at M14; HTTP serialises the same pydantic models.
- [M14 README](../phases/milestone_14_mcp_http/README.md) —
  milestone scope, non-goals, threat model.
- [M14 T01 task spec](../phases/milestone_14_mcp_http/task_01_http_transport.md)
  — the original spec that prescribed `server.add_middleware`.
- [M14 T01 audit issue file](../phases/milestone_14_mcp_http/issues/task_01_issue.md)
  — records the pre-authorised amendment.
- [M14 deep-analysis](../phases/milestone_14_mcp_http/deep_analysis.md) —
  surfaced M14-DA-04 which this ADR closes.
- [`ai_workflows/mcp/__main__.py`](../../ai_workflows/mcp/__main__.py)
  — the call site.
- FastMCP 3.2.4 source (`.venv/lib/python3.13/site-packages/fastmcp/server/mixins/transport.py`)
  — `ASGIMiddleware`, `run_http_async`, `http_app` call chain.
