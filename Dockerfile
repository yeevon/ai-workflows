# syntax=docker/dockerfile:1.7
#
# ai-workflows sandbox image
# --------------------------
# Sandbox container for hermetic gates AND autonomous-mode work.
# Python 3.13 + uv + git + Node.js + the `claude` CLI (KDR-003).
#
# The image deliberately does NOT bake in the project source — the
# repo is bind-mounted at /home/papa-jochy/prj/ai-workflows via
# docker-compose.yml so a code edit on the host shows up inside the
# container immediately, no rebuild. The venv lives in a named
# volume (`aiw_venv`) so it persists across `docker compose run --rm`
# invocations.
#
# Why match the host path inside the container? Claude Code's
# auto-memory directory hashes off the current working directory
# (cwd → `-home-papa-jochy-prj-ai-workflows`). Bind-mounting the
# repo at the same path inside the container preserves the hash, so
# the auto-memory bind-mount in docker-compose.yml lands on the same
# project directory the host conversation already populated. (Point
# 8 of the autonomy decisions: persistent .claude memory.)
#
# Runtime tools wired here:
#   - `claude` CLI         — KDR-003 Claude Code OAuth subprocess.
#                            User auths interactively inside the
#                            container the first time autonomous
#                            mode runs (point 5 of the decisions —
#                            no host credential leak).
#   - Ollama HTTP endpoint — NOT installed here; the host daemon is
#                            reachable as `host.docker.internal:11434`
#                            via the docker-compose extra_hosts entry
#                            (point 7).
#   - Gemini (LiteLLM)     — pure HTTP call out via the dependency,
#                            no extra binary needed.
#
# Build:    make build         # or: docker compose build
# Sync:     make sync          # first-time uv sync (slow)
# Test:     make test          # uv run pytest -q
# Lint:     make lint          # lint-imports + ruff check
# Smoke:    make smoke         # scripts/release_smoke.sh
# Shell:    make shell         # interactive bash
#
# To re-auth Claude inside the container (first run, or after token
# expiry):
#   make shell
#   $ claude /login    # or just `claude` and follow the prompt

ARG PYTHON_VERSION=3.13
ARG UV_VERSION=0.10
ARG NODE_MAJOR=22
# AIW_UID/AIW_GID — match the host user that owns the bind-mounted
# repo so files written from inside the container don't drift to
# root-owned on the host. Defaults to 1000/1000 (the typical first
# user on Linux); override at build time if needed:
#   docker compose build --build-arg AIW_UID=$(id -u) --build-arg AIW_GID=$(id -g)
ARG AIW_UID=1000
ARG AIW_GID=1000

# Pull uv binary from the official Astral image
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv-bin

FROM python:${PYTHON_VERSION}-slim AS runtime

ARG NODE_MAJOR
ARG AIW_UID
ARG AIW_GID

# OS deps:
#   git              — tests + in-container git ops
#   curl + certs     — uv index fetches + Node setup script
#   bash             — scripts/release_smoke.sh + Makefile targets
#   make             — convenience for `make ...` inside the container
#   gnupg            — apt-key for the NodeSource repo
# build-essential intentionally omitted — no current dep needs C
# compilation.
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

# Node.js (for the `claude` CLI, distributed as @anthropic-ai/claude-code
# on npm).  NodeSource APT setup, then pin to the major from build arg.
RUN curl -fsSL https://deb.nodesource.com/setup_${NODE_MAJOR}.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g @anthropic-ai/claude-code \
    && claude --version

# uv binary
COPY --from=uv-bin /uv /uvx /usr/local/bin/

# uv knobs:
#   UV_LINK_MODE=copy        — bind-mount-friendly; avoids hard-link
#                              attempts across the volume boundary.
#   UV_COMPILE_BYTECODE=1    — pre-compile .pyc on install for faster
#                              first import.
#   UV_PROJECT_ENVIRONMENT   — pin the venv path so the named volume
#                              mount in docker-compose lines up.
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/home/papa-jochy/prj/ai-workflows/.venv \
    PATH="/home/papa-jochy/prj/ai-workflows/.venv/bin:/usr/local/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/home/aiw

# Create non-root user `aiw` (UID/GID match the host user that owns
# the bind-mounted repo). The `claude` CLI refuses to run with
# `--dangerously-skip-permissions` or `defaultMode: "bypassPermissions"`
# under root, so non-root is required for unattended autonomy. The
# UID/GID match means files written through the bind-mount stay
# host-owned (no chown drift).
RUN groupadd --gid ${AIW_GID} aiw \
    && useradd --uid ${AIW_UID} --gid ${AIW_GID} --shell /bin/bash --create-home aiw \
    && mkdir -p /home/aiw/.claude /home/papa-jochy/prj/ai-workflows \
    && chown -R aiw:aiw /home/aiw /home/papa-jochy

# Entrypoint runs as root, chowns named-volume mount points to aiw,
# then drops to aiw via gosu. Without this, Docker-managed named
# volumes mount as root-owned and the unprivileged user can't write
# to them. The script path is baked into the image (not via the
# bind-mount) so it survives even if scripts/ goes missing on the
# host. Source is at scripts/aiw-entrypoint.sh on disk.
COPY scripts/aiw-entrypoint.sh /usr/local/bin/aiw-entrypoint.sh
RUN chmod +x /usr/local/bin/aiw-entrypoint.sh

WORKDIR /home/papa-jochy/prj/ai-workflows

ENTRYPOINT ["/usr/local/bin/aiw-entrypoint.sh"]
# Default command — drop into a shell. Override per-target with
# `docker compose run --rm aiw <cmd>` (see Makefile).
CMD ["bash"]
