# Task 06 — stdio Transport + `claude mcp add` Setup Docs — Audit Issues

**Source task:** [../task_06_stdio_transport.md](../task_06_stdio_transport.md)
**Audited on:** 2026-04-20
**Audit scope:** `ai_workflows/mcp/__main__.py` (new stdio entry point), `pyproject.toml` (`[project.scripts]` addition), `design_docs/phases/milestone_4_mcp/mcp_setup.md` (new setup doc), `README.md` (new pointer subsection), `tests/mcp/test_entrypoint.py` (new), `CHANGELOG.md`. Full gates (`uv run pytest`, `uv run lint-imports`, `uv run ruff check`). Cross-referenced against `architecture.md §3` (layer contract), `§4.4` (surfaces, FastMCP), `§6` (dependencies), KDR-002 (portable inside-out MCP surface), KDR-008 (FastMCP), M4 README, prior T01 issue file (scaffold import hygiene).
**Status:** ✅ PASS — 0 OPEN issues.

---

## Design-drift check (architecture.md + KDRs)

| Concern | Finding |
| --- | --- |
| New dependency added? | **None.** `fastmcp>=0.2` was already in `pyproject.toml` (M1 dependency set); the entry point is a thin wrapper around the existing `build_server()` factory. |
| New module or layer? | `ai_workflows/mcp/__main__.py` is the stdio entry point — still inside the `mcp` surfaces package. No new layer. Imports only `ai_workflows.mcp.server.build_server` and `ai_workflows.primitives.logging.configure_logging` — both allowed by the four-layer contract. Lint-imports 3/3 KEPT. |
| LLM call added? | No. The entry point starts the JSON-RPC server; LLM calls only fire when a client invokes `run_workflow` / `resume_run`. |
| Checkpoint / resume logic? | No change. |
| Retry logic? | No change. |
| Observability? | `configure_logging(level="INFO")` called at startup — uses the existing `StructuredLogger` stderr sink, which is the KDR-compatible channel (no Langfuse, OTel, LangSmith). ✓ |
| KDR-002 MCP portable surface | Completes the four-tool inside-out surface with a runnable stdio transport. Claude Code (per the solo-developer pattern) can now register `aiw-mcp` as a stdio MCP server and drive the planner workflow end-to-end. ✓ |
| KDR-003 Anthropic boundary | No provider imports added; `grep -E "ANTHROPIC_API_KEY\|import anthropic\|from anthropic" ai_workflows/mcp/__main__.py` → **0 matches**. The entry point only imports `build_server` + `configure_logging`. ✓ |
| KDR-008 FastMCP | Entry point delegates to FastMCP's `server.run()` (default stdio transport). No custom transport plumbing. ✓ |
| `architecture.md §4.4` — "stdio/HTTP transport" | Stdio is shipped; HTTP is explicitly deferred per M4 README Non-goals. Matches the "first, for Claude Code's local-host use case" framing in §4.4. ✓ |
| Logs on stderr | `configure_logging` routes through `StructuredLogger`'s stderr sink — stdout stays clean for JSON-RPC frames. Docstring at `__main__.py:38-41` calls this out explicitly. A stray `print()` on stdout would corrupt the JSON-RPC channel; source inspection confirms none added. ✓ |

**Verdict:** no drift.

---

## Acceptance-criteria grading

| # | AC | Grade | Evidence |
| --- | --- | --- | --- |
| 1 | `ai_workflows/mcp/__main__.py` exists; `python -m ai_workflows.mcp` starts the server over stdio | ✅ | File exists at [ai_workflows/mcp/__main__.py](../../../../ai_workflows/mcp/__main__.py). Manually verified: `uv run python -m ai_workflows.mcp` prints the FastMCP 3.2.4 banner + server info and then blocks on stdio awaiting JSON-RPC frames (expected stdio-server behaviour). `test_main_module_imports_cleanly` pins the clean-interpreter import path so a side-effect `build_server()` or `server.run()` at import time would regress loudly. |
| 2 | `aiw-mcp` console script resolves post-`uv sync` | ✅ | `pyproject.toml` lines 36-39 carry the new `aiw-mcp = "ai_workflows.mcp.__main__:main"` entry under `[project.scripts]`. Verified: `uv sync` → `uv run which aiw-mcp` → `.venv/bin/aiw-mcp`. `test_aiw_mcp_console_script_is_registered` pins the entry-points registration with exact-value assertion (`aiw_mcp.value == "ai_workflows.mcp.__main__:main"`) — a silent rename would fail the test. |
| 3 | `mcp_setup.md` documents the exact `claude mcp add` invocation + the MCP JSON config alternative | ✅ | [mcp_setup.md §2](../../mcp_setup.md) carries the exact command: `claude mcp add ai-workflows --scope user -- uv run aiw-mcp`; §3 provides a `.mcp.json` snippet with the canonical `command` + `args` + `env` shape for `GEMINI_API_KEY` forwarding. §1 prerequisites, §4 smoke check (`run_workflow` → `resume_run` round-trip), and §5 troubleshooting (PATH + GEMINI_API_KEY not inherited) all present. §(scope boundary) documents the M4/M6 cancellation split + stdio-only transport + `get_cost_report` deferral so MCP clients don't expect those surfaces. |
| 4 | Fresh Claude Code session can invoke `run_workflow` and receive `{run_id, awaiting: "gate"}` (manual — record in T08 CHANGELOG entry) | **DEFERRED** | **Explicitly a manual-verification step** per the spec — "record the tested command + output in the T08 CHANGELOG entry". Carry-over propagated to T08 below so the T08 Builder knows to close this loop. |
| 5 | `uv run pytest tests/mcp/test_entrypoint.py` green | ✅ | Focused run: **3 passed in 2.60s**. |
| 6 | `uv run lint-imports` 3/3 kept; `uv run ruff check` clean | ✅ | Lint-imports: `Contracts: 3 kept, 0 broken.` Ruff: `All checks passed!` |

AC-4 is spec-authorized to be deferred to T08 — this is not an audit failure, it is a planned manual step. All other ACs pass.

---

## 🔴 HIGH — (none)

## 🟡 MEDIUM — (none)

## 🟢 LOW — (none)

---

## Additions beyond spec — audited and justified

1. **`test_main_module_imports_cleanly`** uses a subprocess for the import probe. *Justified.* The task spec mentions `python -m ai_workflows.mcp --help` as one option for a launch smoke; in practice, passing `--help` to a FastMCP server starts the server and prints the banner on stdout (then blocks on stdio), not a Click/Typer-style help text. A subprocess `import ai_workflows.mcp.__main__` is the equivalent "runs without error" signal the spec was after — it catches side-effect import regressions without the test blocking forever on stdio. Matches the T01 scaffold's existing `test_mcp_surface_imports_cleanly_in_clean_interpreter` pattern.

2. **Exact-value assertion for the entry-point target** (`aiw_mcp.value == "ai_workflows.mcp.__main__:main"`). *Justified.* A silent rename to `:start` / `:run` / a target module move would not break `callable(loaded)` alone; asserting the string pins the `claude mcp add` and `.mcp.json` surfaces against drift.

3. **"Scope boundary" section in `mcp_setup.md`** documenting the three non-shipping features (in-flight cancellation, HTTP transport, `get_cost_report` tool). *Justified.* Sets MCP-client expectations explicitly so hosts don't burn a ticket asking "why doesn't cancel abort a running task". Mirrors the M4 README Non-goals and architecture.md §8.7 prose without duplicating them.

4. **README pointer under new `## MCP server` subsection** (instead of inlining into `## Getting started`). *Justified.* The spec allows either. A subsection keeps the `Getting started` block focused on the CLI path that already works, and the pointer-only pattern (no content duplication) matches the spec explicitly: "Do not duplicate the content — the doc is the canonical source."

No other additions. No new dependencies, no new modules, no new public API.

---

## Gate summary

| Gate | Command | Result |
| --- | --- | --- |
| Full pytest | `uv run pytest` | **331 passed, 1 skipped** (3 new T06 tests + 328 existing) |
| Focused T06 | `uv run pytest tests/mcp/test_entrypoint.py` | **3 passed** |
| Layer contract | `uv run lint-imports` | **3 / 3 contracts kept** |
| Lint | `uv run ruff check` | **All checks passed** |
| KDR-003 boundary | `grep -nE "ANTHROPIC_API_KEY\|import anthropic\|from anthropic" ai_workflows/mcp/__main__.py` | **no matches** |
| Console script resolves | `uv run which aiw-mcp` | **`.venv/bin/aiw-mcp`** |

---

## Issue log — cross-task follow-up

| ID | Severity | Note | Owner |
| --- | --- | --- | --- |
| M4-T06-ISS-01 | DEFERRED | Manual verification: fresh Claude Code session registered against `aiw-mcp` invokes `run_workflow(planner, goal=…)` and receives `{run_id, awaiting: "gate"}`. Record the tested command + output in the T08 milestone-closeout CHANGELOG entry. | M4 T08 |

---

## Deferred to nice_to_have

None raised. (HTTP transport is deferred per the M4 README Non-goals, not raised as a new finding here.)

---

## Propagation status

Carry-over propagated to:

- [../task_08_milestone_closeout.md](../task_08_milestone_closeout.md) — `M4-T06-ISS-01` recorded as a carry-over item the T08 Builder must tick off when the manual Claude Code registration loop is validated.
