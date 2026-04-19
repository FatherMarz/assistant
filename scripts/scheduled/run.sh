#!/usr/bin/env bash
# Headless Claude Code wrapper for scheduled tasks.
# Usage: run.sh <task-name>   (task-name matches prompts/<task-name>.md)
#
# Reads .env from the repo root for:
#   PUSHOVER_TOKEN, PUSHOVER_USER   — optional, for failure notifications
#   CLAUDE_MODEL                    — override default model
#   TZ                              — override timezone

set -o pipefail

TASK_NAME="$1"
if [ -z "$TASK_NAME" ]; then
    echo "usage: $0 <task-name>" >&2
    exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PROMPT_FILE="$SCRIPT_DIR/prompts/${TASK_NAME}.md"
LOG_DIR="$REPO_ROOT/logs/scheduled"
LOG_FILE="$LOG_DIR/${TASK_NAME}.log"

mkdir -p "$LOG_DIR"

# Cron/launchd runs with a minimal PATH — add common install locations.
export PATH="$HOME/.local/bin:$HOME/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

# Load .env if present
if [ -f "$REPO_ROOT/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    . "$REPO_ROOT/.env"
    set +a
fi

CLAUDE_MODEL="${CLAUDE_MODEL:-sonnet}"
TIMEOUT_SECS="${TIMEOUT_SECS:-600}"

cd "$REPO_ROOT" || { echo "cannot cd to $REPO_ROOT" >&2; exit 3; }

if [ ! -f "$PROMPT_FILE" ]; then
    echo "prompt file missing: $PROMPT_FILE" >&2
    exit 4
fi

START_TS="$(date '+%Y-%m-%d %H:%M:%S %Z')"
START_EPOCH="$(date +%s)"
{
    echo ""
    echo "=============================================="
    echo "START $TASK_NAME @ $START_TS (model=$CLAUDE_MODEL)"
    echo "=============================================="
} >> "$LOG_FILE"

if ! command -v claude >/dev/null 2>&1; then
    echo "ERROR: 'claude' CLI not found on PATH. Install from https://docs.claude.com/claude-code" >> "$LOG_FILE"
    exit 5
fi

# Run Claude Code headless with a watchdog.
EXIT_CODE=1
(
    claude -p "$(cat "$PROMPT_FILE")" \
        --permission-mode bypassPermissions \
        --model "$CLAUDE_MODEL" \
        --fallback-model sonnet \
        --no-session-persistence \
        --output-format text \
        >> "$LOG_FILE" 2>&1
) &
CLAUDE_PID=$!
(
    sleep "$TIMEOUT_SECS"
    if kill -0 "$CLAUDE_PID" 2>/dev/null; then
        echo "!!! timeout after ${TIMEOUT_SECS}s — SIGTERM $CLAUDE_PID" >> "$LOG_FILE"
        kill -TERM "$CLAUDE_PID" 2>/dev/null
        sleep 10
        if kill -0 "$CLAUDE_PID" 2>/dev/null; then
            echo "!!! still alive — SIGKILL $CLAUDE_PID" >> "$LOG_FILE"
            kill -KILL "$CLAUDE_PID" 2>/dev/null
        fi
    fi
) &
WATCHDOG_PID=$!
wait "$CLAUDE_PID"
EXIT_CODE=$?
kill "$WATCHDOG_PID" 2>/dev/null
wait "$WATCHDOG_PID" 2>/dev/null

END_TS="$(date '+%Y-%m-%d %H:%M:%S %Z')"

# Post-process: auto-wikilink entity mentions written during this run.
{
    echo ""
    echo "--- post_scan_graph ---"
    python3 "$REPO_ROOT/scripts/post_scan_graph.py" --since-start "$((START_EPOCH - 5))" 2>&1 || true
} >> "$LOG_FILE"

{
    echo ""
    echo "END   $TASK_NAME @ $END_TS (exit $EXIT_CODE)"
    echo "=============================================="
} >> "$LOG_FILE"

# Failure notification via Pushover, if configured.
if [ "$EXIT_CODE" -ne 0 ] && [ -n "$PUSHOVER_TOKEN" ] && [ -n "$PUSHOVER_USER" ]; then
    curl -s --max-time 10 \
         -F "token=$PUSHOVER_TOKEN" \
         -F "user=$PUSHOVER_USER" \
         -F "title=Scheduled Task Failed: $TASK_NAME" \
         -F "message=Exit $EXIT_CODE at $END_TS. Tail logs/scheduled/${TASK_NAME}.log for details." \
         https://api.pushover.net/1/messages.json > /dev/null || true
fi

exit "$EXIT_CODE"
