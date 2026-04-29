# Auditor context management — T27 rotation trigger

**Summary:** When an Auditor spawn's input volume reaches the 60K-token threshold and
the verdict is OPEN, the orchestrator rotates: the next Auditor spawn receives a
compacted input (cycle_summary.md + current diff + spec path only) instead of the
standard pre-load set. Path A (server-side `clear_tool_uses_20250919`) is rejected per
audit H6.

---

## Threshold and tunability

- **Default threshold:** 60 000 input tokens (research-brief prior; §Lens 2.1).
- **Override:** set `AIW_AUDITOR_ROTATION_THRESHOLD=<integer>` in the environment
  before invoking the orchestrator. Example:
  ```bash
  AIW_AUDITOR_ROTATION_THRESHOLD=40000 claude /auto-implement m20 t27
  ```
- The threshold is read by `scripts/orchestration/auditor_rotation.py`
  via `get_threshold()`. The orchestrator reads the env var through the helper;
  it does not read it directly.

## Compaction recovery target

The compacted input should be **≤ 30 000 tokens** (cycle_summary.md + current diff +
spec path). T22's per-spawn `auditor.usage.json` records validate this after each
rotation event. If a compacted spawn still exceeds 30K, the diff is too large —
the Builder should be asked to split the change across cycles.

## What is and is not included in the compacted input

**Included:**
- Task spec path (pointer only — Auditor reads on-demand).
- Issue file path (pointer only).
- Current `git diff` (so the Auditor sees the actual code state).
- `runs/<task>/cycle_N/summary.md` content (T03's structured summary — replaces the
  full prior cycle's chat history).
- Cited KDR identifiers (compact pointer per spawn-prompt-template rule).
- Project context brief.

**NOT included after rotation:**
- Prior Builder reports' chat content.
- Prior Auditor verdict text.
- Prior tool-result content (this is what the rotation simulates clearing).
- Whole `architecture.md` content (Auditor reads on-demand — unchanged).
- Whole milestone README content (Auditor reads on-demand — unchanged).
- Prior cycle summaries beyond the most recent one.

## Rotation log

Each rotation event writes a one-line record to
`runs/<task>/cycle_<N>/auditor_rotation.txt`:

```
ROTATED: cycle <N> input_tokens=<value>; cycle <N+1> spawn input compacted (cycle_summary + diff only)
```

The T04 `iter_<N>-shipped.md` telemetry summary section includes any rotation events
that fired during the iteration.

## Why Path A is rejected (audit H6)

**Path A** would use the `clear_tool_uses_20250919` server-side strategy, passed to the
underlying Claude SDK via agent frontmatter `context_management.edits`.

**Rejection rationale (audit H6, 2026-04-27):** Claude Code's `Task` tool frontmatter
accepts only four keys: `name`, `description`, `tools`, `model`. There is no documented
mechanism for the `Task` tool surface to read `context_management:` from agent
frontmatter and pass it through to the underlying Anthropic SDK. This is the same
surface limitation as T01's `outputFormat: json_schema` (the Anthropic SDK has it; the
Claude Code Task wrapper does not expose it).

**T28** owns the broader question of whether *any* context-engineering primitive is
reachable via the `Task` tool surface. If T28's surface check returns YES for
`context_management`, a follow-up M21 task can layer server-side optimization on top of
T27's client-side rotation. **T27 itself ships Path B only.**

## Scope: Auditor-only

T27 applies **only to Auditor spawns**, not to Builder, sr-dev, sr-sdet,
security-reviewer, or task-analyzer:

- **Builder** — tool calls are mostly `Edit` + `Write`; result content is
  success/failure metadata (very small). No high-volume Read-heavy pattern.
- **Reviewers (sr-dev, sr-sdet, security-reviewer)** — single-pass spawns;
  they read a bounded set of files and return a verdict. No accumulation across
  cycles.
- **Auditor** — Read-heavy by design (loads spec + architecture.md + sibling issues
  on-demand across a multi-file task). Accumulated tool-result content can dominate
  input-token cost on long-cycle audits. T27 targets this pattern specifically.

## Integration points

- `scripts/orchestration/auditor_rotation.py` — `should_rotate(cycle_usage, threshold)`
  is the canonical decision function. Tests pin the threshold + verdict-OPEN logic
  against this helper (not against the orchestrator markdown prose).
- `scripts/orchestration/telemetry.py` — produces `auditor.usage.json`; T27 reads
  `input_tokens` and `verdict` from these records.
- `.claude/commands/_common/cycle_summary_template.md` — defines the
  `cycle_<N>/summary.md` format; T27's compacted input uses this file as its
  structured summary source.
- `tests/orchestrator/test_auditor_rotation_trigger.py` — hermetic tests for the
  threshold-fire + threshold-no-fire + verdict-PASS + tunability cases.
- `tests/orchestrator/test_auditor_rotation_doesnt_break_verdict.py` — hermetic 5-cycle
  fixture asserting final verdicts are identical and T27-enabled cumulative input tokens
  are ≤ 70% of T27-disabled.
