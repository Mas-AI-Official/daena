"""Launch readiness API test: hits every endpoint and reports pass/fail.

This is a standalone script, NOT a pytest test module.
Run directly: python tests/launch_api_test.py
Requires a running backend on localhost:8000.
"""
import json
import sys

import requests

BASE = "http://localhost:8000/api/v1"


def run_launch_tests():
    results = {}
    session_id = None
    token = None

    def test(name, method, path, data=None, expect_codes=(200,), auth=True):
        nonlocal token
        url = f"{BASE}{path}" if not path.startswith("http") else path
        headers = {"Content-Type": "application/json"}
        if auth and token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            r = getattr(requests, method.lower())(url, json=data, headers=headers, timeout=15)
            ok = r.status_code in expect_codes
            detail = ""
            try:
                detail = json.dumps(r.json(), default=str)[:120]
            except Exception:
                detail = r.text[:120]
            results[name] = {"ok": ok, "code": r.status_code, "detail": detail}
            return r
        except Exception as e:
            results[name] = {"ok": False, "code": 0, "detail": str(e)[:120]}
            return None

    # 1. Register
    r = test("register", "POST", "/auth/register",
             {"email": "autotest@daena.ai", "password": "TestPass123456!", "display_name": "AutoTest", "tenant_name": "AutoTestOrg"},
             expect_codes=(200, 201, 409), auth=False)

    # 2. Login
    r = test("login", "POST", "/auth/login",
             {"email": "autotest@daena.ai", "password": "TestPass123456!"},
             expect_codes=(200,), auth=False)
    if r and r.status_code == 200:
        body = r.json()
        token = body.get("access_token") or body.get("data", {}).get("access_token", "")

    # 3. Health detailed
    test("health_detailed", "GET", "/health/detailed")

    # 4. Sessions list
    test("sessions_list", "GET", "/chat/sessions")

    # 5. Create session
    r = test("create_session", "POST", "/chat/sessions", {"title": "Launch Test"}, expect_codes=(200, 201))
    if r and r.status_code in (200, 201):
        body = r.json()
        data = body.get("data") or body
        session_id = data.get("id", "")
        print(f"  >> Session created: {session_id[:8]}..." if session_id else "  >> No session ID")

    # 6. Departments
    test("departments", "GET", "/agents/departments")

    # 7. Model registry
    test("model_registry", "GET", "/chat/model-registry")

    # 8. Governance audit
    test("governance_audit", "GET", "/governance/audit")

    # 9. Governance approvals
    test("governance_approvals", "GET", "/governance/approvals")

    # 10. Memory list
    test("memory_list", "GET", "/memory/memories")

    # 11. Connections (connectors)
    test("connections", "GET", "/connections/connectors")

    # 12. Founder telemetry
    test("founder_telemetry", "GET", "/founder/routing/telemetry")

    # 13. Founder policy
    test("founder_policy", "GET", "/founder/routing/policy")

    # 14. Skills catalog
    test("skills_catalog", "GET", "/skills/refinery/catalog")

    # 15. DaenaBot agents
    test("daenabot_agents", "GET", "/daenabot/agents")

    # 16. Skill extraction
    test("skill_extract", "POST", "/skills/refinery/extract", {
        "content": "To negotiate: 1. Let the other side speak first. 2. Ask questions. 3. Use silence.",
        "source": {"platform": "manual", "creator": "test"}
    }, expect_codes=(200, 201))

    # 17. Chat streaming test (SSE)
    if session_id and token:
        try:
            r = requests.post(
                f"{BASE}/chat/messages/stream",
                json={"content": "Say hello in one sentence.", "session_id": session_id, "model": None},
                headers={"Authorization": f"Bearer {token}", "Accept": "text/event-stream"},
                stream=True, timeout=30
            )
            chunks = []
            for line in r.iter_lines(decode_unicode=True):
                if line:
                    chunks.append(line)
                if len(chunks) > 20:
                    break
            has_data = any("data:" in c for c in chunks)
            results["chat_stream"] = {
                "ok": has_data, "code": r.status_code,
                "detail": f"{len(chunks)} chunks received, has_data={has_data}"
            }
        except Exception as e:
            results["chat_stream"] = {"ok": False, "code": 0, "detail": str(e)[:120]}

    # 18. Session persistence check
    r = test("session_messages", "GET", f"/chat/sessions/{session_id}/messages" if session_id else "/chat/sessions",
             expect_codes=(200,))

    # 19. Founder policy update
    test("founder_policy_set", "PUT", "/founder/routing/policy",
         {"preferred_models": {"CODING": "qwen2.5:14b-instruct"}})

    # 20. Founder policy reset
    test("founder_policy_reset", "POST", "/founder/routing/policy/reset", expect_codes=(200,))

    # Print results
    print("=" * 60)
    print("  DAENA LAUNCH API TEST RESULTS")
    print("=" * 60)
    passes = sum(1 for v in results.values() if v["ok"])
    fails = sum(1 for v in results.values() if not v["ok"])
    for name, r in results.items():
        status = "PASS" if r["ok"] else "FAIL"
        print(f"  [{status}] {name}: HTTP {r['code']}")
        if not r["ok"]:
            print(f"         {r['detail']}")
    print(f"\nTotal: {passes} passed, {fails} failed out of {len(results)}")
    return fails


if __name__ == "__main__":
    sys.exit(0 if run_launch_tests() == 0 else 1)
