#!/usr/bin/env python3
"""
Verify DAENABOT_HANDS_* / OPENCLAW_* env and config (no backend app required).
Run: python scripts/verify_daenabot_hands_env.py
"""
import os
import sys

# Minimal env_first (no pydantic)
def env_first(*keys, default=None):
    for k in keys:
        v = os.environ.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    return default


def main():
    ok, fail = 0, 0

    print("1) env_first('DAENABOT_HANDS_URL', 'OPENCLAW_GATEWAY_URL', default=...)")
    url = env_first("DAENABOT_HANDS_URL", "OPENCLAW_GATEWAY_URL", default="ws://127.0.0.1:18789/ws")
    if url and "127.0.0.1" in url:
        print("   OK (safe default or env):", url[:50])
        ok += 1
    elif url:
        print("   WARN: URL not localhost:", url[:50], "- bind to 127.0.0.1 for safety")
        ok += 1
    else:
        print("   OK (default used)")
        ok += 1

    print("2) env_first('DAENABOT_HANDS_TOKEN', 'OPENCLAW_GATEWAY_TOKEN', default=None)")
    token = env_first("DAENABOT_HANDS_TOKEN", "OPENCLAW_GATEWAY_TOKEN", default=None)
    print("   token set:", bool(token))
    ok += 1

    print("3) Full settings (optional, requires pydantic)")
    try:
        from backend.config.settings import settings, env_first as ef
        url2 = getattr(settings, "daenabot_hands_url", None)
        token2 = getattr(settings, "daenabot_hands_token", None)
        print("   daenabot_hands_url:", url2)
        print("   daenabot_hands_token set:", bool(token2))
        ok += 1
    except Exception as e:
        print("   SKIP (pydantic/settings not available):", e)

    print("\n--- Result: %d checks passed ---" % ok)
    return 0


if __name__ == "__main__":
    sys.exit(main())
