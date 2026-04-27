# Adoption checklist

Walk this top-to-bottom when adopting the template into a new project.

## 1. Copy the files

```bash
cp -r template/infrastructure/* <new-project-root>/
cp -r template/.claude <new-project-root>/.claude
cp template/CLAUDE.md.template <new-project-root>/CLAUDE.md
```

Make `infrastructure/sandbox-entrypoint.sh` executable: `chmod +x <new-project-root>/scripts/sandbox-entrypoint.sh` (relocate from `infrastructure/` to `scripts/` if you keep that convention).

## 2. Decide your placeholder values

Every `<PLACEHOLDER>` token in the agent + command files maps to a specific decision your project must make. Fill these in once, then `sed` or hand-edit through the files.

| Token | What it is | Example value |
| --- | --- | --- |
| `<PROJECT_NAME>` | Short project name | `myproject` |
| `<PACKAGE_NAME>` | Package name as published / consumed | `acme-myproject` |
| `<PROJECT_ROOT>` | Absolute path the container will bind-mount the repo at. Match the host path so cwd-based hashes (Claude Code auto-memory) line up. | `/home/<you>/prj/myproject` |
| `<USER_HOME>` | Host `$HOME` of the operator. | `/home/<you>` |
| `<USER_UID>` | Host UID owning the repo (run `id -u` on the host). | `1000` |
| `<USER_GID>` | Host GID. | `1000` |
| `<DESIGN_BRANCH>` | Branch where autonomous commits land. Never `main`. | `design_branch` |
| `<MAIN_BRANCH>` | Release branch the autonomy must NEVER touch. | `main` |
| `<KDR_LIST>` | Your project's load-bearing architectural rules. Replace the seven KDRs in the auditor / builder / task-analyzer files. | "KDR-001 (no anthropic SDK), KDR-002 (..." |
| `<LAYER_RULE>` | Module / package layer rule, if any. | `primitives → graph → workflows → surfaces` |
| `<GATE_COMMANDS>` | Whatever your test / lint / typecheck commands are. | `pytest`, `ruff check`, `mypy` |
| `<RELEASE_COMMAND>` | Publish operation that must NEVER run in autonomy. | `uv publish`, `npm publish`, etc. |
| `<DEPLOYMENT_SHAPE>` | One-line summary for the security-reviewer's threat model. | "single-user local + published PyPI wheel" |
| `<MEMORY_PATH_HASH>` | Hash of the bind-mount cwd. Compute: `echo "$<PROJECT_ROOT>" \| tr / -`. | `-home-<you>-prj-myproject` |
| `<SPEC_DIR>` | Where per-task spec files live. | `design_docs/phases/milestone_<N>_<name>/task_<NN>_<slug>.md` |
| `<MILESTONE_README>` | Path pattern for milestone overview. | `design_docs/phases/milestone_<N>_<name>/README.md` |
| `<ISSUE_FILE>` | Where audit issue files land. | `design_docs/phases/milestone_<N>_<name>/issues/task_<NN>_issue.md` |
| `<TASK_ANALYSIS>` | Where task-analyzer writes its report. | `design_docs/phases/milestone_<N>_<name>/task_analysis.md` |
| `<NICE_TO_HAVE>` | Deferred-parking-lot file. | `design_docs/nice_to_have.md` |
| `<ARCHITECTURE_DOC>` | Architecture-of-record. | `design_docs/architecture.md` |
| `<ROADMAP>` | Milestone index. | `design_docs/roadmap.md` |

A `find . -type f -name '*.md' -exec grep -l '<' {} +` will surface every placeholder file at once.

## 3. Bootstrapping a new project (no existing specs)

If the project doesn't have an established spec layout, the minimum to make the autonomy loop functional:

1. Create `design_docs/architecture.md` — list 3-7 load-bearing rules ("KDRs"). Each rule names a failure mode, a locked pattern, and the alternative considered.
2. Create `design_docs/nice_to_have.md` — empty parking lot for deferred ideas.
3. Create `design_docs/roadmap.md` — milestone index.
4. Create at least one `design_docs/phases/milestone_<N>_<name>/README.md` with: "Why this exists", a Goals list, an Exit Criteria list, and a Task Order table.
5. Create `<DESIGN_BRANCH>` branch. Set `git config branch.<DESIGN_BRANCH>.merge` etc. as needed.
6. Add `runs/` to `.gitignore` with a `!runs/.gitkeep` exception so the bind-mount target survives.
7. Add `.claude/settings.local.json` to `.gitignore` (Claude Code rewrites it; not a project artifact).

After these, `/queue-pick` will return `NEEDS-CLEAN-TASKS <milestone>` and you can drive `/clean-tasks` to generate the task spec files from the README.

## 4. Container readiness

```bash
make build                    # builds image with non-root user matching host UID/GID
make sync                     # populates the venv volume
make test                     # confirms gates pass inside the sandbox
make lint                     # confirms layer / style rules pass
make smoke                    # runs your project's release smoke if defined
```

If `make sync` fails on permission errors, the entrypoint chown step has a path mismatch; see `infrastructure/sandbox-entrypoint.sh` and add the failing path.

## 5. Claude Code authentication inside the container

```bash
make shell                    # bash inside the container
claude /login                 # one-time OAuth (device-code flow opens a URL on host browser)
```

The container's `~/.claude/.persisted-claude-json` (in the named volume) holds session state via a symlink the entrypoint sets up — auth survives container restarts.

## 6. Settings

`.claude/settings.local.json` is gitignored and operator-local. The `.example` file in the template is a starting point. The two load-bearing fields:

- `permissions.defaultMode: "bypassPermissions"` — autonomy mode requires bypass; without it every Bash invocation prompts.
- `permissions.additionalDirectories: [...]` — directories Claude Code may touch without per-dir trust prompts.

The `deny` list at the bottom is **defense-in-depth** — it hard-blocks `git push origin main`, `uv publish`, `git tag`, etc. at the harness level, even if a sub-agent prompt-level halt fails.

## 7. First run

```bash
make shell                    # inside the container
claude                        # bypass mode applies automatically
> /autopilot                  # autonomous queue drain
```

Watch for the per-iteration one-liner. If anything halts unexpectedly, the recommendation file under `runs/autopilot-*.md` and the audit issue file under `<ISSUE_FILE>` carry the reasoning.

## 8. Memory file initialization

Claude Code's auto-memory directory is hashed off the cwd. The first conversation in the project creates it at `<USER_HOME>/.claude/projects/<MEMORY_PATH_HASH>/memory/`. Add a `MEMORY.md` index there and optionally seed with feedback / project memos. The roadmap-selector and other agents read it to surface context that isn't in the codebase (deferred milestones, on-hold flags, return triggers).

A first memo every project should have:

```markdown
# autonomous_mode_boundaries.md
---
type: feedback
description: Hard boundaries for the autonomy sandbox.
---
1. Auto-push to <DESIGN_BRANCH> only. HARD HALT on <MAIN_BRANCH>, releases, tags.
2. KDR additions land on isolated commits.
3. Sub-agent disagreement = halt, user arbitrates.
4. Queue universe is every milestone in <SPEC_DIR>; no enumerated allow-list.
5. User auths Claude inside the container; host credentials NOT bind-mounted.
6. Cost ceiling per project policy.
7. Host-side services (Ollama, etc.) reachable as host.docker.internal.
8. Auto-memory persists between host and container.
```

## 9. Iterate

Run `/autopilot` overnight. The morning audit:

- `git log --oneline origin/<DESIGN_BRANCH>` — count + diff each new commit.
- `<ISSUE_FILE>` per shipped task — read the team's verdicts.
- `runs/autopilot-*.md` — read each iteration's reasoning.

Tune the prompts where the trash showed up. Re-run.
