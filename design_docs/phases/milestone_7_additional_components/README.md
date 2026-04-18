# Milestone 7 — Additional Components (On Demand)

## Goal

Add components only when a new workflow demands them. Do not build speculatively. The rule: a component is extracted from a workflow when a **second** workflow reveals the same pattern.

## Components Waiting

Each component below has a trigger condition — the scenario that justifies building it.

---

### Router

**Trigger:** A workflow needs to route tasks to different tiers based on `change_type` or other classification, and a `Worker`-based approach is too blunt.

**Decision:** Fixed escalation order `local_coder → haiku → sonnet → opus`, configurable override per workflow. Router classifies each task and returns a tier name.

---

### Escalator

**Trigger:** A workflow is paying too much because Sonnet handles tasks that Haiku could do, and a Router alone isn't enough.

**Decision:** Cheap tier first → Validator → escalate on failure. Escalation cost tracked separately in run log.

---

### Synthesizer

**Trigger:** A workflow produces many Worker outputs that need consolidation into one result (e.g., per-file review comments → PR-level summary).

**Decision:** Hierarchical synthesis for large input sets — batch inputs, synthesize batches, synthesize summaries.

---

### MCP Server

**Trigger:** CLI commands (`aiw inspect`, `aiw cost`) are too slow or too manual for monitoring runs, and you want to query run data from Claude clients directly.

**Decision (from grilling):** Thin read-only MCP server on top of SQLite storage. Additive — zero changes to primitives. Post-Milestone 2 target. No schema changes required.

Build steps when triggered:
1. Define MCP server as a separate process: `aiw serve --mcp --port 3000`
2. Expose tools: `get_run`, `list_runs`, `get_cost_breakdown`, `get_task_states`, `get_gate_state`
3. No write tools in initial version

---

### Additional Planned Workflows (future)

These are validation targets from the design doc, not committed work:

- **code_review** — PR diff → per-file review comments → PR-level summary
- **doc_generation** — explore codebase → doc outline → fan-out section generation
- **migration_audit** — inventory → classify → synthesize report
- **incident_postmortem** — logs + chat ingestion → timeline → analysis → human gate

Each will be started the same way: write the `workflow.yaml` first, discover which components are missing, extract only what's needed.
