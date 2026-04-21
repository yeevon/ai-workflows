"""Filesystem layout + serialization helpers for eval fixtures (M7 Task 01).

Per `task_01_dataset_schema.md` under `design_docs/phases/milestone_7_evals/`:

* Fixtures live under ``<root>/<workflow_id>/<node_name>/<case_id>.json``.
* Default root is ``evals/`` at the repo root; override with
  ``AIW_EVALS_ROOT``.
* Serialization is ``EvalCase.model_dump_json(indent=2)`` so PRs diff
  cleanly against JSON fixtures.

Keeps this module free of graph/workflow imports — per the task-added
import-linter contract, :mod:`ai_workflows.evals` depends on
:mod:`ai_workflows.primitives` only, and this file touches neither.
"""

from __future__ import annotations

import os
from pathlib import Path

from ai_workflows.evals.schemas import EvalCase, EvalSuite

__all__ = [
    "EVALS_ROOT",
    "default_evals_root",
    "fixture_path",
    "load_case",
    "load_suite",
    "save_case",
]

EVALS_ROOT = Path("evals")
"""Default fixture root, relative to the process CWD.

In practice the T04 CLI runs from the repo root and ``evals/`` is the
committed sibling of ``ai_workflows/``. Override with ``AIW_EVALS_ROOT``
for tests or alternate layouts.
"""


def default_evals_root() -> Path:
    """Resolve the fixture root, honouring ``AIW_EVALS_ROOT`` override."""

    override = os.getenv("AIW_EVALS_ROOT")
    if override:
        return Path(override)
    return EVALS_ROOT


def fixture_path(root: Path, workflow_id: str, node_name: str, case_id: str) -> Path:
    """Canonical on-disk path for a single eval fixture."""

    return root / workflow_id / node_name / f"{case_id}.json"


def save_case(case: EvalCase, root: Path | None = None, *, overwrite: bool = False) -> Path:
    """Write one case to its canonical path.

    Refuses to overwrite an existing fixture unless ``overwrite=True``.
    The T02 ``CaptureCallback`` disambiguates collisions by suffixing
    the ``case_id`` rather than flipping this flag — the refusal is the
    invariant a collision-handling caller has to step around explicitly.
    """

    if root is None:
        root = default_evals_root()
    path = fixture_path(root, case.workflow_id, case.node_name, case.case_id)
    if path.exists() and not overwrite:
        raise FileExistsError(
            f"eval fixture already exists at {path}; pass overwrite=True to replace"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(case.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_case(path: Path) -> EvalCase:
    """Load one eval case from disk."""

    return EvalCase.model_validate_json(path.read_text(encoding="utf-8"))


def load_suite(workflow_id: str, root: Path | None = None) -> EvalSuite:
    """Aggregate every case under ``<root>/<workflow_id>/**/*.json``.

    Non-JSON files (e.g. stray READMEs) are ignored. Files that do not
    parse as ``EvalCase`` raise at load time — a malformed commit fails
    loudly rather than silently shrinking the suite.
    """

    if root is None:
        root = default_evals_root()
    workflow_root = root / workflow_id
    if not workflow_root.exists():
        return EvalSuite(workflow_id=workflow_id, cases=())
    cases: list[EvalCase] = []
    for path in sorted(workflow_root.rglob("*.json")):
        if not path.is_file():
            continue
        cases.append(load_case(path))
    return EvalSuite(workflow_id=workflow_id, cases=tuple(cases))
