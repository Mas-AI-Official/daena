#  Daena Secure Telemetry Injector 
$telemetryDir = "D:\Ideas\Daena\Core\telemetry"
$logDir = "$telemetryDir\logs"
$mainPath = "D:\Ideas\Daena\backend\main.py"
$launchPath = "D:\Ideas\Daena\launch_daena.ps1"

# Create telemetry directories
New-Item -ItemType Directory -Path $telemetryDir -Force | Out-Null
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

# Write websocket_trace.py
@'
import os
from datetime import datetime

LOG_FILE = os.path.join(os.path.dirname(__file__), "logs", "websocket.log")

def log_websocket_event(event: str):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"[{timestamp}] {event}\\n")
