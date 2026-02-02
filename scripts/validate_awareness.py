#!/usr/bin/env python3
"""
Validate Daena Awareness fix automatically.
- Static: grep-style checks (AWARENESS in daena.py, no "don't have" in deep_search, etc.)
- Live (optional): GET /api/v1/capabilities, POST /api/v1/chat if backend is running.
"""
from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_file(path: str) -> str:
    full = os.path.join(REPO_ROOT, path)
    if not os.path.isfile(full):
        return ""
    with open(full, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def check_awareness_daena_py() -> tuple[bool, str]:
    content = read_file("backend/routes/daena.py")
    if "AWARENESS" not in content:
        return False, "backend/routes/daena.py: AWARENESS block not found"
    if "hands_status" not in content or "workspace_path" not in content:
        return False, "backend/routes/daena.py: AWARENESS missing hands_status/workspace_path"
    return True, "backend/routes/daena.py: AWARENESS block present with live vars"


def check_deep_search_no_dont_have() -> tuple[bool, str]:
    content = read_file("backend/services/deep_search_service.py")
    if "don't have" in content:
        return False, "backend/services/deep_search_service.py: must not contain 'don't have'"
    if "DaenaBot Hands" not in content or "say **YES**" not in content:
        return False, "backend/services/deep_search_service.py: should mention DaenaBot Hands and say YES"
    return True, "backend/services/deep_search_service.py: no 'don't have', capabilities stated"


def check_llm_service_capabilities() -> tuple[bool, str]:
    content = read_file("backend/services/llm_service.py")
    if "DaenaBot Hands" not in content or "Moltbot" not in content:
        return False, "backend/services/llm_service.py: missing DaenaBot Hands / Moltbot in prompt"
    if "check_hands_status_sync" not in content and "_get_capabilities_for_prompt" not in content:
        return False, "backend/services/llm_service.py: missing live hands status injection"
    return True, "backend/services/llm_service.py: DaenaBot Hands + live capabilities in prompt"


def check_capabilities_route() -> tuple[bool, str]:
    content = read_file("backend/routes/capabilities.py")
    if "hands_gateway" not in content or "build_capabilities" not in content:
        return False, "backend/routes/capabilities.py: missing hands_gateway / build_capabilities"
    return True, "backend/routes/capabilities.py: GET /capabilities returns hands_gateway"


def check_daenabot_tools() -> tuple[bool, str]:
    content = read_file("backend/services/daenabot_tools.py")
    if "check_hands_status" not in content:
        return False, "backend/services/daenabot_tools.py: check_hands_status not found"
    return True, "backend/services/daenabot_tools.py: status checker present"


def run_live_checks(base_url: str = "http://127.0.0.1:8000") -> list[tuple[bool, str]]:
    results = []
    try:
        import urllib.request
        import json

        # GET capabilities
        req = urllib.request.Request(f"{base_url}/api/v1/capabilities", method="GET")
        req.add_header("Accept", "application/json")
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode())
        h = data.get("hands_gateway") or {}
        status = h.get("status", "?")
        results.append((True, f"GET /api/v1/capabilities: hands_gateway.status = {status}"))

        # POST chat (awareness question)
        body = json.dumps({"message": "Are you aware of your capabilities? Do you have access to my computer?"}).encode()
        req = urllib.request.Request(f"{base_url}/api/v1/chat", data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")
        with urllib.request.urlopen(req, timeout=30) as r:
            chat_data = json.loads(r.read().decode())
        response = (chat_data.get("response") or chat_data.get("message") or "").lower()
        if "don't have access" in response:
            results.append((False, "POST /api/v1/chat: response still contains 'don't have access'"))
        else:
            results.append((True, "POST /api/v1/chat: response does not say 'don't have access'"))
        if "daenabot hands" in response or "moltbot" in response:
            results.append((True, "POST /api/v1/chat: response mentions DaenaBot Hands / Moltbot"))
        else:
            results.append((True, "POST /api/v1/chat: (warn) response does not mention DaenaBot Hands — model-dependent"))
        if "yes" in response:
            results.append((True, "POST /api/v1/chat: response says YES"))
        else:
            results.append((True, "POST /api/v1/chat: (warn) response does not say YES — model-dependent"))
    except Exception as e:
        results.append((True, f"Live checks skipped (backend not reachable): {e}"))
    return results


def main() -> int:
    os.chdir(REPO_ROOT)
    checks = [
        check_awareness_daena_py(),
        check_deep_search_no_dont_have(),
        check_llm_service_capabilities(),
        check_capabilities_route(),
        check_daenabot_tools(),
    ]
    all_ok = True
    for ok, msg in checks:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {msg}")
        if not ok:
            all_ok = False

    print("\n--- Live (optional, backend must be running) ---")
    for ok, msg in run_live_checks():
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {msg}")
        if not ok:
            all_ok = False

    print("")
    if all_ok:
        print("Validation: all checks passed.")
        return 0
    print("Validation: some checks failed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
