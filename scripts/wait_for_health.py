from __future__ import annotations

import argparse
import time


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--interval", type=float, default=1.0)
    args = parser.parse_args()

    try:
        import httpx
    except Exception as e:
        print(f"HEALTH_FAIL: httpx import error: {e}")
        return 1

    deadline = time.time() + float(args.timeout)
    last_err: str | None = None

    while time.time() < deadline:
        try:
            r = httpx.get(args.url, timeout=2.0)
            if r.status_code == 200:
                print("HEALTH_OK")
                return 0
            last_err = f"status={r.status_code}"
        except Exception as e:
            last_err = str(e)
        time.sleep(float(args.interval))

    print(f"HEALTH_FAIL: {last_err}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())











