# Skill-extraction pattern

This file documents the Skill-extraction pattern — the process of promoting a reusable agent capability into a standalone `.claude/skills/<name>/` Skill.
The pattern follows Anthropic's Agent Skills progressive-disclosure model: ~100 tokens of metadata at session start; full SKILL.md loads on trigger; helper files load only when referenced.
Future T12-shaped tasks (test-quality eval, threat-model walk, etc.) follow this pattern by reference.

## When to extract

Extract an agent capability into a Skill when it satisfies all three criteria: (1) the capability is reusable across contexts — it can fire in main context, not only during a spawned agent run; (2) the trigger can be described in 200 characters or fewer, trigger-led ("Use when…", "Run when…"); and (3) the full procedure benefits from progressive disclosure — a short metadata block at session start plus a helper file that loads only when the procedure fires. Capabilities that are tightly agent-specific (severity grading, threat-model framing, final-verdict authority) stay in the agent prompt. Operational shortcuts with a clear run-this-command recipe are the best extraction candidates.

## The 4-rule Skill structure

Every Skill under `.claude/skills/` must satisfy:

- **Frontmatter.** `name:` (kebab-case, matches directory name) and `description:` (≤ 200 chars, trigger-led so routing is unambiguous — e.g. "Run when pyproject.toml or uv.lock change").
- **Body ≤ 5K tokens.** SKILL.md covers: when to use, when NOT to use, the step-by-step procedure, and references to helper files. Helper files (e.g. `runbook.md`) live alongside SKILL.md and load only when the Skill body references them.
- **Helper-file references, not inline copies.** Per progressive-disclosure discipline, if an inline code block exceeds 20 lines, move it to a helper file or a `src/foo.py:line` reference (same rubric as T24 discoverability rule 4).
- **No silent agent-prompt duplication.** When a Skill is extracted from an agent prompt, the agent prompt replaces the inlined capability with a one-line pointer to the Skill (`## Operational shortcuts` section). T10's `_common/` pattern is the precedent.

## How to validate

The operator-side validation for a new Skill (matching `### T12 — Skills extraction (per-agent capabilities)` in the research brief) is: (1) confirm `SKILL.md` frontmatter has `name:` + `description:` ≤ 200 chars; (2) proxy-check body size via `wc -w SKILL.md` × 1.3 ≤ 5000; (3) run the four T24-rubric checks via `uv run python scripts/audit/md_discoverability.py` against the Skill directory; (4) confirm the source agent prompt contains an `## Operational shortcuts` section pointing to the Skill. The omit-the-Skill regression test (verify Claude underperforms without the Skill loaded) is a useful manual one-shot but is not Auditor-gated.

Live Skills: ai-workflows (legacy), dep-audit (T12), triage (T13), check (T14).
