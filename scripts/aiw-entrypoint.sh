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
# Skip /home/aiw/.ssh: that's a read-only bind-mount of host keys;
# chown would fail and SSH cares about its ownership being exactly
# right (UID/GID 1000 in the container already matches the host
# user that owns the source dir, so no fix is needed).
chown -R aiw:aiw \
    /home/aiw/.cache \
    /home/aiw/.claude \
    /home/papa-jochy/prj/ai-workflows/.venv \
    2>/dev/null || true

# Persist /home/aiw/.claude.json across container restarts by
# symlinking it into the .claude/ volume. Claude Code writes
# .claude.json at the home dir level (NOT inside .claude/), so on
# its own it lives in the ephemeral container layer and gets lost
# every restart — forcing a re-login. The backup file the CLI
# emits before each write is in .claude/backups/, but that's after
# the fact. Symlinking the live file into the persistent volume
# means writes flow into the volume directly; the file survives.
PERSISTED_CLAUDE_JSON="/home/aiw/.claude/.persisted-claude-json"
LIVE_CLAUDE_JSON="/home/aiw/.claude.json"

# First boot of a fresh volume: no persisted copy yet. If the live
# file exists as a real file (the CLI wrote it during this session
# or it was carried in by some other path), promote it. Otherwise
# seed an empty-but-parseable JSON object — Claude Code parses
# .claude.json as JSON at startup and a zero-byte file is
# "Unexpected EOF" not "no file", which is fatal where empty
# JSON is fine. The CLI populates fields on next write.
if [[ -f "$LIVE_CLAUDE_JSON" && ! -L "$LIVE_CLAUDE_JSON" ]]; then
    mv "$LIVE_CLAUDE_JSON" "$PERSISTED_CLAUDE_JSON"
fi
if [[ ! -s "$PERSISTED_CLAUDE_JSON" ]]; then
    # `! -s` covers both "missing" and "exists-but-zero-bytes" so
    # an empty placeholder from the prior buggy entrypoint version
    # gets reseeded too.
    printf '{}\n' > "$PERSISTED_CLAUDE_JSON"
fi

# Always (re)create the symlink — `ln -snf` is idempotent.
ln -snf "$PERSISTED_CLAUDE_JSON" "$LIVE_CLAUDE_JSON"
chown -h aiw:aiw "$LIVE_CLAUDE_JSON"
chown aiw:aiw "$PERSISTED_CLAUDE_JSON"

# Drop privileges and exec the actual command.
exec gosu aiw "$@"
