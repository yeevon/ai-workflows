# Task 01 — HTTP transport flag + CORS middleware + tests + doc — Audit Issues

**Source task:** [../task_01_http_transport.md](../task_01_http_transport.md)
**Audited on:** 2026-04-22
**Audit scope:** `ai_workflows/mcp/__main__.py` (rewrite), `tests/mcp/test_http_transport.py` (new), `design_docs/phases/milestone_9_skill/skill_install.md` (§5 new), `tests/skill/test_doc_links.py` (new test), `design_docs/architecture.md` (§4.4 sub-bullet), `CHANGELOG.md` (`[Unreleased]` entry). Protected files: `ai_workflows/mcp/server.py`, `ai_workflows/mcp/schemas.py`, `ai_workflows/mcp/__init__.py`, `.claude/skills/ai-workflows/SKILL.md`, `pyproject.toml` — all byte-identical (verified via `git diff HEAD`).
**Status:** ✅ PASS — all 18 acceptance criteria green; no OPEN issues; no design drift.

## Design-drift check (mandatory, per CLAUDE.md)

Cross-referenced against [architecture.md](../../../architecture.md) and every KDR cited in the task/milestone (KDR-002, KDR-003, KDR-008).

| Check | Finding |
| --- | --- |
| New dependency? | **None.** `typer` (already a direct dep — `ai_workflows.cli` uses it); `starlette` (transitive via FastMCP/uvicorn — used by the FastMCP server itself); `httpx` (transitive via FastMCP). `pyproject.toml` unchanged. |
| New module or layer? | **None.** Only `ai_workflows/mcp/__main__.py` rewritten — same surface layer, same console-script entry `ai_workflows.mcp.__main__:main`. Four-layer import contract kept (`uv run lint-imports` → 4 contracts kept). |
| LLM call added? | **None.** No new `TieredNode`, no new provider call. |
| Checkpoint / resume logic added? | **None.** `build_server()` reused byte-identically (AC exit criterion 6). |
| Retry logic added? | **None.** |
| Observability change? | **None.** `configure_logging(level="INFO")` call preserved in both transport paths. |
| KDR-003 (no Anthropic API)? | ✅ Preserved. No `anthropic` import, no `ANTHROPIC_API_KEY` reference anywhere in the diff. |
| KDR-008 (FastMCP public schema contract)? | ✅ Preserved. `schemas.py` byte-identical; HTTP transport serialises the exact pydantic models stdio serialises. |
| KDR-002 (skill packaging-only, stdio-primary)? | ✅ Preserved. `.claude/skills/ai-workflows/SKILL.md` unchanged; HTTP documented separately in `skill_install.md` §5 as a non-skill surface. |
| `nice_to_have.md` scope creep? | **None.** Auth/TLS/rate-limiting explicitly out of scope per milestone README non-goals. |

**No drift HIGHs.**

## Acceptance criteria grading

All 18 ACs from [task_01_http_transport.md §Acceptance Criteria](../task_01_http_transport.md#acceptance-criteria).

| # | AC | Verdict | Evidence |
| --- | --- | --- | --- |
| 1 | `aiw-mcp` no flags → stdio, stdio tests green | ✅ | `_cli` routes `transport == "stdio"` through `server.run()` (byte-identical to pre-M14). `tests/mcp/` non-HTTP suite unchanged and passing. |
| 2 | `aiw-mcp --transport http` → HTTP on 127.0.0.1:8000 | ✅ | Typer option defaults `host="127.0.0.1"`, `port=8000`; `test_http_default_bind_is_loopback` pins the Typer default *and* exercises a live loopback connection on the default host. |
| 3 | `--cors-origin <url>` → preflight with ACAO echo | ✅ | `test_http_cors_headers_present_when_origin_configured` asserts `Access-Control-Allow-Origin: http://localhost:4321` on preflight. |
| 4 | No `--cors-origin` → no ACAO header | ✅ | `test_http_cors_headers_absent_when_origin_unconfigured` asserts ACAO header absent (case-insensitive key check). |
| 5 | Default loopback + documented `0.0.0.0` | ✅ | `--host` help: *"Loopback default; pass 0.0.0.0 only if you own every process on the host."* `skill_install.md` §5 threat-model paragraph carries the same warning. |
| 6 | `--port 8099` binds chosen port | ✅ | Tests reserve ephemeral ports (`sock.bind((127.0.0.1, 0))`) and verify the server answers on that port. |
| 7 | `test_http_transport.py` — 4 tests green | ✅ | `uv run pytest tests/mcp/test_http_transport.py -v` → 4 passed in 0.96s. |
| 8 | `test_skill_install_doc_covers_http_mode` green | ✅ | Full-suite run includes it; passes. |
| 9 | Stdio-path tests unchanged count, all green | ✅ | Full suite 607 passed / 5 skipped (was 602/5 pre-M14; +4 HTTP tests, +1 doc-link test = +5, matches the delta). No pre-existing stdio test modified. |
| 10 | `uv run pytest` full suite green | ✅ | 607 passed, 5 skipped, 2 warnings (pre-existing yoyo-datetime deprecation). |
| 11 | `uv run lint-imports` — 4 contracts kept | ✅ | Output: "Contracts: 4 kept, 0 broken." |
| 12 | `uv run ruff check` clean | ✅ | "All checks passed!" |
| 13 | `ai_workflows/mcp/schemas.py` byte-identical | ✅ | `git diff HEAD -- ai_workflows/mcp/schemas.py` → empty. |
| 14 | `ai_workflows/mcp/server.py` byte-identical | ✅ | `git diff HEAD -- ai_workflows/mcp/server.py` → empty. HTTP mode reuses `build_server()`; no second factory. |
| 15 | `.claude/skills/ai-workflows/SKILL.md` unchanged | ✅ | `git diff HEAD -- .claude/skills/` → empty. |
| 16 | `skill_install.md` §5 with 4 flags + threat-model + Astro + M14 link | ✅ | §5 "HTTP mode for external hosts" added; subsections: Invocation (all four flags block-quoted), Threat model (loopback default + no-auth/no-TLS + opt-in exact-match CORS), Reference consumer (Astro CS-300 notes site), Cross-reference (milestone README + T01 task file). Old §5 Troubleshooting renumbered §6. |
| 17 | `architecture.md` §4.4 sub-bullet lands | ✅ | New sub-bullet under the MCP tool list cites M14 + `--transport http` + CORS + loopback default. |
| 18 | CHANGELOG `[Unreleased]` entry | ✅ | `### Added — M14 Task 01: MCP HTTP Transport (2026-04-22)` landed under `[Unreleased]` with file list, deviation note, AC pointer, "no schema change" invariant. |

## 🔴 HIGH

*(none)*

## 🟡 MEDIUM

*(none)*

## 🟢 LOW

*(none)*

## Additions beyond spec — audited and justified

| Addition | Justification |
| --- | --- |
| Runtime `if transport not in ("stdio", "http")` guard with `typer.BadParameter` | Task spec typed the Typer option as `Literal["stdio", "http"]`. Typer 0.17's handling of `Literal` option types varies across versions; a runtime guard hard-fails invalid values with a Typer-idiomatic error regardless of whether the `Literal` enforces at parse time. Three lines; no behavioural change on the happy path. |
| `main()` wrapper delegating to `app()` | Required to preserve the `ai_workflows.mcp.__main__:main` console-script entry from `pyproject.toml` (milestone README exit criterion 1 line 39: *"The entry point stays `ai_workflows.mcp.__main__:main`; no new console-script registration."*). Typer's `@app.command()` does not rewrite the decorated function to parse `sys.argv` when invoked directly — the wrapper routes through `app()` so console-script callers get Typer argv parsing. Documented inline. |
| `# noqa: PLC0415` on the two in-function imports (`starlette.middleware.Middleware`, `starlette.middleware.cors.CORSMiddleware`) | Kept inside `_run_http` to avoid starlette import cost on the stdio path. The `noqa` pin was pre-authorised in the task spec (line 90). |

## Deviation from spec — audited and justified

The task spec (lines 73-78) prescribed:

```python
server.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    ...
)
```

**This call does not match FastMCP 3.2.4's actual API.** FastMCP
3.2.4's [`server.add_middleware`](../../../../.venv/lib/python3.13/site-packages/fastmcp/server/server.py) takes a FastMCP-internal `Middleware` instance (not the Starlette class), and passing a Starlette class raises `TypeError`. The correct accessor is to pass a list of `starlette.middleware.Middleware` wrappers through `server.run(transport="http", middleware=[...])` — this flows through `run_http_async` → `http_app(middleware=...)` (see `fastmcp/server/mixins/transport.py:235, 310`).

Task spec [§Risks #2](../task_01_http_transport.md#risks--mitigations) explicitly authorised the Builder to pick the correct accessor at implementation time:

> *"Starlette CORSMiddleware attachment point. FastMCP 3.x may expose the ASGI app as `server.app` or via a method. Mitigation: the spec commits to the behaviour (CORS attached before `run()`); the Builder inspects the FastMCP 3.2.4 source at implementation time and updates the line with the correct accessor. No audit-level design decision depends on the exact shape."*

The behaviour is unchanged from the spec's intent (CORS attached before the server begins serving). Recorded in `_run_http`'s docstring and in the CHANGELOG `Deviation from spec` paragraph.

## Gate summary

| Gate | Command | Result |
| --- | --- | --- |
| Full test suite | `uv run pytest` | **607 passed, 5 skipped, 2 warnings** (pre-existing yoyo deprecation). |
| Layer contracts | `uv run lint-imports` | **4 kept, 0 broken.** |
| Lint | `uv run ruff check` | **All checks passed.** |
| New HTTP suite | `uv run pytest tests/mcp/test_http_transport.py -v` | **4 passed in 0.96s.** |
| MCP+skill focused | `uv run pytest tests/mcp/ tests/skill/ -v` | **70 passed.** |
| Manual smoke — `aiw-mcp --help` | `uv run aiw-mcp --help` | Flag surface renders: `--transport`, `--host`, `--port`, `--cors-origin` all present with the spec'd defaults and help text. |

## Issue log — cross-task follow-up

*(none — no DEFERRED items from this audit.)*

## Deferred to `nice_to_have.md`

*(none — auth/TLS/rate-limiting are already captured in the milestone README §Propagation status as future triggers, and M14's non-goals explicitly scope them out. No new nice_to_have entry required.)*

## Propagation status

*(none — clean audit, no forward-deferrals required.)*

## Close-out readiness

T01 lands clean. M14 T02 (milestone close-out) is the next task per
[milestone README §Task order](../README.md#task-order); it is spec'd
at T01's close-out time, so the Builder for T02 writes the task file
first, then closes the milestone. No blocker from T01 to T02.
