# Verification discipline — shared rules

**Scope:** applies to all subagents. Code-task verification rules for Builders and Auditors; Bash-safety rules for all agents.

---

## 1. Code-task verification is non-inferential

Build-clean is necessary but not sufficient. Every code task spec must name an explicit smoke test the Auditor runs — an end-to-end LangGraph run, an MCP tool round-trip, a CLI invocation, or a stub-LLM eval.

Inferential claims about runtime behaviour from build success alone are HIGH at audit.

## 2. Smoke tests must be wire-level

Tests that pre-register workflows via fixtures or bypass the published CLI / MCP dispatch path do NOT count as wire-level proof.

Canonical incident: the 0.3.0 spec-API dispatch regression was missed because the fixture re-registered the workflow imperatively, side-stepping the broken dispatch lookup.

## 3. Real-install release smoke

Every release runs `aiw` against a `uv pip install dist/*.whl` install in a fresh venv. Gate: `tests/release/test_install_smoke.py` plus `scripts/release_smoke.sh` Stage 7. Non-skippable — no `AIW_E2E=1` opt-in.

## 4. Gate-rerun discipline

The Auditor independently runs `uv run pytest`, `uv run lint-imports`, `uv run ruff check`. Does not trust the Builder's reported results. Captures outcomes via `.claude/commands/_common/gate_parse_patterns.md`.

---

## Bash-safety rules (all agents)

Prefer `Read` for file inspection. Use `Bash` only when a runtime command is needed.

- One-line `grep -n PATTERN file` over chained pipes.
- No multi-line `python -c "..."` blocks — use a one-liner or temp script.
- No `echo` to narrate reasoning — use thinking, not shell output.
- Avoid shell-injection patterns: `$(...)`, `${VAR:-default}`, `$VAR` in loop bodies, newline+`#` in quoted strings, `=` in unquoted args, `{...}` with quote chars. These trip the harness even in bypassPermissions mode.
- For assemblies needing multiple shell-derived values: use separate Bash calls; assemble in thinking, not shell substitution.
