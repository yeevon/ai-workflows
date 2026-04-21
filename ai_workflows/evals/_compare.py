"""Comparison semantics for eval replay (M7 Task 03).

Resolves the per-case :class:`EvalTolerance` into a single
``(passed, diff)`` verdict the runner can stamp onto an
:class:`ai_workflows.evals.EvalResult`. Three tolerance modes:

* ``strict_json`` — parse both sides through the case's resolved
  ``output_schema`` (via :func:`_resolve_schema`) and compare the
  :meth:`BaseModel.model_dump` dicts. The diff is a
  :func:`difflib.unified_diff` over the pretty-printed JSON so a
  human reading a CI log can locate the drift quickly.
* ``substring`` — for every string-typed field in the expected
  output (top-level dict), assert ``expected.lower() in actual.lower()``.
  Non-string fields fall back to strict equality so a partial-string
  tolerance does not accidentally pass on structural mismatches.
* ``regex`` — for every string-typed field, assert
  :func:`re.search` matches. Non-string fields strict-compare.

``field_overrides`` lets a case mix modes — the canonical pattern
``strict_json`` + ``{"summary": "substring"}`` keeps the structured
half of the output rigid while relaxing the free-text field that
drifts most under live replay.

Sibling of :mod:`ai_workflows.evals._stub_adapter` — both are
runner-internal helpers (underscore-prefixed) that :mod:`runner`
composes into the public :class:`EvalRunner` surface. No graph or
workflow imports; pure pydantic + stdlib.
"""

from __future__ import annotations

import difflib
import importlib
import json
import re
from typing import Any

from pydantic import BaseModel, ValidationError

from ai_workflows.evals.schemas import EvalTolerance, ToleranceMode

__all__ = ["compare"]


def compare(
    expected: Any,
    actual: Any,
    tolerance: EvalTolerance,
    output_schema_fqn: str | None,
) -> tuple[bool, str]:
    """Return ``(passed, diff)`` per ``tolerance`` for one replay output.

    Parameters
    ----------
    expected:
        The pinned :attr:`EvalCase.expected_output`. For structured
        nodes this is the raw JSON string the provider returned at
        capture time; for free-text nodes it's the raw text.
    actual:
        The output the replay produced. Same shape expectations as
        ``expected`` — raw string for structured nodes (the
        ``TieredNode``'s ``{node}_output`` state key), raw string for
        free-text nodes.
    tolerance:
        Per-case comparison policy. When ``output_schema_fqn`` is
        ``None`` (free-text node), ``strict_json`` degrades to raw
        string equality — ``substring`` / ``regex`` still apply to
        the raw text.
    output_schema_fqn:
        Fully qualified name of the pydantic model the
        ``ValidatorNode`` downstream of this node parses against.
        ``None`` signals a free-text node.

    Returns
    -------
    ``(True, "")`` on match, ``(False, diff_string)`` otherwise. The
    diff is either a pretty-printed pydantic-dict delta (strict_json)
    or a one-line explanation of which field missed (substring /
    regex).
    """

    if tolerance.mode == "strict_json" and not tolerance.field_overrides:
        return _compare_strict_json(expected, actual, output_schema_fqn)

    if tolerance.mode in ("substring", "regex") and not tolerance.field_overrides:
        return _compare_by_field(
            expected, actual, tolerance.mode, output_schema_fqn
        )

    return _compare_with_overrides(
        expected, actual, tolerance, output_schema_fqn
    )


def _compare_strict_json(
    expected: Any,
    actual: Any,
    output_schema_fqn: str | None,
) -> tuple[bool, str]:
    """Strict equality via the resolved ``output_schema`` model_dump."""

    schema = _resolve_schema(output_schema_fqn)
    if schema is None:
        # Free-text node: raw string equality, no pydantic hop.
        if expected == actual:
            return True, ""
        return False, _unified_diff(str(expected), str(actual))

    expected_dump = _model_dump_via_schema(expected, schema)
    actual_dump = _model_dump_via_schema(actual, schema)
    if expected_dump == actual_dump:
        return True, ""
    return False, _unified_diff(
        json.dumps(expected_dump, indent=2, sort_keys=True),
        json.dumps(actual_dump, indent=2, sort_keys=True),
    )


def _compare_by_field(
    expected: Any,
    actual: Any,
    mode: ToleranceMode,
    output_schema_fqn: str | None,
) -> tuple[bool, str]:
    """Per-field substring / regex comparison (no mixed overrides)."""

    schema = _resolve_schema(output_schema_fqn)
    if schema is None:
        # Free-text node: compare as raw strings.
        ok, detail = _field_match(str(expected), str(actual), mode)
        if ok:
            return True, ""
        return False, f"field '$': {detail}"

    expected_dump = _model_dump_via_schema(expected, schema)
    actual_dump = _model_dump_via_schema(actual, schema)
    return _walk_fields(expected_dump, actual_dump, default_mode=mode)


def _compare_with_overrides(
    expected: Any,
    actual: Any,
    tolerance: EvalTolerance,
    output_schema_fqn: str | None,
) -> tuple[bool, str]:
    """Mixed-mode compare using ``tolerance.field_overrides`` per field."""

    schema = _resolve_schema(output_schema_fqn)
    if schema is None:
        # Free-text + overrides: overrides are a no-op because there
        # are no fields to address. Degrade to the default mode.
        return _compare_by_field(expected, actual, tolerance.mode, None)

    expected_dump = _model_dump_via_schema(expected, schema)
    actual_dump = _model_dump_via_schema(actual, schema)
    return _walk_fields(
        expected_dump,
        actual_dump,
        default_mode=tolerance.mode,
        field_overrides=tolerance.field_overrides,
    )


def _walk_fields(
    expected_dump: dict[str, Any],
    actual_dump: dict[str, Any],
    *,
    default_mode: ToleranceMode,
    field_overrides: dict[str, ToleranceMode] | None = None,
) -> tuple[bool, str]:
    """Compare two top-level pydantic dumps field-by-field."""

    overrides = field_overrides or {}
    missing_keys = set(expected_dump) - set(actual_dump)
    if missing_keys:
        return False, f"missing fields in actual: {sorted(missing_keys)}"

    problems: list[str] = []
    for key, exp_val in expected_dump.items():
        act_val = actual_dump.get(key)
        mode = overrides.get(key, default_mode)
        if isinstance(exp_val, str) and isinstance(act_val, str):
            ok, detail = _field_match(exp_val, act_val, mode)
            if not ok:
                problems.append(f"field '{key}': {detail}")
        else:
            # Structural values always strict-compare regardless of mode
            # — substring / regex semantics on lists / ints / dicts do
            # not generalise cleanly. Users who want lax structural
            # compare should dump to a free-text summary and override.
            if exp_val != act_val:
                problems.append(
                    f"field '{key}': structural mismatch "
                    f"(expected {exp_val!r}, actual {act_val!r})"
                )

    if problems:
        return False, "\n".join(problems)
    return True, ""


def _field_match(
    expected: str, actual: str, mode: ToleranceMode
) -> tuple[bool, str]:
    """Apply one tolerance mode to one string field."""

    if mode == "strict_json":
        if expected == actual:
            return True, ""
        return False, (
            f"expected exact string {expected!r} but got {actual!r}"
        )
    if mode == "substring":
        if expected.lower() in actual.lower():
            return True, ""
        return False, (
            f"expected substring {expected!r} not found in {actual!r}"
        )
    if mode == "regex":
        try:
            if re.search(expected, actual):
                return True, ""
        except re.error as exc:
            return False, f"invalid regex {expected!r}: {exc}"
        return False, f"regex {expected!r} did not match {actual!r}"
    return False, f"unsupported tolerance mode: {mode!r}"


def _resolve_schema(output_schema_fqn: str | None) -> type[BaseModel] | None:
    """Import a pydantic model by fully qualified name, or return None."""

    if output_schema_fqn is None:
        return None
    module_path, _, qualname = output_schema_fqn.rpartition(".")
    if not module_path:
        return None
    module = importlib.import_module(module_path)
    candidate = getattr(module, qualname, None)
    if isinstance(candidate, type) and issubclass(candidate, BaseModel):
        return candidate
    return None


def _model_dump_via_schema(
    raw: Any, schema: type[BaseModel]
) -> dict[str, Any]:
    """Parse a raw JSON string (or pre-parsed dict) through ``schema``.

    On :class:`ValidationError` the input is returned untouched — the
    caller's unified-diff renders the parse failure as a
    raw-string-vs-dict delta, which surfaces schema drift without
    swallowing it.
    """

    if isinstance(raw, dict):
        try:
            return schema.model_validate(raw).model_dump()
        except ValidationError:
            return raw
    if isinstance(raw, str):
        try:
            return schema.model_validate_json(raw).model_dump()
        except ValidationError:
            # Fall back to parsed-json-or-raw-string: we want a dict-
            # shaped compare when possible.
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {"__raw__": raw}
    # Anything else (already-a-model, etc.) — dump if possible, else
    # wrap so the dict walk still terminates.
    if isinstance(raw, BaseModel):
        return raw.model_dump()
    return {"__raw__": raw}


def _unified_diff(expected: str, actual: str) -> str:
    """Render a unified diff string humans can read on a CI log."""

    lines = list(
        difflib.unified_diff(
            expected.splitlines(keepends=True),
            actual.splitlines(keepends=True),
            fromfile="expected",
            tofile="actual",
            lineterm="",
        )
    )
    if not lines:
        return ""
    return "".join(lines)
