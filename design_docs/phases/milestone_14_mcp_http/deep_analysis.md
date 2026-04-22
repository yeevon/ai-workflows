# Milestone 14 — Deep-analysis pass

**Written:** 2026-04-22, after M14 T01 landed clean (commit baseline pending T02).
**Rebased:** 2026-04-22 against the project's **local-only / solo-use** invariant after the first draft implicitly modelled cloud / LAN / reverse-proxy threats that do not apply.
**Mirrors:** the 2026-04-21 M8 deep-analysis pass that produced M10 + ADR-0003 + five `nice_to_have.md` entries. Same shape — critical re-read of the landed surface, then propose where findings flow — but sized to M14's deployment scope, which is materially smaller than M8's runtime-fault-tolerance scope.
**Grounding:** [milestone README](README.md) · [task_01_http_transport.md](task_01_http_transport.md) · [task_01 audit issue file](issues/task_01_issue.md) · [architecture.md §4.4](../../architecture.md) · `ai_workflows/mcp/__main__.py` · `ai_workflows/mcp/server.py` · FastMCP 3.2.4 source (`.venv/lib/python3.13/site-packages/fastmcp/`).

---

## TL;DR

M14 T01 landed clean — 607 tests green, 4 import-linter contracts kept, zero schema drift. The surface is **minimal and load-bearing exactly as scoped**. Once the findings are re-graded against the project's committed threat model (loopback, single machine, single operator, **no hosting interest for any pending project** — see [project memory `project_local_only_deployment.md`]), the set collapses sharply:

- **4 legit issues** — all threat-model-independent (documentation debt, regression guards, public-contract parity). All absorb into **M14 T02**.
- **Several moot under scope** — recorded here with the trigger that would re-open them, but **no carry-over, no nice_to_have entry, no new milestone**. They are defenses against threats the project has explicitly committed not to model (hosting, LAN, reverse proxy, CORS beyond the loopback Astro consumer).

**No new milestone (M15) is justified.** M14 T02 absorbs every legit finding. The hardening budget is asymmetric to M8's because M14's surface is ~40 LOC of transport wiring — not a runtime-semantics surface.

Recommend executing the propagation in T02 and closing the milestone.

---

## Threat model grounding (read this first)

ai-workflows is a **solo-use, local-only** tool. The operator runs the MCP server on their own laptop; every consumer — including the Astro CS-300 notes site that drives the M14 HTTP transport — also runs on that same laptop. No cloud deployment, no LAN host, no reverse proxy, no CDN, no multi-machine surface at any milestone on the committed roadmap (through at least M15+). The milestone README's non-goals call this out verbatim: *"local-only consumers on the same machine have no threat model that TLS addresses."*

Every finding in this pass is graded against **loopback / single-machine / single-operator** as the invariant. Scenarios that assume non-loopback network paths (LAN / reverse proxy / CDN / remote origin / multi-user) are **moot under the current scope, not LOW**. They do not collapse to a startup WARN, a `/health` route, or a `--stateless-http` flag — they collapse to "not a threat this project models."

The triggers listed under each moot finding are the signals that would flip the invariant and re-open the finding as legit. The operator owns those triggers explicitly (a second consumer, a non-loopback deployment, hostility in the host environment). Absent a trigger, the findings stay moot.

---

## Method

1. Re-read [task_01_http_transport.md](task_01_http_transport.md) + milestone README + architecture.md §4.4 with fresh eyes.
2. Read FastMCP 3.2.4 streamable-HTTP source (`server/mixins/transport.py`, `server/http.py`) for invariants not pinned by the spec.
3. First pass stressed the surface against three threat-model angles (server-side restart mid-run, non-loopback bind + zero auth, long-running tool call over HTTP) — which **over-reached** on non-loopback scenarios and was rebased here.
4. Stress the **spec / implementation gap** — the CORS-middleware accessor rewrite was authorised by Risks §2 but not ADR-ised. Threat-model-independent.
5. Stress the **invariant-test coverage** — what regressions would the existing 4-test suite fail to catch. Threat-model-independent.
6. Re-grade every finding against the local-only invariant before assigning severity.
7. Cross-check against [nice_to_have.md](../../nice_to_have.md) to avoid duplicate entries.

---

## Findings

### 🔴 HIGH — none

Scope held. No KDR violation, no layer break, no schema drift, no drive-by refactor. The four-layer contract is intact; `build_server()` reused byte-identically.

### 🟡 MEDIUM

#### M14-DA-04 — CORS-middleware accessor deviation is undocumented beyond a docstring

**Fact.** Task spec prescribed `server.add_middleware(CORSMiddleware, ...)`; FastMCP 3.2.4's `add_middleware` takes a FastMCP-internal `Middleware` instance, not the Starlette class. The Builder picked `server.run(transport="http", middleware=[Middleware(CORSMiddleware, ...)])` which flows through `run_http_async` → `http_app(middleware=...)` → `create_streamable_http_app(middleware=...)` (see `fastmcp/server/mixins/transport.py:235, 310`).

Risks §2 of the task spec **pre-authorised** this amendment. The decision is recorded in three places: `_run_http`'s docstring, the task audit issue file's "Deviation from spec" section, and the CHANGELOG entry. But **no ADR** captures the choice.

**Why it matters.** The next time FastMCP ships a minor bump (3.3.x, 4.x) with a renamed accessor, the next Builder — including future-you — reads `_run_http`'s docstring but not the reasoning behind *why* the Builder picked `run(middleware=...)` over the obvious alternative `http_app(middleware=...) + uvicorn.run(...)`. An ADR captures the trade-off (the former is one-line; the latter requires re-deriving the uvicorn config FastMCP already bakes in — log level, lifespan, timeouts, WS backend). Mirrors [ADR-0003]'s retroactive shape from the M8 deep-analysis pass.

**Threat-model relevance.** None. This is documentation debt, not a threat-model finding. Legit regardless of deployment shape.

**Why MEDIUM.** The decision is not load-bearing in the runtime sense (behaviour is pinned by tests), but the **reasoning** is load-bearing for future maintenance. Retroactive ADRs are cheap.

**Action — Address in M14 T02:** file [`design_docs/adr/0005_fastmcp_http_middleware_accessor.md`](../../adr/0005_fastmcp_http_middleware_accessor.md) (new); add a row to architecture.md §9 KDRs-or-ADRs table *(no new KDR — ADR-only)*.

---

#### M14-DA-SP — HTTP / stdio schema-parity test is missing

**Fact.** T01's 4-test suite exercises `run_workflow` over HTTP end-to-end, but does not assert that the HTTP response's `RunWorkflowOutput` shape is equal to the stdio response's shape for the same input. KDR-008 names the MCP schemas as the project's **public contract**; if FastMCP's HTTP transport serialises pydantic models differently than its stdio transport (a field dropped, a `None` serialised as `null` in one and missing in the other), consumers silently break.

**Threat-model relevance.** None. The schema-contract invariant is a consumer-facing guarantee regardless of deployment shape. An Astro browser consumer deserialising different-shaped responses than a stdio MCP host is a bug whether one or both are on loopback.

**Why MEDIUM.** Pins a KDR-level invariant at the transport layer. Without it, a FastMCP version bump could regress the contract silently.

**Action — Address in M14 T02:** new test `test_http_run_workflow_schema_byte_identical_to_stdio` (~30 LOC). Runs the same `run_workflow` payload over both transports, asserts resulting `RunWorkflowOutput` dicts are equal modulo `run_id`. Extend `tests/mcp/test_http_transport.py` or create `tests/mcp/test_http_schema_parity.py`.

---

#### M14-DA-LR — Only `run_workflow` is exercised over HTTP; `list_runs` / `resume_run` / `cancel_run` are not

**Fact.** T01's HTTP suite exercises exactly one of the four MCP tools (`run_workflow`). The other three (`list_runs`, `resume_run`, `cancel_run`) are covered over stdio but not over HTTP. Each has a different return shape — `list_runs` returns a list, `resume_run` returns a run-result dict, `cancel_run` returns a boolean envelope. Pydantic → JSON serialisation paths differ per shape; a FastMCP regression on one would miss the others.

**Threat-model relevance.** None. Same public-contract argument as M14-DA-SP.

**Why MEDIUM.** Coverage gap, not a behavioural bug. Catches the regression class where "one tool serialises fine, another doesn't" — which is exactly the kind of silent drift a minor-version bump can introduce.

**Action — Address in M14 T02:** one round-trip test per remaining tool (~30 LOC total). `test_http_list_runs_roundtrip`, `test_http_cancel_run_roundtrip`, `test_http_resume_run_roundtrip_without_resume_branch` (resume's gate-branch semantics are already pinned stdio-side; the HTTP version just confirms the tool is reachable and returns the expected envelope).

---

### 🟢 LOW

#### M14-DA-05 — Stdio-default not pinned at the `__main__` layer

**Fact.** The new HTTP suite pins `--host` default (`test_http_default_bind_is_loopback`) but not `--transport`'s default. A regression that flipped default to `http` would pass every existing test — the stdio-path tests call `build_server()` directly and never shell through `__main__`.

**Threat-model relevance.** None. Every existing MCP host registration (Claude Code, Cursor, Zed) invokes `aiw-mcp` with zero flags and expects stdio. Flipping the default silently breaks all of them regardless of deployment shape.

**Why LOW.** Invariant test, one line. Trivial to land with M14-DA-04/SP/LR.

**Action — Address in M14 T02:** one-line invariant test — `assert inspect.signature(_cli).parameters["transport"].default.default == "stdio"` — alongside the existing `test_http_default_bind_is_loopback`.

---

## Findings re-graded and relocated

### Moot under current scope (no action, re-open only on trigger)

The findings below were MEDIUMs or LOWs in the first draft. They are all defenses against threats the project has committed not to model (hosting, LAN, reverse proxy, CORS beyond the loopback Astro consumer). They are **moot**, not LOW — LOW implies "small but legit." These are not legit under the committed deployment shape. Recorded here for future-you when scope shifts.

#### M14-DA-01 (moot) — Session-state is process-local; restart drops in-flight HTTP sessions

**First-draft fact.** FastMCP 3.2.4 streamable-HTTP defaults to stateful (`stateless_http: bool = False`, `settings.py:320`). A restart drops in-flight sessions. A mid-run browser consumer sees a 404 / connection drop.

**Why moot under scope.** The recovery is "re-open the tab" — the operator owns both the server and the browser, on the same machine. The LangGraph checkpoint is safe (SQLite-backed via `SqliteSaver`), the `runs` row is safe, the run completes or fails to storage regardless of whether the originating HTTP session survived. A solo operator who restarts their own server mid-run can glance at `aiw list-runs` to find the orphaned run-id.

**Re-open trigger.** A second consumer appears that cannot tolerate session loss (e.g. an unattended automation that kicks off a run and expects the same session to carry the gate-pause response back). At that point `--stateless-http` becomes legit; file under the triggering milestone's scope.

**Not filed under nice_to_have.** Because a `--stateless-http` flag by itself solves nothing — stateless HTTP is a trade-off (loses server-initiated notifications, session-scoped auth) that only makes sense when the *consumer* can't reconnect. Filing a knob without a consumer is premature.

---

#### M14-DA-02 (moot) — No startup WARN when binding non-loopback with no auth

**First-draft fact.** `aiw-mcp --transport http --host 0.0.0.0` starts listening on every interface with zero authentication.

**Why moot under scope.** `--host 0.0.0.0` is a foot-gun on your own laptop, not a LAN exposure. There is no committed non-loopback deployment path. The help text and [skill_install.md §5](../milestone_9_skill/skill_install.md) threat-model paragraph already warn pre-invocation; a startup WARN would be defense-in-depth against a threat the project explicitly does not model.

**Re-open trigger.** The operator commits to a non-loopback deployment shape (second machine on a trusted LAN, a reverse proxy, a cloud host). At that point a startup WARN is one signal among many that auth/TLS/rate-limiting also need to land — it belongs in the same milestone as those, not here.

**Not filed under nice_to_have.** Because the WARN is only useful in a deployment shape the project hasn't committed to. Parking it with a trigger here is sufficient.

---

#### M14-DA-03 (moot) — `run_workflow` over HTTP holds the connection ~30-60s before the gate

**First-draft fact.** The `planner` workflow runs two LLM calls before hitting `plan_review_gate`; over HTTP the call is one request/response, holding the connection ~30-60s.

**Why moot under scope.** Chrome and Firefox have no default request timeout on loopback. There is no reverse proxy layer (nginx, Cloudflare, Fly, Vercel) to hit with a 60s / 100s default. The Astro CS-300 consumer runs on the same machine and connects directly.

**Re-open trigger.** A reverse-proxy deployment shape appears. Same trigger as M14-DA-02 (non-loopback deployment).

**Not filed under nice_to_have.** Same reasoning as M14-DA-02.

---

#### M14-DA-07 (moot) — No `/health` or `/readyz` endpoint

**First-draft fact.** FastMCP exposes `@server.custom_route("/health", ...)` as a first-class surface.

**Why moot under scope.** The operator knows when their own server is up. They started it in their own terminal. A browser consumer that wants "MCP offline" state can catch the MCP-shaped request failure — same round-trip it needs for the real call anyway.

**Re-open trigger.** An automated-monitoring consumer appears (a scheduled job, a cloud uptime check, a multi-machine deploy where the operator isn't the one pressing enter on `uv run aiw-mcp`).

**Not filed under nice_to_have.** Same reasoning — only useful in a deployment shape the project hasn't committed to.

---

#### M14-DA-08 (moot) — Port-collision surfaces as raw uvicorn OSError

**First-draft fact.** `aiw-mcp --transport http --port 8000` with 8000 in use prints a stack trace ending in `OSError: [Errno 98] Address already in use`.

**Why moot under scope.** Not M14-specific — every Typer CLI binding a socket does this. Solo operator; one-second diagnosis from the error message.

**Re-open trigger.** A second operator finds the raw traceback confusing. Wrap with `typer.BadParameter` at that point. Not worth pre-emptive polish.

**Not filed under nice_to_have.** Applies to every Typer CLI the project ships, not M14 specifically. If it becomes a polish item, it's project-wide.

---

## ADR candidate — M14 T02 deliverable

### ADR-0005 — FastMCP HTTP middleware accessor

**Status:** draft (to be filed alongside M14 T02).

**Shape:**

> *Context.* M14 T01 needed to attach Starlette CORSMiddleware to the FastMCP streamable-HTTP server. Task spec prescribed `server.add_middleware(CORSMiddleware, ...)`; FastMCP 3.2.4's `add_middleware` method takes a FastMCP-internal `Middleware`, not the Starlette class. The spec's Risks §2 pre-authorised the Builder to pick the correct accessor at implementation time.
>
> *Decision.* Pass `middleware=[Middleware(CORSMiddleware, ...)]` as a transport kwarg to `server.run(transport="http", ...)`. This flows through FastMCP's `run_http_async` → `http_app(middleware=...)` → `create_streamable_http_app(middleware=...)`.
>
> *Rejected alternatives.*
>
> - `server.http_app(middleware=[...]) + uvicorn.run(app, host, port)` — requires re-deriving FastMCP's uvicorn config (`timeout_graceful_shutdown=2`, `lifespan="on"`, `ws="websockets-sansio"`, log_level routing). Not worth the re-derivation at M14's solo-use scope.
> - `server.add_middleware(CORSMiddleware, ...)` — FastMCP 3.2.4 raises `TypeError` (mismatched parameter types).
> - Fork to a Starlette-first pattern (`app = Starlette(routes=[...], middleware=[...])` wrapping FastMCP's ASGI app) — maximum flexibility but doubles the lines and couples to FastMCP's internal ASGI app shape more tightly, not less.
>
> *Consequences.* Implicit coupling to FastMCP's uvicorn defaults. Upside: zero re-derivation. Downside: no direct uvicorn-level knob at M14 (e.g. `proxy_headers`, `forwarded_allow_ips`) — acceptable because the project does not model reverse-proxy deployments. Revisit if the deployment shape ever flips to non-loopback.

**Storage:** `design_docs/adr/0005_fastmcp_http_middleware_accessor.md`.

**Architecture.md §9 KDRs+ADRs table update.** Add the ADR row; no new KDR.

---

## `nice_to_have.md` candidates

None. The only candidate the first draft would have filed (a `--cors-origin` + stdio guard) is moot — the operator has no interest in hosting-adjacent UX polish for any pending project. CORS only exists on the loopback Astro consumer path; a misuse there is one-second diagnosis from the browser's dev-tools console.

---

## Items already covered — no new entry needed

The M14 README §Propagation status already names three triggers that would promote existing parking-lot candidates. Not re-listing here:

- **Auth (bearer / OAuth).** Trigger: non-loopback deployment. M14 README names the trigger; `nice_to_have.md` would be premature.
- **TLS termination.** Trigger: same. User-level deployment doc when it lands.
- **Rate limiting / concurrency caps.** Trigger: a second consumer that can burn provider quota concurrently with the operator's own use. M14 README names it.

The cross-referenced `nice_to_have.md §12` (Promote read-only MCP tools to `_dispatch`) is orthogonal to HTTP transport and unaffected by M14.

---

## Invariant-test candidates (M14 T02 carry-over)

Consolidated list (addresses M14-DA-05, M14-DA-SP, M14-DA-LR):

- `test_http_cli_default_transport_is_stdio` — one-line assertion on the Typer signature; protects the zero-flag invocation contract every MCP-host registration depends on.
- `test_http_run_workflow_schema_byte_identical_to_stdio` — runs the same `run_workflow` payload over both transports, asserts `RunWorkflowOutput` dicts equal modulo `run_id`. Pins KDR-008 at the transport layer.
- `test_http_list_runs_roundtrip` — exercises `list_runs` over HTTP to pin the second tool end-to-end.
- `test_http_cancel_run_roundtrip` — exercises `cancel_run` over HTTP (third tool).
- `test_http_resume_run_roundtrip_without_resume_branch` — exercises `resume_run` envelope over HTTP (fourth tool). Resume-branch semantics are already pinned stdio-side; the HTTP version just confirms reachability + envelope shape.

Each is ~30 LOC, no new fixtures. Fold into a new `tests/mcp/test_http_schema_parity.py` or extend `test_http_transport.py`.

---

## Propagation shape — no M15 milestone

**Absorb everything legit at M14 T02. Moot items carry no propagation.**

Rationale:

- M8 deep-analysis justified M10 because the **runtime** fault-tolerance surface had five distinct design gaps spread across the circuit-breaker, gate, and retry semantics. M14's surface is ~40 LOC of transport wiring; after re-grading against the local-only invariant, the legit findings are all documentation + regression-guard debt.
- No finding here requires a new graph primitive, a KDR amendment, or an architecture-layer change. ADR-0005 is local to the M14 surface.
- No finding here naturally belongs in a future milestone that touches the same area — there is no planned future milestone touching MCP HTTP transport on the committed roadmap.
- The operator has M13 (v0.1.0 release) as the next load-bearing milestone; opening M15 for what fits in a close-out task would delay the first wheel for diminishing returns.

### What lands where (final)

| Finding | Legit under scope? | Destination |
| --- | --- | --- |
| M14-DA-04 — ADR-0005 (middleware accessor) | ✅ Yes (threat-model-independent) | **M14 T02:** new ADR + architecture.md §9 row |
| M14-DA-SP — HTTP/stdio schema parity test | ✅ Yes (public contract, KDR-008) | **M14 T02:** 1 new test |
| M14-DA-LR — HTTP round-trip for `list_runs` / `resume_run` / `cancel_run` | ✅ Yes (public contract, KDR-008) | **M14 T02:** 3 new tests |
| M14-DA-05 — stdio-default invariant test | ✅ Yes (regression guard) | **M14 T02:** 1-line test |
| M14-DA-06 — `--cors-origin` with stdio guard | ❌ No (hosting-adjacent; operator uninterested) | Dropped entirely |
| M14-DA-01 — session-state on restart | ❌ Moot (recovery is "re-open the tab") | Recorded; re-open on second-consumer trigger |
| M14-DA-02 — non-loopback startup WARN | ❌ Moot (no non-loopback deployment) | Recorded; re-open on non-loopback trigger |
| M14-DA-03 — idle-timeout behind reverse proxy | ❌ Moot (no reverse proxy) | Recorded; re-open on reverse-proxy trigger |
| M14-DA-07 — `/health` endpoint | ❌ Moot (operator knows their own server) | Recorded; re-open on monitoring trigger |
| M14-DA-08 — port-collision UX | ❌ Moot (not M14-specific) | Recorded; re-open on operator complaint |

**Net M14 T02 scope budget:** ADR-0005 + 5 new tests + the standard close-out deliverables (roadmap flip, CHANGELOG promote, milestone README Outcome). Fits within one close-out task. **Smaller than the first draft proposed** — no new AC for a WARN, no §5 extensions for doc caveats against threats the project doesn't model, no `--stateless-http` flag speculation, no nice_to_have entries.

---

## What this analysis is *not*

- **Not a re-scoping of M14 T01.** T01 is green and shipped. Nothing here is a HIGH or a blocker.
- **Not a KDR amendment.** No finding rises to "architectural rule change"; ADR-0005 is local to the M14 surface.
- **Not a live-smoke re-run.** The operator owns the live smoke at T02 close-out (mirrors the M11 / M9 close-out pattern).
- **Not an audit re-do.** The T01 audit is final and passes; this pass is orthogonal — forward-looking maintenance.
- **Not a threat-model exercise against hypothetical deployment shapes.** The first draft drifted here and was rebased. The committed scope is loopback + single-machine + single-operator; findings against non-loopback shapes are parked with triggers, not filed as LOW / nice_to_have.

---

## Next step

Default recommendation: **accept the T02 carry-over list above** (ADR-0005 + 5 new tests) — T02 Builder spec picks it up. All moot findings stay recorded here; no cross-file propagation needed until a trigger flips.

If the operator wants to prune further:

- Drop M14-DA-LR's `resume_run` round-trip test (3 → 2 round-trip tests). The stdio-side resume coverage is dense; an HTTP envelope check is belt-and-suspenders.

No re-scope option proposes a new milestone.
