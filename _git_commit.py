"""One-shot git commit + push script. Run outside sandbox."""
import subprocess
import os

os.chdir(r"D:\Ideas\Daena")

print("=== Staging ===")
r = subprocess.run(["git", "add", "-A"], capture_output=True, text=True)
print(r.stdout, r.stderr)

print("=== Status ===")
r = subprocess.run(["git", "status", "--short"], capture_output=True, text=True)
print(r.stdout)

print("=== Committing ===")
msg = """Phase I: Department routing + OAuth connector flow + frontend wiring

Backend:
- DepartmentRouter: maps task types to 60 department agents (MIND/EYES/HANDS/VOICE/SHIELD/MEMORY)
- SwarmPlanner + SwarmExecutor wired into Stage 7.5 (was dead code, now active)
- ConnectorOAuthService: Google OAuth 2.0 for Gmail/Calendar connectors
- Connector OAuth API: /connectors/{id}/oauth/authorize + callback
- IntegrationRouter: auto-refresh expired OAuth tokens before API calls

Frontend:
- 7 broken connector icons fixed (inline SVG)
- Tool call/result SSE rendering in chat
- AGI Mode toggle in Settings
- CdnIcon fallback shows letter badge

Tests: 1550 passing, 0 failing
Frontend: 0 TypeScript errors

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"""

r = subprocess.run(["git", "commit", "-m", msg], capture_output=True, text=True)
print(r.stdout, r.stderr)

print("=== Pushing ===")
r = subprocess.run(["git", "push"], capture_output=True, text=True)
print(r.stdout, r.stderr)

print("=== Done ===")
r = subprocess.run(["git", "log", "--oneline", "-3"], capture_output=True, text=True)
print(r.stdout)
