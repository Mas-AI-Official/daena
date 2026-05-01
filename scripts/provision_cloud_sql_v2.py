"""Provision a clean Cloud SQL Postgres database + user for Daena v2.

What this does (single-shot, idempotent re-run safe):
1. Resets the `postgres` superuser password to a session-only generated
   value. Brief argv exposure during the gcloud call; never printed.
2. Connects to the Cloud SQL instance via `cloud-sql-python-connector`
   (handles IAM auth + proxy automatically; no external binaries).
3. Creates user `daena_app` with a generated password (idempotent;
   resets password if user exists).
4. Creates database `daena_v2` owned by `daena_app` (idempotent;
   no-op if database exists with correct owner).
5. Builds the Cloud Run-compatible Unix-socket DATABASE_URL.
6. Pushes the URL as a new version of Secret Manager secret
   `daena-database-url` (creates secret if missing).
7. Resets the `postgres` password to a new random value (then
   forgets it -- we don't need it again).

Hard rules:
- NEVER prints any password or full DATABASE_URL to stdout / stderr.
- Status output is only secret/user/database names + booleans.
- Script aborts on any error rather than retrying blindly.

Usage:
    python scripts/provision_cloud_sql_v2.py
    python scripts/provision_cloud_sql_v2.py --dry-run

Requires:
    pip install 'cloud-sql-python-connector[pg8000]'
    gcloud auth (active project = daena-467315; permissions:
    cloudsql.users.update, cloudsql.databases.create,
    secretmanager.versions.add).

Author: Claude Code (Opus 4.7) -- 2026-05-01
Reference: docs/Ultraview/CLEAN_GCLOUD_REBUILD_PLAN.md §6, §7 Phase 2
"""

from __future__ import annotations

import argparse
import secrets
import shutil
import subprocess
import sys
from typing import Optional


GCLOUD = shutil.which("gcloud") or shutil.which("gcloud.cmd") or "gcloud"

PROJECT = "daena-467315"
REGION = "us-central1"
INSTANCE = "daena-db"
INSTANCE_CONNECTION_NAME = f"{PROJECT}:{REGION}:{INSTANCE}"

NEW_DB = "daena_v2"
NEW_USER = "daena_app"

DATABASE_URL_SECRET = "daena-database-url"
RUNTIME_SA = "daena-run@daena-467315.iam.gserviceaccount.com"


def _run(args: list[str], *, input_bytes: Optional[bytes] = None,
         allow_fail: bool = False, timeout: float = 60.0,
         hide_args_after: int = 999) -> subprocess.CompletedProcess:
    """Run a command. Never echoes input.

    hide_args_after: index after which args contain secrets (so we never
    print past it on failure).
    """
    try:
        r = subprocess.run(
            args, input=input_bytes, capture_output=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        sys.stderr.write(f"TIMEOUT (>{timeout}s) {' '.join(args[:6])}\n")
        sys.exit(3)
    if r.returncode != 0 and not allow_fail:
        sys.stderr.write(
            f"FAIL {' '.join(args[:min(len(args), hide_args_after)])}\n"
        )
        sys.stderr.write(r.stderr.decode(errors="replace")[:1000] + "\n")
        sys.exit(1)
    return r


def gen_password() -> str:
    """Generate a 48-byte URL-safe password.

    URL-safe base64: A-Z, a-z, 0-9, -, _. None of these need URL
    encoding when embedded in the password component of a DSN.
    """
    return secrets.token_urlsafe(48)


def reset_postgres_password(pw: str, dry_run: bool) -> None:
    """Reset the postgres superuser password to a known value.

    Brief argv exposure during this gcloud call (~1 sec). The value
    is in the bash subprocess argv, not in our Python stdout/stderr,
    not in any committed file.
    """
    if dry_run:
        print("  [dry-run] would reset postgres password")
        return
    _run([
        GCLOUD, "sql", "users", "set-password", "postgres",
        f"--instance={INSTANCE}", f"--project={PROJECT}",
        f"--password={pw}", "--quiet",
    ], hide_args_after=6)


def secret_exists(name: str) -> bool:
    r = _run([
        GCLOUD, "secrets", "describe", name, f"--project={PROJECT}",
        "--format=value(name)",
    ], allow_fail=True)
    return r.returncode == 0


def add_database_url_secret_version(url_bytes: bytes,
                                    dry_run: bool) -> str:
    """Push the DATABASE_URL into Secret Manager.

    If `daena-database-url` already exists (it does from prior session),
    add a new version. If somehow missing, create with this as v1.
    """
    if dry_run:
        return "would-add-version"
    if secret_exists(DATABASE_URL_SECRET):
        _run([
            GCLOUD, "secrets", "versions", "add", DATABASE_URL_SECRET,
            f"--project={PROJECT}", "--data-file=-",
        ], input_bytes=url_bytes)
        return "added-version"
    _run([
        GCLOUD, "secrets", "create", DATABASE_URL_SECRET,
        f"--project={PROJECT}", "--replication-policy=automatic",
        "--data-file=-",
    ], input_bytes=url_bytes)
    # Ensure runtime SA can read
    _run([
        GCLOUD, "secrets", "add-iam-policy-binding", DATABASE_URL_SECRET,
        f"--project={PROJECT}",
        f"--member=serviceAccount:{RUNTIME_SA}",
        "--role=roles/secretmanager.secretAccessor",
        "--condition=None",
    ], allow_fail=True)
    return "created"


def provision_via_connector(postgres_pw: str, app_pw: str,
                            dry_run: bool) -> dict:
    """Connect as postgres, create user + database. Idempotent.

    Returns dict of statuses: { 'user': ..., 'database': ... }.
    """
    if dry_run:
        return {"user": "would-create", "database": "would-create"}

    try:
        from google.cloud.sql.connector import Connector  # type: ignore
        from google.oauth2.credentials import Credentials  # type: ignore
    except ImportError:
        sys.stderr.write(
            "FAIL: cloud-sql-python-connector not installed.\n"
            "Run: pip install 'cloud-sql-python-connector[pg8000]'\n"
        )
        sys.exit(1)

    # Bypass ADC: get a fresh access token from gcloud directly. This
    # avoids the "GOOGLE_APPLICATION_CREDENTIALS points at missing file"
    # issue and the expired-ADC issue. The token is valid for ~1 hour
    # which is plenty for this script's runtime.
    tok_r = _run([
        GCLOUD, "auth", "print-access-token",
        f"--project={PROJECT}",
    ])
    access_token = tok_r.stdout.decode().strip()
    creds = Credentials(token=access_token)
    connector = Connector(credentials=creds)
    statuses: dict = {}
    try:
        # Connect to the default postgres database first to manage
        # users + create the new database.
        conn = connector.connect(
            INSTANCE_CONNECTION_NAME,
            "pg8000",
            user="postgres",
            password=postgres_pw,
            db="postgres",
        )
        # IMPORTANT: pg8000 default is autocommit=False. We need to
        # commit DDL ourselves OR enable autocommit. CREATE DATABASE
        # cannot run in a transaction block, so autocommit=True.
        conn.autocommit = True
        cur = conn.cursor()

        # 1. Create user (or reset password if exists)
        cur.execute(
            "SELECT 1 FROM pg_roles WHERE rolname = %s", (NEW_USER,)
        )
        exists = cur.fetchone() is not None
        if exists:
            # Reset password
            # WARNING: app_pw is interpolated as a SQL literal. We
            # MUST escape it. pg8000 does not support parameterized
            # ALTER ROLE; we use SQL identifier quoting and string
            # quoting carefully.
            # urlsafe_base64 contains only [A-Za-z0-9_-]; no quotes
            # to escape, but we double-check by rejecting any value
            # that would break SQL.
            if any(c in app_pw for c in ["'", "\"", "\\", ";", "\x00"]):
                raise RuntimeError(
                    "Generated password contains forbidden chars; "
                    "regenerate."
                )
            cur.execute(f"ALTER ROLE {NEW_USER} WITH PASSWORD '{app_pw}'")
            statuses["user"] = "password-rotated"
        else:
            if any(c in app_pw for c in ["'", "\"", "\\", ";", "\x00"]):
                raise RuntimeError(
                    "Generated password contains forbidden chars; "
                    "regenerate."
                )
            cur.execute(
                f"CREATE ROLE {NEW_USER} WITH LOGIN PASSWORD '{app_pw}'"
            )
            statuses["user"] = "created"

        # 2. Create database (idempotent: skip if exists)
        cur.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (NEW_DB,)
        )
        db_exists = cur.fetchone() is not None
        if db_exists:
            # Verify owner; reassign if not daena_app
            cur.execute(
                "SELECT pg_catalog.pg_get_userbyid(datdba) "
                "FROM pg_database WHERE datname = %s",
                (NEW_DB,),
            )
            owner = cur.fetchone()[0]
            if owner != NEW_USER:
                cur.execute(
                    f"ALTER DATABASE {NEW_DB} OWNER TO {NEW_USER}"
                )
                statuses["database"] = "owner-reassigned"
            else:
                statuses["database"] = "exists-correct-owner"
        else:
            cur.execute(
                f"CREATE DATABASE {NEW_DB} OWNER {NEW_USER}"
            )
            statuses["database"] = "created"

        # 3. Defense in depth: GRANT on schema public if connecting
        # to the new DB requires it. Connect to the new DB and grant.
        conn.close()

        # Reconnect to the new database to set up schema permissions.
        conn2 = connector.connect(
            INSTANCE_CONNECTION_NAME,
            "pg8000",
            user="postgres",
            password=postgres_pw,
            db=NEW_DB,
        )
        conn2.autocommit = True
        cur2 = conn2.cursor()
        # Postgres 15+: public schema is owned by the database owner
        # by default; daena_app already has full perms on it. These
        # grants are belt-and-suspenders.
        cur2.execute(f"GRANT ALL ON SCHEMA public TO {NEW_USER}")
        cur2.execute(
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            f"GRANT ALL ON TABLES TO {NEW_USER}"
        )
        cur2.execute(
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            f"GRANT ALL ON SEQUENCES TO {NEW_USER}"
        )
        conn2.close()
        statuses["schema_grants"] = "applied"
    finally:
        connector.close()

    return statuses


def build_database_url(password: str) -> str:
    """Cloud Run Unix-socket DSN. Never printed to stdout."""
    return (
        f"postgresql+asyncpg://{NEW_USER}:{password}"
        f"@/{NEW_DB}"
        f"?host=/cloudsql/{INSTANCE_CONNECTION_NAME}"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="Plan only; do not call any mutating gcloud or DB.")
    args = ap.parse_args()

    print("=== Daena Cloud SQL v2 provisioning ===")
    print(f"Project   : {PROJECT}")
    print(f"Instance  : {INSTANCE_CONNECTION_NAME}")
    print(f"New DB    : {NEW_DB}")
    print(f"New user  : {NEW_USER}")
    print(f"Mode      : {'DRY-RUN' if args.dry_run else 'APPLY'}")
    print("SECURITY  : never prints passwords or full DATABASE_URL.")
    print()

    # Generate session-only postgres password + permanent app password.
    postgres_pw = gen_password()
    app_pw = gen_password()

    # Phase 2.1 -- reset postgres password
    print("[1/4] Reset postgres superuser password (session-only)...")
    reset_postgres_password(postgres_pw, args.dry_run)
    print("      done.")

    # Phase 2.2 -- provision via cloud-sql-python-connector
    print("[2/4] Connect via cloud-sql-python-connector + provision...")
    if args.dry_run:
        statuses = provision_via_connector("", "", args.dry_run)
    else:
        statuses = provision_via_connector(postgres_pw, app_pw, args.dry_run)
    print(f"      user      : {statuses.get('user', '?')}")
    print(f"      database  : {statuses.get('database', '?')}")
    print(f"      schema    : {statuses.get('schema_grants', '?')}")

    # Phase 2.3 -- build DATABASE_URL + push to Secret Manager
    print("[3/4] Push DATABASE_URL to Secret Manager...")
    url = build_database_url(app_pw)
    url_bytes = url.encode()
    url = None  # clear local
    secret_status = add_database_url_secret_version(url_bytes, args.dry_run)
    url_bytes = None  # clear local
    print(f"      {DATABASE_URL_SECRET}: {secret_status}")

    # Phase 2.4 -- reset postgres password to a fresh random value
    # We never need the old session-only postgres password again.
    print("[4/4] Reset postgres password to a fresh random (session-only) value, then discard...")
    new_postgres_pw = gen_password()
    reset_postgres_password(new_postgres_pw, args.dry_run)
    new_postgres_pw = None
    postgres_pw = None
    app_pw = None
    print("      done.")

    print()
    print("Provisioning complete.")
    print("Next: cloudbuild.yaml deploys daena-v2 with DATABASE_URL "
          "bound from Secret Manager.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
