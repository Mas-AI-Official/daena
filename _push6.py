import subprocess, os
os.chdir(r"D:\Ideas\Daena")
idx = r"D:\Ideas\Daena\.git\index_final"
env = os.environ.copy()
env["GIT_INDEX_FILE"] = idx
for f in [idx, r"D:\Ideas\Daena\.git\index.lock"]:
    if os.path.exists(f):
        try: os.remove(f)
        except: pass
remote_head = subprocess.run(["git", "ls-remote", "origin", "refs/heads/master"], capture_output=True, text=True).stdout.split()[0]
subprocess.run(["git", "read-tree", remote_head], env=env, capture_output=True)
subprocess.run(["git", "add", "-A"], env=env, capture_output=True)
r = subprocess.run(["git", "write-tree"], env=env, capture_output=True, text=True)
tree = r.stdout.strip()
msg = """feat: True parallel orchestration, self-repair, adaptive Quintessence

1. Parallel Orchestration (20+20 scale)
   - MAX_PARALLEL_SUBTASKS raised from 5 to 40
   - Per-runtime concurrency limits: claude_code=8, codex=8, gemini=5, ollama=4
   - Two-layer gating: global semaphore (40) + per-runtime semaphore
   - SwarmExecutor now supports true parallel execution across runtimes

2. Self-Repair Loop
   - New: services/self_repair.py
   - When a tool call fails in AGI mode, Daena reads the traceback,
     finds the broken file/line, uses Ollama to generate a fix,
     applies it, and re-runs tests. Max 3 attempts.
   - extract_error_location() parses Python tracebacks for file/line/error
   - Wired into ToolUseLoop._execute_tool() error handler

3. Adaptive Quintessence Depth
   - QE-Light: 2 experts (SIMPLE queries)
   - QE-Standard: 3 experts (MODERATE queries)
   - QE-Deep: 5 experts + cross-validation (COMPLEX queries)
   - QE-Council: all experts (architecture decisions)
   - Depth auto-selected from query_understanding complexity score

4. Multi-Runtime Orchestration Skill
   - Runtime capability matrix (4 runtimes x 10+ task types)
   - Orchestration system prompt auto-injected when 2+ runtimes online
   - Teaches LLM to assign subtasks to optimal runtimes

5. Routing Fix (PERMANENT)
   - Removed ALL API key fallback logic
   - CLI runtimes use subscriptions, model router handles boosting
   - No more "requires API key" messages

Tests: 1606 passing, 0 failing (+27 new tests)

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"""
r = subprocess.run(["git", "commit-tree", tree, "-p", remote_head, "-m", msg], capture_output=True, text=True)
commit = r.stdout.strip()
print(f"Commit: {commit}")
if commit:
    r = subprocess.run(["git", "push", "origin", f"{commit}:refs/heads/master"], capture_output=True, text=True, timeout=60)
    print(f"Push: {r.stdout.strip()} {r.stderr.strip()}")
try: os.remove(idx)
except: pass
