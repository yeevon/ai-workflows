#!/usr/bin/env bash
# Claude Code autonomy sandbox — container entrypoint (template).
# ---------------------------------------------------------------
# Runs as root, fixes named-volume ownership, persists Claude
# session state, then drops privileges to `aiw` via gosu.
#
# Why this exists:
#   1. Docker named volumes mount as root-owned by default. The
#      unprivileged `aiw` user inside the container can't write to
#      those mount points without this chown step.
#   2. Claude Code writes /home/aiw/.claude.json (NOT inside .claude/),
#      so it lives in the ephemeral container layer and gets lost
#      every restart, forcing a re-login. We symlink it into the
#      .claude/ named volume so it persists.
#
# Adapt the chown list and PROJECT_ROOT path if your bind-mount
# target differs from the default.

set -e

# Replace <PROJECT_ROOT> with your bind-mount target. The chown
# list also covers /home/aiw/.cache and /home/aiw/.claude — those
# are named volumes that mount as root-owned otherwise.
chown -R aiw:aiw \
    /home/aiw/.cache \
    /home/aiw/.claude \
    <PROJECT_ROOT>/.venv \
    2>/dev/null || true

# Persist /home/aiw/.claude.json across container restarts by
# symlinking it into the .claude/ volume. Claude Code writes
# .claude.json at the home dir level (NOT inside .claude/), so on
# its own it gets lost every restart. The symlink lives in the
# ephemeral layer; the target lives in the persistent volume.
PERSISTED_CLAUDE_JSON="/home/aiw/.claude/.persisted-claude-json"
LIVE_CLAUDE_JSON="/home/aiw/.claude.json"

# First boot of a fresh volume: no persisted copy yet. If a real
# file exists at the live path (carried in some other way),
# promote it. Otherwise seed an empty-but-parseable JSON object —
# Claude Code parses .claude.json as JSON at startup and zero
# bytes is "Unexpected EOF" which is fatal even though `{}` is
# fine. The CLI populates fields on next write.
if [[ -f "$LIVE_CLAUDE_JSON" && ! -L "$LIVE_CLAUDE_JSON" ]]; then
    mv "$LIVE_CLAUDE_JSON" "$PERSISTED_CLAUDE_JSON"
fi
if [[ ! -s "$PERSISTED_CLAUDE_JSON" ]]; then
    printf '{}\n' > "$PERSISTED_CLAUDE_JSON"
fi

# Always (re)create the symlink — `ln -snf` is idempotent.
ln -snf "$PERSISTED_CLAUDE_JSON" "$LIVE_CLAUDE_JSON"
chown -h aiw:aiw "$LIVE_CLAUDE_JSON"
chown aiw:aiw "$PERSISTED_CLAUDE_JSON"

# Drop privileges and exec the actual command.
exec gosu aiw "$@"
