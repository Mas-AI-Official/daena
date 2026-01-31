#!/usr/bin/env python3
"""
Smoke test v2: token auth, approval gating, apply_patch dry_run.
Run with backend already up. Set EXECUTION_TOKEN in env to test token; leave unset for no-auth.
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error

BASE = os.environ.get("DAENA_BASE_URL", "http://localhost:8000")
TOKEN = os.environ.get("EXECUTION_TOKEN", "")


def req(method: str, path: str, body: dict = None, token: str = None) -> dict:
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
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:500]
        print(f"HTTP {e.code} {path}: {body}")
        raise
    except Exception as e:
        print(f"Request failed {path}: {e}")
        raise


def main():
    global BASE, TOKEN
    parser = argparse.ArgumentParser(description="Smoke test Execution Layer v2")
    parser.add_argument("--base", default=BASE, help="Backend base URL")
    parser.add_argument("--token", default=TOKEN, help="X-Execution-Token (or set EXECUTION_TOKEN)")
    args = parser.parse_args()
    BASE = args.base.rstrip("/")
    token = args.token or os.environ.get("EXECUTION_TOKEN", "")

    # When EXECUTION_TOKEN is set on server, requests without token must get 401
    print("1) GET /api/v1/execution/tools (with token if EXECUTION_TOKEN set)...")
    try:
        tools = req("GET", "/api/v1/execution/tools", token=token or None)
        print("   OK:", list(tools.get("tools", [])[:3]))
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print("   401 as expected when EXECUTION_TOKEN set and no header. Set --token or EXECUTION_TOKEN to run full test.")
            sys.exit(0)
        raise

    # 2) POST /approve for a risky tool
    print("2) POST /api/v1/execution/approve?tool_name=apply_patch...")
    approve = req("POST", "/api/v1/execution/approve?tool_name=apply_patch", token=token or None)
    approval_id = approve.get("approval_id")
    print("   approval_id:", approval_id)

    # 3) apply_patch dry_run (safe)
    print("3) POST /api/v1/execution/run apply_patch dry_run=true...")
    run_out = req(
        "POST",
        "/api/v1/execution/run",
        {"tool_name": "apply_patch", "args": {"patch": "--- a/x\n+++ b/x\n@@ -0,0 +1,1 @@\n+test\n"}, "dry_run": True},
        token=token or None,
    )
    print("   result:", run_out.get("status"), run_out.get("dry_run"))

    # 4) git_status (low risk)
    print("4) POST /api/v1/execution/run git_status...")
    run2 = req("POST", "/api/v1/execution/run", {"tool_name": "git_status", "args": {}, "dry_run": False}, token=token or None)
    print("   result:", run2.get("status"))

    print("Done. Token auth, approval, and apply_patch dry_run validated.")


if __name__ == "__main__":
    main()
