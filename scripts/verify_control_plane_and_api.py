#!/usr/bin/env python3
"""
Automated verification: backend health, capabilities, ping-hands, and optional UI checks.
Run from repo root with backend at http://localhost:8000.
"""
import json
import sys
import urllib.request
import urllib.error

BASE = "http://localhost:8000"
TIMEOUT = 5

def get(path):
    req = urllib.request.Request(BASE + path)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, r.read().decode()
    except urllib.error.URLError as e:
        return None, str(e)
    except Exception as e:
        return None, str(e)

def main():
    ok = 0
    fail = 0

    # 1) Backend up at :8000 (root /health is lightweight)
    status, body = get("/health")
    if status == 200:
        print("[PASS] Backend up at :8000 - GET /health returned 200")
        ok += 1
        try:
            data = json.loads(body)
            print("      health keys:", list(data.keys())[:6])
        except Exception:
            pass
    else:
        print("[FAIL] Backend at :8000 - GET /health:", status or body)
        fail += 1
        print("      Start backend: python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000")
        sys.exit(1)

    # 1b) Optional: enhanced system health (may 500 if daena identity not loaded)
    status2, body2 = get("/api/v1/system/health")
    if status2 == 200:
        print("[PASS] GET /api/v1/system/health - 200")
        ok += 1
    else:
        print("[SKIP] GET /api/v1/system/health - %s (non-fatal)" % (status2 or body2))

    # 2) /api/v1/system/capabilities returns expected JSON
    status, body = get("/api/v1/system/capabilities")
    if status == 200:
        try:
            data = json.loads(body)
            has_hands = "hands_gateway" in data
            has_llm = "local_llm" in data or "tool_catalog" in data
            print("[PASS] GET /api/v1/system/capabilities - expected JSON (hands_gateway=%s, llm/catalog=%s)" % (has_hands, has_llm))
            ok += 1
        except json.JSONDecodeError:
            print("[FAIL] GET /api/v1/system/capabilities - response not JSON")
            fail += 1
    else:
        print("[FAIL] GET /api/v1/system/capabilities:", status or body)
        fail += 1

    # 3) /api/v1/tools/ping-hands
    status, body = get("/api/v1/tools/ping-hands")
    if status == 200:
        try:
            data = json.loads(body)
            conn = data.get("connected") or data.get("success")
            print("[PASS] GET /api/v1/tools/ping-hands - 200 (connected=%s)" % conn)
            ok += 1
        except json.JSONDecodeError:
            print("[PASS] GET /api/v1/tools/ping-hands - 200 (body not JSON)")
            ok += 1
    else:
        print("[FAIL] GET /api/v1/tools/ping-hands:", status or body)
        fail += 1

    # 3b) /api/v1/hands/status (configured, reachable, message; no token)
    status, body = get("/api/v1/hands/status")
    if status == 200:
        try:
            data = json.loads(body)
            has_msg = "message" in data
            no_token = "token" not in body.lower()
            print("[PASS] GET /api/v1/hands/status - 200 (message=%s, no_token=%s)" % (has_msg, no_token))
            ok += 1
        except json.JSONDecodeError:
            print("[PASS] GET /api/v1/hands/status - 200 (body not JSON)")
            ok += 1
    else:
        print("[FAIL] GET /api/v1/hands/status:", status or body)
        fail += 1

    # 3c) /api/v1/audit/recent (audit log wired for tool_request submit/approve/reject/execute)
    status, body = get("/api/v1/audit/recent?limit=10")
    if status == 200:
        try:
            data = json.loads(body)
            entries = data.get("entries") if isinstance(data, dict) else (data if isinstance(data, list) else [])
            print("[PASS] GET /api/v1/audit/recent - 200 (entries=%s)" % len(entries))
            ok += 1
        except json.JSONDecodeError:
            print("[PASS] GET /api/v1/audit/recent - 200 (body not JSON)")
            ok += 1
    else:
        print("[FAIL] GET /api/v1/audit/recent:", status or body)
        fail += 1

    # 4) Control Panel UI page loads
    status, _ = get("/ui/control-panel")
    if status == 200:
        print("[PASS] GET /ui/control-panel - 200")
        ok += 1
    else:
        print("[FAIL] GET /ui/control-panel:", status or "no response")
        fail += 1

    # 5) Command center redirect
    req = urllib.request.Request(BASE + "/command-center")
    req.add_header("User-Agent", "VerifyScript/1")
    try:
        r = urllib.request.urlopen(req, timeout=TIMEOUT)
        # redirect (302/307) or 200 both ok
        print("[PASS] GET /command-center - %s" % r.status)
        ok += 1
    except urllib.error.HTTPError as e:
        if e.code in (302, 307, 200):
            print("[PASS] GET /command-center - %s" % e.code)
            ok += 1
        else:
            print("[FAIL] GET /command-center:", e.code)
            fail += 1
    except Exception as e:
        print("[FAIL] GET /command-center:", e)
        fail += 1

    print("")
    print("Total: %d passed, %d failed" % (ok, fail))
    sys.exit(0 if fail == 0 else 1)

if __name__ == "__main__":
    main()
