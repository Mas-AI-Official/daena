import sys
import os
from pathlib import Path

# Add root to sys.path
sys.path.append(os.getcwd())

try:
    import backend.routes.qa_guardian as qa
    print(f"File: {qa.__file__}")
    print(f"Resolved Path: {qa.DASHBOARD_TEMPLATE}")
    print(f"Exists: {qa.DASHBOARD_TEMPLATE.exists()}")
except Exception as e:
    print(f"Error: {e}")
