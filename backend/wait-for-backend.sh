#!/bin/bash
# One-shot helper: waits for .daena-port, confirms uvicorn is listening,
# and hits /api/v1/health. Written so we can invoke it via wsl without
# fighting bash-in-bash quoting.

set -u
PORT_FILE=/mnt/d/Ideas/Daena/backend/.daena-port
LOG_FILE=/tmp/daena-logs/backend.log

for i in $(seq 1 120); do
    if [ -f "$PORT_FILE" ]; then
        PORT=$(cat "$PORT_FILE" 2>/dev/null)
        if [ -n "$PORT" ] && ss -tln 2>/dev/null | grep -q ":$PORT "; then
            echo "Backend LIVE on port $PORT after ${i}s"
            curl -sf -m 3 "http://127.0.0.1:$PORT/api/v1/health" 2>&1 | head -5
            exit 0
        fi
    fi
    sleep 1
done

echo "Backend did not start within 120s"
echo "--- last 40 lines of log ---"
tail -40 "$LOG_FILE" 2>&1
exit 1
