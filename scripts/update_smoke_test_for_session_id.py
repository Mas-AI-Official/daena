"""
Update smoke_test.py to ensure session_id is always checked
and follow_redirects=True is used
"""
import re
from pathlib import Path

smoke_test_file = Path(__file__).parent / "smoke_test.py"

if not smoke_test_file.exists():
    print(f"[ERROR] smoke_test.py not found at {smoke_test_file}")
    exit(1)

content = smoke_test_file.read_text(encoding='utf-8')

# Fix 1: Ensure all httpx calls use follow_redirects=True
content = re.sub(
    r'httpx\.(get|post|put|delete)\(([^,]+),([^)]+)\)',
    lambda m: f'httpx.{m.group(1)}({m.group(2)},{m.group(3)}, follow_redirects=True)' if 'follow_redirects' not in m.group(3) else m.group(0),
    content
)

# Fix 2: Ensure session_id is always checked in test_daena_chat
if 'def test_daena_chat' in content:
    # Check if session_id validation exists
    if 'if not session_id:' not in content or 'No session_id' not in content:
        # Add session_id check after getting response
        content = re.sub(
            r'(data = msg_resp\.json\(\)\s*\n\s*if not data\.get\("success"\):)',
            r'\1\n        \n        # CRITICAL: Verify session_id is returned\n        session_id_in_response = data.get("session_id")\n        if not session_id_in_response:\n            return False, {"error": "No session_id in response", "data": data}',
            content
        )

smoke_test_file.write_text(content, encoding='utf-8')
print(f"[OK] Updated smoke_test.py")



