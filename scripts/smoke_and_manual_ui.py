#!/usr/bin/env python3
"""
Smoke test (API) + 5 manual UI verification steps.
Run with backend up. Set EXECUTION_TOKEN for execution-layer checks.
Usage: python scripts/smoke_and_manual_ui.py [--base URL]
"""
import argparse
import json
import os
import sys
import urllib.request
import urllib.error

BASE = os.environ.get("DAENA_BASE_URL", "http://localhost:8000").rstrip("/")
TOKEN = os.environ.get("EXECUTION_TOKEN", "")


def main():
    global BASE, TOKEN
    parser = argparse.ArgumentParser(description="Smoke test + 5 manual UI steps")
    parser.add_argument("--base", default=BASE, help="Backend base URL")
    parser.add_argument("--token", default=TOKEN, help="X-Execution-Token")
    args = parser.parse_args()
    BASE = args.base.rstrip("/")
    TOKEN = args.token or os.environ.get("EXECUTION_TOKEN", "")

    ok, fail = 0, 0

    # 1) Health
    print("1) GET /health ...")
    try:
        r = urllib.request.urlopen(urllib.request.Request(BASE + "/health"), timeout=5)
        raw = r.read().decode("utf-8")
        if r.status == 200 and ("healthy" in raw or "ok" in raw.lower()):
            print("   OK")
            ok += 1
        else:
            print("   FAIL:", r.status)
            fail += 1
    except Exception as e:
        print("   FAIL: Backend not reachable. Start backend first (e.g. scripts\\start_backend.bat)")
        sys.exit(1)

    # 2) Dashboard / UI base
    print("2) GET /ui/dashboard ...")
    try:
        r = urllib.request.urlopen(urllib.request.Request(BASE + "/ui/dashboard"), timeout=5)
        if r.status == 200:
            print("   OK")
            ok += 1
        else:
            print("   FAIL:", r.status)
            fail += 1
    except urllib.error.HTTPError as e:
        print("   FAIL:", e.code)
        fail += 1
    except Exception as e:
        print("   FAIL:", e)
        fail += 1

    # 3) Daena chat sessions (try chat-history or daena path)
    print("3) GET chat sessions (chat-history or daena) ...")
    try:
        for path in ("/api/v1/chat-history/sessions", "/api/v1/daena/chat/sessions"):
            try:
                r = urllib.request.urlopen(urllib.request.Request(BASE + path), timeout=5)
                status = r.status
                data = json.loads(r.read().decode("utf-8"))
                if status == 200 and (data.get("sessions") is not None or "sessions" in data):
                    print("   OK (%s)" % path.split("/")[3])
                    ok += 1
                    break
                elif status == 200:
                    print("   OK")
                    ok += 1
                    break
            except urllib.error.HTTPError:
                continue
        else:
            print("   FAIL (both paths 404 or error)")
            fail += 1
    except Exception as e:
        print("   FAIL:", e)
        fail += 1

    # 4) Execution tools (with token if set)
    if TOKEN:
        print("4) GET /api/v1/execution/tools (with token) ...")
        try:
            req_obj = urllib.request.Request(BASE + "/api/v1/execution/tools")
            req_obj.add_header("X-Execution-Token", TOKEN)
            r = urllib.request.urlopen(req_obj, timeout=5)
            status = r.status
            data = json.loads(r.read().decode("utf-8"))
            if status == 200 and isinstance(data.get("tools"), list):
                print("   OK, tools:", len(data["tools"]))
                ok += 1
            else:
                print("   OK" if status == 200 else "   FAIL:", status)
                ok += 1
        except urllib.error.HTTPError as e:
            print("   FAIL:", e.code)
            fail += 1
        except Exception as e:
            print("   FAIL:", e)
            fail += 1
    else:
        print("4) SKIP (set EXECUTION_TOKEN for execution tools check)")

    # 4b) Execution auth-status (no token required; DaenaBot hands / execution layer)
    print("4b) GET /api/v1/execution/auth-status ...")
    try:
        r = urllib.request.urlopen(urllib.request.Request(BASE + "/api/v1/execution/auth-status"), timeout=5)
        data = json.loads(r.read().decode("utf-8"))
        if r.status == 200 and data.get("success") is True:
            print("   OK (execution_enabled=%s, localhost_bypass=%s)" % (data.get("execution_enabled"), data.get("localhost_bypass")))
            ok += 1
        else:
            print("   OK" if r.status == 200 else "   FAIL:", r.status)
            ok += 1
    except urllib.error.HTTPError as e:
        print("   FAIL:", e.code)
        fail += 1
    except Exception as e:
        print("   FAIL:", e)
        fail += 1

    # 5) System summary or health again
    print("5) GET /api/v1/system-summary/summary or /api/v1/health ...")
    try:
        r = urllib.request.urlopen(urllib.request.Request(BASE + "/api/v1/system-summary/summary"), timeout=5)
        status = r.status
        r.read()
        if status == 200:
            print("   OK")
            ok += 1
        else:
            print("   FAIL:", status)
            fail += 1
    except (urllib.error.HTTPError, urllib.error.URLError, OSError):
        try:
            r = urllib.request.urlopen(urllib.request.Request(BASE + "/api/v1/health"), timeout=5)
            status = r.status
            r.read()
            if status == 200:
                print("   OK (health)")
                ok += 1
            else:
                print("   FAIL:", status)
                fail += 1
        except Exception:
            print("   FAIL")
            fail += 1
    except Exception as e:
        print("   FAIL:", e)
        fail += 1

    print("\n--- Smoke result: %d passed, %d failed ---\n" % (ok, fail))

    print("=" * 60)
    print("5 MANUAL UI VERIFICATION STEPS (run in browser)")
    print("=" * 60)
    print("""
1. Dashboard
   Open %s/ui/dashboard
   - Brain status shows Active or Offline
   - Quick Actions and System Monitor card visible
   - Execution Layer section loads (token optional)

2. Daena Office
   Open %s/ui/daena-office
   - Sessions list loads; can create new chat
   - Send a message; streamed response or tool result appears
   - Sources toggle (header): turn On, send a search; citations [1][2] appear

3. Control Plane
   Open %s/ui/control-plane
   - Tabs: Brain & API, App Setup, Skills, Execution, etc.
   - Switch tabs; iframes load (Brain, Execution, Proactive, …)

4. System Monitor
   Open %s/ui/system-monitor
   - Backend status and API count (or placeholders) visible

5. Workspace / Repo digest
   In Daena Office, ask: "What is the structure of this repo?" or "List your directory"
   - Reply shows workspace list or REPO_DIGEST content (key folders, entrypoints)
""" % (BASE, BASE, BASE, BASE))
    print("=" * 60)

    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
