# Milestone 9 — Post-close-out deep analysis

**Performed on:** 2026-04-21.
**Scope:** cross-milestone drift check, alignment with M1–M8, unresolved-issue propagation audit, [nice_to_have.md](../../nice_to_have.md) trigger sweep against the M9 delivered surface.
**Inputs:** all four task specs + their issue files, milestone [README](README.md), root [README.md](../../../README.md), [`.claude/skills/ai-workflows/SKILL.md`](../../../.claude/skills/ai-workflows/SKILL.md), [`skill_install.md`](skill_install.md), [architecture.md](../../architecture.md) (§§3 / 4.4 / 6 / 9), every KDR M9 cites (KDR-001, KDR-002, KDR-003, KDR-008), [`CHANGELOG.md`](../../../CHANGELOG.md) M9 section, [`tests/skill/`](../../../tests/skill/), [roadmap.md](../../roadmap.md).

This pass mirrors the [M8 post-close-out deep-analysis](../milestone_10_ollama_hardening/README.md) pattern — a synthesis step run *after* the per-task `/clean-implement` loop closes, whose job is to surface design-rationale gaps that the mechanical AC-grading audit would not catch. Outputs from this pass either fold into an already-created successor milestone's carry-over, spawn a new milestone or nice_to_have entry, or record a no-action finding with its own justification.

## TL;DR

M9 is **clean on drift and alignment**. One HIGH issue (ISS-02 — gate-pause plan projection) was surfaced by the close-out live smoke and **forward-deferred to [M11 T01](../../milestone_11_gate_review/task_01_gate_pause_projection.md)** per user decision; one architectural thread (auditor cascade) was captured in [ADR-0004](../../adr/0004_tiered_audit_cascade.md) and scoped into [M12](../../milestone_12_audit_cascade/README.md). Two [nice_to_have.md](../../nice_to_have.md) entries (§11 prune CostTracker rollups; §16 env-var centralisation) get **minor wording updates** as a result of M9 + M12 landing — no promotion, no new milestone, no new task. Everything else was untriggered.

## 1. Drift check

Cross-reference against [architecture.md](../../architecture.md) (§3 layer contract, §4.4 MCP surface, §6 dependencies, §9 KDRs) and every KDR M9 cites.

| Concern | Finding |
| --- | --- |
| New dependency | None. `pyproject.toml` diff against baseline `0e6db6e` is empty. |
| New `ai_workflows.*` module | None. `git diff --stat 0e6db6e -- ai_workflows/ migrations/ pyproject.toml` returns empty output across all four M9 tasks. KDR-002 honoured across the milestone. |
| New layer / contract | None. `uv run lint-imports` still reports **4 contracts kept**. No new layer contract was added at M9 (packaging-only milestone does not touch `ai_workflows.*`). |
| LLM call added | None. |
| Checkpoint / resume logic | None. M9 docs describe what the existing M4 MCP surface exposes; no state-layer change. |
| Retry logic | None. |
| Observability backend | None. |
| KDR-003 (no Anthropic API) | Guardrail extended into the new packaging surface: `test_skill_md_forbids_anthropic_api` + `test_skill_install_doc_forbids_anthropic_api` pin absence of `ANTHROPIC_API_KEY` / `anthropic.com/api` in the skill body and `skill_install.md`. Neither surface names the SDK; both steer users to `GEMINI_API_KEY` + the `claude` CLI on PATH. |
| KDR-002 (packaging-only skill) | Honoured. Skill is text-only, every action resolves to an MCP tool call or an `aiw` shell-out, no orchestration logic in the skill surface. |
| KDR-008 (MCP schemas are the public contract) | SKILL.md and `skill_install.md §4` mirror the `RunWorkflowOutput` / `ResumeRunOutput` schemas verbatim — `status` / `awaiting` / `plan` / `total_cost_usd` / `error` only. `test_skill_md_tool_names_match_mcp_server` + the workflow-name test pin the set against live module introspection, so schema drift would fail the gate. |
| KDR-001 (human-in-the-loop gate) | Skill documents the gate-pause flow. The live smoke exposed a structural gap between the skill's *informed-review* expectation and the MCP surface's actual `plan: null` projection — logged as ISS-02 and forward-deferred to M11 T01 (see §4 below). The gap is not M9 drift; it is a pre-existing M4 surface defect that M9 made visible by being the first milestone that exercised the human-facing flow end-to-end. |

**No drift. No HIGH audit finding attributable to M9's own scope.**

## 2. Implementation alignment with M1–M8

| Milestone | M9's relationship | Verdict |
| --- | --- | --- |
| M1 (primitives baseline) | M9 reads `workflows.list_workflows()`, `SQLiteStorage` behaviour, and the `GEMINI_API_KEY` provider-tier config implicitly through `skill_install.md §1` prereqs. Zero code change. | Aligned. |
| M2 (tier routing + `ClaudeCodeSubprocess`) | M9 does not reference tier routing at the skill surface — correct, tiers are implementation detail below the MCP boundary. `skill_install.md §1` names the `claude` CLI on PATH (the subprocess driver's hard dependency), matching M2's OAuth-only posture. | Aligned. |
| M3 (planner workflow) | M9 tests read `workflows.list_workflows()` live to verify every registered workflow name appears in SKILL.md. `planner` is the workflow used in `skill_install.md §4` smoke. | Aligned. |
| M4 (MCP surface) | **M9 sits directly on top of M4.** SKILL.md documents the four `@mcp.tool()`s M4 shipped. `test_skill_md_tool_names_match_mcp_server` parses the server module to enforce verbatim match; no tool-name drift possible. `skill_install.md §2` links to M4's [`mcp_setup.md`](../milestone_4_mcp/mcp_setup.md) rather than duplicating it. The M4-era `plan: null` at gate-pause projection is the exact shape M9's skill surfaces — which is *faithful*, not drift, and the faithful surfacing is what exposed ISS-02. | Aligned (with ISS-02 noted downstream). |
| M5 (cost + storage polish) | M9 references `total_cost_usd` in the documented MCP response shape — the scalar M3 T06 + M5 left in place. No call sites into `CostTracker.by_tier` / `by_model` introduced. | Aligned. |
| M6 (slice_refactor workflow) | `slice_refactor` appears in the live-read set of workflow names that SKILL.md must enumerate. No surface-level change. | Aligned. |
| M7 (evals) | M9 does not touch the eval surface. `AIW_EVAL_LIVE=1` remains gate-only; M9 adds no env-var footprint. | Aligned. |
| M8 (Ollama circuit breaker + fallback gate) | `skill_install.md §5` and SKILL.md's *Gate pauses* section describe the fallback-gate flow using the `status="pending"` + `awaiting="gate"` MCP signal — the T01 Cycle 2 correction pinned this to the actual MCP schema rather than an invented `gate_reason` field. Names the `cooldown_s` wait before RETRY-equivalent resume. Matches M8's semantics verbatim. | Aligned. |

**No alignment breaks.** M9 is a pure additive packaging surface.

## 3. Spec drift surfaced during M9 (recap)

The per-task audit loop recorded two deviations — neither is architectural drift:

1. **T01 Cycle 2 correction** — the *Gate pauses* paragraph was re-written to name `status="pending"` + `awaiting="gate"` instead of a non-existent `gate_reason` field, and to relocate the failing-tier detail to the LangGraph checkpointer state rather than `list_runs` (which returns `RunSummary` rows only). The correction tightened the surface against the real schema.
2. **T03 §5 wording deviation** — the T03 spec body called for `gate_reason` in the fallback-gate section. Same root cause as T01 Cycle 2; the landed doc uses the real MCP projection. Logged LOW in [issues/task_03_issue.md](issues/task_03_issue.md) and pinned in the M9 README *Spec drift observed during M9* subsection.

Both deviations trace back to spec text that **pre-supposed a richer MCP projection than M4 actually shipped**. That's the same structural gap ISS-02 names — the M4 surface gives the skill less to work with than the skill's spec text expected. M11 T01 closes it.

## 4. Unresolved issue disposition

Every M9 issue file carries `✅ PASS`. Issue log consolidated:

| ID | Severity | Final status | Owner |
| --- | --- | --- | --- |
| M9-T01-ISS-01 | 🟢 LOW | ✅ RESOLVED Cycle 2 (2026-04-21) | In-task. Gate-pauses paragraph reworded. |
| M9-T02-* | — | 📝 Deferred task (no trigger fired) | Findings pinned in [task_02_plugin_manifest.md](task_02_plugin_manifest.md) for a future Builder; re-open when marketplace / second-host / internal-distribution trigger fires. |
| M9-T03-* | 🟢 LOW | ✅ RESOLVED Cycle 1 (2026-04-21) | In-task deviation; surfaced in M9 README + [issues/task_03_issue.md](issues/task_03_issue.md). |
| M9-T04-ISS-01 | 🟡 MEDIUM | ✅ RESOLVED (2026-04-21) | Live smoke walked; CHANGELOG *Close-out-time live verification* block added. |
| M9-T04-ISS-02 | 🔴 HIGH | 🔜 DEFERRED → [M11 T01](../../milestone_11_gate_review/task_01_gate_pause_projection.md) | Carry-over back-link live on the M11 README; flips to RESOLVED when M11 T01 lands. |

**No open HIGH/MEDIUM. No task-file-level deferrals below M11/M12.** No finding landed on [nice_to_have.md](../../nice_to_have.md) from the audit loop itself.

## 5. Adjacent architectural threads that landed during M9 close-out

Two architectural artefacts were authored in the same close-out window even though they are technically post-M9:

- **[ADR-0004 — Tiered audit cascade](../../adr/0004_tiered_audit_cascade.md)** + **[KDR-011](../../architecture.md)** + architecture.md §4.2 / §4.4 updates — captured the broader "Opus audits Sonnet; Sonnet audits Haiku/Gemini/Qwen" design thread that surfaced during the same conversation as ISS-02. The thread is **not** a fix for M9's live-smoke defect; it is a separate design decision about quality gating under the post-pivot provider set. [M12](../../milestone_12_audit_cascade/README.md) is scoped to ship the cascade.
- **[M11](../../milestone_11_gate_review/README.md)** — the dedicated milestone that owns ISS-02's resolution. Split from M12 deliberately: gate-surface projection is a pure MCP / skill-text diff, while the cascade is a graph-layer + MCP-tool + workflow-config diff. Keeping them separate lets M11 land without blocking on M12 design, and lets M12 consume the M11 projection as a dependency.

Both are already referenced from M9 T04's issue file propagation footer.

## 6. [nice_to_have.md](../../nice_to_have.md) trigger sweep

Every one of the 16 nice_to_have entries was re-read against the M9 delivered surface to check whether M9's implementation fired a trigger that the audit loop would not surface (since those items have no milestone owner).

| § | Entry | Trigger fired by M9? | Action |
| --- | --- | --- | --- |
| 1 | Langfuse | No — no observability surface added. | None. |
| 2 | Instructor / pydantic-ai | No — no LLM-call path added. | None. |
| 3 | LangSmith | No. | None. |
| 4 | Typer (pydantic-native CLI) | No — M9 no CLI change. | None. |
| 5 | Docker Compose | No. | None. |
| 6 | mkdocs-material doc site | No — `skill_install.md` lives in-repo under `design_docs/`; no external site. | None. |
| 7 | DeepAgents templates | No. | None. |
| 9 | `aiw cost-report` per-run breakdown | No — no billing surface change. | None. |
| 10 | OpenTelemetry exporter | No. | None. |
| 11 | Prune `CostTracker.by_tier` / `by_model` / `sub_models` | **Indirect effect** — [M12 T04](../../milestone_12_audit_cascade/README.md) plans a new `by_role(run_id)` aggregator over `TokenUsage` that reuses the same rollup pattern. §11's *Why not now* line (which blocks on §9 firing) gains a second reason: the cascade introduces a sibling consumer of the rollup idiom. | **Minor wording update** to §11 — add a sentence noting the M12 role-tagged aggregator as a second "why not now" reason. No promotion. No structural change. |
| 12 | Promote `list_runs` / `cancel_run` to `_dispatch` | No — M9 adds no surface. | None. |
| 13 | pydantic msgpack registry | No. | None. |
| 14 | Nightly live-mode eval replay | No — M9 adds no eval work. | None. |
| 15 | Eval tools on MCP surface | No. | None. |
| 16 | Centralise env-var documentation | **Weak trigger** — §16 itself lists *"a packaging / distribution step (container image, standalone binary, Claude Code skill packaging per roadmap.md M9)"* as one of three candidate triggers. `skill_install.md §1` enumerates `GEMINI_API_KEY` + the `claude` CLI on PATH — which is exactly the kind of external-facing env-var enumeration §16 anticipated. But the counter-argument also holds: the skill doc is consumed *in-repo* (no external distribution artefact, no `docker run -e AIW_FOO=...` line), the single-maintainer precondition is still in force, and the two real prereqs §1 names are already discoverable at their module sites. | **Minor wording update** to §16 — acknowledge that M9 fired the skill-packaging sub-trigger weakly, record that the threshold was judged not met (single-maintainer + doc-in-repo), and name the follow-on trigger that would flip the call (a second human contributor or an external distribution artefact). No promotion. No new task. |

**No entry was triggered strongly enough to promote.** Two entries get brief clarifying updates that preserve their "deferred" status while recording the M9 + M12 signal for the next reviewer.

## 7. Recommendations

Concrete edits. All are doc-only updates to [nice_to_have.md](../../nice_to_have.md). No milestone or task is created; the two existing successor milestones (M11, M12) already cover the structural findings.

1. **[nice_to_have.md §11 — prune CostTracker rollups](../../nice_to_have.md)** — extend the *Why not now* / *Related history* text to name the M12 role-tagged aggregator as an additional "leave it in place" reason. Keep status: deferred.
2. **[nice_to_have.md §16 — env-var doc table](../../nice_to_have.md)** — extend the *Related history* line to record the M9 skill-packaging sub-trigger firing weakly, the threshold-not-met judgement, and the follow-on trigger that would flip the call. Keep status: deferred.
3. **No action** on all other nice_to_have entries.
4. **No new milestone.** M11 owns ISS-02; M12 owns the cascade thread. No other structural gap is surfaced by this analysis.
5. **No new nice_to_have entry.** The two structural findings above have milestone owners; nothing else is milestone-sized and trigger-less.

## 8. What this analysis does *not* propose

- No change to KDR-002 (packaging-only skill) — M9 honoured it, the next gate-review projection (M11) is deliberately a separate milestone because it is not packaging-only.
- No change to KDR-008 (MCP schema is the public contract) — M11 will grow the output models additively (new `gate_context` field, `plan` population rule widened), which is a non-breaking change per KDR-008's own "additive is non-breaking" clause.
- No `_v2` of the M9 T04 issue file. All updates stayed in-place; ISS-02 flip to RESOLVED happens when M11 T01 lands.
- No retrospective re-audit of M1–M8. Each closed clean and still does; the drift check above is forward-facing alignment only.

## 9. Propagation footer

- **[nice_to_have.md §11 + §16](../../nice_to_have.md)** — doc updates land as part of this analysis's commit (minor, same commit).
- **[M9 T04 issue file](issues/task_04_issue.md)** — already updated (ISS-02 deferred, ISS-01 resolved, status ✅ PASS). Flips from DEFERRED → RESOLVED on M11 T01 landing.
- **[M11 README](../milestone_11_gate_review/README.md)** — carry-over entry from M9 T04 ISS-02 live; task-order already lists T01 (projection) + T02 (close-out). No additional carry-over from this analysis.
- **[M12 README](../milestone_12_audit_cascade/README.md)** — no additional carry-over from this analysis. M12's dependency on M11 already captured.
- **[ADR-0004](../../adr/0004_tiered_audit_cascade.md)** — captures the cascade design rationale that surfaced during the same close-out window. Referenced from M9 T04 issue file, M11 README, M12 README, architecture.md §9 (KDR-011).

End of analysis.
