# Task 04 — ValidatorNode Adapter — Audit Issues

**Source task:** [../task_04_validator_node.md](../task_04_validator_node.md)
**Audited on:** 2026-04-19
**Audit scope:** `ai_workflows/graph/validator_node.py`, `tests/graph/test_validator_node.py`, `CHANGELOG.md` unreleased entry, cross-checked against [architecture.md §3 / §4.2 / §8.2](../../../architecture.md) and KDR-004 (validator-after-every-LLM-node). Sibling tasks T01 / T02 / T03 reviewed for contract alignment; M1 T07 (`RetryableSemantic`) confirmed as the exception source.
**Status:** ✅ PASS on T04's explicit ACs (AC-1..AC-4 all met, no OPEN issues).

## Design-drift check

| Axis | Verdict | Evidence |
| --- | --- | --- |
| New dependency | None | No new entries in [pyproject.toml](../../../../pyproject.toml); module imports only stdlib, `pydantic`, and the existing `primitives.retry` symbol. |
| Four-layer contract | KEPT | `import-linter` reports 3 / 3 contracts kept, 0 broken (15 files analyzed). New module lives in `ai_workflows.graph` and imports only from `ai_workflows.primitives.retry`. |
| LLM call present? | No | Zero `litellm` / subprocess / CostTracker / TokenUsage imports. `grep` clean on `anthropic` and `ANTHROPIC_API_KEY`. Pure validation per spec and KDR-004. |
| KDR-004 compliance | Met | This module **is** the validator primitive — it raises `RetryableSemantic` with a prompt-ready hint that `RetryingEdge` (M2 T07) will forward. KDR-004 is implemented, not drifted. |
| Checkpoint / resume logic | None | Not touched. |
| Retry logic | No new retry loop | Raises `RetryableSemantic` once per invocation. Attempt budget delegated to `RetryingEdge` per spec. |
| Observability | No new backends | No `StructuredLogger` wired in (spec explicitly bans logs from this node — logs live at the `TieredNode` boundary). No Langfuse / OTel / LangSmith creep. |
| Secrets | None read | Module reads nothing from env. |

No drift. Task passes the design-drift gate.

## AC grading

| AC | Verdict | Evidence |
| --- | --- | --- |
| AC-1 — Node writes a pydantic instance to state on success | ✅ | [ai_workflows/graph/validator_node.py:90-95](../../../../ai_workflows/graph/validator_node.py#L90-L95) returns `{output_key: parsed, …}` where `parsed = schema.model_validate_json(text)` is a `BaseModel`. Asserted by [tests/graph/test_validator_node.py:31-41](../../../../tests/graph/test_validator_node.py#L31-L41). |
| AC-2 — `revision_hint` populated and references the schema mismatch | ✅ | [`_format_revision_hint`](../../../../ai_workflows/graph/validator_node.py#L101-L118) builds header plus per-`ValidationError`-entry lines with dotted `loc` and pydantic `msg`. Asserted by [test_schema_violation_raises_retryable_semantic_with_hint](../../../../tests/graph/test_validator_node.py#L44-L61) (checks schema name + both mismatched field names) and [test_missing_required_field_hint_references_field_name](../../../../tests/graph/test_validator_node.py#L82-L94). |
| AC-3 — No LLM call, no cost record (pure validation) | ✅ | Import surface confirms no `litellm`, no `CostTracker`, no `TokenUsage`, no subprocess shell-out. Structurally enforced. |
| AC-4 — `uv run pytest tests/graph/test_validator_node.py` green | ✅ | 6 / 6 passed in 0.80s. Full suite: 177 passed in 2.51s. |

## 🔴 HIGH

None.

## 🟡 MEDIUM

None.

## 🟢 LOW

None.

## Additions beyond spec — audited and justified

1. **`max_attempts < 1` ValueError guard at factory build time.**
   Spec describes `max_attempts` as "a soft documentation hint; enforcement lives in `RetryingEdge`." The guard does **not** enforce retry behaviour — it only rejects a nonsense configuration (`0` or negative) at build time, before any LangGraph wiring sees the node. This is input validation, not retry enforcement, and matches the defensive patterns already in [primitives/retry.py:105-108](../../../../ai_workflows/primitives/retry.py#L105-L108) (`Field(..., ge=1)` on `max_transient_attempts` / `max_semantic_attempts`). One unit test ([test_factory_rejects_max_attempts_below_one](../../../../tests/graph/test_validator_node.py#L97-L105)) pins it. Justified.
2. **Extra test cases beyond the spec's three.**
   Spec lists happy path, schema violation, non-JSON. Added `test_success_clears_stale_revision_hint` (pins the `f"{input_key}_revision_hint": None` reset, which the spec's return shape implies but does not isolate) and `test_missing_required_field_hint_references_field_name` (pins hint content for the common "missing field" retry path). Both test existing behaviour; no new production code. Justified.

## Gate summary

| Gate | Result |
| --- | --- |
| `uv run pytest` | ✅ 177 passed, 2 warnings (pre-existing `yoyo` datetime deprecation, unrelated to T04) in 2.51s |
| `uv run lint-imports` | ✅ 3 contracts kept, 0 broken (15 files analyzed) |
| `uv run ruff check` | ✅ All checks passed! |

## Issue log — cross-task follow-up

None. No deferrals; no cross-task findings.

## Deferred to nice_to_have

None.

## Propagation status

Not applicable. Task closed clean with no forward-deferred items.
