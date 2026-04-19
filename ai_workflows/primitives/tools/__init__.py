"""Tool primitives — the registry, forensic logger, and stdlib tools.

Modules:

* :mod:`~ai_workflows.primitives.tools.registry` (Task 05) — the injected
  :class:`~ai_workflows.primitives.tools.registry.ToolRegistry`. Components
  receive a registry instance rather than importing tool functions directly;
  this keeps tool wiring explicit, testable, and per-component scoped
  (Anthropic subagent pattern).
* :mod:`~ai_workflows.primitives.tools.forensic_logger` (Task 05) — scans
  tool outputs for known prompt-injection marker patterns and emits a
  structlog ``WARNING`` event for post-hoc review. **Not** a security
  boundary; see CRIT-04 in ``design_docs/issues.md``. The real defences are
  ``ContentBlock`` ``tool_result`` wrapping, the per-component tool
  allowlists enforced by the registry, ``run_command`` CWD restriction, and
  ``HumanGate``.
* ``fs``, ``shell``, ``http``, ``git`` (Task 06) — the standard library of
  tools available to every workflow unless explicitly excluded.
"""
