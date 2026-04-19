"""Per-workflow tool registry.

Produced by M1 Task 05 (P-11, P-20). The :class:`ToolRegistry` is **injected
per workflow run** — never a singleton — and serves two jobs:

1. It is the single source of truth for which callables are exposed as tools.
   Components receive a registry instance rather than importing tool
   functions directly; this keeps tool wiring explicit and testable.
2. It enforces **per-component tool scoping** (Anthropic's subagent pattern):
   a Worker declaring ``tools: [read_file, grep]`` in its config gets exactly
   those two tools — never the full registry. The scoping happens inside
   :meth:`ToolRegistry.build_pydantic_ai_tools`.

Tool execution flow
-------------------
When pydantic-ai calls a registry-built tool:

1. pydantic-ai invokes the wrapped callable returned by
   :meth:`build_pydantic_ai_tools`.
2. The wrapper calls the original (registered) callable and captures its raw
   output.
3. The wrapper passes the stringified output to
   :func:`ai_workflows.primitives.tools.forensic_logger.log_suspicious_patterns`
   — logging only, **no mutation**.
4. The raw output is returned to pydantic-ai, which packages it into its
   internal message format (which maps to our :class:`ToolResultBlock`
   semantics). The ``tool_result`` wrapping — the *actual* defence against
   prompt injection — happens at this layer, by virtue of the pydantic-ai
   protocol. See CRIT-04.

Related
-------
* :mod:`ai_workflows.primitives.tools.forensic_logger` — the logger this
  registry hooks into on every tool call.
* :mod:`ai_workflows.primitives.llm.types` — :class:`WorkflowDeps` carries
  ``run_id``, which the wrapper lifts out of ``RunContext`` and forwards to
  the forensic logger.
"""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic_ai import Tool

from ai_workflows.primitives.tools.forensic_logger import log_suspicious_patterns

__all__ = ["ToolRegistry", "ToolAlreadyRegisteredError", "ToolNotRegisteredError"]


class ToolAlreadyRegisteredError(ValueError):
    """Raised when :meth:`ToolRegistry.register` is called with a duplicate name.

    Overwriting an existing registration is an unambiguous programmer error —
    a workflow almost never *wants* two different callables under the same
    tool name. Fail loudly instead of silently shadowing.
    """


class ToolNotRegisteredError(KeyError):
    """Raised when a caller asks for a tool that was never registered.

    Used by :meth:`ToolRegistry.get_tool_callable` and
    :meth:`ToolRegistry.build_pydantic_ai_tools`. Subclasses :class:`KeyError`
    so the idiomatic ``except KeyError`` also catches it.
    """


@dataclass(frozen=True)
class _Entry:
    """Internal record for a registered tool — callable plus description."""

    fn: Callable[..., Any]
    description: str


class ToolRegistry:
    """Injected per workflow run. Not a singleton.

    Register callables with :meth:`register`; retrieve them either as raw
    callables (:meth:`get_tool_callable`) or as a scoped list of
    ``pydantic_ai.Tool`` instances (:meth:`build_pydantic_ai_tools`).

    Each instance owns its own storage — there is **no module-level state**
    and no class-level dict. Two ``ToolRegistry()`` instances in the same
    process share nothing; this is tested as AC-1 of M1 Task 05.
    """

    def __init__(self) -> None:
        self._entries: dict[str, _Entry] = {}

    def register(
        self,
        name: str,
        fn: Callable[..., Any],
        description: str,
    ) -> None:
        """Register ``fn`` under ``name`` with a human-readable ``description``.

        The description is forwarded to ``pydantic_ai.Tool(..., description=)``
        so the model sees it in the tool schema. ``fn`` may be sync or async;
        it may optionally take ``ctx: RunContext[WorkflowDeps]`` as its first
        positional parameter (pydantic-ai auto-detects this).

        Raises
        ------
        ToolAlreadyRegisteredError
            If ``name`` is already registered on *this* instance.
        ValueError
            If ``name`` is empty or ``description`` is empty.
        """
        if not name:
            raise ValueError("Tool name must be a non-empty string.")
        if not description:
            raise ValueError(f"Tool {name!r} must be registered with a non-empty description.")
        if name in self._entries:
            raise ToolAlreadyRegisteredError(
                f"Tool {name!r} is already registered on this ToolRegistry instance."
            )
        self._entries[name] = _Entry(fn=fn, description=description)

    def get_tool_callable(self, name: str) -> Callable[..., Any]:
        """Return the raw callable registered under ``name`` (no forensic wrapping).

        Used by call sites that need direct access — e.g. unit tests, replay
        harnesses. Production call sites should almost always go through
        :meth:`build_pydantic_ai_tools` so the forensic logger is in the path.

        Raises
        ------
        ToolNotRegisteredError
            If ``name`` was never registered.
        """
        entry = self._entries.get(name)
        if entry is None:
            raise ToolNotRegisteredError(
                f"Tool {name!r} is not registered. "
                f"Registered tools: {sorted(self._entries)!r}."
            )
        return entry.fn

    def registered_names(self) -> list[str]:
        """Return the sorted list of names currently registered on this instance.

        Convenience for diagnostics, logging, and the ``aiw`` CLI. Does not
        mirror the insertion order — sorted for deterministic output.
        """
        return sorted(self._entries)

    def build_pydantic_ai_tools(self, names: list[str]) -> list[Tool]:
        """Return ``pydantic_ai.Tool`` instances for **only** the named tools.

        This is the scoping boundary: a Worker config declaring
        ``tools: [read_file, grep]`` yields exactly two ``Tool`` instances
        here, never the full registry. Pass the result to
        ``Agent(tools=build_pydantic_ai_tools([...]))``.

        Every returned ``Tool`` wraps its callable so the output passes
        through :func:`forensic_logger.log_suspicious_patterns` after the tool
        returns — logging only, no mutation of the value that reaches the
        model.

        Parameters
        ----------
        names:
            Tool names to expose, in call order. Duplicates are rejected; an
            empty list returns an empty result (legal — a component may
            legitimately have no tools).

        Raises
        ------
        ToolNotRegisteredError
            If any name in ``names`` is absent from the registry. The error
            message lists every missing name so the caller can fix the config
            in one pass.
        ValueError
            If ``names`` contains duplicates.
        """
        duplicates = sorted({n for n in names if names.count(n) > 1})
        if duplicates:
            raise ValueError(
                f"build_pydantic_ai_tools() called with duplicate names: {duplicates!r}."
            )
        missing = [n for n in names if n not in self._entries]
        if missing:
            raise ToolNotRegisteredError(
                f"Tool(s) {missing!r} not registered. "
                f"Registered tools: {sorted(self._entries)!r}."
            )
        return [
            Tool(
                _wrap_with_forensics(name, self._entries[name].fn),
                name=name,
                description=self._entries[name].description,
            )
            for name in names
        ]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _wrap_with_forensics(tool_name: str, fn: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap ``fn`` so its output is passed through the forensic logger.

    The wrapper:

    * Preserves ``fn``'s original signature (via :func:`functools.wraps`) so
      pydantic-ai's JSON-schema generator still sees the intended parameter
      names and type hints.
    * Supports both sync and async callables; the returned wrapper matches
      the original's sync/async-ness.
    * Extracts ``run_id`` from the first positional argument when that
      argument is a ``RunContext`` (pydantic-ai's convention for tools that
      opt into context). When the tool does not take a context, ``run_id``
      is logged as ``"unknown"`` — the forensic entry is still useful for
      post-hoc review.
    * **Never mutates the return value.** The output is stringified *only*
      for the logger; the original object is returned to the caller.

    Private to this module — call via
    :meth:`ToolRegistry.build_pydantic_ai_tools`.
    """
    sig = inspect.signature(fn)
    params = list(sig.parameters.values())
    takes_ctx = bool(params) and params[0].name == "ctx"

    if inspect.iscoroutinefunction(fn):

        @functools.wraps(fn)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            result = await fn(*args, **kwargs)
            run_id = _extract_run_id(args, takes_ctx)
            log_suspicious_patterns(tool_name=tool_name, output=str(result), run_id=run_id)
            return result

        return async_wrapper

    @functools.wraps(fn)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        result = fn(*args, **kwargs)
        run_id = _extract_run_id(args, takes_ctx)
        log_suspicious_patterns(tool_name=tool_name, output=str(result), run_id=run_id)
        return result

    return sync_wrapper


def _extract_run_id(args: tuple[Any, ...], takes_ctx: bool) -> str:
    """Return ``ctx.deps.run_id`` when a context is present, else ``"unknown"``.

    The pydantic-ai ``RunContext`` carries ``deps`` as a public attribute; our
    :class:`~ai_workflows.primitives.llm.types.WorkflowDeps` puts ``run_id``
    directly on ``deps``. If anything in that chain is missing (unusual
    calling pattern, test shim, …), fall through to ``"unknown"`` rather than
    crashing — the forensic log line should always be emitted when a pattern
    matches.
    """
    if not takes_ctx or not args:
        return "unknown"
    ctx = args[0]
    deps = getattr(ctx, "deps", None)
    run_id = getattr(deps, "run_id", None)
    return run_id if isinstance(run_id, str) and run_id else "unknown"
