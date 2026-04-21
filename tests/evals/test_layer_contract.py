"""Layer-contract companion test for M7 Task 01 / Task 02.

The import-linter contract added in ``pyproject.toml`` polices one
direction (``evals → {workflows, cli, mcp}`` is forbidden). The
complementary invariant — ``graph`` does not import
``ai_workflows.evals`` — is policed here by a one-shot AST grep.

Why the asymmetry: ``evals`` sits *above* ``graph`` in the layer order
(it imports ``TieredNode`` / ``ValidatorNode`` adapters for replay at
T03, and the ``CaptureCallback`` class itself lives here at T02 so
``TieredNode`` can stay evals-unaware). ``workflows`` is the layer
that wires the capture callback onto a running graph at dispatch
time (T02 ``_dispatch.run_workflow``), so ``workflows → evals`` is
expected and allowed. The original T01 spec listed ``workflows`` in
this check; T02 surfaced the contradiction and T01 issue M7-T01-ISS-02
records the correction: only ``graph → evals`` is forbidden.
"""

from __future__ import annotations

import ast
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent.parent / "ai_workflows"


def _imports_evals(py_file: Path) -> bool:
    source = py_file.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(py_file))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "ai_workflows.evals" or alias.name.startswith(
                    "ai_workflows.evals."
                ):
                    return True
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "ai_workflows.evals" or module.startswith("ai_workflows.evals."):
                return True
    return False


def test_graph_does_not_import_evals() -> None:
    subroot = PACKAGE_ROOT / "graph"
    offenders: list[Path] = []
    for py_file in subroot.rglob("*.py"):
        if _imports_evals(py_file):
            offenders.append(py_file)
    assert not offenders, (
        f"graph/ must not import ai_workflows.evals; offenders: {offenders}"
    )
