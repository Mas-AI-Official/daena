"""CLI wrapper for the vault V1 -> V2 migration (Phase 4a-3).

Default mode is dry-run. ``--apply`` is required to write rows. Drift in
apply mode aborts the batch unless ``--force`` is passed.

Usage examples::

    # Dry-run, all tenants (default)
    python -m backend.scripts.migrate_vault_to_v2

    # Dry-run, single tenant + JSON report
    python -m backend.scripts.migrate_vault_to_v2 \
        --tenant-id 01926e7f-... \
        --report-json out/migration_report.json

    # Apply for one tenant, capped at 10 rows
    python -m backend.scripts.migrate_vault_to_v2 \
        --apply --tenant-id 01926e7f-... --limit 10

    # Apply through drift (operator override)
    python -m backend.scripts.migrate_vault_to_v2 --apply --force

The library logic lives in ``app.services.vault_migration``; this CLI is
a thin argparse + DB-session wrapper. Per Phase 4a-3 founder rules:
  - dry-run is the default
  - decrypted secrets are never printed
  - counts are always logged (and optionally written to JSON)
  - no legacy module is deleted by this script
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import logging
import sys
from pathlib import Path
from uuid import UUID

# Backend Python path bootstrap so this works either as
# ``python backend/scripts/migrate_vault_to_v2.py`` or as
# ``python -m backend.scripts.migrate_vault_to_v2``.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.core.database import async_session_factory  # noqa: E402
from app.core.vault_boot import load_kek_from_env  # noqa: E402
from app.services.vault_migration import (  # noqa: E402
    MigrationOptions,
    run_migration,
)

logger = logging.getLogger("migrate_vault_to_v2")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="migrate_vault_to_v2",
        description="Re-encrypt legacy ConnectorInstance.credentials under vault_v2 envelope.",
    )
    mode_group = p.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=True,
        help="(default) Validate cipher roundtrip without writing anything.",
    )
    mode_group.add_argument(
        "--apply",
        dest="dry_run",
        action="store_false",
        help="Persist Secret rows AND provision per-tenant DEKs. Mutually exclusive with --dry-run.",
    )
    p.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="In --apply mode: continue past drift instead of aborting the batch.",
    )
    p.add_argument(
        "--tenant-id",
        type=str,
        default=None,
        help="Restrict scope to one tenant (UUID).",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cap candidates inspected.",
    )
    p.add_argument(
        "--report-json",
        type=str,
        default=None,
        help="Write structured counts + drift list as JSON (no plaintext) to this path.",
    )
    return p.parse_args(argv)


async def _amain(args: argparse.Namespace) -> int:
    settings = get_settings()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Load KEK with the same is_production flag the live app uses.
    # In production this raises RefuseToBoot if DAENA_KEK is missing.
    kek = load_kek_from_env(is_production=settings.is_production)

    options = MigrationOptions(
        dry_run=args.dry_run,
        force=args.force,
        tenant_id=UUID(args.tenant_id) if args.tenant_id else None,
        limit=args.limit,
    )

    if not options.dry_run:
        logger.warning(
            "vault_migration.cli.apply_mode_requested "
            "force=%s tenant_id=%s limit=%s",
            options.force, options.tenant_id, options.limit,
        )

    async with async_session_factory() as db:
        try:
            report = await run_migration(db, kek_seed=kek, options=options)
            if not options.dry_run and not report.aborted:
                await db.commit()
            else:
                # In dry-run we may have flushed transient state; rollback
                # to keep the DB byte-identical.
                await db.rollback()
        except Exception:
            await db.rollback()
            raise

    # Summary printed to stdout (counts + drift count only -- never plaintext).
    summary_line = (
        "candidate=%d already_migrated=%d skipped=%d failed=%d "
        "drift=%d written=%d dek_provisioned=%d aborted=%s"
    ) % (
        report.counters["candidate"],
        report.counters["already_migrated"],
        report.counters["skipped"],
        report.counters["failed"],
        report.counters["drift"],
        report.counters["written"],
        report.counters["dek_provisioned"],
        report.aborted,
    )
    print(summary_line)

    if args.report_json:
        report_path = Path(args.report_json)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(dataclasses.asdict(report), indent=2, default=str),
            encoding="utf-8",
        )
        logger.info("vault_migration.cli.report_written path=%s", report_path)

    # Exit code: 0 success, 2 drift in apply mode (operator override required),
    # 1 generic failure (any failed row in apply mode).
    if report.aborted:
        return 2
    if not options.dry_run and report.counters["failed"] > 0:
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    return asyncio.run(_amain(args))


if __name__ == "__main__":
    sys.exit(main())
