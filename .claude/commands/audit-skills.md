# /audit-skills — Periodic Skill and slash-command efficiency audit

Quarterly operator-invoked audit over every Skill and slash command in the
repo. Surfaces four failure-mode heuristics (two CI-gated via
`scripts/audit/skills_efficiency.py`, two operator-only). Produces a
timestamped report at `runs/audit-skills/<timestamp>/report.md`.

Cadence: quarterly (or after any new Skill or slash command is added).

## Inputs

- **Skills target** (default): `.claude/skills/` — walks `*/SKILL.md` and
  helper files (`*/runbook.md`, etc.) for every Skill directory found.
- **Commands target** (default): `.claude/commands/` — walks `*.md` for
  every slash-command file.
- No required arguments. Run as: `/audit-skills`

## Procedure

### Step 1 — CI-gated heuristics (scripts/audit/skills_efficiency.py)

Run both CI-gated checks against the live Skills directory:

```bash
uv run python scripts/audit/skills_efficiency.py --check screenshot-overuse --target .claude/skills/
uv run python scripts/audit/skills_efficiency.py --check missing-tool-decl --target .claude/skills/
```

Collect any `Rule N FAIL` lines from stdout. Exit code 1 = findings exist.

### Step 2 — Operator-only heuristic: tool-roundtrips

For each SKILL.md, count `##`-level sections inside `## Procedure` (or the
equivalent top-level procedure section) that contain a fenced bash block.

Flag as `FLAG` when the same `## Procedure` section contains **3 or more**
separate fenced bash blocks — this suggests batch-able invocations that could
be merged into one `&&`-chained command.

Report: "do these N bash blocks need separate invocations or can they batch?"

### Step 3 — Operator-only heuristic: file-rereads

Scan each SKILL.md and helper file for literal duplicate `Read <path>`
patterns appearing more than once in the procedure body. Flag when the same
file path appears in two or more distinct `Read` instructions in the same
procedure — this suggests the Skill is asking the model to re-read a file
already loaded into context.

### Step 4 — Slash-command walk (.claude/commands/*.md)

For each slash-command file (excluding `_common/` helpers), check:

- **Inline-procedure size**: if the file body exceeds 200 lines, flag as
  `FLAG` (composite commands that loop or retry should inline the full
  procedure; very large files suggest missing progressive-disclosure
  structure).
- **Missing return-schema anchor**: if the file contains a `## Procedure`
  section but no `## Return schema` or reference to
  `.claude/commands/_common/agent_return_schema.md`, flag as `FLAG` (audit-
  style commands without a return schema can break the autonomy loop's
  orchestrator parser).

### Step 5 — Write report

Create `runs/audit-skills/<timestamp>/report.md` with one section per Skill
and one section per slash command. Each section lists the heuristic name,
verdict (`OK` or `FLAG`), and a one-line reason for any `FLAG`.

Example section:

```markdown
## dep-audit

| Heuristic | Verdict | Reason |
|---|---|---|
| screenshot-overuse | OK | — |
| missing-tool-decl | OK | allowed-tools: frontmatter present |
| tool-roundtrips | OK | — |
| file-rereads | OK | — |
```

## Outputs

- `runs/audit-skills/<timestamp>/report.md` — one section per Skill, one
  per slash command. Each section lists all four heuristics + verdicts.
- Stdout summary of FLAGS found (or "All clean" if zero flags).

## Return schema

```
verdict: <CLEAN | FLAGS-FOUND>
file: runs/audit-skills/<timestamp>/report.md
section: —
```

- `CLEAN` — zero findings across all heuristics and all targets.
- `FLAGS-FOUND` — one or more heuristic FLAGs detected; the report lists
  them. Operator decides whether to act on each FLAG.
