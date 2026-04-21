# Task 06 — End-to-End Smoke — Audit Issues

**Source task:** [../task_06_e2e_smoke.md](../task_06_e2e_smoke.md)
**Audited on:** 2026-04-20
**Audit scope:** `tests/e2e/test_planner_smoke.py` (rewrite);
`tests/e2e/test_tier_override_smoke.py` (new); `tests/e2e/conftest.py`
(gate behaviour verified, untouched);
`design_docs/phases/milestone_5_multitier_planner/manual_smoke.md`
(new); `CHANGELOG.md` (`[Unreleased]` entry); touched-upstream
read-through of
`ai_workflows/workflows/planner.py::planner_tier_registry`,
`ai_workflows/graph/tiered_node.py::ClaudeCodeSubprocess` import site,
`ai_workflows/primitives/cost.py::CostTracker.record`,
`ai_workflows/mcp/__init__.py::build_server`,
`ai_workflows/mcp/schemas.py::RunWorkflowInput.tier_overrides`;
architecture drift check against [architecture.md](../../../architecture.md)
§3 / §4.3 / §4.4 / §11, KDR-003, KDR-004, KDR-007, KDR-009; sibling
issue files
[`task_01_issue.md`](task_01_issue.md)–[`task_05_issue.md`](task_05_issue.md);
target-task forward-deferral check against
[`task_07_milestone_closeout.md`](../task_07_milestone_closeout.md);
full gates (`uv run pytest`, `uv run pytest tests/e2e/`,
`uv run lint-imports`, `uv run ruff check`).
**Status:** ✅ PASS — 7 / 7 ACs green (AC-1 and AC-2 deferred to T07
execution per spec; T07's own ACs already carry the signal, so no
carry-over propagation is required). Three LOW observations filed; no
HIGH / MEDIUM issues open.

## Design-drift check

Cross-referenced each change against
[architecture.md](../../../architecture.md) and the KDRs the task
cites or could drift on. No drift found:

- **Layer contract (§3).** Changes land entirely under `tests/e2e/` and
  `design_docs/`. `uv run lint-imports` reports 3 / 3 contracts kept.
- **§4.3 multi-tier planner / §4.4 tier-override surface.** The
  override test exercises the MCP `tier_overrides` path exactly as §4.4
  defines it (caller-supplied `{logical: replacement}` mapping resolved
  at dispatch). The multi-tier smoke drives the §4.3 two-phase sub-graph
  via the CLI surface.
- **§11 testing strategy.** The `AIW_E2E=1` gate matches §11's
  split: hermetic default + opt-in live. Collection hook at
  `tests/e2e/conftest.py::pytest_collection_modifyitems` is unchanged
  and confirmed covering both new tests (2 skipped on a no-`AIW_E2E`
  run).
- **New dependency?** None. Builder reused `pytest`, `typer.testing`,
  `fastmcp` (via `build_server`), and module-level objects already in
  the tree. `pyproject.toml` unchanged.
- **KDR-003 (no Anthropic API).** The new
  `_assert_no_anthropic_in_production_tree` helper compiles a regex
  scoped to real-use signals (`^import anthropic`, `^from anthropic`,
  literal `ANTHROPIC_API_KEY`) and scans every `*.py` under
  `ai_workflows/`. Confirmed the regex matches all seven static-import
  variants we tested (including `import anthropic as ant` and
  `os.getenv("ANTHROPIC_API_KEY")`) while correctly not matching the
  docstring prose hits in
  `ai_workflows/{cli.py, workflows/planner.py, primitives/tiers.py,
  primitives/llm/claude_code.py}` that describe the ban itself.
  Dynamic-import gap (`importlib.import_module("anthropic")`) exists
  but is backstopped by `pyproject.toml` not listing `anthropic` — a
  runtime import would fail at CI collection. Logged as LOW.
- **KDR-004 (validator after every LLM node).** No new LLM nodes or
  graphs added. Existing pair is preserved by calling the same
  `register("planner", build_planner)` graph. Clean.
- **KDR-007 (LiteLLM hosted + bespoke Claude Code).** Monkeypatch
  target `ai_workflows.graph.tiered_node.ClaudeCodeSubprocess` matches
  the use site: `tiered_node.py` imports it at module scope
  (line 86) and constructs it at line 346 inside `_dispatch`.
  Patching the `tiered_node` module's binding intercepts the
  construction call correctly — the driver is never resolved via
  `primitives.llm.claude_code` at dispatch time. Verified.
- **KDR-009 (LangGraph's `SqliteSaver` owns checkpoints).** Tests set
  `AIW_CHECKPOINT_DB` to a tmp path and let the CLI / MCP surface
  wire the checkpointer as normal. No hand-rolled checkpoint logic
  introduced.

## AC grading

| # | AC | Verdict | Notes |
|---|----|---------|-------|
| 1 | Multi-tier smoke green once against real Qwen + real Claude Code (record in T07 close-out CHANGELOG) | ⏸ Deferred to T07 | Spec's parenthetical hands the recording of the green run to T07. T07's AC-3 already carries the signal verbatim. Code deliverable shipped; live execution + capture is T07 work. |
| 2 | Tier-override smoke green once against real Gemini — override forces cheaper path | ⏸ Deferred to T07 | Same deferral structure as AC-1. T07's AC-3 covers both runs. The raise-on-`__init__` `ClaudeCodeSubprocess` stub is the primary override-applied signal in the test body; the Gemini Flash cost reported may be `$0.00` on the free tier, which is why `total_cost_usd >= 0` (see Addition A1). |
| 3 | Default `uv run pytest` skips both cleanly; hermetic suite at 332 + M5 new-test-count | ✅ | `uv run pytest` → 366 passed, 2 skipped. `uv run pytest tests/e2e/` → 2 skipped. Both skip markers applied via the untouched collection hook. |
| 4 | Prereq checks produce readable skip reasons | ✅ | Multi-tier smoke: three independent `pytest.skip` calls with the install hint (`install ollama and pull qwen2.5-coder:32b`, `start \`ollama serve\``, `install Claude Code and log in (\`claude setup-token\`)`). Override smoke: one `GEMINI_API_KEY not set; cannot exercise Gemini path`. |
| 5 | KDR-003 grep returns zero hits | ✅ | `_assert_no_anthropic_in_production_tree` invoked at test start (line 101). Regex is narrow but covers every realistic static-import regression. Dynamic-import gap is theoretical (`anthropic` not in `pyproject.toml`) — filed as LOW observation. |
| 6 | `uv run lint-imports` 3 / 3 | ✅ | Contracts kept. No new imports crossing layers. |
| 7 | `uv run ruff check` clean | ✅ | "All checks passed!". |

## 🔴 HIGH — none

## 🟡 MEDIUM — none

## 🟢 LOW

### M5-T06-LOW-01 — `manual_smoke.md` §4 heading says "route synth through Gemini Flash" but demonstrates Qwen routing

**File:** `design_docs/phases/milestone_5_multitier_planner/manual_smoke.md` §4

**Finding:** The heading reads `## 4. Tier-override — route synth through Gemini Flash` but the concrete override demonstrated
(`tier_overrides={'planner-synth': 'planner-explorer'}`) replaces
`planner-synth` with `planner-explorer`, which under the M5 T01
refit points at **Qwen**, not Gemini Flash. The body correctly flags
this ("both calls now run on Qwen") and notes the Gemini Flash path
requires a workflow that declares a `gemini_flash` tier. The heading
remains misleading — a reader scanning section headings will expect
Gemini Flash routing and hit the disclaimer only after reading the
prose.

**Recommendation:** Retitle §4 to
`## 4. Tier-override — route synth through the explorer tier (Qwen)`
or `## 4. Tier-override — route synth onto the cheaper tier`.
Cosmetic, no AC impact, and the automated e2e is covered by
`test_tier_override_smoke.py` anyway (which uses the monkeypatched
Gemini Flash registry). Safe to defer until T07 close-out doc pass.

### M5-T06-LOW-02 — KDR-003 regex misses dynamic imports and indirect env-var reads

**File:** `tests/e2e/test_planner_smoke.py::_KDR_003_REGRESSION`

**Finding:** The regex pattern
`(^\s*import\s+anthropic\b|^\s*from\s+anthropic\b|ANTHROPIC_API_KEY)`
correctly identifies every static-import variant tested (`import
anthropic`, `import anthropic as ant`, `from anthropic.types import
foo`, double-space whitespace) and the literal env-var name in any
context (`os.environ["…"]`, `os.getenv("…")`). It does *not* match:

- `importlib.import_module("anthropic")` — dynamic import by string.
- `__import__("anthropic")` — the builtin form.
- `os.environ[f"ANTHROPIC_{suffix}"]` — interpolated env-var lookup.

The ban is backstopped by `pyproject.toml` not declaring `anthropic`
as a dependency — a dynamic import would raise `ModuleNotFoundError`
at first call, which the CI `uv run pytest` would catch. Net risk of a
silent regression sliding past this regex is low. Judgement: keep
filesystem-level grep at the narrow scope (wider patterns would
flag the docstring prose that describes the ban itself — the same
trade-off the helper's docstring calls out).

**Recommendation:** None required. If a future task adds a runtime
dependency graph audit (e.g. an ADR on provider-surface enforcement),
fold the dynamic-import pattern into it then. Flag-only — no action
this cycle.

### M5-T06-LOW-03 — `_assert_captured_usages_shape` relies on runtime tier string, not the registry name

**File:** `tests/e2e/test_planner_smoke.py::_assert_captured_usages_shape`

**Finding:** Explorer-row detection uses
`u.model.startswith("ollama/") or u.tier == "planner-explorer"`. In the
multi-tier smoke (the only caller) this matches the Qwen row exactly
once — nothing else in that run carries `ollama/` or `planner-explorer`.
The OR-branch on `tier` would also match if the workflow renamed the
logical tier downstream; today the tier string is the *workflow-level*
name `planner-explorer`, which is what
`ai_workflows/graph/tiered_node.py::tiered_node` stamps onto
`TokenUsage.tier` before `record`. Not called from the override test,
so the hypothetical confusion ("a Gemini-Flash-backed explorer call
satisfying `tier == 'planner-explorer'` and corrupting the Qwen-row
cost invariant") does not arise in practice.

**Recommendation:** None required. If a future task flips the logical
tier name (e.g. `planner-explorer` → `planner-local-coder`), this
helper needs a follow-up rename — but that's a straightforward
test-local change and doesn't constitute drift today. Flag-only.

## Additions beyond spec — audited and justified

### A1 — `total_cost_usd >= 0` relaxation on the override test

**Where:** `tests/e2e/test_tier_override_smoke.py` lines 148 + 158.

**Spec wording:** AC-2 says "override forces cheaper path." The
multi-tier smoke's AC (implied by the T06 deliverable text) says
`runs.total_cost_usd is strictly positive (Claude Code + any Haiku
sub-model); Qwen contributes 0.` The spec does *not* name a specific
assertion shape for the override test's cost field.

**Why relaxed:** Gemini Flash on the free tier reports `cost_usd=0.0`
per call — LiteLLM's pricing table for the free-tier SKU yields $0.
A strict `> 0` check would make the test flake purely on billing-tier
state. The primary override-applied signal is the raise-on-`__init__`
`ClaudeCodeSubprocess` stub: if the override regresses and synth
reaches Claude Code, `_RaiseIfInstantiated.__init__` fires, the
`run_workflow` coroutine raises, and the test fails loudly — which
is a stronger signal than any cost-threshold assertion would be.

**Verdict:** Justified. CHANGELOG already documents the deviation.

### A2 — Per-call `TokenUsage` capture via `CostTracker.record` monkeypatch

**Where:** `tests/e2e/test_planner_smoke.py::_install_usage_capture`.

**Spec wording:** "`TokenUsage.sub_models` on the Claude Code row is
non-empty if the `modelUsage` JSON the CLI returned contained
sub-models (skip the assertion if not — some Opus calls do not
auto-spawn)."

**Why added:** The M3 spec prescribed
`CostTracker.from_storage(storage, run_id).total(run_id)` for the
per-call replay surface; that helper was never implemented (M1 T05
+ T08 dropped the `llm_calls` table and made `CostTracker` in-memory
only — nice_to_have.md §9 now owns the promotion trigger). To satisfy
the `sub_models` shape check without resurrecting the deprecated
table, the Builder intercepts the single write path
(`CostTracker.record`) and appends each `TokenUsage` to a local list
while still letting the real method run. Preserves `CostTracker`
aggregates; adds a test-only shadow of the per-call ledger.

**Verdict:** Justified. Docstring on the helper explicitly cites the
M3 → M5 reframe and links back to the nice_to_have deferral. CHANGELOG
documents the approach.

### A3 — `_pinned_tier_registry` monkeypatch on the override test

**Where:** `tests/e2e/test_tier_override_smoke.py::_pinned_tier_registry`.

**Spec wording:** "overriding `planner-synth` back to Gemini Flash and
confirming the override actually routes a cheaper tier."

**Why added:** Under the M5 T01 refit the default
`planner_tier_registry` maps `planner-explorer` to Qwen/Ollama, not
Gemini Flash. The spec's "back to Gemini Flash" wording is vestigial
(inherited from the pre-M5-T01 registry, where explorer was hosted
Gemini). To honour the spec's intent — the override routes the synth
call onto a cheaper **hosted** tier that only requires `GEMINI_API_KEY`
— the Builder monkeypatches the registry so `planner-explorer` points
at Gemini Flash for this test only. The override
(`{"planner-synth": "planner-explorer"}`) then collapses both calls
onto Gemini Flash, which is the "cheaper tier" signal the test
proves. The raise-on-`__init__` Claude Code stub ensures the override
is the reason synth does not hit Claude Code (not a silent skip).

**Verdict:** Justified. This is a faithful interpretation of "routes a
cheaper tier" given the post-M5-T01 registry. CHANGELOG documents the
monkeypatch. Without it, the test would need Ollama running — which
violates the AC-4 principle ("Prerequisite: Gemini `GEMINI_API_KEY`
(sufficient on its own)").

## Gate summary

| Gate | Result |
|------|--------|
| `uv run pytest` | ✅ 366 passed, 2 skipped, 2 warnings (unrelated yoyo deprecation), 13.73s |
| `uv run pytest tests/e2e/` | ✅ 2 skipped in 1.17s |
| `uv run lint-imports` | ✅ 3 / 3 contracts kept |
| `uv run ruff check` | ✅ All checks passed |
| Design-drift scan | ✅ no KDR-003 / KDR-004 / KDR-007 / KDR-009 violations |
| Builder deliverables (files touched) | ✅ all four files present, content matches CHANGELOG entry |

## Issue log

No cross-task follow-up beyond the three LOW flag-only observations
above. All three are test-local and can be addressed during the T07
close-out doc pass (LOW-01) or deferred indefinitely (LOW-02, LOW-03).

| ID | Severity | Owner | Action |
|----|----------|-------|--------|
| M5-T06-LOW-01 | LOW | T07 close-out | Retitle `manual_smoke.md` §4 to drop the "Gemini Flash" heading. |
| M5-T06-LOW-02 | LOW | Flag-only | No action. Re-evaluate if a dependency-graph audit task lands. |
| M5-T06-LOW-03 | LOW | Flag-only | No action. Revisit if `planner-explorer` is renamed. |

## Deferred forward to T07

AC-1 and AC-2 are deferred to T07 per the T06 spec's explicit
phrasing: "*record the run in the T07 close-out CHANGELOG entry*".
The Builder cannot execute the live multi-tier run nor the live
override run from within the T06 deliverable — T06 ships the **code**
that makes the live runs executable; T07 ships the **recorded
capture** (commit sha + observed `total_cost_usd` + goal string) in
the dated `## [M5 Multi-Tier Planner] - <YYYY-MM-DD>` CHANGELOG
section.

**Propagation check against
[`task_07_milestone_closeout.md`](../task_07_milestone_closeout.md):**
T07's spec already carries this signal as a **first-class AC**, not a
carry-over:

> AC-3: `AIW_E2E=1 uv run pytest tests/e2e/` recorded in the
> close-out CHANGELOG entry (both the multi-tier smoke and the
> tier-override smoke).

> AC-4: Manual `aiw-mcp` multi-tier round-trip recorded in the
> close-out CHANGELOG entry (command + observed payload).

Because T07's own ACs already name the deferred work, no additional
"Carry-over from prior audits" section is required at the bottom of
`task_07_milestone_closeout.md`. The Builder working T07 will see the
deferral via T07's primary AC list. CLAUDE.md propagation discipline
is satisfied structurally — the channel the rule protects (Builder
visibility) is live via a stronger mechanism (explicit AC vs.
carry-over bullet).

## Propagation status

- **T07 target file:**
  [`../task_07_milestone_closeout.md`](../task_07_milestone_closeout.md)
  AC-3 + AC-4 (primary ACs, not carry-over).
- **No carry-over entry added to T07** — intentionally, per the
  analysis above. If future CLAUDE.md revisions require a belt-and-
  braces carry-over even when the target AC already carries the
  signal, this audit should be re-examined.
