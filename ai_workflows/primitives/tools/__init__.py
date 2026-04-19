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
* :mod:`~ai_workflows.primitives.tools.fs` (Task 06) — ``read_file``,
  ``write_file``, ``list_dir``, ``grep``. UTF-8 with latin-1 fallback,
  entry caps, and truncation markers.
* :mod:`~ai_workflows.primitives.tools.shell` (Task 06) — ``run_command``
  gated by CWD containment, executable allowlist, dry-run, and timeout
  guards. Never raises to the LLM.
* :mod:`~ai_workflows.primitives.tools.http` (Task 06) — ``http_fetch``,
  one tool for every HTTP method.
* :mod:`~ai_workflows.primitives.tools.git` (Task 06) — ``git_diff``,
  ``git_log``, ``git_apply``. ``git_apply`` refuses on a dirty tree.
* :mod:`~ai_workflows.primitives.tools.stdlib` (Task 06) — the
  :func:`register_stdlib_tools` helper that binds every stdlib callable
  onto a :class:`ToolRegistry` at workflow load time.
"""
