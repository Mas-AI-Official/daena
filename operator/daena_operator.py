#!/usr/bin/env python3
"""Daena Operator Runner -- local, file-based autonomous sprint supervisor.

Reads the active next-prompt, optionally invokes an available agent CLI to work a sprint,
monitors output, classifies hard gates, records everything to logs, and continues only
through safe local work. Stops for hard gates. Never exposes secrets.

Modes:
  python daena_operator.py --dry-run     # plan only; never invokes an agent (default)
  python daena_operator.py --once        # one loop iteration
  python daena_operator.py --loop N      # up to N iterations (bounded by config max_loops)

Honesty rule: if no agent CLI has a verified non-interactive mode (or agent execution is not
explicitly enabled in the real config), the runner writes NEEDS_USER_LOOP.md and does NOT
pretend automation happened. See OPERATOR_PROTOCOL.md.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXAMPLE_CONFIG = HERE / "operator_config.example.json"
REAL_CONFIG = HERE / "operator_config.json"
LOGS = HERE / "logs"

# Known non-interactive invocation templates. UNVERIFIED for safe autonomous tool-exec here;
# only used when agent_exec.enabled is true in the real config. {prompt_text}/{prompt_path} substituted.
AGENT_COMMANDS = {
    # claude headless: --permission-mode acceptEdits = functional (auto-accepts edits) yet SAFE -- the founder's
    # pretooluse_guard PreToolUse hook still fires on every tool call (blocks sends/secrets/deploy/NEVERs). No
    # danger flag (never --dangerously-skip-permissions / bypassPermissions for an unattended loop).
    "claude": ["claude", "-p", "{prompt_text}", "--permission-mode", "acceptEdits"],
    # Flags MUST precede the prompt positional or codex silently ignores them (verified 2026-06-04).
    # --sandbox workspace-write: confine writes to repo+temp and disable network (blocks MCP sends).
    # Codex defaults to danger-full-access here; never run it unattended without this downgrade.
    "codex": ["codex", "exec", "--skip-git-repo-check", "--sandbox", "workspace-write", "{prompt_text}"],
    "gemini": ["gemini", "-p", "{prompt_text}"],
}
TOOLS = ["claude", "codex", "gemini", "perplexity", "python", "node", "git", "gh", "rtk", "ollama"]

# Secret-looking patterns -- redacted before anything is written to a log.
SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|token|password|passwd|bearer|authorization|client[_-]?secret)\s*[:=]\s*\S+"),
    re.compile(r"sk-[A-Za-z0-9]{12,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)(ghp|github_pat)_[A-Za-z0-9_]{20,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]
# TRUE_HARD_GATE (STOP): the agent says it cannot perform the NEXT action NOW without a founder-only action
# (secret/.env/deploy/spend/real send/unsafe scan/delete/prod migration/legal-business/public submit). Merely
# MENTIONING that gated items exist is NOT a gate -- see MENTION_ONLY_MARKERS; the runner CONTINUES on those.
# Agents must emit "TRUE_HARD_GATE: <founder action needed>" when genuinely blocked.
GATE_MARKERS = [
    re.compile(r"(?i)\bTRUE_HARD_GATE\b"),
    re.compile(r"(?i)\bHARD_GATE\b"),
    re.compile(r"(?i)BLOCKED_NEEDS_FOUNDER"),
    re.compile(r"(?i)STOPPED_ONLY_BECAUSE"),
    re.compile(r"(?i)\bI cannot (safely |now )?(proceed|continue)\b"),
    re.compile(r"(?i)cannot (proceed|continue|do this|do that) without (a |an |the )?(secret|key|password|credential|deploy|spend|payment|real send|approval|founder)"),
    re.compile(r"(?i)need(s)? founder approval to\b"),
    re.compile(r"(?i)require(s)? founder approval\b"),
]
# MENTION_ONLY (CONTINUE): output merely references gated items / future founder actions. NEVER a stop.
MENTION_ONLY_MARKERS = [
    re.compile(r"(?i)founder[ _-]?gated (item|remainder|step|remain)"),
    re.compile(r"(?i)\bDEP-001\b"),
    re.compile(r"(?i)founder should (later|eventually|then|approve)"),
    re.compile(r"(?i)remain(s)? founder[ _-]?gated"),
    re.compile(r"(?i)\bfounder[ _-]?gated\b"),
]
# Markers meaning the agent reached a clean boundary / finished a chunk.
DONE_MARKERS = [
    re.compile(r"(?i)STOPPED_AT_SPRINT_BOUNDARY"),
    re.compile(r"(?i)\bSPRINT (COMPLETE|DONE)\b"),
    re.compile(r"(?m)^\s*NEXT:"),
]


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def ts_slug() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def redact(text: str) -> str:
    out = text
    for pat in SECRET_PATTERNS:
        out = pat.sub("[REDACTED]", out)
    return out


def load_config(path: str | None = None) -> dict:
    cfg: dict = {}
    if EXAMPLE_CONFIG.exists():
        cfg.update(json.loads(EXAMPLE_CONFIG.read_text(encoding="utf-8")))
    chosen = Path(path) if path else (REAL_CONFIG if REAL_CONFIG.exists() else None)
    if chosen and chosen.exists():
        cfg.update(json.loads(chosen.read_text(encoding="utf-8")))
        cfg["_config_source"] = str(chosen)
    else:
        cfg["_config_source"] = f"{EXAMPLE_CONFIG} (defaults)"
    return cfg


def detect_tools() -> dict:
    return {t: {"status": "AVAILABLE" if shutil.which(t) else "NOT_FOUND", "path": shutil.which(t) or ""}
            for t in TOOLS}


def find_next_prompt(cfg: dict) -> str | None:
    for p in cfg.get("next_prompt_priority", []):
        if Path(p).exists():
            return p
    return None


def write_state(state: dict) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    (LOGS / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")


def write_text(name: str, text: str) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    (LOGS / name).write_text(text, encoding="utf-8")


def scan(text: str, patterns) -> list:
    hits = []
    for pat in patterns:
        m = pat.search(text)
        if m:
            hits.append(m.group(0)[:80])
    return hits


def usable_agents(cfg: dict, tools: dict) -> list:
    return [a for a in cfg.get("agent_order", [])
            if a in AGENT_COMMANDS and tools.get(a, {}).get("status") == "AVAILABLE"]


def needs_user_loop(reason: str, tools: dict, prompt: str | None) -> None:
    avail = ", ".join(n for n, v in tools.items()
                      if v["status"] == "AVAILABLE" and n in AGENT_COMMANDS) or "none"
    msg = (
        f"# NEEDS_USER_LOOP\n\nGenerated {now_iso()}\n\n"
        f"The operator runner cannot SAFELY self-start agent execution.\n\n"
        f"Reason: {reason}\n\nActive prompt: {prompt}\n\nAgent CLIs present: {avail}\n\n"
        f"To proceed, either:\n"
        f"1. Invoke `/loop` inside an interactive Claude Code session with the active prompt, OR\n"
        f"2. Set `agent_exec.enabled: true` in operator_config.json AFTER verifying your chosen agent CLI runs "
        f"the prompt non-interactively and safely (see OPERATOR_PROTOCOL.md section 10).\n\n"
        f"The runner did NOT invoke any agent and did NOT fake automation.\n"
    )
    write_text("NEEDS_USER_LOOP.md", msg)
    (HERE / "NEEDS_USER_LOOP.md").write_text(msg, encoding="utf-8")


def build_plan(cfg: dict, tools: dict, usable: list, prompt: str | None, agent_enabled: bool) -> str:
    avail = [f"{n} ({v['path']})" for n, v in tools.items() if v["status"] == "AVAILABLE"]
    self_start = "YES" if (usable and agent_enabled) else "NO"
    lines = [
        "# Daena Operator -- DRY RUN PLAN", "", f"Generated {now_iso()}", "",
        f"- Config source: {cfg.get('_config_source')}",
        f"- Active prompt: {prompt}",
        f"- Agent order (configured): {', '.join(cfg.get('agent_order', []))}",
        f"- Agent CLIs usable now: {', '.join(usable) if usable else 'NONE'}",
        f"- agent_exec.enabled: {agent_enabled}",
        f"- SELF_START available: {self_start}",
        f"- post_agent_verify enabled: {bool((cfg.get('post_agent_verify') or {}).get('enabled'))} "
        f"(operator runs tests for the agent's changes + commits scoped if green)",
        "", "## Would do (no agent invoked in dry-run):",
    ]
    if self_start == "YES":
        lines += [
            f"1. Invoke `{usable[0]}` non-interactively on the active prompt.",
            "2. Stream redacted output to logs/session_<ts>.log; heartbeat state.json every checkpoint_minutes.",
            "3. Scan output for hard-gate markers; if any -> write hard_gate.md and STOP.",
            "4. Write last_result.md + state.json; continue up to max_loops or until only gated items remain.",
        ]
    else:
        lines += [
            "1. Write NEEDS_USER_LOOP.md (no usable+enabled agent CLI).",
            "2. Require `/loop` in an interactive session OR enable+verify agent_exec.",
            "3. Do NOT fake automation.",
        ]
    lines += ["", "## Tools detected", *[f"- {a}" for a in avail],
              "", "## Hard gates (never auto-acted): " + ", ".join(cfg.get("hard_gates", []))]
    return "\n".join(lines) + "\n"


def render_result(agent: str, prompt: str, res: dict) -> str:
    return (
        f"# last_result\n\nGenerated {now_iso()}\n\n"
        f"- Agent: {agent}\n- Prompt: {prompt}\n- Exit code: {res.get('exit_code')}\n"
        f"- Timed out: {res.get('timed_out')}\n- TRUE_HARD_GATE markers (STOP): {res.get('gate_hits')}\n"
        f"- MENTION_ONLY markers (informational, NOT a stop): {res.get('mention_hits')}\n"
        f"- Done markers: {res.get('done_hits')}\n"
        + (f"- Launch error: {res['error']}\n" if res.get("error") else "")
        + f"\n## Tail (redacted, last 4k chars)\n\n```\n{(res.get('tail') or '')[-4000:]}\n```\n"
    )


def run_agent(cfg: dict, agent: str, prompt_path: str, session_log: Path) -> dict:
    """Invoke an agent CLI non-interactively. Streams redacted output to session_log."""
    prompt_text = Path(prompt_path).read_text(encoding="utf-8")
    template = AGENT_COMMANDS[agent]
    exe = shutil.which(agent) or template[0]
    cmd = [exe] + [c.replace("{prompt_text}", prompt_text).replace("{prompt_path}", str(prompt_path))
                   for c in template[1:]]
    timeout_s = int(cfg.get("max_minutes_per_loop", 90)) * 60
    checkpoint_s = max(60, int(cfg.get("checkpoint_minutes", 15)) * 60)
    start = time.time()
    last_ckpt = start
    tail: list[str] = []
    with open(session_log, "a", encoding="utf-8") as log:
        log.write(f"\n=== RUN_AGENT {agent} @ {now_iso()} (prompt inline; secrets redacted) ===\n")
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, encoding="utf-8", errors="replace", bufsize=1,
                                    cwd=cfg.get("root", str(HERE)))
        except Exception as e:  # noqa: BLE001 -- report, never raise into the loop
            log.write(f"AGENT_LAUNCH_ERROR: {e}\n")
            return {"exit_code": None, "tail": "", "gate_hits": [], "done_hits": [],
                    "timed_out": False, "error": str(e)}
        timed_out = False
        for line in proc.stdout:  # type: ignore[union-attr]
            line = redact(line.rstrip("\n"))
            log.write(line + "\n")
            log.flush()
            tail.append(line)
            if len(tail) > 200:
                tail.pop(0)
            t = time.time()
            if t - last_ckpt >= checkpoint_s:
                last_ckpt = t
                write_state({"state": "MONITOR", "agent": agent, "elapsed_s": int(t - start), "ts": now_iso()})
            if t - start > timeout_s:
                proc.kill()
                timed_out = True
                log.write(f"TIMEOUT after {timeout_s}s -- killed\n")
                break
        proc.wait()
    tail_text = "\n".join(tail)
    return {"exit_code": proc.returncode, "tail": tail_text, "timed_out": timed_out,
            "gate_hits": scan(tail_text, GATE_MARKERS),
            "mention_hits": scan(tail_text, MENTION_ONLY_MARKERS),
            "done_hits": scan(tail_text, DONE_MARKERS)}


# Backend files whose change warrants a full-suite regression (hot paths).
HOT_PATH_FILES = ("chat_orchestrator.py", "llm_service.py", "tool_use_loop.py", "query_understanding.py", "security_gate.py")


def git_status_map(root: str) -> dict:
    """{path: 'XY'} from `git status --porcelain` -- the current working-tree state."""
    try:
        out = subprocess.run(["git", "status", "--porcelain"], cwd=root,
                             capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    except Exception:  # noqa: BLE001
        return {}
    m = {}
    for line in out.stdout.splitlines():
        if len(line) > 3:
            m[line[3:].strip().strip('"')] = line[:2]
    return m


def classify_change(path: str) -> str:
    p = path.replace("\\", "/")
    if p.startswith("backend/migrations/") or "/models/" in p:
        return "migration_or_model"
    if p.startswith("backend/") and p.endswith(".py"):
        return "backend_code"
    if p.startswith("frontend/"):
        return "frontend"
    if p.endswith(".md") or p.startswith("Doc/") or p.startswith("docs/"):
        return "docs"
    return "other"


def _run_cmd(cmd: list, cwd: str, session_log: Path, timeout_s: int) -> int:
    """Run a SAFE local command, append redacted output to the session log. Returns exit code."""
    with open(session_log, "a", encoding="utf-8") as log:
        log.write(f"\n$ ({cwd}) {' '.join(str(c) for c in cmd)}\n")
        try:
            out = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                                 encoding="utf-8", errors="replace", timeout=timeout_s)
        except Exception as e:  # noqa: BLE001
            log.write(f"CMD_ERROR: {e}\n")
            return 1
        log.write(redact((out.stdout or "") + (out.stderr or ""))[-3000:] + f"\n[exit {out.returncode}]\n")
        return out.returncode


def post_agent_verify(cfg: dict, before: dict, after: dict, session_log: Path) -> dict:
    """Operator-side verification: headless agents can edit but cannot run pytest/Docker, so after an agent run
    the OPERATOR classifies THIS run's changes (diff vs the pre-run snapshot -- never the pre-existing dirty tree),
    runs the safe test/build/smoke commands for what changed, and commits ONLY those scoped files if green.
    Never sends, deploys, touches secrets, or runs `git add -A`."""
    pv = cfg.get("post_agent_verify") or {}
    if not pv.get("enabled", False):
        return {"ran": False, "reason": "post_agent_verify disabled"}
    root = cfg.get("root", str(HERE))
    backend = str(Path(root) / "backend")
    py = str(Path(backend) / ".venv" / "Scripts" / "python.exe")
    changed = sorted(p for p, code in after.items() if before.get(p) != code)
    if not changed:
        return {"ran": True, "changed": [], "committed": False, "reason": "no new changes from this agent run"}
    kinds = sorted({classify_change(p) for p in changed})
    results: list = []
    green = True

    def runc(cmd, cwd, timeout_s, label):
        nonlocal green
        rc = _run_cmd(cmd, cwd, session_log, timeout_s)
        results.append({"label": label, "exit": rc})
        if rc != 0:
            green = False
        return rc

    if ("backend_code" in kinds or "migration_or_model" in kinds) and pv.get("run_backend_targeted", True):
        runc([py, "-m", "pytest", "-q", "tests", "-k",
              "runtime or trace or memory or stream or governance or settings or error_event",
              "--timeout=120"], backend, 1800, "backend_targeted")
        hot = any(any(h in p for h in HOT_PATH_FILES) for p in changed)
        if hot and green and pv.get("full_suite_after_backend_hot_path", True):
            runc([py, "-m", "pytest", "-q", "--timeout=120"], backend, 3600, "full_suite")
    if "migration_or_model" in kinds:
        runc([py, "-m", "alembic", "-c", "migrations/alembic.ini", "heads"], backend, 120, "alembic_heads")
        if (pv.get("full_suite_after_migration", True) and green
                and not any(r["label"].startswith("full_suite") for r in results)):
            runc([py, "-m", "pytest", "-q", "--timeout=120"], backend, 3600, "full_suite_migration")
    if "frontend" in kinds and pv.get("run_frontend_build_if_changed", True):
        runc(["npm", "run", "build"], str(Path(root) / "frontend"), 900, "frontend_build")
    runtime_relevant = any(k in kinds for k in ("backend_code", "migration_or_model", "frontend"))
    if pv.get("run_smoke", True) and runtime_relevant:
        runc(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "scripts/verify_runtime_local.ps1"],
             root, 300, "smoke")

    committed = False
    if green and pv.get("commit_if_green", True):
        subprocess.run(["git", "add", "--"] + changed, cwd=root, capture_output=True, text=True, timeout=120)
        msg = ("chore(operator): verified + committed agent changes [" + ", ".join(kinds) + "]\n\n"
               "Auto-committed by the operator post_agent_verify step after GREEN tests (the headless agent cannot "
               "run pytest). Scoped to this run's changes only; no git add -A.\n\n"
               "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>")
        cm = subprocess.run(["git", "commit", "-q", "-m", msg], cwd=root, capture_output=True, text=True, timeout=300)
        committed = cm.returncode == 0
    return {"ran": True, "changed": changed, "kinds": kinds, "results": results,
            "green": green, "committed": committed}


def render_verify(v: dict) -> str:
    if not v.get("ran"):
        return f"\n## Post-agent verify\n\nNOT RUN ({v.get('reason')}).\n"
    lines = [f"  - {r['label']}: exit {r['exit']}" for r in v.get("results", [])]
    return (f"\n## Post-agent verify\n\n- Changed (this run): {v.get('changed')}\n- Kinds: {v.get('kinds')}\n"
            f"- Green: {v.get('green')}\n- Committed (scoped): {v.get('committed')}\n"
            + (f"- Reason: {v['reason']}\n" if v.get("reason") else "")
            + ("- Verify commands:\n" + "\n".join(lines) + "\n" if lines else ""))


def operator_loop(cfg: dict, mode: str, max_iter: int, dry_run: bool) -> int:
    LOGS.mkdir(parents=True, exist_ok=True)
    session_log = LOGS / f"session_{ts_slug()}.log"
    tools = detect_tools()
    usable = usable_agents(cfg, tools)
    agent_enabled = bool((cfg.get("agent_exec") or {}).get("enabled", False)) and bool(cfg.get("allow_code_changes", True))

    def log(msg: str) -> None:
        with open(session_log, "a", encoding="utf-8") as f:
            f.write(f"[{now_iso()}] {msg}\n")

    state = {"state": "IDLE", "mode": mode, "ts": now_iso(), "session_log": str(session_log),
             "config_source": cfg.get("_config_source"), "loops_done": 0}
    write_state(state)
    log(f"operator start mode={mode} dry_run={dry_run} usable={usable} agent_enabled={agent_enabled}")

    cap = max(1, min(int(max_iter), int(cfg.get("max_loops", 3))))
    for i in range(1, cap + 1):
        state.update(state="LOAD_PROMPT", loops_done=i - 1, ts=now_iso())
        write_state(state)
        prompt = find_next_prompt(cfg)
        if not prompt:
            log("ERROR: no next-prompt file found")
            state.update(state="ERROR", ts=now_iso())
            write_state(state)
            write_text("last_result.md", "# last_result\n\nERROR: no next-prompt file found in priority list.\n")
            return 2
        log(f"iter {i}/{cap} prompt={prompt}")

        if dry_run:
            plan = build_plan(cfg, tools, usable, prompt, agent_enabled)
            write_text("last_result.md", plan)
            state.update(state="DONE", loops_done=i, ts=now_iso())
            write_state(state)
            log("dry-run plan written; no agent invoked")
            print(plan)
            return 0

        if not usable or not agent_enabled:
            reason = ("no available agent CLI with a known non-interactive mode" if not usable
                      else "agent_exec.enabled is false / not verified")
            needs_user_loop(reason, tools, prompt)
            state.update(state="HARD_GATE", ts=now_iso(), note=reason)
            write_state(state)
            log(f"cannot self-start: {reason}")
            return 3

        agent = usable[0]
        state.update(state="RUN_AGENT", agent=agent, ts=now_iso())
        write_state(state)
        log(f"invoking agent={agent}")
        before = git_status_map(cfg.get("root", str(HERE)))
        res = run_agent(cfg, agent, prompt, session_log)
        state.update(state="PARSE_RESULT", ts=now_iso(), exit_code=res.get("exit_code"))
        write_state(state)

        if res.get("gate_hits"):
            write_text("last_result.md", render_result(agent, prompt, res))
            write_text("hard_gate.md",
                       f"# HARD_GATE\n\n{now_iso()}\n\nAgent signalled a gate/block:\n- "
                       + "\n- ".join(res["gate_hits"])
                       + f"\n\nAgent: {agent}\nPrompt: {prompt}\n\nStopped. Founder action required.\n")
            state.update(state="HARD_GATE", ts=now_iso())
            write_state(state)
            log("HARD_GATE detected in agent output -- stopping")
            return 4

        # Post-agent SELF-VERIFY: operator runs tests for what THIS agent run changed (headless agents can't run
        # pytest), then commits the scoped changes only if green. Never sends/deploys/touches secrets.
        state.update(state="VERIFY", ts=now_iso())
        write_state(state)
        verify = post_agent_verify(cfg, before, git_status_map(cfg.get("root", str(HERE))), session_log)
        write_text("last_result.md", render_result(agent, prompt, res) + render_verify(verify))
        log(f"verify ran={verify.get('ran')} green={verify.get('green')} committed={verify.get('committed')}")
        if verify.get("ran") and verify.get("changed") and not verify.get("green", True):
            write_text("verify_failed.md",
                       f"# VERIFY_FAILED\n\n{now_iso()}\n\nAgent edits failed verification -- NOT committed (held "
                       f"for review).\nChanged: {verify.get('changed')}\nResults: {verify.get('results')}\n")
            state.update(state="VERIFY_FAILED", ts=now_iso())
            write_state(state)
            log("post-agent verify FAILED -- changes held, stopping")
            return 5

        if mode == "once":
            state.update(state="DONE", loops_done=i, ts=now_iso())
            write_state(state)
            return 0
        state.update(state="CONTINUE", loops_done=i, ts=now_iso())
        write_state(state)
        log("iteration complete -- continuing")

    state.update(state="DONE", ts=now_iso())
    write_state(state)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Daena Operator Runner -- safe local sprint supervisor")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", help="plan only; never invoke an agent (default)")
    g.add_argument("--once", action="store_true", help="one loop iteration")
    g.add_argument("--loop", type=int, metavar="N", help="up to N iterations (bounded by config max_loops)")
    ap.add_argument("--config", help="path to operator_config.json")
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    if args.once:
        return operator_loop(cfg, "once", 1, dry_run=False)
    if args.loop is not None:
        return operator_loop(cfg, "loop", args.loop, dry_run=False)
    return operator_loop(cfg, "dry-run", 1, dry_run=True)


if __name__ == "__main__":
    sys.exit(main())
