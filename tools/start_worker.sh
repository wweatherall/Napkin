#!/bin/bash
# Opens a Terminal window running a Claude worker with Remote Control (F005, P38): the same as typing
#   cd <this checkout> ; claude ; /remote-control ; Check the board
# so you can follow it, or answer it, from the Claude app on your phone. One job, then it asks for a /clear (P37).
#   tools/start_worker.sh [name]     name shown in the Claude app (default worker-HHMM)
# DRY_RUN=1 prints the command instead of opening the window. The first run may ask you to let Terminal be
# controlled (System Settings > Privacy & Security > Automation).
set -euo pipefail
repo="$(cd "$(dirname "$0")/.." && pwd)"
name="${1:-worker-$(date +%H%M)}"
cmd="cd $(printf %q "$repo") && claude --remote-control $(printf %q "$name") $(printf %q "Check the board")"
if [ "${DRY_RUN:-}" = 1 ]; then
    echo "$cmd"
    exit 0
fi
osascript -e 'on run argv' -e 'tell application "Terminal" to do script (item 1 of argv)' -e 'end run' "$cmd" >/dev/null
echo "started $name in a new Terminal window (Remote Control: open it in the Claude app)"
