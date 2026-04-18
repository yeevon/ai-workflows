# Task 01 — Project Scaffolding — Audit Issues

**Source task:** [../task_01_project_scaffolding.md](../task_01_project_scaffolding.md)
**Audited on:** 2026-04-18
**Audit scope:** full project (pyproject.toml, package tree, scaffolding
files, tests, CI, CHANGELOG).
**Status:** functional — gates green (21/21 pytest, `lint-imports`
2 kept / 0 broken, `ruff check` clean, CI secret-scan verified), but one
acceptance criterion is technically unmet due to a spec-level bug.

---

## 🔴 HIGH — Contract 3 cannot be expressed in import-linter

**Acceptance criterion violated:** task spec line
`uv run lint-imports passes with all three contracts above`.

**Spec says:**

```toml
[[tool.importlinter.contracts]]
name = "components cannot peek at each other's private state"
type = "forbidden"
source_modules = ["ai_workflows.components.*"]
forbidden_modules = ["ai_workflows.components.*._*"]
```

**Reality:** import-linter 2.11 rejects this at load time:

```text
Contract "components cannot peek at each other's private state" is not
configured correctly:
    forbidden_modules: A wildcard can only replace a whole module.
```

The wildcard syntax only accepts `*` as a full segment substitute, so
`components.*._*` (partial-prefix matching) is not a supported pattern.

**Current state:** contract 3 is commented out in `pyproject.toml`. The
scaffolding test asserts `>= 2` contracts, not `== 3`, and documents the
deferral.

**Options to resolve:**

1. **Enumerate private modules.** Once M2 Task 01 lands `BaseComponent`,
   each component that exposes private modules names them explicitly in
   the contract. Downside: every new private module needs a pyproject edit.
2. **Custom contract via AST test.** Write a pytest that walks
   `ai_workflows.components.*` ASTs and flags any import of a sibling
   component's underscore-prefixed module. Downside: not enforceable at
   package build / CI lint-only stage without a dedicated entry point.
3. **Pre-commit regex hook.** Quick but brittle.
4. **Drop the rule.** If the underscore-prefix convention is considered
   soft discipline, remove the criterion from the spec and rely on code
   review.

**Recommendation:** (2) — ship a pytest-based contract in M2 Task 01 so
the rule is enforced on every run. Update this task's spec to mark
criterion 3 as *deferred to M2 Task 01, tracked in
`tests/components/test_private_module_discipline.py`*.

**Action:** update
[task_01_project_scaffolding.md](../task_01_project_scaffolding.md) to
remove the "three contracts" claim or cross-reference the M2 Task 01
enforcement mechanism.

---

## 🟡 MEDIUM — `docs/` directory not created

**Spec directory tree includes:**

```text
└── docs/
    ├── architecture.md
    ├── writing-a-component.md
    └── writing-a-workflow.md
```

Not in acceptance criteria, but listed as a deliverable in the task's
"Directory Structure" section. Currently absent. Later tasks reference
`docs/` as the canonical location for cross-cutting documentation; if the
convention is not established now, it drifts to ad-hoc `design_docs/`
additions.

**Action:** create `docs/architecture.md`, `docs/writing-a-component.md`,
`docs/writing-a-workflow.md` as placeholder stubs explicitly marked "to be
authored by M1 Task 11 / M2 Task 01 / M3 Task 01" so future tasks have a
known landing spot.

---

## 🟢 LOW — Per-module stub files not created

Spec tree enumerates concrete `.py` files inside `primitives/` (types.py,
model_factory.py, caching.py, registry.py, forensic_logger.py, fs.py,
shell.py, http.py, git.py, tiers.py, workflow_hash.py, storage.py,
cost.py, retry.py, logging.py).

Each is annotated with the task number that lands it. Reading in context,
these are **forward-looking markers** in the tree — not Task 01 empty
stubs. Current `__init__.py` docstrings already forward-declare the
modules.

**Action:** none required. Flagging only so no future audit mistakes the
absence for regression.

---

## 🟢 LOW — `tests/{primitives,components,workflows}/__init__.py` absent

Spec tree shows three test subdirectories. They exist but lack
`__init__.py`. Pytest discovers tests without them, so this is fine
unless we later move to explicit package-style test layout.

**Action:** none required.

---

## 🟢 LOW — `README.md` left as placeholder

14-byte file (`# ai-workflows`). Not a Task 01 deliverable. Flagging so
it gets picked up by M3 Task 01 or whoever adds the first user-facing
quickstart.

**Action:** none required for Task 01.

---

## Additions beyond spec — audited and justified

All of these are required for CI / tests / build to pass given the
spec's own acceptance criteria. None is a scope creep concern.

| Addition                                | Required by                          |
| --------------------------------------- | ------------------------------------ |
| `[dependency-groups].dev`               | CI calls `lint-imports`, `ruff`      |
| `[tool.ruff]` section                   | CI calls `ruff check`                |
| `[tool.hatch.build.targets.wheel]`      | hatchling needs an explicit package  |
| `_root` Typer callback                  | Keeps `aiw --help` surface on single-command app |
| `aiw version` subcommand                | Gives Typer something real to expose |
| `CHANGELOG.md`                          | User-requested, not in spec          |

---

## Gate summary

| Gate                        | Status                                    |
| --------------------------- | ----------------------------------------- |
| `uv sync` resolves          | ✓                                         |
| `uv run pytest`             | ✓ — 21/21                                 |
| `uv run lint-imports`       | ✓ — 2 kept / 0 broken (third deferred)    |
| `uv run ruff check`         | ✓                                         |
| `import ai_workflows.primitives` | ✓                                    |
| `aiw --help`                | ✓                                         |
| CI secret-scan on planted key | ✓ — manually verified                   |

## Issue log — tracked for cross-task follow-up

- **M1-T01-ISS-01** (HIGH) — import-linter contract 3 cannot be
  expressed; pick enforcement strategy and update task spec. Owner:
  picked up by M2 Task 01.
- **M1-T01-ISS-02** (MEDIUM) — `docs/` directory placeholders. Owner:
  whoever next touches cross-cutting docs.
- **M1-T01-ISS-03** (LOW) — flesh out `README.md`. Owner: M3 Task 01.
