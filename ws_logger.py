# === TELEMETRY TRACE LAYER FOR DAENA ===

# 1. Define telemetry Python modules
$telemetryDir = "D:\Ideas\Daena\Core\telemetry"
New-Item -ItemType Directory -Force -Path $telemetryDir | Out-Null

@'
import os, datetime
from fastapi import Request

log_file = os.path.join(os.path.dirname(__file__), "daena_ws_telemetry.log")

def log_websocket_event(message: str):
    timestamp = datetime.datetime.utcnow().isoformat()
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")
