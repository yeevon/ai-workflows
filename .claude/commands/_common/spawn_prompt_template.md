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
| Project context brief | `architecture.md` content |
| Issue file path (may not exist yet) | `CHANGELOG.md` content |
| | Whole-milestone README content |

**Cycle-N pre-load rule:** on cycle 1 also pass the parent milestone README path; on
cycle N ≥ 2 replace it with the most recent `cycle_{N-1}/summary.md` (path + content).
See `.claude/commands/_common/cycle_summary_template.md` §Read-only-latest-summary rule
for the authoritative per-cycle Builder pre-load definition.

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

---

## Stable-prefix discipline (T23 — Cache-breakpoint discipline)

Claude Code caches the **stable prefix** of each sub-agent spawn prompt. A
misplaced cache breakpoint (one that sits *inside* the dynamic context rather
than at the end of the stable block) causes Claude Code to re-cache the entire
conversation on every spawn, producing **5–20× session-cost blowups**. The
anthropics/claude-code issue tracker documents this failure mode in issues
#27048, #34629, #42338, and #43657.

### What the stable prefix is

The stable prefix is the byte-for-byte-identical portion of the spawn prompt
that does **not** change between calls within a session. It consists of:

1. The agent system prompt (the per-agent Markdown body in `.claude/agents/`).
2. The `CLAUDE.md` / non-negotiables block (when prepended by the orchestrator).
3. The tool list (Claude Code locks these at session start; never modified mid-session).

The dynamic context follows **after** the stable prefix, separated by `\n\n`.

Structured as:

```
<stable prefix>

<dynamic context>
```

### Rules (MUST hold for every spawn)

1. **No timestamps, UUIDs, or per-request strings in the prefix.** Any value
   that changes between spawns within a session (wall-clock time, run ID,
   hostname, random nonce) belongs in the dynamic context, never the prefix.

2. **Tool list is fixed at session start; never modified mid-session.** Adding
   or removing MCP tools mid-session invalidates the entire conversation cache
   (per research brief §Lens 2.2). The orchestrator must not alter the tool
   list between spawns within a single `/auto-implement` run.

3. **Agent system prompt (frontmatter + body) is byte-identical between spawns
   within a session.** The orchestrator reads the agent's `.md` file exactly
   once at startup and passes the same bytes to every spawn. No dynamic
   interpolation in the system-prompt portion.

4. **`\n\n` boundary between prefix and dynamic context.** The orchestrator
   constructs every spawn prompt by concatenating the stable prefix first, then
   appending `\n\n`, then the dynamic context (task-specific data: current diff,
   issue-file content, cycle_summary). This boundary is where Claude Code's
   cache-detection algorithm splits the prompt.

### Verification

T23 ships `scripts/orchestration/cache_verify.py` — a 2-call verification
harness that reads T22's `cache_read_input_tokens` telemetry records:

- **Spawn 1:** `cache_creation_input_tokens` ≈ stable-prefix-token-count,
  `cache_read_input_tokens` ≈ 0.
- **Spawn 2 (within 5 min TTL):** `cache_read_input_tokens` ≈
  stable-prefix-token-count.

If spawn 2's `cache_read_input_tokens` is < 80% of the stable-prefix token
count, the harness surfaces:

```
🚧 Cache breakpoint regression — see runs/<task>/cache_verification.txt
```

Run on demand:

```bash
python scripts/orchestration/cache_verify.py --agent auditor --task m12_t01
```

Dry-run (hermetic, no real claude subprocess):

```bash
python scripts/orchestration/cache_verify.py --agent auditor --task m12_t01 \
    --dry-run \
    --spawn1-record runs/m12_t01/cycle_1/auditor.usage.json \
    --spawn2-record runs/m12_t01/cycle_2/auditor.usage.json
```

Output lands at `runs/<task>/cache_verification.txt`.

The empirical validation (running M12 T01 audit cycle twice in close succession
and asserting spawn 2's `cache_read_input_tokens` > 80%) is an **operator-resume
step** deferred to outside the autopilot iteration (parallel to T06 L5 deferral).
See `runs/cache_verification/methodology.md` for the operator runbook.

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
- The stable-prefix discipline rules above are tested in
  `tests/orchestrator/test_stable_prefix_construction.py` and
  `tests/orchestrator/test_cache_breakpoint_verification.py` (T23).
