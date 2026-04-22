# Task 01 — `pyproject.toml` polish + wheel contents fix

**Status:** 📝 Planned (drafted 2026-04-21).
**Grounding:** [milestone README](README.md) · [architecture.md §6](../../architecture.md) · [pyproject.toml:5-43](../../../pyproject.toml).

## What to Build

Two edits in `pyproject.toml` and one new hermetic test. The milestone's two shipping-blockers (PyPI listing metadata + wheel missing `migrations/`) close here.

## Deliverables

### [pyproject.toml](../../../pyproject.toml) — `[project]` metadata

Add under `[project]` (do not reorder existing keys):

- `authors = [{name = "Jose de Lima", email = "delimajm@gmail.com"}]`.
- `urls.Homepage = "https://github.com/yeevon/ai-workflows"`.
- `urls.Repository = "https://github.com/yeevon/ai-workflows"`.
- `urls.Issues = "https://github.com/yeevon/ai-workflows/issues"`.
- `keywords = ["langgraph", "mcp", "claude-code", "ai-workflow", "litellm", "ollama"]`.
- `classifiers`:
  - `"Development Status :: 3 - Alpha"`
  - `"Intended Audience :: Developers"`
  - `"License :: OSI Approved :: MIT License"`
  - `"Operating System :: OS Independent"`
  - `"Programming Language :: Python :: 3"`
  - `"Programming Language :: Python :: 3.12"`
  - `"Topic :: Software Development :: Libraries"`

No dependency change. No version bump. Do not add `[project.optional-dependencies]`.

### [pyproject.toml](../../../pyproject.toml) — `[tool.hatch.build.targets.wheel]` — bundle `migrations/`

Today's block ([pyproject.toml:42-43](../../../pyproject.toml#L42-L43)):

```toml
[tool.hatch.build.targets.wheel]
packages = ["ai_workflows"]
```

sweeps `ai_workflows/` only. The `migrations/` directory at repo root is silently omitted from the wheel. `yoyo-migrations` (declared at [pyproject.toml:23](../../../pyproject.toml#L23)) is unusable from a `site-packages` install because it reads from a path the wheel never shipped — every first-run `aiw` / `aiw-mcp` invocation against a `uvx` / `uv tool install` wheel would fail with a yoyo "no migration scripts found" equivalent.

Fix: `force-include` `migrations/` into the wheel under a `migrations/` top-level path. Exact shape:

```toml
[tool.hatch.build.targets.wheel]
packages = ["ai_workflows"]

[tool.hatch.build.targets.wheel.force-include]
"migrations" = "migrations"
```

`force-include` is hatchling's canonical hook for data dirs that sit outside the package tree. Do **not** move `migrations/` under `ai_workflows/` — that would conflict with the four-layer import contract (migrations are data, not a primitive-layer module) and would drag the yoyo runtime discovery path into `ai_workflows/` with no benefit.

### Storage layer — locate bundled `migrations/`

Verify that the existing Storage open path works from a wheel install. [`ai_workflows/primitives/storage.py`](../../../ai_workflows/primitives/storage.py) presumably locates `migrations/` via a relative path from repo root; that path resolves under `uv run` (cwd is the repo) but **will not** resolve under a `site-packages` install. The fix has two shapes, pick the one that matches the current code:

1. If Storage already uses `importlib.resources` or a `pathlib.Path(__file__).parent` walk-up — confirm the walk-up lands on the `site-packages/migrations/` that `force-include` produces. Test covers this.
2. If Storage uses a hardcoded `Path("migrations")` relative to cwd — rewrite to an `importlib.resources.files(...)`-based resolution that reads `migrations/` as a packaged data directory. Update `primitives/storage.py` accordingly.

**Do not** ship `migrations/` under `ai_workflows/migrations/` to make the lookup easier — that breaks the layout contract. Keep `migrations/` at repo root (the source-of-truth location) and let `force-include` + `importlib.resources` handle the lookup.

### [tests/test_wheel_contents.py](../../../tests/test_wheel_contents.py) — new hermetic test

One test file, two tests:

1. **`test_built_wheel_includes_migrations`** — in a `tmp_path`, run `uv build --wheel --out-dir <tmp>` as a subprocess, find the produced `.whl`, open it as a zipfile, assert `migrations/001_initial.sql` and `migrations/002_reconciliation.sql` are both present as archive entries.
2. **`test_built_wheel_includes_ai_workflows_package`** — against the same wheel, assert `ai_workflows/__init__.py` + `ai_workflows/primitives/storage.py` are present. Sanity guard so the `force-include` edit does not regress the `packages = ["ai_workflows"]` sweep.

The test is **hermetic** — `uv build` runs against the committed source tree, no network, no provider call. Runs in the default `uv run pytest` suite. If `uv build` is not available in the test environment, skip the test with a `pytest.skip("uv CLI not available")` (matching the e2e-smoke skip pattern); CI always has `uv` on PATH.

### [CHANGELOG.md](../../../CHANGELOG.md)

Under `## [Unreleased]`, add a `### Changed — M13 Task 01: pyproject polish + wheel migrations bundle (YYYY-MM-DD)` entry. List:

- Files touched: `pyproject.toml` (authors/urls/classifiers/keywords + hatchling force-include for `migrations/`), `ai_workflows/primitives/storage.py` (if migration-path lookup changed), `tests/test_wheel_contents.py` (new).
- ACs satisfied.
- Explicit note: **no runtime behaviour change** — this task makes the published wheel usable; does not alter a running-from-repo workflow.

## Acceptance Criteria

- [ ] `pyproject.toml [project]` contains `authors`, `urls.Homepage`, `urls.Repository`, `urls.Issues`, `keywords`, `classifiers` per the spec above.
- [ ] `pyproject.toml [tool.hatch.build.targets.wheel.force-include]` maps `migrations` → `migrations`.
- [ ] `uv build --wheel` produces a wheel whose archive includes `migrations/001_initial.sql` and `migrations/002_reconciliation.sql`.
- [ ] Storage layer resolves `migrations/` correctly when imported from a wheel install (verified via the new test suite + manual unzip).
- [ ] `tests/test_wheel_contents.py` lands with both tests green.
- [ ] No dependency change. No version bump. `[project.version]` stays `0.1.0`.
- [ ] No diff under `ai_workflows/workflows/`, `ai_workflows/mcp/`, `ai_workflows/graph/` (T01 is pure packaging metadata + one possible storage-path lookup fix).
- [ ] `uv run pytest` + `uv run lint-imports` (4 contracts kept) + `uv run ruff check` all clean.
- [ ] CHANGELOG entry under `[Unreleased]` lists files + ACs + the "no runtime behaviour change" note.

## Dependencies

- None. T01 is the foundation. T02 (clean-venv install smoke) consumes the wheel T01 makes shippable.

## Out of scope (explicit)

- **No PyPI upload.** Lands at T04.
- **No README install section.** Lands at T03.
- **No `uvx`-variant of the Claude Code skill install.** Lands at T03.
- **No CHANGELOG `[0.1.0]` release section.** Lands at T04.
- **No version bump.** `0.1.0` is the target — T01 just makes the artefact publishable, the `0.1.0` header in CHANGELOG is T04's.
- **No `[project.optional-dependencies]` groups** (e.g. `[dev]`, `[observability]`). None of the four layers need an extras-gated dep at M13.
- **No new CI job.** The wheel-contents test is in the default hermetic suite; release smoke (T02) stays a manual script.

## Propagation status

Filled in at audit time. Anticipated forward-deferrals: none — T01 is narrow. If the audit surfaces a storage-path lookup pattern that needs refactoring beyond the minimal `importlib.resources` fix, log as a `nice_to_have.md` candidate with trigger "a second Storage consumer needs the migrations path at a different resolution order".
