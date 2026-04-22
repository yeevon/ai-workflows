# Task 03 — Distribution / Install Docs — Audit Issues

**Source task:** [../task_03_distribution_docs.md](../task_03_distribution_docs.md)
**Audited on:** 2026-04-21
**Audit scope:** new `skill_install.md` + root README link + four doc-link tests + CHANGELOG entry; verified link resolution, KDR-003 guardrail in doc body, alignment with the M9 T01 Cycle 2 correction (no `gate_reason` claim), T02-deferred Option C treatment.
**Status:** ✅ PASS — Cycle 1/10. One deviation from spec documented + justified (T03 §5 *Fallback gate fires mid-run* reworded to drop the spec's inaccurate `gate_reason` reference, matching T01 Cycle 2's correction). No OPEN issues.

## Design-drift check

Cross-check against [architecture.md](../../../architecture.md) + cited KDRs.

| Concern | Finding |
| --- | --- |
| New dependency | None. `pyproject.toml` diff empty. |
| New `ai_workflows.*` module | None. Docs + tests only. |
| New layer / contract | None. `uv run lint-imports` still 4 kept. |
| LLM call added | None. |
| Checkpoint / resume logic | None. |
| Retry logic | None. |
| Observability backend | None. |
| Anthropic API surface | `skill_install.md` body does not contain `ANTHROPIC_API_KEY` or `anthropic.com/api`. KDR-003 guardrail honoured and test-enforced by `test_skill_install_doc_forbids_anthropic_api`. The §1 prereq was reworded mid-implement from "No `ANTHROPIC_API_KEY` required or consulted" to "No Anthropic API key required or consulted" precisely to satisfy the guardrail test. |
| KDR-002 (packaging-only) | Honoured. No `ai_workflows/` diff. |
| T01 Cycle 2 alignment | `skill_install.md` §5 matches the T01 correction: names `status="pending"` + `awaiting="gate"` as the operator signal, locates the reason in the LangGraph checkpointer (not `list_runs`), names the `cooldown_s` wait before RETRY. |
| T02 deferred treatment | `skill_install.md` §3 Option C marked "not applicable at this revision" with a back-link to `task_02_plugin_manifest.md`, matching the T02 deferred disposition. |

No drift. No HIGH findings.

## Acceptance criteria grading

| # | Criterion | Verdict |
| --- | --- | --- |
| 1 | `skill_install.md` exists with the five sections above | ✅ All five present: §1 *Prerequisites*, §2 *Install the MCP server*, §3 *Install the skill* (Options A / B / C), §4 *End-to-end smoke*, §5 *Troubleshooting*. `test_skill_install_doc_exists` pins presence. |
| 2 | Root `README.md` links to `skill_install.md` from a single contextually appropriate line | ✅ Single line appended to the existing §*MCP server* section. `test_root_readme_links_skill_install` pins substring presence. No install-step duplication. |
| 3 | Every relative link in `skill_install.md` resolves on disk | ✅ `test_skill_install_doc_links_resolve` walks every `[text](target)` link (skipping `#`-anchors and external schemes), trims the anchor fragment, resolves against `DOC_PATH.parent`, fails on any miss. Green. |
| 4 | `skill_install.md` does not contain `ANTHROPIC_API_KEY` or `anthropic.com/api` — KDR-003 guardrail | ✅ `test_skill_install_doc_forbids_anthropic_api` pins both substrings as absent. |
| 5 | No new runtime or dev dependency. No new import-linter contract. Four-contract count preserved | ✅ `pyproject.toml` diff empty; `uv run lint-imports` → 4 kept, 0 broken. |
| 6 | `uv run pytest` + `uv run lint-imports` + `uv run ruff check` all clean | ✅ 596 passed / 5 skipped (9 new in `tests/skill/` post-T01+T03); lint-imports 4 kept; ruff clean. |

## 🔴 HIGH

*None.*

## 🟡 MEDIUM

*None.*

## 🟢 LOW

*None.*

## Additions beyond spec — audited and justified

- **`test_skill_install_doc_forbids_anthropic_api` added** (fourth test, spec listed three). Spec AC-4 names the guardrail as an AC but the spec's test list only covered the other three ACs. The fourth test operationalises AC-4 — without it, the KDR-003 guardrail is a doc claim with no mechanical check. Neutral-to-positive on audit grade; strengthens the spec, doesn't widen scope.
- **§5 *Fallback gate fires mid-run* rewording (spec drift, documented as *Deviation from spec* in CHANGELOG).** T03 spec says "the skill surfaces `gate_reason` to the user". The MCP surface does not project a `gate_reason` field — [`ai_workflows/mcp/schemas.py:80-97`](../../../../ai_workflows/mcp/schemas.py#L80-L97) (`RunWorkflowOutput`) and [lines 107-122](../../../../ai_workflows/mcp/schemas.py#L107-L122) (`ResumeRunOutput`) only expose `status` / `awaiting` / `plan` / `total_cost_usd` / `error`. Writing the spec's literal wording would have re-introduced the same doc-accuracy error the T01 Cycle 2 audit caught + corrected. Rewording §5 to match T01's corrected §*Gate pauses* is the right call; the CHANGELOG entry captures the deviation explicitly so it is not silent spec drift.

## Gate summary

| Gate | Result |
| --- | --- |
| `uv run pytest` | ✅ 596 passed, 5 skipped |
| `uv run pytest tests/skill/` | ✅ 9 passed (5 shape + 4 doc-link) |
| `uv run lint-imports` | ✅ 4 contracts kept |
| `uv run ruff check` | ✅ clean |
| `pyproject.toml` diff | ✅ empty |
| `ai_workflows/*` diff | ✅ empty |
| KDR-003 guardrail (doc body) | ✅ absent substrings (test-enforced) |

## Issue log

| ID | Severity | Status | Owner |
| --- | --- | --- | --- |
| *(none)* | — | — | — |

## Deferred to nice_to_have

*None.*

## Propagation status

*No forward deferrals.* The spec deviation (§5 reworded) is resolved in-task; the CHANGELOG entry + this audit note the alignment with T01 Cycle 2. T04 close-out will fold the disposition into the milestone README *Outcome* section.
