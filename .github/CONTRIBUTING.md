# Contributing to ai-workflows

Development happens on the **`design_branch`**. `main` is the release branch
— only user-facing surfaces land here (source, tests, `docs/`, `README.md`,
`CHANGELOG.md`, packaging metadata). The builder/auditor workflow, task
specs, audit issue files, ADRs, and architecture of record live on the
[`design_branch`](https://github.com/yeevon/ai-workflows/tree/design_branch).

Clone, switch to `design_branch`, and follow the Builder / Auditor mode
conventions in
[`CLAUDE.md`](https://github.com/yeevon/ai-workflows/blob/design_branch/CLAUDE.md).

> **PR direction:** `design_branch → main`, per-task at milestone close-out.
> Never the reverse — `main` must not accumulate builder artefacts.
