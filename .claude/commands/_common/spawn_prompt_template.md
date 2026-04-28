# Spawn-Prompt Template (Canonical Scaffold)

**Task:** M20 Task 02 — Sub-agent input prune
**Canonical reference for:** all 5 slash commands that spawn agents — determines what the
orchestrator passes to each `Task` call.

This file is the single source of truth for the minimal pre-load set, output budget
directives, and schema reminder for every agent spawn. Slash commands link here instead
of duplicating per-agent rules — changes to the pre-load policy require only this file.

---

## Guiding principle

> **The cost of an under-pre-fed sub-agent is one extra Read call.
> The cost of an over-pre-fed sub-agent is token waste + attention dilution.
> Asymmetry favours under-pre-feeding.**

Pass only what the agent will *certainly* use. Let the agent pull the rest on demand via
its own `Read` tool. Path references are always safe to pass; inlining full content of
large documents is wasteful and should be avoided.

---

## Per-agent minimal pre-load set

### Builder

| Always pass | Never inline |
|---|---|
| Task spec path | Sibling task issue files (content) |
| Parent milestone README path | `architecture.md` content |
| Project context brief | `CHANGELOG.md` content |
| Issue file path (may not exist yet) | Whole-milestone README content |

### Auditor

| Always pass | Never inline |
|---|---|
| Task spec path | `architecture.md` content (Auditor reads on-demand) |
| Issue file path | Sibling issue file content |
| Parent milestone README path | Whole-milestone README content |
| Project context brief | Full §9 KDR table content |
| Current `git diff` | |
| Cited KDR identifiers (parsed from spec) | |

**KDR pre-load rule for the Auditor:** parse the KDR citations from the task spec
(e.g. "KDR-003, KDR-013") and pass *only* the cited KDR identifiers as a compact list.
The Auditor reads the full §9 entries on-demand. When no KDRs are cited, pass the §9
grid header only as a compact pointer.

See `tests/orchestrator/test_kdr_section_extractor.py` for the parsing logic and
`tests/orchestrator/_helpers.py` for the `extract_cited_kdrs()` and
`build_kdr_compact_pointer()` helper implementations.

### Reviewer spawns (sr-dev, sr-sdet, security-reviewer, dependency-auditor)

| Always pass | Never inline |
|---|---|
| Task spec path | Full source file content |
| Issue file path | Full test file content |
| Project context brief | `architecture.md` content |
| Current `git diff` | |
| List of files touched (aggregated from Builder reports) | |

### task-analyzer

| Always pass | Never inline |
|---|---|
| Milestone directory path | Full task spec contents (analyzer reads via own Read) |
| Analysis-output file path | `architecture.md` content |
| Project context brief | Sibling milestone READMEs content |
| Round number | |
| List of task spec filenames | |

### roadmap-selector

| Always pass | Never inline |
|---|---|
| Recommendation file path | Full milestone README contents |
| Project context brief | Full task spec contents |
| Milestone scope (from `$ARGUMENTS`) | `architecture.md` content |

### architect

| Always pass | Never inline |
|---|---|
| Trigger type and finding ID | Full source files |
| Project context brief | Full architecture.md |

---

## Output budget directives

Include this block verbatim in every spawn prompt, substituting `<BUDGET>` per the table
below:

```
Output budget: <BUDGET> tokens. Durable findings live in the file you write;
the return is the 3-line schema only — see .claude/commands/_common/agent_return_schema.md
```

| Agent | Budget |
|---|---|
| `builder` | 4 K |
| `auditor` | 1–2 K |
| `security-reviewer` | 1–2 K |
| `dependency-auditor` | 1–2 K |
| `task-analyzer` | 1–2 K |
| `architect` | 1–2 K |
| `sr-dev` | 1–2 K |
| `sr-sdet` | 1–2 K |
| `roadmap-selector` | 1–2 K |

---

## Schema reminder (include in every spawn prompt)

```
Return per .claude/commands/_common/agent_return_schema.md — exactly 3 lines:
verdict: <token>
file: <path or —>
section: <## header or —>
No prose, no preamble, no chat body outside those three lines.
```

---

## Per-spawn token-count instrumentation

After every `Task` spawn, the orchestrator captures the spawn-prompt size into:

```
runs/<task>/cycle_<N>/spawn_<agent>.tokens.txt
```

Format: a single line containing the integer token count (via the regex-proxy
`len(re.findall(r"\S+", text)) * 1.3`, truncated to int).

- The nested per-cycle directory provides the namespace; no `_<cycle>` suffix on the
  filename.
- T22 consumes these files to build the aggregated per-cycle telemetry surface.
- T02 only *emits* the per-spawn measurement; T22 owns the aggregation.

---

## Token ceilings (hermetic test thresholds)

These ceilings are validated by `tests/orchestrator/test_spawn_prompt_size.py`:

| Agent | Spawn-prompt ceiling |
|---|---|
| `builder` | 8 000 tokens |
| `auditor` | 6 000 tokens |
| `sr-dev` | 4 000 tokens |
| `sr-sdet` | 4 000 tokens |
| `security-reviewer` | 4 000 tokens |
| `dependency-auditor` | 4 000 tokens |
| `task-analyzer` | 6 000 tokens |
| `roadmap-selector` | 4 000 tokens |

---

## Notes

- This file is the second entry under `.claude/commands/_common/` (after
  `agent_return_schema.md` from T01).
- Subsequent M20 tasks populate additional files in `_common/`:
  `parallel_spawn_pattern.md` (T05), `dispatch_table.md` (T07),
  `gate_parse_patterns.md` (T08), `integrity_checks.md` (T09),
  `effort_table.md` (T21), `auditor_context_management.md` (T27).
- The KDR extraction helper is implemented in `tests/orchestrator/_helpers.py`
  and tested in `tests/orchestrator/test_kdr_section_extractor.py`.
