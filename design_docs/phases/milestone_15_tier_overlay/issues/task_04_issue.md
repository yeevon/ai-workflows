# Task 04 — ADR-0006 + `docs/tiers.example.yaml` relocation + `docs/writing-a-workflow.md` tier-config section — Audit Issues

**Source task:** [task_04_adr_0006_and_tiers_doc_relocation.md](../task_04_adr_0006_and_tiers_doc_relocation.md)
**Audited on:** 2026-04-30 (cycle 1)
**Audit scope:** Doc-only task — ADR-0006, `tiers.yaml` → `docs/tiers.example.yaml` relocation, `### Fallback chains` subsection, test-fixture path updates, four LOW carry-overs.
**Status:** ✅ PASS

---

## Cycle 1 — Builder notes (preserved)

**Deliverables landed:**

- `design_docs/adr/0006_tier_fallback_cascade_semantics.md` — new ADR, seven decision points
  and four rejected alternatives as specified.
- `docs/tiers.example.yaml` — relocated from `tiers.yaml`; stale "Forward-looking" sentence
  removed; header updated per spec.
- `tiers.yaml` — deleted from repo root.
- `docs/writing-a-workflow.md` — `### Fallback chains` subsection inserted after
  `### Tier registry (\`tiers=\`)` and before `### Minimum viable spec`.
- `tests/primitives/test_tiers_loader.py` — `DOCS_DIR` constant + `_load_example_tiers()`
  helper added; four committed-file tests use the helper instead of `TierRegistry.load(REPO_ROOT)`.
- `tests/test_scaffolding.py` — parametrize entry updated to `"docs/tiers.example.yaml"`.
- `tests/test_wheel_contents.py` — stale `tiers.yaml` strings updated (TA-LOW-04).
- `CHANGELOG.md` — entry added under `[Unreleased]`.
- Status surfaces flipped: spec `**Status:**`, milestone README task-04 row.

**Carry-over items resolved (per Builder):** TA-LOW-01, TA-LOW-02, TA-LOW-04 (all visibly diffed). TA-LOW-03 was a spec-only fix (no Builder action).

**Deviations from spec:** None.

---

## Design-drift check

No drift detected. ADR-0006 cites KDR-004 / KDR-006 / KDR-014 correctly and reinforces the framework-owns-policy invariant. No new dependencies introduced (verified `pyproject.toml` not in change set). No layer additions, no new LLM call surfaces, no checkpoint/retry rewiring. KDR-014 is *strengthened* by the explicit YAML-overlay rejection in §Decision point 7 + §Alternatives rejected.

---

## AC grading

| AC | Status | Notes |
|---|---|---|
| AC-1 | ✅ met | ADR-0006 present at `design_docs/adr/0006_tier_fallback_cascade_semantics.md`. All seven decision points covered (schema, trigger, cascade walk, cost, validator, error shape, YAML rejection). All four rejected alternatives covered (immediate-fail-over, score-based routing, provider-health probes, YAML overlay). |
| AC-2 | ✅ met | `docs/tiers.example.yaml` exists with `local_coder` / `opus` / `sonnet` / `haiku` (verified via `python -c "yaml.safe_load(...)"` smoke). Stale "Forward-looking" sentence removed; "M15 shipped" replacement present at lines 11-13. |
| AC-3 | ✅ met | `ls tiers.yaml` exits non-zero. `git status` confirms `D tiers.yaml`. |
| AC-4 | ✅ met | Five committed-file references updated cleanly: 4 tests in `test_tiers_loader.py` (lines 79, 108, 123, 134) all call `_load_example_tiers()`; `DOCS_DIR` constant at line 51, helper at lines 54-65; 1 entry in `test_scaffolding.py:117` (`"docs/tiers.example.yaml"`). `REPO_ROOT` preserved for `pricing.yaml` + `_write` helpers. Targeted re-run (3 test files) → 57 passed, 3 skipped. |
| AC-5 | ✅ met | `### Fallback chains` subsection at line 68. Contains: `TierConfig.fallback` Python example with `ClaudeCodeRoute` → `LiteLLMRoute` cascade (lines 77-92), four-bullet semantics block (flat-only, retry-budget trigger, truthful cost, validator interaction), YAML schema-reference cross-link, ADR-0006 cross-link with `(builder-only, on design branch)` suffix at line 106. |
| AC-6 | ✅ met | `CHANGELOG.md` entry under `[Unreleased]` at line 12 with full Deliverable A/B/C breakdown + ACs satisfied. |
| AC-7 | ✅ met | Re-ran `uv run pytest`: **1532 passed, 12 skipped**. |
| AC-8 | ✅ met | Re-ran `uv run lint-imports`: **5 contracts kept, 0 broken**. |
| AC-9 | ✅ met | Re-ran `uv run ruff check`: **All checks passed!** |

### Carry-over from task analysis (graded individually)

| Carry-over | Status | Notes |
|---|---|---|
| TA-LOW-01 (Grounding line) | ✅ met | Spec line 4 cites `[docs/tiers.example.yaml](../../../docs/tiers.example.yaml)`. Diff hunk present. |
| TA-LOW-02 (ADR-0006 link suffix) | ✅ met | `docs/writing-a-workflow.md:106` carries `(builder-only, on design branch)` suffix matching the established pattern. Diff hunk present. |
| TA-LOW-03 (Dependencies §) | ✅ met | Resolved inline by task analysis pre-Builder; spec line 179 reads "No production-code dependency…". No Builder action required. |
| TA-LOW-04 (`test_wheel_contents.py` strings) | ✅ met | Stale `tiers.yaml` strings updated to `docs/tiers.example.yaml` at lines 150, 170. Diff hunk present. |

---

## 🔴 HIGH — none

## 🟡 MEDIUM — none

## 🟢 LOW

### LOW-1 — carry-over checkboxes left unticked despite resolved diffs

The four `[ ]` carry-over items in the spec's `## Carry-over from task analysis` section (lines 204, 208, 212, 215) remain unticked, even though TA-LOW-01 / TA-LOW-02 / TA-LOW-04 are visibly addressed in the cycle's diff and TA-LOW-03 was resolved inline pre-Builder. Per CLAUDE.md "Carry-over section at the bottom of a spec = extra ACs. Tick each as it lands."

**Action / Recommendation:** Builder hygiene reminder for next cycle. Non-blocking — diff-vs-checkbox cross-reference confirms each item is materially complete; the unticked boxes are bookkeeping cruft only. Consider ticking all four to `[x]` on the next admin pass through the spec (orchestrator may do this, or roll into M15 T05 close-out).

### LOW-2 — `architecture.md §3.1` line 67 still names `tiers.yaml` (not in T04 scope)

`design_docs/architecture.md:67` references `tiers.yaml` in the `TierConfig` row description. T04 is doc-only and the architecture doc was not in scope. Production code in `ai_workflows/primitives/tiers.py` still loads `tiers.yaml` from a passed `root` arg (only used by test helpers; not invoked at dispatch — verified at M1 T06 audit).

**Action / Recommendation:** Forward-defer to M15 T05 (milestone close-out) as a `## Carry-over from prior audits` entry: refresh `architecture.md §3.1` description to read `pricing.yaml` / `docs/tiers.example.yaml` (or drop the YAML reference, since the authoritative path is the per-workflow Python registry per KDR-014). Optionally also touch up the `ai_workflows/primitives/tiers.py` module + `TierRegistry.load()` docstrings to clarify the helper's `root/tiers.yaml` lookup is dev-fixture only — non-blocking, cosmetic.

---

## Additions beyond spec — audited and justified

None. All changes trace 1:1 to the §Deliverables list; the `test_wheel_contents.py` touch-up was authorised by carry-over TA-LOW-04.

---

## Gate summary

| Gate | Command | Pass/Fail |
|---|---|---|
| pytest | `uv run pytest` | ✅ 1532 passed, 12 skipped |
| lint-imports | `uv run lint-imports` | ✅ 5 contracts kept, 0 broken |
| ruff | `uv run ruff check` | ✅ all checks passed |
| ADR-0006 present | `ls design_docs/adr/0006_tier_fallback_cascade_semantics.md` | ✅ exists |
| `tiers.yaml` removed | `ls tiers.yaml` | ✅ exits non-zero (file absent) |
| `docs/tiers.example.yaml` parses | `python -c "yaml.safe_load(...)"` | ✅ keys = `[local_coder, opus, sonnet, haiku]` |
| Fallback chains section | `grep -n "Fallback chains" docs/writing-a-workflow.md` | ✅ line 68 |

---

## Issue log — cross-task follow-up

| ID | Severity | Owner | Status |
|---|---|---|---|
| M15-T04-LOW-01 | LOW | Builder hygiene (next cycle / orchestrator) | OPEN — diff-vs-checkbox cosmetic |
| M15-T04-LOW-02 | LOW | M15 T05 (milestone close-out) | DEFERRED — out-of-scope architecture.md/tiers.py docstring refresh |

## Deferred to nice_to_have

None.

## Propagation status

- **M15-T04-LOW-02** → forward-deferred to M15 T05 (milestone close-out). Will be appended as `## Carry-over from prior audits` to the T05 spec when that spec lands (T05 spec is incremental per the milestone README convention; not yet written). The orchestrator should attach this finding when authoring T05.
- **M15-T04-LOW-01** → no propagation; cosmetic local hygiene only.

---

## Terminal gate — cycle 1 (2026-04-30)

**Verdicts:** sr-dev=SHIP · sr-sdet=FIX-THEN-SHIP · security=SHIP

### Locked terminal decisions (loop-controller + reviewer concur, 2026-04-30)

**FIX-1 (sr-sdet Lens 2 — env-expansion bypass):**
`_load_example_tiers()` bypassed `_expand_env_recursive()`, leaving `${OLLAMA_BASE_URL:-…}` unexpanded in `local_coder.route.api_base`. Applied option (b): import `_expand_env_recursive` from `ai_workflows.primitives.tiers`, call `expanded = _expand_env_recursive(raw)` before the `model_validate` loop, and assert `"${" not in api_base` in `test_litellm_tier_carries_ollama_model_string`. Single clear recommendation; no KDR conflict; no production-code change. Decision: apply.

**FIX-2 (sr-sdet Lens 6 — docstring caveat):**
Moot once FIX-1 is applied (env vars are now expanded; adding a non-expansion caveat would be incorrect). Updated docstring instead to document the `_expand_env_recursive` step. Decision: close as resolved-by-FIX-1.

**Advisory items (sr-dev Advisory-1/2/3, sr-sdet Advisory-1/2, security ADV-01):** non-blocking; no action required for terminal clean.

### Gate results after FIX-1 applied

| Gate | Result |
|---|---|
| `uv run pytest` | ✅ 1532 passed, 12 skipped |
| `uv run lint-imports` | ✅ 5 contracts kept, 0 broken |
| `uv run ruff check` | ✅ all checks passed |

**Status: ✅ TERMINAL CLEAN (cycle 1 — terminal-gate bypass applied; sr-sdet FIX-THEN-SHIP resolved; sr-dev SHIP; security SHIP; all gates green)**
