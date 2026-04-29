# Autonomous-mode boundaries — shared non-negotiables

**Source:** project memory `feedback_autonomous_mode_boundaries.md` (8 rules locked 2026-04-27).
**Scope:** subagent-relevant rules only (rules 1, 2, 3-decision-rule). Rules 4–8 are operator-side infrastructure not loaded into subagent prompts.

---

## Rule 1 — No git mutations or publish

Do not run `git commit`, `git push`, `git merge`, `git rebase`, `git tag`, `uv publish`, or any other branch-modifying / release operation.

The `/auto-implement` orchestrator owns commit + push. It is restricted to `design_branch` only.

**HARD HALT triggers:**
- Any merge to `main` or `git push origin main`.
- Any `uv publish` invocation. Releasing to PyPI is a human decision.

If your role requires describing a needed git action, write it in your output — do not run the command.

## Rule 2 — KDR additions land on isolated commits

When a finding warrants a new KDR or KDR amendment:
- Write the change to `design_docs/architecture.md §9` plus an ADR plus rationale.
- The orchestrator commits it on its own commit (separate from the code change).
- KDR review is not blocking — work continues; the isolated commit sits on `design_branch` for human review.

## Rule 3 — Sub-agent team decision rule

Sub-agents collaborating on a question must ALIGN / AGREE before work proceeds. Disagreement = halt for user input.

Agents in the team: `builder`, `auditor`, `security-reviewer`, `dependency-auditor`, `task-analyzer`, `architect`, `sr-dev`, `sr-sdet`.
