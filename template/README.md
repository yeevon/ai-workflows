# Claude Code Autonomy Template

A drop-in scaffolding for building an **autonomous coding workflow** on top of [Claude Code](https://code.claude.com). It gives you:

- A **Docker sandbox** that isolates the autonomous loop from your host (no rogue `git push origin main`, no accidental package publish).
- A **9-agent review team** (builder, auditor, security, dependency, sr-dev, sr-sdet, architect, roadmap-selector, task-analyzer) plus a single-purpose split that mirrors how a senior engineering org reviews a PR.
- **6 slash commands** that compose the team into loops:
  - one-shot review (`/queue-pick`)
  - spec hardening (`/clean-tasks`)
  - manual implement (`/clean-implement`)
  - autonomous implement (`/auto-implement`)
  - autonomous queue drain (`/autopilot`)
  - plus single-step `/implement` and `/audit` for ad-hoc work
- **Halt boundaries** on every commit: no `main`, no publish, no scope creep, no team disagreement bypass.
- **Persistent memory** between host and container so context survives restarts.

This template is **structure, not content.** The infrastructure files (Dockerfile, Makefile, etc.) are runnable as-is. The agent and command files are skeletons — you fill in the project-specific parts (KDRs / decision records, layer rules, deployment shape, gate commands) marked with `<PLACEHOLDER>` tokens.

## What this is not

- It is not a framework that runs your code. It runs Claude Code, which runs sub-agents, which read your specs and write your code.
- It does not assume any particular language. The infrastructure favors Python (uv, pytest), but every agent and command is language-neutral; replace gate commands with whatever your stack uses.
- It does not assume any particular deployment shape. Defaults are tuned for **single-user local development** (the most common Claude Code scenario). For multi-user or hosted deployments, the security-reviewer's threat model needs reframing.

## Directory layout

```
template/
├── README.md                          # this file
├── SETUP.md                           # adoption checklist + placeholder map
├── CLAUDE.md.template                 # project conventions (placeholders)
├── infrastructure/
│   ├── Dockerfile                     # python + uv + node + claude CLI + non-root user
│   ├── docker-compose.yml             # bind mounts, volumes, env, host integration
│   ├── Makefile                       # build / sync / test / lint / smoke / shell
│   ├── sandbox-entrypoint.sh          # chowns volumes, persists .claude.json, gosu drop
│   └── .dockerignore                  # standard excludes
└── .claude/
    ├── settings.local.json.example    # bypass mode + allow/deny lists + dir trust
    ├── agents/                        # 9 sub-agents
    │   ├── architect.md
    │   ├── auditor.md
    │   ├── builder.md
    │   ├── dependency-auditor.md
    │   ├── roadmap-selector.md
    │   ├── security-reviewer.md
    │   ├── sr-dev.md
    │   ├── sr-sdet.md
    │   └── task-analyzer.md
    └── commands/                      # 7 slash commands
        ├── audit.md
        ├── auto-implement.md
        ├── autopilot.md
        ├── clean-implement.md
        ├── clean-tasks.md
        ├── implement.md
        └── queue-pick.md
```

## How the pieces fit

```
                    ┌─────────────────────────────────────────────────┐
                    │  /autopilot — meta-loop, drains the queue       │
                    │    inlines:                                     │
                    │      ┌───────────────────────────────────────┐  │
                    │      │ /queue-pick                            │  │
                    │      │   spawns roadmap-selector              │  │
                    │      │   verdict: PROCEED / NEEDS-CLEAN-TASKS │  │
                    │      │           / HALT-AND-ASK              │  │
                    │      └───────────────────────────────────────┘  │
                    │                    ↓                            │
                    │         ┌────────────────────────┐              │
                    │         │ /clean-tasks <m>       │              │
                    │         │   spawns task-analyzer │              │
                    │         │   loop until LOW-only  │              │
                    │         └────────────────────────┘              │
                    │                    ↓                            │
                    │         ┌────────────────────────────────────┐  │
                    │         │ /auto-implement <task>             │  │
                    │         │   builder → auditor (1..10 cycles) │  │
                    │         │   security gate                    │  │
                    │         │   team gate (sr-dev + sr-sdet)     │  │
                    │         │   commit ceremony → push           │  │
                    │         └────────────────────────────────────┘  │
                    └─────────────────────────────────────────────────┘
```

`/clean-implement` is the same as `/auto-implement` minus the team gate, commit ceremony, and sandbox pre-flight. Use it for interactive work.

`/implement` and `/audit` are single-step versions for spot use.

## Hard halt boundaries (the load-bearing safety rails)

Every autonomous-mode command refuses to:

- Push to `main` / `master`. Auto-push is **only** to a designated branch (default: `design_branch`).
- `uv publish` / `npm publish` / equivalent release operations.
- Modify `pyproject.toml` `version` (or equivalent) beyond what a task spec calls for.
- Continue when sub-agents disagree (one says `BLOCK`, another says `SHIP`). User arbitrates.
- Run on the host outside the sandbox container (env-var check at pre-flight).
- Touch a dirty working tree (would conflate prior changes with the task's diff).

These rails are enforced at three layers: the orchestrator's prompt rules, the harness `deny:` permission list, and the agent files (each forbids git mutations + publish).

## Quickstart

1. Copy `template/` into a new project, rename to your liking (most files don't need a rename).
2. Read `SETUP.md` for the placeholder map — every `<PLACEHOLDER>` token in the agent and command files needs to be replaced with your project's specifics (KDR numbers, layer rule, gate commands, etc.).
3. Build the sandbox: `make build && make sync`.
4. Verify gates inside the sandbox: `make test && make lint && make smoke`.
5. Inside the container: `claude /login`, then `/autopilot` to start the autonomous queue drain.

The template assumes you already have:

- A `design_docs/` directory with milestone READMEs and per-task spec files.
- An architectural-decisions document (KDRs / ADRs / "load-bearing rules") cited by the agent files.
- A `CHANGELOG.md` following Keep-a-Changelog convention.
- A separate working branch (`design_branch` by default) where autonomous-mode commits land.

If you don't have those, see `SETUP.md` §"Bootstrapping a new project."
