import sys
import os
from pathlib import Path

# Add root to sys.path
sys.path.append(os.getcwd())

try:
    import backend.routes.qa_guardian as qa
    print(f"File: {qa.__file__}")
    print(f"Resolved Path: {qa.DASHBOARD_TEMPLATE}")
    
    content = qa.DASHBOARD_TEMPLATE.read_text(encoding='utf-8')
    print(f"Read success. Length: {len(content)}")
    print(f"First 100 chars: {content[:100]}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
