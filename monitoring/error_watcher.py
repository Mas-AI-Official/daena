"""
Error Watcher - Monitors logs and reports to QA Guardian

Integrated with QA Guardian for proper incident tracking.
"""

import time
import os
import logging
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

log_path = os.path.join(os.path.dirname(__file__), "..", "logs", "backend.log")
last_size = 0

logging.basicConfig(
    filename=os.path.join(os.path.dirname(__file__), "..", "logs", "error_watcher.log"),
    level=logging.INFO
)

# QA Guardian integration
guardian_available = False
guardian_loop = None

def init_guardian():
    """Initialize QA Guardian connection"""
    global guardian_available, guardian_loop
    try:
        from backend.qa_guardian.guardian_loop import get_guardian_loop
        from backend.qa_guardian import is_enabled
        
        if is_enabled():
            guardian_loop = get_guardian_loop()
            guardian_available = True
            logging.info("QA Guardian integration enabled")
        else:
            logging.info("QA Guardian is disabled")
    except ImportError as e:
        logging.warning(f"QA Guardian not available: {e}")
        guardian_available = False

def report_to_guardian(line: str):
    """Report error to QA Guardian"""
    global guardian_loop
    if guardian_available and guardian_loop:
        try:
            # Parse error line
            if "ERROR" in line:
                error_type = "RuntimeError"
            elif "Exception" in line:
                error_type = "Exception"
            else:
                error_type = "LogError"
            
            guardian_loop.report_error(
                error_type=error_type,
                error_message=line.strip(),
                subsystem="backend"
            )
        except Exception as e:
            logging.error(f"Failed to report to Guardian: {e}")

def watch():
    global last_size
    
    # Try to initialize Guardian (non-blocking)
    init_guardian()
    
    while True:
        if not os.path.exists(log_path):
            time.sleep(5)
            continue

        try:
            with open(log_path, "r", errors='ignore') as f:
                f.seek(last_size)
                new_lines = f.readlines()
                last_size = f.tell()

                for line in new_lines:
                    if "ERROR" in line or "Exception" in line:
                        logging.info(f"[ERROR DETECTED] {line.strip()}")
                        
                        # Report to QA Guardian
                        report_to_guardian(line)
        except Exception as e:
            logging.error(f"Error reading log: {e}")

        time.sleep(3)

if __name__ == "__main__":
    watch()

