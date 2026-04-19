"""Shared fixtures for the stdlib-tools test suite.

Exposes :class:`CtxShim` — a lightweight stand-in for
``pydantic_ai.RunContext[WorkflowDeps]`` that carries only the ``deps``
attribute the stdlib tools actually read. Avoids constructing a real
``RunContext`` (which requires a live ``Model`` and ``RunUsage``) just to
feed ``ctx.deps.project_root`` into a filesystem tool.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from ai_workflows.primitives.llm.types import WorkflowDeps


@dataclass
class CtxShim:
    """Minimal ``RunContext`` stand-in — only carries ``deps``."""

    deps: WorkflowDeps


def make_deps(
    *,
    project_root: str,
    allowed_executables: list[str] | None = None,
    run_id: str = "run-test",
) -> WorkflowDeps:
    """Build a :class:`WorkflowDeps` with defaults suitable for tool tests."""
    return WorkflowDeps(
        run_id=run_id,
        workflow_id="wf-test",
        component="worker",
        tier="local_coder",
        allowed_executables=list(allowed_executables or []),
        project_root=project_root,
    )


@pytest.fixture
def ctx_factory():
    """Return a factory that builds :class:`CtxShim` instances for each test."""

    def _make(
        *,
        project_root: str,
        allowed_executables: list[str] | None = None,
        run_id: str = "run-test",
    ) -> CtxShim:
        return CtxShim(
            deps=make_deps(
                project_root=project_root,
                allowed_executables=allowed_executables,
                run_id=run_id,
            )
        )

    return _make
