"""Phase 4b PR 3: Reconciliation CLI.

Compare legacy ConnectorInstance + V2 ConnectionV2 + V2 Secret state
and produce a structured drift report. Dry-run by default.

Usage:
    python -m backend.scripts.reconcile_connection_v2 --dry-run
    python -m backend.scripts.reconcile_connection_v2 --tenant-id <uuid>
    python -m backend.scripts.reconcile_connection_v2 --report-json drift.json
    python -m backend.scripts.reconcile_connection_v2 --apply  # founder-only

Safety:
    * dry-run is default -- pass --apply to enable safe mutations
    * --apply only cleans expired ConnectionV2OpLock rows (never
      touches legacy ConnectorInstance or Secret rows)
    * --apply is silently downgraded if USE_CONNECTION_REGISTRY_V2
      is off in settings
    * report NEVER includes plaintext secrets / KEK / DEK material
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from uuid import UUID

# Allow `python backend/scripts/reconcile_connection_v2.py` from repo root.
_THIS = Path(__file__).resolve()
_BACKEND = _THIS.parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


async def _amain(args: argparse.Namespace) -> int:
    from app.core.config import get_settings
    from app.core.database import async_session_factory
    from app.services.connection_v2.legacy_bridge import is_v2_enabled
    from app.services.connection_v2.reconciliation import (
        ConnectionReconciliationService,
    )

    settings = get_settings()

    tenant_id: UUID | None = None
    if args.tenant_id:
        try:
            tenant_id = UUID(args.tenant_id)
        except ValueError:
            print(f"ERROR: --tenant-id must be a valid UUID, got: {args.tenant_id}",
                  file=sys.stderr)
            return 2

    apply = bool(args.apply)
    if apply and not is_v2_enabled():
        print(
            "WARN: --apply requested but USE_CONNECTION_REGISTRY_V2 is False. "
            "Downgrading to dry-run.",
            file=sys.stderr,
        )

    async with async_session_factory() as session:
        svc = ConnectionReconciliationService(session)
        report = await svc.run(tenant_id=tenant_id, apply=apply)
        if report.mutations_applied > 0:
            await session.commit()

    payload = report.to_dict()
    payload["env"] = {
        "use_connection_registry_v2": is_v2_enabled(),
        "is_production": settings.is_production,
    }

    if args.report_json:
        Path(args.report_json).write_text(
            json.dumps(payload, indent=2), encoding="utf-8",
        )
        print(f"Wrote JSON report -> {args.report_json}")

    # Human-readable summary on stdout.
    print("=" * 60)
    print("ConnectionV2 Reconciliation Report")
    print("=" * 60)
    print(f"  started_at        : {payload['started_at']}")
    print(f"  finished_at       : {payload['finished_at']}")
    print(f"  duration_ms       : {payload['duration_ms']}")
    print(f"  apply_mode        : {payload['apply_mode']}")
    print(f"  use_v2_flag       : {payload['env']['use_connection_registry_v2']}")
    print(f"  is_production     : {payload['env']['is_production']}")
    print()
    print(f"  legacy_row_count  : {payload['legacy_row_count']}")
    print(f"  v2_row_count      : {payload['v2_row_count']}")
    print(f"  secret_row_count  : {payload['secret_row_count']}")
    print(f"  mutations_applied : {payload['mutations_applied']}")
    print()
    print("  Drift counters:")
    if not payload["counters"]:
        print("    (none)")
    for kind, n in sorted(payload["counters"].items()):
        print(f"    - {kind:30s} : {n}")
    print()
    if args.verbose and payload["drift"]:
        print("  Drift entries:")
        for d in payload["drift"]:
            print(
                f"    [{d['severity'].upper():5s}] {d['kind']:25s} "
                f"tenant={d['tenant_id']} legacy={d['legacy_instance_id']} "
                f"v2={d['v2_connection_id']}"
            )
            print(f"        detail: {d['detail']}")
            if d.get("suggested_action"):
                print(f"        action: {d['suggested_action']}")
    print()
    print(f"  has_drift: {payload['has_drift']}")
    print("=" * 60)

    # Exit code: 0 = clean, 1 = drift detected, 2 = bad invocation.
    return 1 if payload["has_drift"] else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reconcile legacy ConnectorInstance vs ConnectionV2 vs Secret",
    )
    parser.add_argument(
        "--tenant-id",
        help="Limit scope to a single tenant UUID. Default: all tenants.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Perform safe mutations (orphan op-lock cleanup only). "
            "Silently downgraded if USE_CONNECTION_REGISTRY_V2 is off."
        ),
    )
    parser.add_argument(
        "--report-json",
        help="Write structured report to this JSON file.",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print every drift entry to stdout.",
    )
    args = parser.parse_args()

    try:
        return asyncio.run(_amain(args))
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
