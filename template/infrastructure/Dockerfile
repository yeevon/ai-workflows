# syntax=docker/dockerfile:1.7
#
# Claude Code autonomy sandbox image (template).
# ---------------------------------------------
# Generic for any project. Two adoption knobs (build args):
#
#   PROJECT_ROOT   — absolute path the bind-mount target uses.
#                    MUST match the host path so cwd-based hashes
#                    (Claude Code auto-memory) line up. Default
#                    /workspace is fine if your host repo lives at
#                    /workspace too; otherwise override.
#   AIW_UID/AIW_GID — match the host user that owns the bind-mounted
#                    repo. Defaults 1000/1000.
#
# What's baked in:
#   - python:3.13-slim
#   - uv (from ghcr.io/astral-sh/uv) — replace if your stack is not Python
#   - git, openssh-client, gosu (entrypoint privilege drop)
#   - Node.js + the @anthropic-ai/claude-code CLI
#   - non-root user (UID/GID match host) so claude --dangerously-skip-permissions
#     and defaultMode=bypassPermissions work (root is blocked)
#
# What's intentionally NOT baked in:
#   - source code (bind-mounted at runtime so host edits surface live)
#   - SSH keys (bind-mounted read-only at runtime; never bake)
#   - .env / API tokens (env_file in docker-compose; never bake)
#
# Build:    make build
# Sync:     make sync          # populate venv volume
# Test:     make test
# Lint:     make lint
# Smoke:    make smoke
# Shell:    make shell

ARG PYTHON_VERSION=3.13
ARG UV_VERSION=0.10
ARG NODE_MAJOR=22
ARG AIW_UID=1000
ARG AIW_GID=1000
ARG PROJECT_ROOT=/workspace

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv-bin

FROM python:${PYTHON_VERSION}-slim AS runtime
ARG NODE_MAJOR
ARG AIW_UID
ARG AIW_GID
ARG PROJECT_ROOT

# OS deps. build-essential intentionally omitted — re-add if any
# project dep needs C compilation.
RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        curl \
        ca-certificates \
        bash \
        make \
        gnupg \
        gosu \
        openssh-client \
    && rm -rf /var/lib/apt/lists/*

# Node.js + claude CLI. The CLI is the OAuth subprocess primitive
# every Claude-tier sub-agent runs through.
RUN curl -fsSL https://deb.nodesource.com/setup_${NODE_MAJOR}.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g @anthropic-ai/claude-code \
    && claude --version

# uv binary
COPY --from=uv-bin /uv /uvx /usr/local/bin/

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=${PROJECT_ROOT}/.venv \
    PATH="${PROJECT_ROOT}/.venv/bin:/usr/local/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/home/aiw

# Non-root user. The claude CLI refuses to start with bypass mode
# under root; non-root is required for unattended autonomy. UID/GID
# match means files written through the bind-mount stay host-owned.
RUN groupadd --gid ${AIW_GID} aiw \
    && useradd --uid ${AIW_UID} --gid ${AIW_GID} --shell /bin/bash --create-home aiw \
    && mkdir -p /home/aiw/.claude ${PROJECT_ROOT} \
    && chown -R aiw:aiw /home/aiw ${PROJECT_ROOT}

# Entrypoint: chown volume mount points + symlink .claude.json into
# persistent volume + drop to aiw via gosu.
COPY scripts/sandbox-entrypoint.sh /usr/local/bin/sandbox-entrypoint.sh
RUN chmod +x /usr/local/bin/sandbox-entrypoint.sh

WORKDIR ${PROJECT_ROOT}

ENTRYPOINT ["/usr/local/bin/sandbox-entrypoint.sh"]
CMD ["bash"]
