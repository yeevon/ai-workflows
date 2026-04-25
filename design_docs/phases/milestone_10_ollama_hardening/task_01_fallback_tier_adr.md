# Task 01 — ADR-0003 + `OllamaFallback` Docstring Lock for `fallback_tier`

**Status:** 📝 Planned.
**Grounding:** [milestone README §Exit criteria 1](README.md) · [architecture.md §8.4](../../architecture.md) · [KDR-003](../../architecture.md) · [M8 T04 deep-analysis (fragility #3 / debt #3)](../milestone_8_ollama/README.md).

## What to Build

A retroactive [ADR-0003](../../adr/0003_ollama_fallback_tier_choice.md) that
locks the M8 T04 decision to use `planner-synth` (Claude Code Opus via the
OAuth subprocess tier, KDR-003) as `OllamaFallback.fallback_tier` for both
`PLANNER_OLLAMA_FALLBACK` and `SLICE_REFACTOR_OLLAMA_FALLBACK`, instead of the
`gemini_flash` route the M8 T03/T04 specs anticipated in their prose.

The decision was correct but undocumented. The ADR records the cost +
availability trade-offs, names `gemini_flash` as the rejected alternative
with rationale, and is cited from the two `OllamaFallback` constants'
docstrings so a future reader doesn't relitigate the choice.

This is a **doc + docstring** task. No code path changes. No tier swap.

## Deliverables

### [design_docs/adr/0003_ollama_fallback_tier_choice.md](../../adr/0003_ollama_fallback_tier_choice.md)

Mirror the shape of the existing ADRs ([0001](../../adr/0001_workflow_hash.md),
[0002](../../adr/0002_bare_typed_response_format_schemas.md),
[0004](../../adr/0004_tiered_audit_cascade.md)). Sections:

- **Status** — `Accepted (retroactive, 2026-04-21 origin; recorded <YYYY-MM-DD>)`.
- **Context** — M8 T04 wired `OllamaFallback` for both planner and slice_refactor;
  the spec body referred to `gemini_flash` as the illustrative replacement, the
  implementation chose `planner-synth`. The mismatch was flagged at M8 T05
  audit (LOW ISS-02, see [issues/task_05_issue.md](../milestone_8_ollama/issues/task_05_issue.md))
  and again in the M8 deep-analysis post-mortem (debt #3).
- **Decision** — `fallback_tier="planner-synth"` for both workflows.
- **Rationale** — three load-bearing reasons:
  1. **Vendor-independence.** The three tier vendors in play
     (Ollama-local, Gemini, Claude Code OAuth) have **independent failure
     surfaces**: Ollama outages are local-machine (GPU/daemon/model
     file); Gemini outages are remote-API (rate limits, regional
     incidents); Claude Code is a third independent vendor (OAuth
     subprocess via the `claude` CLI per KDR-003). When the operator
     hits an Ollama outage, falling back to a third independent vendor
     maximises the chance the fallback path is healthy. Falling back to
     Gemini would expose the same fallback round-trip to whatever
     remote-API conditions the operator's `planner-synth` calls already
     experience in the rest of the run — correlated failure modes are
     the wrong shape for a one-shot fallback.
  2. **No marginal API key.** The user already has the `claude` CLI
     authenticated via OAuth (KDR-003); using `planner-synth` adds zero
     net config burden. `gemini_flash` would require `GOOGLE_API_KEY`
     to be set; on a fresh laptop that is a second yak.
  3. **Cost / quality envelope is acceptable.** A fallback round-trip
     happens at most once per run (sticky-OR `_ollama_fallback_fired`,
     architecture.md §8.4). Opus-grade output for one round-trip is
     within the run's budget for any realistic invocation; the fallback
     branch is not the hot path.
- **Alternatives considered** — `gemini_flash` (rejected: requires
  marginal `GOOGLE_API_KEY` config, and a Gemini fallback shares vendor
  with the operator's other Gemini-backed tier calls — correlated
  failure surface in the same super-step); abort-only (rejected: too
  brittle for a daemon-down case); periodic health-check (rejected at
  M8 T01 — KDR-006 per-call classification is the primary signal).
- **Consequences** — locked at this milestone; future change requires a new
  ADR. M10 T05 (§25 in `nice_to_have.md`) records the second-level
  fallback-chain extension trigger if a real outage exposes the single-level
  limitation.
- **Related** — KDR-003 (no Anthropic API; Claude Code is OAuth-only),
  architecture.md §8.4, M8 T04 spec, M8 T05 audit LOW ISS-02.

### [ai_workflows/workflows/planner.py](../../../ai_workflows/workflows/planner.py)

Edit the `PLANNER_OLLAMA_FALLBACK` docstring (currently at
[planner.py:118-127](../../../ai_workflows/workflows/planner.py#L118-L127))
so it cites ADR-0003 and names the trade-off in one sentence. Suggested
wording:

> The fallback choice is locked at [ADR-0003](../../../design_docs/adr/0003_ollama_fallback_tier_choice.md):
> `planner-synth` is preferred over `gemini_flash` because it decouples the
> fallback path from the operator's Gemini network egress (Ollama outages
> are local-machine failures; a non-Ollama tier sharing network paths with
> the rest of the run is the wrong fallback).

### [ai_workflows/workflows/slice_refactor.py](../../../ai_workflows/workflows/slice_refactor.py)

Same edit on `SLICE_REFACTOR_OLLAMA_FALLBACK` (currently around
[slice_refactor.py:204](../../../ai_workflows/workflows/slice_refactor.py#L204)).
Cite ADR-0003. One-sentence trade-off line.

### Tests

No new tests. The two docstrings are import-checked by the existing
fallback-path suites
([`tests/workflows/test_planner_ollama_fallback.py`](../../../tests/workflows/test_planner_ollama_fallback.py)
and
[`tests/workflows/test_slice_refactor_ollama_fallback.py`](../../../tests/workflows/test_slice_refactor_ollama_fallback.py))
simply by being re-imported on every test run; an ADR is a markdown
artefact with no test surface.

The Auditor's smoke verification is a literal grep — Python does not
store assignment-statement docstrings on instances (PEP 257 variable
docstrings are read by Sphinx-style doc tools, not by Python itself), so
introspection-based checks would be unreliable:

```bash
grep -n "ADR-0003" \
  ai_workflows/workflows/planner.py \
  ai_workflows/workflows/slice_refactor.py \
  design_docs/adr/0003_ollama_fallback_tier_choice.md
```

Expected: at least one hit in each of the two `.py` files (the
docstring-style comment block immediately following the
`PLANNER_OLLAMA_FALLBACK = ...` / `SLICE_REFACTOR_OLLAMA_FALLBACK = ...`
assignment) plus the ADR file's own self-reference. Zero hits in either
`.py` file fails the AC.

## Acceptance Criteria

- [ ] [`design_docs/adr/0003_ollama_fallback_tier_choice.md`](../../adr/0003_ollama_fallback_tier_choice.md)
      exists with all six ADR sections (Status, Context, Decision, Rationale,
      Alternatives considered, Consequences, Related).
- [ ] `PLANNER_OLLAMA_FALLBACK` docstring cites `ADR-0003` and names the
      "decouple from Gemini network egress" trade-off in one sentence.
- [ ] `SLICE_REFACTOR_OLLAMA_FALLBACK` docstring cites `ADR-0003` and names
      the same trade-off.
- [ ] No code in `_dispatch.py`, `planner.py`, `slice_refactor.py`,
      `tiered_node.py`, or `ollama_fallback_gate.py` changes — diff is
      confined to the new ADR file + the two docstrings.
- [ ] `uv run pytest` green.
- [ ] `uv run lint-imports` reports **4 contracts kept** (ADR is design_docs
      only; no new layer edge).
- [ ] `uv run ruff check` clean.
- [ ] `CHANGELOG.md` `[Unreleased]` gets a
      `### Changed — M10 Task 01: ADR-0003 + OllamaFallback docstring lock for fallback_tier (<YYYY-MM-DD>)`
      entry citing the new ADR + the two docstrings. (`### Changed`
      because the ADR formalises an existing decision rather than
      introducing a new behavioural surface; the project's CHANGELOG
      vocabulary is `Added | Changed | Deprecated | Removed | Fixed |
      Security` per Keep-a-Changelog — `### Docs` is off-vocabulary.)

## Dependencies

- M8 closed (the decision under lock has shipped).

## Out of scope (explicit)

- **No `fallback_tier` swap.** `planner-synth` stays — this task locks the
  choice, it does not revisit it. A swap to `gemini_flash` (or any third
  option) requires a new ADR, not a docstring edit.
- **No second-level fallback chain (Ollama → Claude Code → Gemini).** Deferred
  to T05 as `nice_to_have.md` §25. M10 documents the single-level model;
  it does not extend it.
- **No new KDR.** ADR-0003 is a workflow-config decision, not an architectural
  rule. The seven KDRs (002, 003, 004, 006, 008, 009, 013) are unchanged.

## Carry-over from task analysis

- [ ] **TA-LOW-02 — Markdown-link syntax in suggested docstring wording**
      (severity: LOW, source: task_analysis.md round 4)
      The suggested docstring wording uses `[ADR-0003](../../../design_docs/adr/0003_ollama_fallback_tier_choice.md)`
      (markdown link). Markdown `[text](url)` is valid in Sphinx-style RST
      but produces ugly raw text inside a Python docstring rendered by
      `help()` / `pydoc`. Existing project docstrings (e.g. `slice_refactor.py:208–222`)
      use plain `M8 T04`, `KDR-006`, `:func:` references — no markdown
      brackets.
      **Recommendation:** Switch to plain `ADR-0003` (the Auditor's smoke
      grep already expects the literal `ADR-0003` string).
