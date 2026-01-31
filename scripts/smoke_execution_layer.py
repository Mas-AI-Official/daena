#!/usr/bin/env python3
"""
Smoke test for Execution Layer: list tools, run git_status (dry_run), print audit log.
Run with backend already up: python scripts/smoke_execution_layer.py
Or use: python scripts/smoke_execution_layer.py --start (start backend in subprocess, then run).
"""

import argparse
import json
import os
import subprocess
import sys
import time

try:
    import urllib.request
    import urllib.error
except ImportError:
    urllib = None

BASE = "http://localhost:8000"


def req(method: str, path: str, body: dict = None) -> dict:
    url = BASE + path
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req_obj = urllib.request.Request(url, data=data, method=method)
    if data:
        req_obj.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req_obj, timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code} {path}: {e.read().decode('utf-8', errors='replace')[:500]}")
        raise
    except Exception as e:
        print(f"Request failed {path}: {e}")
        raise


def main():
    global BASE
    parser = argparse.ArgumentParser(description="Smoke test Execution Layer")
    parser.add_argument("--base", default="http://localhost:8000", help="Backend base URL")
    parser.add_argument("--start", action="store_true", help="Start backend in subprocess then run test")
    args = parser.parse_args()
    BASE = args.base.rstrip("/")

    if args.start:
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent
        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000"],
            cwd=str(root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(30):
            time.sleep(0.5)
            try:
                req("GET", "/api/v1/execution/tools")
                break
            except Exception:
                continue
        else:
            proc.terminate()
            print("Backend did not become ready in time")
            sys.exit(1)

    try:
        # 1) List tools
        print("1) GET /api/v1/execution/tools")
        tools = req("GET", "/api/v1/execution/tools")
        print(json.dumps(tools, indent=2)[:800])
        print()

        # 2) Run git_status (dry_run)
        print("2) POST /api/v1/execution/run { tool_name: git_status, dry_run: true }")
        run_out = req("POST", "/api/v1/execution/run", {"tool_name": "git_status", "args": {}, "dry_run": True})
        print(json.dumps(run_out, indent=2))
        print()

        # 3) Run git_status for real (if enabled)
        print("3) POST /api/v1/execution/run { tool_name: git_status, dry_run: false }")
        run_real = req("POST", "/api/v1/execution/run", {"tool_name": "git_status", "args": {}, "dry_run": False})
        print(json.dumps(run_real, indent=2))
        print()

        # 4) Audit log
        print("4) GET /api/v1/execution/logs?limit=1 (latest audit entry)")
        logs = req("GET", "/api/v1/execution/logs?limit=1")
        if logs.get("logs"):
            print(json.dumps(logs["logs"][0], indent=2))
        else:
            print("(no log entries)")
        print("Done.")
    finally:
        if args.start and proc:
            proc.terminate()


if __name__ == "__main__":
    main()
