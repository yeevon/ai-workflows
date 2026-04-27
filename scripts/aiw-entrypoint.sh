#!/usr/bin/env bash
# Container entrypoint — runs as root, chowns named-volume mount
# points to the unprivileged `aiw` user, then drops privileges via
# gosu before exec'ing the actual command.
#
# Why this exists: Docker named volumes mount as root-owned by
# default, even when the container's USER directive specifies a
# non-root account. The unprivileged user inside the container
# can't write to those mount points without this chown step.
#
# Paths chowned here are the volume mount targets in
# docker-compose.yml — keep this list in sync if mounts change.

set -e

# Idempotent — chown is cheap when ownership already matches.
chown -R aiw:aiw \
    /home/aiw \
    /home/papa-jochy/prj/ai-workflows/.venv \
    2>/dev/null || true

# Drop privileges and exec the actual command.
exec gosu aiw "$@"
