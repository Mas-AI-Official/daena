#!/usr/bin/env python3
"""
Smoke test: Windows Node (Pair Node) and execution layer node endpoints.
- Without X-Execution-Token: node/health and node/config must return 401.
- With token: GET node/config returns url and has_token; GET node/health returns success (true if node up, false if down).
- Does not require the Windows node to be running; backend must be up.
Usage:
  set EXECUTION_TOKEN=your-token
  python scripts/smoke_windows_node.py [--base http://localhost:8000] [--token %EXECUTION_TOKEN%]
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
    """Returns (data_dict, status_code). Raises HTTPError on 4xx/5xx."""
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
        return data, e.code


def main():
    global BASE, TOKEN
    parser = argparse.ArgumentParser(description="Smoke test Windows Node (Pair Node) endpoints")
    parser.add_argument("--base", default=BASE, help="Backend base URL")
    parser.add_argument("--token", default=TOKEN, help="X-Execution-Token (or set EXECUTION_TOKEN)")
    args = parser.parse_args()
    BASE = args.base.rstrip("/")
    token = args.token or os.environ.get("EXECUTION_TOKEN", "")

    print("Smoke test: Windows Node (Pair Node)")
    print("  Base: %s" % BASE)
    print("  Token: %s" % ("(set)" if token else "(not set)"))

    # Backend reachability
    try:
        r = urllib.request.urlopen(urllib.request.Request(BASE + "/health"), timeout=3)
        if r.status != 200:
            raise urllib.error.URLError("health returned %s" % r.status)
    except (urllib.error.URLError, OSError) as e:
        print("ERROR: Backend not reachable at %s" % BASE)
        print("  Start the backend first, then set EXECUTION_TOKEN and run again.")
        sys.exit(1)

    ok = 0
    fail = 0

    # 1) Without token: GET node/health → 401
    print("1) GET /api/v1/execution/node/health (no token) -> expect 401")
    try:
        data, status = req("GET", "/api/v1/execution/node/health", token=None)
        if status == 401:
            print("   OK (401 Unauthorized)")
            ok += 1
        else:
            print("   FAIL: expected 401, got %s" % status)
            fail += 1
    except Exception as e:
        print("   FAIL: %s" % e)
        fail += 1

    # 2) Without token: GET node/config → 401
    print("2) GET /api/v1/execution/node/config (no token) -> expect 401")
    try:
        data, status = req("GET", "/api/v1/execution/node/config", token=None)
        if status == 401:
            print("   OK (401 Unauthorized)")
            ok += 1
        else:
            print("   FAIL: expected 401, got %s" % status)
            fail += 1
    except Exception as e:
        print("   FAIL: %s" % e)
        fail += 1

    if not token:
        print("  (Skipping token-required checks; set EXECUTION_TOKEN to run them)")
        print("--- Result: %d passed, %d failed ---" % (ok, fail))
        sys.exit(0 if fail == 0 else 1)

    # 3) With token: GET node/config → 200, url and has_token
    print("3) GET /api/v1/execution/node/config (with token)")
    try:
        data, status = req("GET", "/api/v1/execution/node/config", token=token)
        if status == 200 and data.get("success") and "url" in data:
            print("   OK url=%s has_token=%s" % (data.get("url", ""), data.get("has_token", False)))
            ok += 1
        else:
            print("   FAIL: %s %s" % (status, data))
            fail += 1
    except Exception as e:
        print("   FAIL: %s" % e)
        fail += 1

    # 4) With token: GET node/health → 200 (success true or false depending on node)
    print("4) GET /api/v1/execution/node/health (with token)")
    try:
        data, status = req("GET", "/api/v1/execution/node/health", token=token)
        if status == 200 and "success" in data:
            node_ok = data.get("node", {}).get("status") == "ok"
            print("   OK (node %s)" % ("up" if node_ok else "down/unreachable"))
            ok += 1
        else:
            print("   FAIL: %s %s" % (status, data))
            fail += 1
    except Exception as e:
        print("   FAIL: %s" % e)
        fail += 1

    # 5) With token: POST node/config (optional) - save url only, no token
    print("5) POST /api/v1/execution/node/config (with token, url only)")
    try:
        data, status = req("POST", "/api/v1/execution/node/config", body={"url": "http://127.0.0.1:18888"}, token=token)
        if status == 200 and data.get("success"):
            print("   OK (config saved)")
            ok += 1
        else:
            print("   FAIL: %s %s" % (status, data))
            fail += 1
    except Exception as e:
        print("   FAIL: %s" % e)
        fail += 1

    print("--- Result: %d passed, %d failed ---" % (ok, fail))
    sys.exit(0 if fail == 0 else 1)


if __name__ == "__main__":
    main()
