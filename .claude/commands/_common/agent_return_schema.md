# Agent Return-Value Schema (3-line verdict / file / section)

**Task:** M20 Task 01 — Sub-agent return-value schema
**Canonical reference for:** all 5 slash commands that spawn agents; all 9 agent prompts

This file is the single source of truth for the 3-line return-value schema used across
the ai-workflows autonomy fleet. Slash commands link here instead of duplicating the
per-agent verdict table — changes to verdict tokens require only this file to be updated.

---

## Schema format

Every agent returns exactly three lines, no more, no less:

```
verdict: <one of the agent's allowed tokens — see table below>
file: <repo-relative path to the durable artifact written, or "—" if none>
section: <"## Section header" just written, or "—" if a standalone file or no file>
```

- No prose summary, no preamble, no chat body before or after the three lines.
- A return that includes anything outside the three-line schema is **non-conformant**.
- The orchestrator halts the autonomy loop and surfaces the malformed return for user investigation. **No auto-retry on non-conformant return** — a schema violation signals a deeper problem with the agent prompt or reasoning.

---

## Orchestrator-side parser convention

After every `Task` spawn, the orchestrator:

1. Captures the agent's full text return into `runs/<task>/cycle_<N>/agent_<name>_raw_return.txt` (durable record for debugging).
2. Splits the return on `\n`; expects exactly 3 non-empty lines.
3. Each line matches `^(verdict|file|section): ?(.+)$`.
4. The `verdict` value must be one of the agent's allowed tokens (see table below).
5. On any failure: halt the loop, surface `BLOCKED: agent <name> returned non-conformant text — see runs/<task>/cycle_<N>/agent_<name>_raw_return.txt for full output`. Do not auto-retry.

---

## Per-agent verdict tokens and durable artifacts

| Agent | Verdict tokens | Durable artifact (`file:` field) | Section header (`section:` field) |
|---|---|---|---|
| `builder` | `BUILT` / `BLOCKED` / `STOP-AND-ASK` | `runs/<task>/cycle_<N>/builder_handoff.md` (per-cycle nested directory; T03 §directory layout is authoritative on artifact placement) | `—` |
| `auditor` | `PASS` / `OPEN` / `BLOCKED` | `design_docs/phases/<milestone>/issues/task_<NN>_issue.md` | `—` (auditor writes the entire issue file) |
| `security-reviewer` | `SHIP` / `FIX-THEN-SHIP` / `BLOCK` | `runs/<task>/cycle_<N>/security-review.md` | `## Security review (YYYY-MM-DD)` |
| `dependency-auditor` | `SHIP` / `FIX-THEN-SHIP` / `BLOCK` | `design_docs/phases/<milestone>/issues/task_<NN>_issue.md` (or CHANGELOG `### Security`) | `## Dependency audit (YYYY-MM-DD)` |
| `task-analyzer` | `CLEAN` / `LOW-ONLY` / `OPEN` | `design_docs/phases/<milestone>/task_analysis.md` | `—` |
| `architect` | `ALIGNED` / `MISALIGNED` / `OPEN` / `PROPOSE-NEW-KDR` | `design_docs/phases/<milestone>/issues/task_<NN>_issue.md` | `## Architect review (YYYY-MM-DD)` |
| `sr-dev` | `SHIP` / `FIX-THEN-SHIP` / `BLOCK` | `runs/<task>/cycle_<N>/sr-dev-review.md` | `## Sr. Dev review (YYYY-MM-DD)` |
| `sr-sdet` | `SHIP` / `FIX-THEN-SHIP` / `BLOCK` | `runs/<task>/cycle_<N>/sr-sdet-review.md` | `## Sr. SDET review (YYYY-MM-DD)` |
| `roadmap-selector` | `PROCEED` / `NEEDS-CLEAN-TASKS` / `HALT-AND-ASK` | `runs/queue-pick-<ts>.md` (or invoker-named recommendation file) | `—` |

(`section:` is `—` for agents that write a whole standalone file. The orchestrator reads the entire file for those.)

---

## Notes

- Subsequent M20 tasks populate additional files in this `_common/` directory:
  `spawn_prompt_template.md` (T02), `parallel_spawn_pattern.md` (T05),
  `dispatch_table.md` (T07), `gate_parse_patterns.md` (T08),
  `integrity_checks.md` (T09), `effort_table.md` (T21),
  `auditor_context_management.md` (T27).
- The parser helper is extracted into `ai_workflows/agents/return_schema.py` for
  testability. See `tests/agents/test_orchestrator_parser.py`.
