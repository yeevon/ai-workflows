---
model: claude-opus-4-7
thinking: max
---

# /audit

Single Auditor pass for: $ARGUMENTS

Spawn the `auditor` subagent via `Task` with the resolved task identifier, spec path, issue file path, architecture docs + KDR paths, gate commands, project context brief, and the most recent Builder report (if available — empty allowed). Wait for completion. Surface the issue file path + status line.

**Do not implement. Do not commit.** This command runs Auditor once and stops. Use `/clean-implement <task>` to run the full Builder → Auditor loop.

## Project context brief

Same shape as `/implement.md`'s brief. Add the architecture docs + KDR paths the Auditor specifically needs:

```text
Architecture: <ARCHITECTURE_DOC>  (ESPECIALLY layer rule, dep table, KDR section)
ADRs: <ADR_DIR>/*.md
Issue file path: <ISSUE_FILE for the resolved task>
Builder report (if from this session): <attach if available>
```

Resolve `$ARGUMENTS` to the task spec path. Halt and ask if multiple matches.
