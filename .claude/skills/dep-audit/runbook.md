# dep-audit runbook

The runbook details wheel-contents inspection — the file allowlist (`ai_workflows/`, `migrations/`, `*.dist-info/`) and denylist (`.env*`, `design_docs/`, `runs/`, `*.sqlite3`).
It documents dep-manifest change-detection — `git diff --exit-code <pre-task>..HEAD -- pyproject.toml uv.lock` semantics and the trigger threshold for the dep-audit gate.
It describes lockfile-diff inspection — `git diff <pre-task-commit>..HEAD -- uv.lock` parsing patterns for `+` added/upgraded and `-` removed/downgraded entries.

## Wheel-contents

Run `uv build` then `unzip -l dist/*.whl` to inspect the wheel archive.

**Allowlist** — the wheel MUST contain (and nothing else):

- `ai_workflows/` and its subpackages (primitives, graph, workflows, mcp, cli, evals)
- `migrations/` (top-level; six SQL migration files)
- `*.dist-info/` (metadata directory carrying METADATA, RECORD, WHEEL, entry_points.txt, and licenses/LICENSE)

**Denylist** — HALT immediately if any of these appear in `unzip -l` output:

| Pattern | Risk |
|---|---|
| `.env*` | API keys / secrets leaked to PyPI consumers |
| `design_docs/` | Internal specs leaked |
| `runs/` | Checkpoint data / run history leaked |
| `*.sqlite3` | Checkpoint databases leaked |
| `.claude/` | Agent prompts / skills leaked |
| `htmlcov/` | Coverage HTML reports bloat the wheel |
| `.coverage` | Coverage data file |
| `.pytest_cache/` | Test cache artifacts |
| `dist/` | Nested dist directory (recursive build artifact) |
| `.github/` | CI configuration leaked |

**Verdict thresholds:** any denylist hit is BLOCK (pre-publish). Missing allowlist entry is HIGH.

Example clean output:
```
Archive:  dist/jmdl_ai_workflows-0.3.1-py3-none-any.whl
  Length      Date    Time    Name
---------  ---------- -----   ----
     ...   ...        ...     ai_workflows/__init__.py
     ...   ...        ...     ai_workflows/cli.py
     ...   ...        ...     migrations/001_initial.sql
     ...   ...        ...     jmdl_ai_workflows-0.3.1.dist-info/METADATA
```

## Dep-detection

Invoke: `git diff --exit-code <pre-task-commit>..HEAD -- pyproject.toml uv.lock`

Exit-code semantics:

- Exit 0 / empty stdout — no manifest changes; dep-audit gate does NOT fire.
- Exit 1 / any stdout lines — changes detected; spawn the `dependency-auditor` agent.

The `<pre-task-commit>` is the SHA recorded at task kickoff (e.g. the `pre_task_commit` field in the task input or the orchestrator's pre-flight log). When no pre-task SHA is available, use `HEAD~1`.

Watch for:

- New entries under `[project.dependencies]` or `[project.optional-dependencies.dev]`.
- Version specifier changes (`>=1.0` → `>=2.0`).
- Any `uv.lock` hash-line change (indicates a transitive dep bump even if `pyproject.toml` is unchanged).

## Lockfile-diff

Invoke: `git diff <pre-task-commit>..HEAD -- uv.lock`

Parsing patterns (standard git-diff format):

- Lines starting with `+` — newly added or upgraded package versions.
- Lines starting with `-` — removed or downgraded package versions.
- A `- pkg==old` / `+ pkg==new` pair — version bump; compare major.minor for breaking-change risk.

Example output snippet:
```
- langgraph==0.2.14
+ langgraph==0.2.19
```

Triage rule: same-major bumps with upstream changelog entries are Advisory. Cross-major bumps or new transitive deps with no prior history are High — spawn the full `dependency-auditor` agent.
