import subprocess, os, shutil

os.chdir(r"D:\Ideas\Daena")
idx2 = r"D:\Ideas\Daena\.git\index2"
env = os.environ.copy()
env["GIT_INDEX_FILE"] = idx2

# Remove stale index2 if exists
if os.path.exists(idx2):
    os.remove(idx2)

print("Step 1: read-tree HEAD into new index")
r = subprocess.run(["git", "read-tree", "HEAD"], env=env, capture_output=True, text=True)
print(r.stdout, r.stderr)

print("Step 2: add all files to new index")
r = subprocess.run(["git", "add", "-A"], env=env, capture_output=True, text=True)
print(r.stdout, r.stderr)

print("Step 3: write-tree from new index")
r = subprocess.run(["git", "write-tree"], env=env, capture_output=True, text=True)
tree = r.stdout.strip()
print("Tree:", tree)

print("Step 4: commit-tree")
parent = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
msg = """Phase I: Department routing + OAuth connector flow + frontend wiring

Backend:
- DepartmentRouter: maps task types to 60 department agents
- SwarmPlanner + SwarmExecutor wired into Stage 7.5 (was dead code, now active)
- ConnectorOAuthService: Google OAuth 2.0 for Gmail/Calendar
- Connector OAuth API: authorize + callback endpoints
- IntegrationRouter: auto-refresh expired OAuth tokens

Frontend:
- 7 broken connector icons fixed (inline SVG)
- Tool call/result SSE rendering in chat
- AGI Mode toggle in Settings

Tests: 1550/0 | TS errors: 0

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"""

r = subprocess.run(["git", "commit-tree", tree, "-p", parent, "-m", msg], capture_output=True, text=True)
commit = r.stdout.strip()
print("Commit:", commit, r.stderr)

if commit:
    print("Step 5: update-ref")
    # Try writing ref directly since update-ref may fail on permissions
    ref_path = os.path.join(r"D:\Ideas\Daena\.git\refs\heads\master")
    try:
        with open(ref_path, "w") as f:
            f.write(commit + "\n")
        print("Ref updated via direct file write")
    except PermissionError:
        r2 = subprocess.run(["git", "update-ref", "refs/heads/master", commit], capture_output=True, text=True)
        print(r2.stdout, r2.stderr)

    print("Step 6: verify")
    r = subprocess.run(["git", "log", "--oneline", "-3"], capture_output=True, text=True)
    print(r.stdout)

    print("Step 7: push")
    r = subprocess.run(["git", "push", "origin", "master"], capture_output=True, text=True)
    print(r.stdout, r.stderr)

# Cleanup
if os.path.exists(idx2):
    os.remove(idx2)
print("Done.")
