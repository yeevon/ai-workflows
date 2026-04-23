# Post-0.1.2 Project Audit — Finding Disposition

**Date:** 2026-04-23
**Trigger:** Post-publish review after shipping 0.1.0 → 0.1.1 → 0.1.2 in quick succession. The operator requested a deep audit of the entire project to surface critical items missing before focus pivots to CS300.
**Audit vehicles:** three parallel Explore agents covering (a) architecture + KDR drift, (b) test coverage + doc-code parity, (c) release + ops + security.
**Grounding:** [architecture.md](../architecture.md) · [roadmap.md](../roadmap.md) · [nice_to_have.md](../nice_to_have.md) · [CLAUDE.md](../../CLAUDE.md) Auditor-mode conventions.

---

## Audit scope

The three agents re-loaded the full project scope: every KDR (architecture.md §9), the four-layer contract (§3), every shipped workflow's tier registry, the MCP surface, `docs/*.md`, README.md on `main`, [`tests/`](../../../tests/), [`.github/workflows/ci.yml`](../../../.github/workflows/ci.yml), `pyproject.toml`, `CHANGELOG.md`, and the three project-memory records that inform triage (`project_provider_strategy.md`, `project_local_only_deployment.md`, `project_m13_shipped_cs300_next.md`).

The operator surfaced two concerns **during** the audit that shaped disposition:

1. *"Tiers don't have backup and should be configurable by user"* — a real feature gap not yet tracked.
2. *"Gemini Flash was never the planner/orchestrator"* — grounded a re-read of `tiers.yaml` vs. the workflow-Python registries; the file is dead config at runtime but its contents mislead.

---

## ✅ Non-findings (verified clean)

These are documented for completeness — the audit agents verified each invariant holds today. No action required.

- **KDR-003 (no Anthropic API)** — zero `anthropic` SDK imports; zero `ANTHROPIC_API_KEY` env-var reads in runtime code. Claude access is OAuth-subprocess only.
- **KDR-004 (validator after every LLM node)** — every `TieredNode` in `planner` and `slice_refactor` is paired with a `ValidatorNode` downstream.
- **KDR-006 (three-bucket retry via `RetryingEdge`)** — no bespoke try/except retry loops outside the edge.
- **KDR-007 (LiteLLM unified + Claude Code bespoke)** — clean. Claude Code subprocess is the only non-LiteLLM adapter.
- **KDR-009 (LangGraph `SqliteSaver` owns checkpoints)** — no hand-rolled checkpoint writes.
- **Four-layer contract** — `uv run lint-imports` reports 4/4 kept, 0 broken.
- **No silent `nice_to_have.md` adoption** — no entry has been pulled in without a trigger.
- **No TODO/FIXME rot** in runtime code.
- **`.env` hygiene** — gitignored, not in any wheel, not in git history (`git ls-files | grep -i env` empty; `git check-ignore .env` reports ignored).
- **Wheel contents** — no `.env*` / no bare-root `*.yaml` / no `design_docs/` / no `CLAUDE.md` / no `.claude/commands/` leak into the published wheel (pinned by `test_built_wheel_excludes_*` tests as of 0.1.1).

---

## Finding disposition table

| # | Finding | Severity | Disposition |
|---|---|---|---|
| 1 | `docs/writing-a-workflow.md:10,31` cites phantom tier names (`orchestrator`, `gemini_flash`, `claude_code`) — pre-pivot vocabulary. | 🔴 HIGH (CS300 blocker) | **0.1.3 patch.** Rewrite tier-name references to match the workflow registries. |
| 2 | `docs/writing-a-workflow.md:118` cites phantom MCP tool `get_run_status` — actual surface has only `run_workflow` / `resume_run` / `list_runs` / `cancel_run`. | 🔴 HIGH (CS300 blocker) | **0.1.3 patch.** Remove reference; point at `list_runs(status=…)` if status querying is needed. |
| 3 | `README.md:94` on `main` says `uv run aiw version # prints 0.1.0` — wheel now ships 0.1.2. | 🔴 HIGH | **0.1.3 patch.** Rewrite line; drop the literal version string in favour of "prints the installed package version". |
| 4 | `ai_workflows/graph/ollama_fallback_gate.py:100-104` dual-logs via stdlib `logging.warning` next to a structlog emit. Violates observability discipline. | 🔴 HIGH (KDR drift) | **0.1.3 patch.** Remove the stdlib call + the now-dead `import logging`. |
| 5 | `ai_workflows/evals/capture_callback.py:57` uses `logging.getLogger(__name__)` instead of structlog. Loses structured-log contract when captures fail. | 🔴 HIGH (KDR drift) | **0.1.3 patch.** Switch to `structlog.get_logger(__name__)`; update the warning-emit call shape to structlog's signature. |
| 6 | `tiers.yaml` at repo root maps `planner → gemini/gemini-2.5-flash` and `implementer → gemini/gemini-2.5-flash`. Operator confirms this was never the plan. File is **dead config at runtime** — never loaded by dispatch; only tested by `tests/primitives/test_tiers_loader.py` as a schema smoke check. | 🔴 HIGH (cross-cutting; plan-doc drift) | **0.1.3 patch.** Delete `planner` and `implementer` entries. Keep `local_coder` + `opus` / `sonnet` / `haiku` (correct per KDR-011). Add a header comment documenting that the file is a schema-smoke fixture; the authoritative tier definitions live in each workflow's `<workflow>_tier_registry()`. `docs/writing-a-workflow.md` gains a corrected "Where tiers come from" paragraph. Full removal of the file is deferred to **M15**, which reframes it as `docs/tiers.example.yaml`. |
| 7 | No tier-level backup chain. A tier whose retry budget exhausts fails the workflow — no automatic cascade to a different provider. The existing `_mid_run_tier_overrides` (M8 T04) is gate-reactive and Ollama-specific, not a general mechanism. | 🟡 MEDIUM (real feature gap, CS300-relevant) | **M15** absorbs this. Fallback chains become a first-class field on `TierConfig`; `TieredNode` walks the chain after retry exhaustion. |
| 8 | No user-level tier configurability from a `uvx` install. The shipped wheel carries no `tiers.yaml`; each workflow's tier registry is hardcoded in Python. A PyPI-installed user cannot override `planner-synth` from Opus to Sonnet without forking. | 🟡 MEDIUM (feature gap, CS300-relevant) | **M15** absorbs this. `AIW_TIERS_PATH` + `~/.ai-workflows/tiers.yaml` overlay merges into the workflow's effective registry at dispatch; the overlay's tier names rebind by key. |
| 9 | No user-supplied workflows/primitives path. The registry ([`ai_workflows/workflows/__init__.py:58-76`](../../../ai_workflows/workflows/__init__.py#L58-L76)) is populated by in-repo imports only. An external consumer who wants their own workflow must fork. | 🟡 MEDIUM (CS300-relevant) | **M16** absorbs this. `AIW_WORKFLOWS_PATH` + `AIW_PRIMITIVES_PATH` directory-scan loader via `importlib.util.spec_from_file_location`; top-level `register(...)` is the contract. |
| 10 | No meta-workflow that helps users build their own workflows/primitives. The project ships two workflows; users face a blank-Python-file problem. | 🟡 MEDIUM | **M17** absorbs this. `scaffold_workflow` — an LLM-backed generator that outputs a workflow module + validator stubs into a user-named path. User owns the generated code; the scaffold validates "parseable Python + `register()` shape" only, not runtime safety. |
| 11 | No `.env.example` at repo root. A new contributor / future-you must guess which env vars the code reads. | 🟡 MEDIUM (ops hygiene) | **0.1.3 patch.** Ship `.env.example` listing `GEMINI_API_KEY` (with link to Google AI Studio), `OLLAMA_BASE_URL`, `AIW_STORAGE_DB`, `AIW_CHECKPOINT_DB`. Do **not** include `PYPI_TOKEN` — that's release-maintainer-only. |
| 12 | No CircuitOpen test over MCP HTTP. `tests/mcp/test_http_transport.py` covers the four tools over HTTP, but Ollama-fallback failures are only tested at the node level — a CS300 HTTP consumer has never observed the envelope shape when the circuit trips. | 🟡 MEDIUM | **M15** absorbs this. M15's fallback-cascade work exercises CircuitOpen naturally; T0N adds an HTTP round-trip that pins the envelope shape on breaker-trip. |
| 13 | `configure_logging()` is only called at CLI/MCP entry. A library-style import (`from ai_workflows.workflows.planner import build_planner` from a user's own Python) silently drops all structured logs. | 🟡 MEDIUM | **M16** absorbs this. When user-supplied workflows become a first-class surface, library-style import becomes an expected pattern. T0N moves `configure_logging()` to `ai_workflows/__init__.py` with a default level, overridable via env var. |
| 14 | `ai_workflows/primitives/llm/claude_code.py:157-162` raises `CalledProcessError` with stderr attached; [`retry.py:162`](../../../ai_workflows/primitives/retry.py#L162)`:classify()` discards the stderr body. Hard to debug Claude CLI version / OAuth expiry. | 🟡 MEDIUM | **0.1.3 patch.** Log `exc.stderr` (truncated, no secrets) as a structlog warning before the classifier returns. Small, belongs with the other observability fixes in 0.1.3. |
| 15 | No release playbook at repo root. Ceremony for 0.1.x patches lives in commit history + `design_docs/phases/milestone_13_v0_release/release_runbook.md` (builder-only). The next patch release will follow oral history. | 🟢 LOW | **nice_to_have.md §17** (new entry). Trigger: fourth patch release, or a patch-release postmortem. Until then, commit messages + M13 runbook cover it. |
| 16 | CI runs on `main` + PRs but not on `design_branch` push. Builder-only edits could regress graph/workflows code before cherry-pick to `main`. | 🟢 LOW | **nice_to_have.md §18** (new entry). Trigger: a design_branch edit regresses main without detection. Currently mitigated by running `uv run pytest` locally before cherry-pick (M13 T08 release discipline). |
| 17 | `--host 0.0.0.0` warning only in `aiw-mcp --help`, not README. | 🟢 LOW | **0.1.3 patch.** Add a one-liner "Security notes" subsection to the README MCP server section noting the loopback default and the foot-gun. |
| 18 | Dependency lower bounds are conservative but unlocked. `litellm>=1.40` is ~6 months old; `fastmcp>=0.2`, `pydantic>=2.0` similarly. | 🟢 LOW | **nice_to_have.md §19** (new entry). Trigger: security advisory for a pinned dep, OR the next minor release (`0.2.0`). `uv update` + committed lockfile at that point. |
| 19 | `StubAdapterMissingCaseError` in the eval harness has no test coverage. | 🟢 LOW | **nice_to_have.md §20** (new entry). Trigger: an eval-replay flake traces back to a stub exhaustion the test suite would have caught. Until then, the exception exists but is never raised in the current deterministic replay set. |
| 20 | Saved memory-index line for `project_provider_strategy.md` claimed "Claude Code is the dev tool, not a runtime provider" — contradicts KDR-003 / KDR-007 / KDR-011 and the actual `tiers.yaml`. | 🟢 LOW (internal) | **Fixed in the audit turn.** `MEMORY.md` hook rewritten to accurately describe the six runtime tiers. The underlying memory file was already correct — only the index description drifted. |

---

## 0.1.3 patch — scoped deliverables (items #1, #2, #3, #4, #5, #6, #11, #14, #17)

Single release-prep commit on both branches. No KDR change. No new milestone. Ships as `0.1.3` — doc-and-observability patch over `0.1.2`.

**Files touched (both branches, byte-identical):**

- `ai_workflows/graph/ollama_fallback_gate.py` — remove `logging.getLogger(...).warning(...)` + unused `import logging`.
- `ai_workflows/evals/capture_callback.py` — switch `_LOG` to `structlog.get_logger(__name__)`; update call shape.
- `ai_workflows/primitives/llm/claude_code.py` / `ai_workflows/primitives/retry.py` — surface Claude CLI stderr through structlog before `classify()` discards it (truncated; no token-shaped payloads).
- `tiers.yaml` — delete `planner:` and `implementer:` entries; add a header comment naming the file as a schema-smoke fixture and pointing at the per-workflow Python registries as the authoritative source.
- `tests/primitives/test_tiers_loader.py` — drop expectations for the deleted entries.
- `.env.example` (new) — documented env vars; placeholder values only.
- `ai_workflows/__init__.py` — `__version__` bumped to `0.1.3`.

**Files touched on `main` only (user-facing docs):**

- `README.md` — drop the `prints 0.1.0` literal from the Contributing section (replace with "prints the installed package version"); add a "Security notes" subsection under `## MCP server` covering the `--host 0.0.0.0` foot-gun.
- `docs/writing-a-workflow.md` — rewrite tier-name references; remove the phantom `get_run_status` reference; add a "Where tiers come from" subsection pointing at the per-workflow registry pattern.
- `CHANGELOG.md` — `[0.1.3] — 2026-04-23` block.

**Gates:** `uv run pytest` + `uv run lint-imports` + `uv run ruff check` green on both branches; `bash scripts/release_smoke.sh` green against the 0.1.3 wheel; post-publish `uvx --refresh --from jmdl-ai-workflows==0.1.3 aiw version` prints `0.1.3`.

---

## Milestones generated by this audit

- **[M15 — Tier overlay + fallback chains](../phases/milestone_15_tier_overlay/README.md)** absorbs findings #7, #8, #12.
- **[M16 — External workflows load path](../phases/milestone_16_external_workflows/README.md)** absorbs findings #9, #13.
- **[M17 — Scaffold workflow meta-workflow](../phases/milestone_17_scaffold_workflow/README.md)** absorbs finding #10.

Findings #15, #16, #18, #19 are promoted to [`nice_to_have.md`](../nice_to_have.md) §§17–20 with explicit triggers. Finding #20 was resolved in the audit turn (memory-index hygiene).

---

## Propagation status

- **0.1.3 patch commits:** to be stamped after the patch lands.
- **M15 carry-over:** `docs/writing-a-workflow.md` rewrite (post-patch) should cite M15 as the source of truth for where user-configurable tiers will live. No runtime carry-over — 0.1.3 is doc-and-observability only.
- **No findings forward-deferred without a home.** Every HIGH + MEDIUM maps to either the 0.1.3 patch or a concrete milestone task. Every LOW maps to either the 0.1.3 patch or a `nice_to_have.md` entry with a real trigger.
- **Operator memory refreshed.** `MEMORY.md` index entry for `project_provider_strategy.md` corrected; the underlying memory file was already accurate.
