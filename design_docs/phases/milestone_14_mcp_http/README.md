# Milestone 14 — MCP HTTP Transport

**Status:** ✅ Complete (2026-04-22).
**Grounding:** [architecture.md §4.4](../../architecture.md) · [roadmap.md](../../roadmap.md) · [ai_workflows/mcp/__main__.py](../../../ai_workflows/mcp/__main__.py) · [M11 README](../milestone_11_gate_review/README.md) (precondition — the HTTP transport projects the same gate-pause surface M11 shipped). · [M13 README](../milestone_13_v0_release/README.md) (downstream — M14 ships before the 0.1.0 release so the first published wheel covers both transports).

## Why this milestone exists

Today `aiw-mcp` registers over **stdio only**. [`ai_workflows/mcp/__main__.py:41-43`](../../../ai_workflows/mcp/__main__.py#L41-L43) calls `server.run()` with no argument, and FastMCP's default transport is stdio. The surface works for every MCP host that launches the server as a subprocess (Claude Code, Cursor, Zed) — stdio is the right default for those.

Browser-origin hosts cannot launch stdio subprocesses. That rules out the entire class of web clients: the first concrete one the project has a commitment to is an **Astro-based CS-300 study tool** (personal, local-only) that wants to invoke `run_workflow` (question generation) from the browser at chapter-page load. The site's transport decision is frozen in the interactive-notes roadmap: *"The notes site does not call Ollama directly; it calls an HTTP adapter over ai-workflows' MCP surface. ... FastMCP supports HTTP transport in addition to stdio."* Without an HTTP entry point on `aiw-mcp`, the notes site has no way to consume the MCP surface — the whole quality-question-generation path stays blocked.

FastMCP 3.2.4 (already pinned in [pyproject.toml:17](../../../pyproject.toml#L17)) ships the `streamable-http` transport natively; the change is a **CLI flag + a `server.run(transport="streamable-http", host=..., port=...)` call** on an already-factored entry point. No new dependency, no new layer, no schema change. The stdio path is unchanged and remains the default — `aiw-mcp` is unmodified for every existing MCP host.

M14 is deliberately scoped to **one flag extension**. Auth, TLS, rate-limiting, and production-hardening are out of scope (see Non-goals). The driving use case is a local-only personal tool; any server-grade deployment concern belongs to a later milestone triggered by a second consumer.

## Goal

`aiw-mcp --transport http` starts the FastMCP server over streamable-HTTP on a configurable `--host` / `--port`, with permissive CORS headers for a configurable localhost origin list. All five MCP tools (`run_workflow`, `resume_run`, `list_runs`, `cancel_run`, and the M11 gate-pause projection that rides on the existing output models) round-trip identically across transports — the wire shape is owned by the pydantic schemas and FastMCP serialises over either transport.

```bash
aiw-mcp                                       # stdio (unchanged default)
aiw-mcp --transport stdio                     # stdio (explicit)
aiw-mcp --transport http                      # streamable-HTTP on 127.0.0.1:8000
aiw-mcp --transport http --port 8099          # custom port
aiw-mcp --transport http \
        --cors-origin http://localhost:4321   # permit Astro dev-server origin
```

The Astro notes-site backend can then register the HTTP server as an MCP endpoint and invoke tools without spawning a subprocess.

## Exit criteria

1. **`aiw-mcp` CLI flags.** [`ai_workflows/mcp/__main__.py`](../../../ai_workflows/mcp/__main__.py) grows four optional flags:
   - `--transport {stdio,http}` — default `stdio`.
   - `--host <addr>` — default `127.0.0.1`. Honoured only when `--transport http`.
   - `--port <int>` — default `8000` (matches FastMCP's HTTP default). Honoured only when `--transport http`.
   - `--cors-origin <url>` — repeatable; each value is an origin string (`http://localhost:4321`). Default: empty list. Honoured only when `--transport http`. An empty list means no `Access-Control-Allow-Origin` header — same-origin requests only.

   The argument parser is **Typer-based** (matches the existing `aiw` CLI convention at [ai_workflows/cli.py](../../../ai_workflows/cli.py)). The entry point stays `ai_workflows.mcp.__main__:main`; no new console-script registration.

2. **HTTP transport wiring.** `main()` routes on `--transport`:
   - `stdio` path — unchanged. `configure_logging(level="INFO")` + `server.run()`.
   - `http` path — `configure_logging(level="INFO")`, construct the server via `build_server()`, attach the CORS middleware (see criterion 3), then `server.run(transport="streamable-http", host=host, port=port)`. Logs go to stderr; HTTP framing uses stdout (FastMCP's uvicorn loop owns the socket — no JSON-RPC-over-stdio contract to protect).

3. **CORS middleware.** When `--cors-origin` has at least one entry, the HTTP server attaches a Starlette-style `CORSMiddleware` (FastMCP exposes the ASGI app; Starlette is a transitive dep of uvicorn/FastMCP). Allowed methods: `GET`, `POST`, `OPTIONS`. Allowed headers: `*`. Exact-match on origin (no regex). If no `--cors-origin` is passed, no middleware is attached — same-origin only. Default-deny is the secure posture; explicit opt-in is the notes-site path.

4. **Bind default is loopback.** The default `--host 127.0.0.1` means the HTTP listener is unreachable from outside the machine unless the operator explicitly passes `--host 0.0.0.0`. The spec documents this in the `aiw-mcp --help` text and in the skill install doc extension (criterion 8). No environment-variable override to bypass loopback (the flag is the surface).

5. **No schema change.** `ai_workflows/mcp/schemas.py` is untouched. Every tool input/output model round-trips identically on stdio and HTTP — FastMCP handles serialisation. The M11 gate-pause projection works unchanged over HTTP because `RunWorkflowOutput.gate_context` / `ResumeRunOutput.gate_context` are plain pydantic fields.

6. **`ai_workflows.mcp.server.build_server()` is reused as-is.** No second factory. The HTTP mode is a deployment choice at `__main__.main()` — the FastMCP server object is the same object stdio runs.

7. **Hermetic tests.** `tests/mcp/test_http_transport.py` — four-test hermetic suite:
   - `test_http_transport_starts_and_serves_run_workflow` — spin the server in a background thread on an ephemeral port (`sock.bind(('127.0.0.1', 0))` then release); issue a `run_workflow` JSON-RPC POST via `httpx.AsyncClient`; assert the response matches the stdio round-trip shape. Use `planner` with a stub tier adapter (existing `tests/mcp/` fixture pattern) — no live provider.
   - `test_http_cors_headers_present_when_origin_configured` — start with `--cors-origin http://localhost:4321`; issue a CORS preflight `OPTIONS` request with `Origin: http://localhost:4321`; assert `Access-Control-Allow-Origin: http://localhost:4321` in the response.
   - `test_http_cors_headers_absent_when_origin_unconfigured` — start with no `--cors-origin`; issue the same preflight; assert no `Access-Control-Allow-Origin` header.
   - `test_http_default_bind_is_loopback` — start the server with `--host` omitted; assert `socket.getsockname()` on the bound listener reports `127.0.0.1`. Negative-path: a probe from a non-loopback alias is out-of-scope (hermetic test runs on loopback anyway) — the assertion is on the bind address, not a cross-interface reachability test.

   No new test-utility dependency beyond `httpx` (already a transitive dep of FastMCP and its eval/test surface).

8. **Skill install doc extension.** [`design_docs/phases/milestone_9_skill/skill_install.md`](../milestone_9_skill/skill_install.md) gains a new **§5 — HTTP mode for external hosts** section that:
   - Documents the `aiw-mcp --transport http --port <N> --cors-origin <origin>` invocation.
   - Names the loopback-bind default explicitly and the threat model (local-only; no auth; do not bind `0.0.0.0` unless you own every process on the host).
   - Cross-references the Astro notes site as the reference consumer without naming that repo (the notes repo is out of scope for ai-workflows' docs at M14).
   - Does **not** replace §2's stdio Claude Code registration — stdio remains the primary skill surface. `test_doc_links.py` stays green; a new test `test_skill_install_doc_covers_http_mode` asserts the §5 heading + the three flags are present.

9. **Architecture.md §4.4 note.** The MCP surface bullet ([architecture.md:100](../../architecture.md#L100)) currently reads *"FastMCP generates the JSON-RPC schema, handles stdio/HTTP transport, and runs the server"* — already HTTP-aware at the prose level. Add one sub-bullet after the tool list noting: *"`aiw-mcp --transport http --port <N> --cors-origin <origin>` serves the same schema over streamable-HTTP (M14) for browser-origin consumers; loopback bind default."* No KDR change; no ADR; no new layer.

10. **Backwards compatibility preserved.** Every existing Claude Code / Cursor / Zed registration of `aiw-mcp` keeps working without flag changes. `tests/mcp/` stdio-path tests stay green unchanged.

11. **Gates green.** `uv run pytest` (existing + the four new tests) + `uv run lint-imports` (4 contracts kept — no new layer contract at M14) + `uv run ruff check`.

## Non-goals

- **No authentication surface.** Bearer tokens, OAuth, API keys — all out of scope. The driving use case is local-only (loopback bind, permissive CORS for a dev server on the same machine). A `--token <secret>` flag is a candidate for a future task triggered by "a second process on the host is hostile to ai-workflows" OR "the notes site moves off localhost"; until one of those fires, the surface is trust-the-loopback.
- **No TLS termination.** Plain HTTP over loopback. TLS is orthogonal — local-only consumers on the same machine have no threat model that TLS addresses. A reverse-proxy recipe (Caddy / Nginx terminating TLS) is user-level deployment, not an M14 deliverable.
- **No rate limiting or concurrency cap.** FastMCP's uvicorn defaults apply. Single-user personal tool.
- **No SSE transport.** FastMCP 3.x offers `"sse"` as a legacy alias; streamable-HTTP is the current recommended path. SSE support would be a separate task if a consumer needs it (MCP spec deprecates SSE in favour of streamable-HTTP).
- **No WebSocket transport.** Not offered by FastMCP 3.x. If a future consumer needs it, that is a separate milestone.
- **No change to stdio default.** The stdio entry point is unmodified for every existing host. `aiw-mcp` with no flags is byte-identical to today's behaviour.
- **No schema change.** KDR-008 is preserved trivially — M14 adds no fields, removes no fields, renames no fields. The HTTP transport serialises the same models the stdio transport serialises.
- **No workflow change.** The graph / workflows / primitives layers are untouched. M14 is a surface-only milestone.
- **No Anthropic API (KDR-003).** No new LLM call, no new provider surface. The flag extension touches argparse + one FastMCP call.

## Key decisions in effect

| Decision | Reference |
| --- | --- |
| MCP tool schemas are the public contract; transport is additive and non-breaking | architecture.md §7 + KDR-008 |
| Skill packaging stays stdio-primary; HTTP is a second surface documented separately | KDR-002 |
| Loopback bind is the secure default; opt-in to wider binds is explicit | project convention (this milestone) |
| No auth at M14 — local-only threat model explicitly documented | project convention (this milestone); promotion triggers logged in this README |
| Four-layer import contract holds — surface-only change, primitives/graph/workflows unchanged | architecture.md §3 |
| No new KDR at M14 | CLAUDE.md non-negotiables |

## Task order

| # | Task | Kind |
| --- | --- | --- |
| 01 | [HTTP transport flag + CORS middleware + tests + doc](task_01_http_transport.md) | code + test + doc |
| 02 | Milestone close-out | doc |

Per-task spec files land as each predecessor closes (same convention as M11 / M12 / M13). T01 is spec'd alongside this README; T02 is written at T01's close-out so the scope stays calibrated against landed surface.

## Dependencies

- **M11 (soft).** M11's gate-pause projection lands on the pydantic output models — both transports pick it up automatically. If M14 lands before M11, the HTTP transport works but inherits the pre-M11 `plan: null` defect at gate pause. **M11 is landing first** in the current roadmap (T02 close-out pending); this ordering preserves the "first HTTP user sees the same reviewable surface every stdio user sees" invariant. If the order inverted, document the gap in T01 and ship the fix as a sibling deliverable with M11 T02.
- **M10 — none.** Ollama hardening is orthogonal.
- **M12 — none.** Audit cascade is orthogonal.
- **M13 — M14 is a precondition** for the v0.1.0 release. The first published wheel should cover both transports so the Astro consumer has an install path that doesn't require a git clone. Without M14 in v0.1.0, the notes site would need to either `pip install` from a git tag or wait for a 0.1.x patch. M13's dependency section is updated in this milestone's T01 to name M14 alongside M11.

## Outcome (2026-04-22)

M14 closed in two tasks.

- **T01 — HTTP transport flag + CORS middleware + tests + doc** (landed clean 2026-04-22, one-shot /clean-implement Cycle 1).
  `aiw-mcp` grew a Typer-based entry point with `--transport {stdio,http}`, `--host`, `--port`, `--cors-origin` flags. Stdio default unchanged. The HTTP path attaches Starlette's `CORSMiddleware` via `server.run(transport="http", middleware=[Middleware(CORSMiddleware, ...)])` — a Risks §2-authorised amendment from the spec-prescribed `server.add_middleware(CORSMiddleware, ...)` (FastMCP 3.2.4's `add_middleware` takes a FastMCP-internal `Middleware` instance, not Starlette's class; the `middleware=` kwarg is the correct public accessor). Four hermetic tests in [`tests/mcp/test_http_transport.py`](../../../tests/mcp/test_http_transport.py) cover the `run_workflow` round-trip, CORS preflight with + without an allow-list, and loopback-default bind. [`skill_install.md §5`](../milestone_9_skill/skill_install.md) gained the HTTP-mode section; [architecture.md §4.4](../../architecture.md) gained the HTTP sub-bullet.

- **T02 — milestone close-out** (this task). Folded in the four legit findings from the [deep-analysis pass](deep_analysis.md):
  - [ADR-0005 — FastMCP HTTP middleware accessor](../../adr/0005_fastmcp_http_middleware_accessor.md) records the T01 accessor choice, three rejected alternatives (raw uvicorn, `server.add_middleware`, Starlette-first wrapping), and the revisit trigger (non-loopback deployment OR FastMCP removes the `middleware=` kwarg).
  - Five new tests in [`tests/mcp/test_http_transport.py`](../../../tests/mcp/test_http_transport.py): `test_http_cli_default_transport_is_stdio` (stdio-default invariant — M14-DA-05), `test_http_run_workflow_schema_parity_with_stdio` (KDR-008 parity guard — M14-DA-SP), and three HTTP round-trip tests for `list_runs`, `cancel_run`, `resume_run` (M14-DA-LR).
  - [architecture.md §4.4](../../architecture.md) sub-bullet now cites ADR-0005.
  - Zero runtime-code diff in `ai_workflows/` at T02.

**Green-gate snapshot at close-out.**

- `uv run pytest` — 607 passed + 5 new T02 tests = **612 passed, 5 skipped**.
- `uv run lint-imports` — **4 contracts kept** (no new layer contract at M14; surface-only milestone).
- `uv run ruff check` — clean.

**Deep-analysis propagation.** The local-only / solo-use invariant ([project memory `project_local_only_deployment.md`]) grounded the deep-analysis re-grading. Four findings graded legit and absorbed at T02 (M14-DA-04, -05, -SP, -LR). Moot findings (M14-DA-01 / -02 / -03 / -07 / -08) stay recorded in [deep_analysis.md](deep_analysis.md) with explicit re-open triggers — **no carry-over to future milestones, no `nice_to_have.md` entries, no new milestone**. M14-DA-06 (`--cors-origin` + `--transport stdio` UX guard) and the hosting-adjacent `nice_to_have.md §17` entry were dropped entirely per operator direction (hosting-adjacent polish is not of interest for any pending project).

**No-surface-change invariant honoured.** KDR-002 (stdio-primary skill packaging) preserved — `.claude/skills/ai-workflows/SKILL.md` byte-identical at M14. KDR-008 (MCP schemas are public contract) preserved and now actively guarded by the new schema-parity test. KDR-009 (LangGraph-owned checkpointing) unaffected. No new KDR. No new dependency (Starlette was already transitive via FastMCP + uvicorn).

**What's next.** M13 (v0.1.0 release) is now unblocked — both of M13's prerequisites (M11 gate-pause projection, M14 HTTP transport) are complete. The first published wheel can now cover both transports + the reviewable gate-pause surface that the packaged skill relies on.

## Carry-over from prior milestones

- *None.* M11 T02 (close-out) ran in parallel with M14 T01; no forward-deferrals from prior milestones targeted M14.

## Propagation status

- **All four legit deep-analysis findings absorbed in T02** — ADR-0005 + 5 tests. Zero forward-deferrals.
- **Moot findings** (M14-DA-01 / -02 / -03 / -07 / -08) stay recorded in [deep_analysis.md §Findings re-graded and relocated](deep_analysis.md) with explicit re-open triggers. None propagated.
- **No new `nice_to_have.md` entries** generated by M14. M14-DA-06 (CORS + stdio UX guard) and the §17 hosting-polish proposal were dropped entirely per operator direction.
- **No new milestone generated.** M13 is the next load-bearing milestone.

## Issues

- [T01 audit issue file](issues/task_01_issue.md) — PASS, Cycle 1, clean.
- T02 audit issue file — land after audit phase.
