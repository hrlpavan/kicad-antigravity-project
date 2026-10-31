#!/usr/bin/env bash
# scripts/notify_mac.sh - Dispatches desktop notifications to macOS client
set -euo pipefail

TITLE="${1:-Antigravity KiCad Automation}"
MESSAGE="${2:-Task update received.}"
SOUND="${3:-Hero}" # Basso, Blow, Bottle, Frog, Funk, Glass, Hero, Morse, Ping, Pop, Purr, Sosumi, Submarine, Tink

# 1. Local Mac Execution (Antigravity running locally on macOS)
if [[ "$(uname)" == "Darwin" ]]; then
    osascript - "$TITLE" "$MESSAGE" "$SOUND" <<'APPLESCRIPT'
on run argv
    display notification (item 2 of argv) with title (item 1 of argv) sound name (item 3 of argv)
end run
APPLESCRIPT
    exit 0
fi

# 2. Remote Workstation Execution (Forwarding notification back to Mac over SSH or Webhook)
MAC_USER="${MAC_SSH_USER:-pavankumars}"
MAC_HOST="${MAC_SSH_HOST:-192.168.250.172}"

if [[ -n "$MAC_HOST" ]]; then
    printf -v REMOTE_CMD 'osascript - %q %q %q' "$TITLE" "$MESSAGE" "$SOUND"
    ssh -T -o ConnectTimeout=3 -o BatchMode=yes "${MAC_USER}@${MAC_HOST}" "$REMOTE_CMD" <<'APPLESCRIPT' 2>/dev/null || {
on run argv
    display notification (item 2 of argv) with title (item 1 of argv) sound name (item 3 of argv)
end run
APPLESCRIPT
        if [[ -n "${NOTIFICATION_WEBHOOK_URL:-}" ]]; then
            python3 -c 'import json,sys; print(json.dumps({"title":sys.argv[1],"body":sys.argv[2]}))' "$TITLE" "$MESSAGE" \
                | curl -fsS -X POST -H "Content-Type: application/json" -d @- "$NOTIFICATION_WEBHOOK_URL" >/dev/null
        fi
    }
fi
