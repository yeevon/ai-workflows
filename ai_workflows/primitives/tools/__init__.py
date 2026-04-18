"""Tool primitives — the registry, forensic logger, and stdlib tools.

Modules (filled in by later M1 tasks):

* ``registry`` (Task 05) — the injected tool registry. Components receive a
  registry instance rather than importing tool functions directly; this
  keeps tool wiring explicit and testable.
* ``forensic_logger`` (Task 05) — wraps every tool invocation, recording
  inputs, outputs, duration, and errors to the run's log directory. This is
  a logging/audit aid only; it is **not** a security boundary (see CRIT-04
  in ``design_docs/issues.md``).
* ``fs``, ``shell``, ``http``, ``git`` (Task 06) — the standard library of
  tools available to every workflow unless explicitly excluded.
"""
