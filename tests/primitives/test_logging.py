"""Tests for M1 Task 09 — :mod:`ai_workflows.primitives.logging`.

Pins the four T09 acceptance criteria plus the three inherited
carry-overs (``M1-T02-ISS-01`` logfire removal, ``M1-T04-ISS-01``
forensic_logger retirement, ``M1-T08-DEF-01`` ``BudgetExceeded`` →
``NonRetryable`` docstring swap).

The `M1-T01-ISS-08` carry-over (secret-scan regex parsing) is pinned
from `tests/test_scaffolding.py` instead; that file owns the
`.github/workflows/ci.yml` extraction.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
import structlog

from ai_workflows.primitives.logging import (
    NODE_LOG_FIELDS,
    configure_logging,
    log_node_event,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _reset_structlog_between_tests():
    """Prevent configuration leakage across tests."""
    yield
    structlog.reset_defaults()


@pytest.fixture
def stderr_buf():
    """In-memory buffer passed to :func:`configure_logging` as ``stream=...``.

    Using the explicit ``stream`` parameter is more reliable than
    monkeypatching :data:`sys.stderr` — pytest's own capture machinery
    can otherwise sit in front of the monkeypatch.
    """
    return io.StringIO()


# ---------------------------------------------------------------------------
# configure_logging — level filtering (preserved from pre-pivot M1 T11)
# ---------------------------------------------------------------------------


def test_info_level_suppresses_debug(stderr_buf):
    configure_logging("INFO", stream=stderr_buf)
    log = structlog.get_logger("t")
    log.debug("hidden_debug_event")
    log.info("visible_info_event")
    output = stderr_buf.getvalue()
    assert "hidden_debug_event" not in output
    assert "visible_info_event" in output


def test_warning_level_suppresses_debug_and_info(stderr_buf):
    configure_logging("WARNING", stream=stderr_buf)
    log = structlog.get_logger("t")
    log.debug("x_debug")
    log.info("x_info")
    log.warning("x_warning")
    output = stderr_buf.getvalue()
    assert "x_debug" not in output
    assert "x_info" not in output
    assert "x_warning" in output


def test_level_is_case_insensitive(stderr_buf):
    configure_logging("info", stream=stderr_buf)
    log = structlog.get_logger("t")
    log.debug("dbg")
    log.info("inf")
    out = stderr_buf.getvalue()
    assert "dbg" not in out
    assert "inf" in out


# ---------------------------------------------------------------------------
# configure_logging — DEBUG swaps in the ConsoleRenderer
# ---------------------------------------------------------------------------


def test_debug_level_emits_human_readable_console(stderr_buf):
    configure_logging("DEBUG", stream=stderr_buf)
    log = structlog.get_logger("t")
    log.debug("an_event_name", some_key="some_value")
    output = stderr_buf.getvalue()
    assert "an_event_name" in output
    assert "some_key" in output
    assert "some_value" in output
    assert "[debug" in output.lower()


def test_debug_console_output_is_not_json(stderr_buf):
    configure_logging("DEBUG", stream=stderr_buf)
    log = structlog.get_logger("t")
    log.debug("nope_not_json")
    first_line = stderr_buf.getvalue().splitlines()[0]
    with pytest.raises(json.JSONDecodeError):
        json.loads(first_line)


# ---------------------------------------------------------------------------
# configure_logging — JSON renderer output at non-DEBUG levels
# ---------------------------------------------------------------------------


def test_info_level_emits_valid_json_per_line(stderr_buf):
    configure_logging("INFO", stream=stderr_buf)
    log = structlog.get_logger("t")
    log.info("first_event", alpha=1)
    log.warning("second_event", beta="two")

    lines = [ln for ln in stderr_buf.getvalue().splitlines() if ln.strip()]
    assert len(lines) == 2
    first = json.loads(lines[0])
    second = json.loads(lines[1])

    assert first["event"] == "first_event"
    assert first["alpha"] == 1
    assert first["level"] == "info"
    assert "timestamp" in first

    assert second["event"] == "second_event"
    assert second["beta"] == "two"
    assert second["level"] == "warning"


# ---------------------------------------------------------------------------
# configure_logging — per-run file sink
# ---------------------------------------------------------------------------


def test_per_run_file_is_created_when_run_id_given(tmp_path, stderr_buf):
    configure_logging("INFO", run_id="run-abc", run_root=tmp_path, stream=stderr_buf)
    log_file = tmp_path / "run-abc" / "run.log"
    assert log_file.is_file()


def test_per_run_file_receives_json_lines(tmp_path, stderr_buf):
    configure_logging("INFO", run_id="run-xyz", run_root=tmp_path, stream=stderr_buf)
    log = structlog.get_logger("t")
    log.info("file_event", foo="bar", n=7)

    log_file = tmp_path / "run-xyz" / "run.log"
    contents = [ln for ln in log_file.read_text().splitlines() if ln.strip()]
    assert contents
    payload = json.loads(contents[-1])
    assert payload["event"] == "file_event"
    assert payload["foo"] == "bar"
    assert payload["n"] == 7
    assert payload["level"] == "info"


def test_per_run_file_is_always_json_even_in_debug_mode(tmp_path, stderr_buf):
    configure_logging("DEBUG", run_id="run-dbg", run_root=tmp_path, stream=stderr_buf)
    log = structlog.get_logger("t")
    log.debug("debug_evt", x=1)

    log_file = tmp_path / "run-dbg" / "run.log"
    contents = [ln for ln in log_file.read_text().splitlines() if ln.strip()]
    assert contents
    payload = json.loads(contents[-1])
    assert payload["event"] == "debug_evt"
    assert payload["x"] == 1


def test_no_per_run_file_when_run_id_missing(tmp_path, stderr_buf):
    configure_logging("INFO", run_root=tmp_path, stream=stderr_buf)
    assert list(tmp_path.iterdir()) == []


# ---------------------------------------------------------------------------
# configure_logging — get_logger works from any module
# ---------------------------------------------------------------------------


def test_get_logger_works_from_arbitrary_module_name(stderr_buf):
    configure_logging("INFO", stream=stderr_buf)
    a = structlog.get_logger("ai_workflows.primitives.cost")
    b = structlog.get_logger("some.other.module")
    a.info("from_a")
    b.warning("from_b")
    output = stderr_buf.getvalue()
    assert "from_a" in output
    assert "from_b" in output


def test_get_logger_with_no_name_works(stderr_buf):
    configure_logging("INFO", stream=stderr_buf)
    log = structlog.get_logger()
    log.info("unnamed_event")
    assert "unnamed_event" in stderr_buf.getvalue()


# ---------------------------------------------------------------------------
# AC — NODE_LOG_FIELDS matches architecture.md §8.1 exactly
# ---------------------------------------------------------------------------


def test_node_log_fields_match_architecture_81():
    """The ten fields architecture.md §8.1 mandates are exposed verbatim."""
    assert NODE_LOG_FIELDS == (
        "run_id",
        "workflow",
        "node",
        "tier",
        "provider",
        "model",
        "duration_ms",
        "input_tokens",
        "output_tokens",
        "cost_usd",
    )


# ---------------------------------------------------------------------------
# AC — log_node_event emits every §8.1 field for each route-kind
# ---------------------------------------------------------------------------


def _load_json_from_run_log(log_file: Path) -> dict:
    lines = [ln for ln in log_file.read_text().splitlines() if ln.strip()]
    assert lines, f"no records landed in {log_file}"
    return json.loads(lines[-1])


def test_log_node_event_emits_all_fields_for_litellm_route(tmp_path, stderr_buf):
    configure_logging(
        "INFO", run_id="run-lite", run_root=tmp_path, stream=stderr_buf
    )
    logger = structlog.get_logger("ai_workflows.graph.tiered_node")
    log_node_event(
        logger,
        run_id="run-lite",
        workflow="slice_refactor",
        node="planner",
        tier="orchestrator",
        provider="litellm",
        model="gemini/gemini-2.5-flash",
        duration_ms=1234,
        input_tokens=500,
        output_tokens=200,
        cost_usd=0.0021,
    )

    record = _load_json_from_run_log(tmp_path / "run-lite" / "run.log")
    for field in NODE_LOG_FIELDS:
        assert field in record, f"missing required §8.1 field {field!r}"
    assert record["run_id"] == "run-lite"
    assert record["provider"] == "litellm"
    assert record["model"] == "gemini/gemini-2.5-flash"
    assert record["duration_ms"] == 1234
    assert record["input_tokens"] == 500
    assert record["output_tokens"] == 200
    assert record["cost_usd"] == 0.0021
    assert record["event"] == "node_completed"
    assert record["level"] == "info"


def test_log_node_event_emits_all_fields_for_claude_code_route(tmp_path, stderr_buf):
    configure_logging(
        "INFO", run_id="run-cc", run_root=tmp_path, stream=stderr_buf
    )
    logger = structlog.get_logger("ai_workflows.graph.tiered_node")
    log_node_event(
        logger,
        event="node_started",
        run_id="run-cc",
        workflow="planner",
        node="opus_planner",
        tier="planner",
        provider="claude_code",
        model="opus",
        duration_ms=4200,
        input_tokens=1100,
        output_tokens=650,
        cost_usd=0.18,
    )

    record = _load_json_from_run_log(tmp_path / "run-cc" / "run.log")
    for field in NODE_LOG_FIELDS:
        assert field in record, f"missing required §8.1 field {field!r}"
    assert record["provider"] == "claude_code"
    assert record["model"] == "opus"
    assert record["event"] == "node_started"


def test_log_node_event_emits_none_for_unpopulated_fields(tmp_path, stderr_buf):
    """Per the task spec: fields unknown at emit time emit None, not a placeholder."""
    configure_logging(
        "INFO", run_id="run-null", run_root=tmp_path, stream=stderr_buf
    )
    logger = structlog.get_logger("ai_workflows.graph.tiered_node")
    log_node_event(
        logger,
        run_id="run-null",
        workflow="slice_refactor",
        node="planner",
        tier="orchestrator",
        provider="litellm",
        model="gemini/gemini-2.5-flash",
    )

    record = _load_json_from_run_log(tmp_path / "run-null" / "run.log")
    for field in NODE_LOG_FIELDS:
        assert field in record, f"missing required §8.1 field {field!r}"
    assert record["duration_ms"] is None
    assert record["input_tokens"] is None
    assert record["output_tokens"] is None
    assert record["cost_usd"] is None


def test_log_node_event_forwards_extra_kwargs(tmp_path, stderr_buf):
    configure_logging(
        "INFO", run_id="run-extra", run_root=tmp_path, stream=stderr_buf
    )
    logger = structlog.get_logger("ai_workflows.graph.tiered_node")
    log_node_event(
        logger,
        run_id="run-extra",
        workflow="slice_refactor",
        node="validator",
        tier="orchestrator",
        provider="litellm",
        model="gemini/gemini-2.5-flash",
        retry_count=2,
        revision_round=1,
    )

    record = _load_json_from_run_log(tmp_path / "run-extra" / "run.log")
    assert record["retry_count"] == 2
    assert record["revision_round"] == 1


def test_log_node_event_level_override_routes_to_warning(tmp_path, stderr_buf):
    configure_logging(
        "INFO", run_id="run-warn", run_root=tmp_path, stream=stderr_buf
    )
    logger = structlog.get_logger("ai_workflows.graph.tiered_node")
    log_node_event(
        logger,
        event="pricing_row_missing",
        level="warning",
        run_id="run-warn",
        workflow="planner",
        node="opus_planner",
        tier="planner",
        provider="claude_code",
        model="opus",
    )

    record = _load_json_from_run_log(tmp_path / "run-warn" / "run.log")
    assert record["level"] == "warning"
    assert record["event"] == "pricing_row_missing"


# ---------------------------------------------------------------------------
# AC — no logfire / no pydantic_ai imports in logging.py
#      (T09 spec ACs 2 and 3 — grep targets)
# ---------------------------------------------------------------------------


def _read(relative: str) -> str:
    return (_REPO_ROOT / relative).read_text(encoding="utf-8")


def test_logging_module_has_no_logfire_import():
    """AC: ``grep -r 'logfire' ai_workflows/`` — zero (T02 removed the dep)."""
    src = _read("ai_workflows/primitives/logging.py")
    for line in src.splitlines():
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            assert "logfire" not in stripped, f"stale logfire import line: {line!r}"


def test_logging_module_source_has_no_logfire_mentions_anywhere():
    """AC-2 (letter): ``grep -r 'logfire' ai_workflows/`` — literal zero.

    Pins the whole-file (not just import-line) reading of the spec AC.
    Docstring narrative that names the removed backend by library name
    would trip the literal grep even though it carries no runtime
    behaviour. Closes M1-T09-ISS-01.
    """
    src = _read("ai_workflows/primitives/logging.py")
    assert "logfire" not in src.lower(), (
        "M1-T09-ISS-01: the module source must not name the removed "
        "logfire backend — AC-2's literal grep reading is zero-match"
    )


def test_logging_module_has_no_pydantic_ai_imports():
    """AC: ``grep -r 'pydantic_ai' ai_workflows/primitives/logging.py`` — zero."""
    src = _read("ai_workflows/primitives/logging.py")
    for line in src.splitlines():
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            assert "pydantic_ai" not in stripped, (
                f"stale pydantic_ai import line: {line!r}"
            )


def test_logging_module_structlog_is_only_backend():
    """AC: structlog is the only observability backend consumed."""
    src = _read("ai_workflows/primitives/logging.py")
    backends_found: set[str] = set()
    for line in src.splitlines():
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            for backend in ("logfire", "langsmith", "langfuse", "opentelemetry"):
                if backend in stripped:
                    backends_found.add(backend)
    assert backends_found == set(), (
        f"unexpected observability backends imported: {sorted(backends_found)}"
    )


# ---------------------------------------------------------------------------
# Carry-over — M1-T04-ISS-01 (a): Related paragraph no longer mentions
#              primitives.tools.forensic_logger
# ---------------------------------------------------------------------------


def test_logging_module_docstring_no_longer_references_forensic_logger():
    src = _read("ai_workflows/primitives/logging.py")
    assert "forensic_logger" not in src, (
        "M1-T04-ISS-01 (a): docstring must not cite the deleted "
        "primitives.tools.forensic_logger module"
    )
    assert "primitives.tools" not in src, (
        "M1-T04-ISS-01 (a): the whole tools/ subpackage was deleted by T04"
    )


# ---------------------------------------------------------------------------
# Carry-over — M1-T08-DEF-01: ``BudgetExceeded`` docstring ref replaced
#              with ``NonRetryable("budget exceeded")``
# ---------------------------------------------------------------------------


def test_logging_module_docstring_uses_nonretryable_not_budgetexceeded():
    src = _read("ai_workflows/primitives/logging.py")
    assert "BudgetExceeded" not in src, (
        "M1-T08-DEF-01: T08 removed BudgetExceeded — the docstring "
        "ERROR-level example must reference NonRetryable('budget exceeded')"
    )
    assert "NonRetryable" in src, (
        "M1-T08-DEF-01: the ERROR-level docstring example must cite "
        "NonRetryable (the post-T08 budget-breach exception)"
    )
