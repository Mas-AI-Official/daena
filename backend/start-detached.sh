#!/bin/bash
# Daena backend -- detached launcher for WSL.
# Called from Windows via: wsl -d kali-linux -- bash /mnt/d/.../start-detached.sh
#
# The reason for this script: when Claude (or any automation) runs
# `wsl -- bash -c "nohup ... &"`, WSL tears the child down as soon as
# the outer bash exits. The workaround is to put the real work in a
# .sh file the orchestrator can invoke with a single, ``fire-and-forget``
# wsl call -- `setsid` detaches from the controlling TTY, and the
# redirect keeps stdio off the now-gone pts.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Fresh port file so the frontend picks up the new port when backend
# registers it during boot.
rm -f .daena-port
mkdir -p /tmp/daena-logs

# setsid + full stdio redirect = survives after parent exit.
setsid bash start-linux.sh </dev/null >/tmp/daena-logs/backend.log 2>&1 &
echo "Detached PID: $!"
