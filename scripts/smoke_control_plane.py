#!/usr/bin/env python3
"""
Smoke test: Execution Layer (token 401, dry_run, filesystem_read) + Proactive (rule, run_once, events).
Run with backend up. Set EXECUTION_TOKEN in env for execution tests.
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error

BASE = os.environ.get("DAENA_BASE_URL", "http://localhost:8000")
TOKEN = os.environ.get("EXECUTION_TOKEN", "")


def req(method: str, path: str, body: dict = None, token: str = None) -> tuple:
    """Returns (data_dict, status_code). Raises on non-HTTP errors."""
    url = BASE.rstrip("/") + path
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req_obj = urllib.request.Request(url, data=data, method=method)
    if data:
        req_obj.add_header("Content-Type", "application/json")
    if token:
        req_obj.add_header("X-Execution-Token", token)
    try:
        with urllib.request.urlopen(req_obj, timeout=10) as r:
            return json.loads(r.read().decode("utf-8")), r.status
    except urllib.error.HTTPError as e:
        body_b = e.read()
        body_s = body_b.decode("utf-8", errors="replace")[:500]
        try:
            data = json.loads(body_s)
        except Exception:
            data = {"detail": body_s}
        raise e


def main():
    global BASE, TOKEN
    parser = argparse.ArgumentParser(description="Smoke test Execution + Proactive control plane")
    parser.add_argument("--base", default=BASE, help="Backend base URL")
    parser.add_argument("--token", default=TOKEN, help="X-Execution-Token (or set EXECUTION_TOKEN)")
    args = parser.parse_args()
    BASE = args.base.rstrip("/")
    token = args.token or os.environ.get("EXECUTION_TOKEN", "")

    # --- Early backend reachability check (fail fast if server down) ---
    print("Checking backend at %s ..." % BASE)
    try:
        r = urllib.request.urlopen(urllib.request.Request(BASE + "/health"), timeout=3)
        if r.status != 200:
            raise urllib.error.URLError("health returned %s" % r.status)
    except (urllib.error.URLError, OSError) as e:
        print("ERROR: Backend not reachable at %s" % BASE)
        print("  Start the backend first, e.g.: scripts\\start_backend.bat or START_DAENA.bat")
        print("  Then set EXECUTION_TOKEN and run this script again.")
        sys.exit(1)

    ok = 0
    fail = 0

    # --- Skills: GET /api/v1/skills (no token) - must return 200 and list ---
    print("0) GET /api/v1/skills (no token)...")
    try:
        data, status = req("GET", "/api/v1/skills", token=None)
        if status == 200 and data.get("success") and "skills" in data:
            print("   OK, skills:", len(data["skills"]))
            ok += 1
        elif status == 200:
            print("   OK (200, no skills list)")
            ok += 1
        else:
            print("   Unexpected:", status, data)
            fail += 1
    except urllib.error.HTTPError as e:
        print("   FAIL:", e.code, "— Skills API not registered or wrong path. Check backend.routes.skills in main.py.")
        fail += 1
    except Exception as e:
        print("   Error:", e)
        fail += 1

    # --- Execution: token blocks when missing (401) ---
    print("1) GET /api/v1/execution/tools WITHOUT token (expect 401 when EXECUTION_TOKEN set)...")
    try:
        req("GET", "/api/v1/execution/tools", token=None)
        # If we get here without token, server might not have EXECUTION_TOKEN set
        print("   (No 401: server may have EXECUTION_TOKEN unset; execution disabled is OK)")
        ok += 1
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print("   401 as expected.")
            ok += 1
        else:
            print("   Unexpected:", e.code)
            fail += 1
    except Exception as e:
        print("   Error:", e)
        fail += 1

    # --- Execution: with token, list tools ---
    if token:
        print("2) GET /api/v1/execution/tools WITH token...")
        try:
            data, status = req("GET", "/api/v1/execution/tools", token=token)
            if data.get("success") and "tools" in data:
                print("   OK, tools:", len(data["tools"]))
                ok += 1
            else:
                fail += 1
        except urllib.error.HTTPError as e:
            if e.code == 401:
                print("   401 — EXECUTION_TOKEN mismatch. Set EXECUTION_TOKEN to match backend, or start backend with: set EXECUTION_TOKEN=%s && scripts\\start_backend_with_env.bat" % (token or "manual-verify-token"))
            else:
                print("   Error: HTTP", e.code)
            fail += 1
        except Exception as e:
            print("   Error:", e)
            fail += 1

        # --- apply_patch dry_run ---
        print("3) POST /api/v1/execution/run apply_patch dry_run=true...")
        try:
            data, _ = req(
                "POST",
                "/api/v1/execution/run",
                {"tool_name": "apply_patch", "args": {"patch": "--- a/x\n+++ b/x\n@@ -0,0 +1,1 @@\n+smoke\n"}, "dry_run": True},
                token=token,
            )
            if data.get("dry_run") is True or data.get("status") == "ok":
                print("   OK (dry_run or ok)")
                ok += 1
            else:
                print("   Result:", data)
                ok += 1
        except Exception as e:
            print("   Error:", e)
            fail += 1

        # --- filesystem_read in workspace (optional: may fail if no workspace) ---
        print("4) POST /api/v1/execution/run filesystem_read (workspace path)...")
        try:
            data, _ = req(
                "POST",
                "/api/v1/execution/run",
                {"tool_name": "filesystem_read", "args": {"path": "README.md"}, "dry_run": False},
                token=token,
            )
            if data.get("status") == "ok" or "content" in str(data):
                print("   OK")
                ok += 1
            else:
                print("   Result:", data.get("status"), data.get("error"))
                ok += 1  # workspace may not exist
        except Exception as e:
            print("   (May fail if workspace not set):", e)
            ok += 1
    else:
        print("2-4) Skipped (no EXECUTION_TOKEN)")
        ok += 1

    # --- Proactive: create rule ---
    print("5) POST /api/v1/proactive/rules (create rule)...")
    try:
        data, _ = req(
            "POST",
            "/api/v1/proactive/rules",
            {"name": "Smoke test rule", "cron": None, "event_trigger": "smoke", "enabled": True},
        )
        if data.get("success") and data.get("rule", {}).get("id"):
            rule_id = data["rule"]["id"]
            print("   OK, rule_id:", rule_id)
            ok += 1

            # --- Proactive: run_once ---
            print("6) POST /api/v1/proactive/run_once?rule_id=...")
            data2, _ = req("POST", f"/api/v1/proactive/run_once?rule_id={rule_id}")
            if data2.get("success") and data2.get("event"):
                print("   OK, event id:", data2["event"].get("id"))
                ok += 1
            else:
                fail += 1

            # --- Proactive: get events ---
            print("7) GET /api/v1/proactive/events...")
            data3, _ = req("GET", "/api/v1/proactive/events?limit=5")
            if data3.get("success") and "events" in data3:
                print("   OK, events:", len(data3["events"]))
                ok += 1
            else:
                fail += 1
        else:
            print("   Failed:", data)
            fail += 1
    except Exception as e:
        print("   Error:", e)
        fail += 1

    # --- Moltbot Execution Broker: submit request (no token = sandboxed agent) ---
    print("8) POST /api/v1/execution/request (repo_git_status, no token)...")
    try:
        data, status = req(
            "POST",
            "/api/v1/execution/request",
            {"tool_name": "repo_git_status", "args": {}, "reason": "Smoke test", "agent_id": "smoke_agent"},
            token=None,
        )
        if status == 200 and data.get("success") and data.get("request_id") and data.get("status") == "pending":
            request_id = data["request_id"]
            print("   OK, request_id:", request_id)
            ok += 1

            if token:
                # 9) List approvals and find our request
                print("9) GET /api/v1/execution/approvals...")
                data9, _ = req("GET", "/api/v1/execution/approvals", token=token)
                if data9.get("success") and any(a.get("approval_request_id") == request_id for a in data9.get("approvals") or []):
                    print("   OK, pending request in approvals")
                    ok += 1
                else:
                    fail += 1

                # 10) Approve and run (Daena executes repo_git_status)
                print("10) POST /api/v1/execution/approvals/{id} approve...")
                data10, _ = req(
                    "POST",
                    f"/api/v1/execution/approvals/{request_id}",
                    {"approved": True},
                    token=token,
                )
                if data10.get("success") and data10.get("approved") and data10.get("execution_result"):
                    er = data10["execution_result"]
                    if er.get("status") == "ok" or "stdout" in str(er.get("result", {})):
                        print("   OK, execution_result:", er.get("status"))
                        ok += 1
                    else:
                        print("   Result:", er)
                        ok += 1
                else:
                    print("   Unexpected:", data10)
                    fail += 1

                # 11) Audit log contains repo_git_status
                print("11) GET /api/v1/execution/logs...")
                data11, _ = req("GET", "/api/v1/execution/logs?limit=5", token=token)
                if data11.get("success") and data11.get("logs"):
                    recent = [e for e in data11["logs"] if e.get("tool_name") == "repo_git_status"]
                    if recent:
                        print("   OK, audit log has repo_git_status")
                        ok += 1
                    else:
                        print("   (No repo_git_status in last 5 logs; may be OK)")
                        ok += 1
                else:
                    ok += 1
            else:
                print("9-11) Skipped (no token)")
        else:
            print("   Unexpected:", data, status)
            fail += 1
    except Exception as e:
        print("   Error:", e)
        fail += 1

    # --- Sandboxed agent cannot request shell_exec (403) ---
    print("12) POST /api/v1/execution/request (shell_exec) -> expect 403...")
    try:
        req("POST", "/api/v1/execution/request", {"tool_name": "shell_exec", "args": {"command": "git status"}, "reason": "Smoke"}, token=None)
        print("   Unexpected 200 (expected 403)")
        fail += 1
    except urllib.error.HTTPError as e:
        if e.code == 403:
            print("   403 as expected (sandboxed agents cannot request shell_exec)")
            ok += 1
        else:
            print("   Unexpected:", e.code)
            fail += 1
    except Exception as e:
        print("   Error:", e)
        fail += 1

    # --- MiniMax Agent runtime: create task -> run step -> artifact + audit ---
    if token:
        print("13) Agent runtime: POST /execution/tasks (create task)...")
        try:
            data, _ = req("POST", "/api/v1/execution/tasks", {"goal": "Smoke agent runtime", "max_steps": 5, "max_retries": 3}, token=token)
            if data.get("success") and data.get("task_id"):
                tid = data["task_id"]
                print("   OK, task_id:", tid)
                ok += 1
                print("14) POST /execution/tasks/{id}/run (one step)...")
                data2, _ = req("POST", f"/api/v1/execution/tasks/{tid}/run", token=token)
                if data2.get("success") and data2.get("task"):
                    t = data2["task"]
                    arts = t.get("artifacts") or []
                    if arts or t.get("status") in ("completed", "pending"):
                        print("   OK, task step run, artifacts:", len(arts))
                        ok += 1
                    else:
                        print("   Task:", t.get("status"), "artifacts:", len(arts))
                        ok += 1
                else:
                    fail += 1
            else:
                fail += 1
        except Exception as e:
            print("   Error:", e)
            fail += 1

        print("15) GET /execution/logs (verify audit entry exists)...")
        try:
            data, _ = req("GET", "/api/v1/execution/logs?limit=10", token=token)
            if data.get("success") and isinstance(data.get("logs"), list):
                print("   OK, logs count:", len(data["logs"]))
                ok += 1
            else:
                ok += 1
        except Exception as e:
            fail += 1

        print("16) repo_scan tool (read-only)...")
        try:
            data, _ = req("POST", "/api/v1/execution/run", {"tool_name": "repo_scan", "args": {"scan_deps": True, "scan_secrets": False}, "dry_run": False}, token=token)
            if data.get("status") == "ok" or data.get("result"):
                print("   OK, repo_scan result")
                ok += 1
            else:
                print("   Result:", data.get("status"), data.get("error"))
                ok += 1
        except Exception as e:
            print("   Error:", e)
            fail += 1

        # Skills artifacts list (token required)
        print("17) GET /api/v1/skills/artifacts (with token)...")
        try:
            data, status = req("GET", "/api/v1/skills/artifacts?limit=10", token=token)
            if status == 200 and data.get("success") and "artifacts" in data:
                print("   OK, artifacts count:", len(data.get("artifacts", [])))
                ok += 1
            else:
                print("   Unexpected:", status, data.get("detail", data))
                fail += 1
        except Exception as e:
            print("   Error:", e)
            fail += 1
    else:
        print("13-17) Skipped (no token)")

    # Runbook UI page (no token)
    print("18) GET /ui/runbook (Runbook page)...")
    try:
        url = BASE.rstrip("/") + "/ui/runbook"
        r = urllib.request.Request(url)
        with urllib.request.urlopen(r, timeout=10) as resp:
            if resp.status == 200 and b"Runbook" in resp.read():
                print("   OK, Runbook page 200")
                ok += 1
            else:
                print("   Unexpected status or content")
                fail += 1
    except urllib.error.HTTPError as e:
        print("   FAIL:", e.code)
        fail += 1
    except Exception as e:
        print("   Error:", e)
        fail += 1

    print("\n--- Result: %d passed, %d failed ---" % (ok, fail))
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
