"""Production hygiene setup: Secret Manager + Cloud SQL credentials.

Idempotent script that creates/populates the 7 Secret Manager secrets
Cloud Run needs and rotates the Cloud SQL `daena` user's password.

Hard rules (mirror feedback_secret_handling memory):
- Never prints secret values to stdout/stderr (even partial / hashed).
- Never writes secret values to disk except as gcloud stdin.
- Reads existing Cloud Run plaintext env values via gcloud JSON; pipes
  them straight into `gcloud secrets versions add --data-file=-`.
- If a secret already has at least one version, SKIPs it (does not
  overwrite -- the operator may have rotated independently).
- Generates fresh values for JWT_SECRET_KEY and DAENA_KEK only when
  the secret has zero versions AND DAENA_KEK is not currently set in
  Cloud Run env (which would imply existing encrypted state).

Usage:
    python scripts/setup_production_secrets.py
    python scripts/setup_production_secrets.py --dry-run

Requires: gcloud auth, project=daena-467315, account with roles for
Secret Manager + Cloud SQL admin.

Author: Claude Code (Opus 4.7) -- 2026-05-01
Reference: docs/Ultraview/PRODUCTION_DB_AND_SECRET_ROTATION_PLAN.md
"""

from __future__ import annotations

import argparse
import json
import secrets
import shutil
import subprocess
import sys
from typing import Optional


GCLOUD = shutil.which("gcloud") or shutil.which("gcloud.cmd") or "gcloud"

PROJECT = "daena-467315"
SERVICE = "daena"
REGION = "us-central1"
SQL_INSTANCE = "daena-db"
SQL_DATABASE = "daena"
SQL_APP_USER = "daena"  # Existing user; we reset its password.
RUNTIME_SA = "daena-run@daena-467315.iam.gserviceaccount.com"

# (env_var_name, secret_manager_secret_name, source_kind)
# source_kind: "move" reads from Cloud Run plaintext env;
#              "gen-hex32" generates 32-byte hex.
SECRET_PLAN: list[tuple[str, str, str]] = [
    ("GROQ_API_KEY",         "daena-groq-api-key",         "move"),
    ("GEMINI_API_KEY",       "daena-gemini-api-key",       "move"),
    ("GOOGLE_CLIENT_SECRET", "daena-google-client-secret", "move"),
    ("GITHUB_CLIENT_SECRET", "daena-github-client-secret", "move"),
    ("JWT_SECRET_KEY",       "daena-jwt-secret-key",       "gen-hex32"),
    ("DAENA_KEK",            "daena-daena-kek",            "gen-hex32"),
]
DATABASE_URL_SECRET = "daena-database-url"


def _run(args: list[str], *, input_bytes: Optional[bytes] = None,
         allow_fail: bool = False,
         timeout: float = 60.0) -> subprocess.CompletedProcess:
    """Run gcloud, never echoing input. Raises on non-zero unless allow_fail.

    Timeout prevents indefinite hangs if a prompt mode doesn't consume
    piped stdin. If the call times out, we kill the subprocess and exit.
    """
    try:
        r = subprocess.run(
            args, input=input_bytes, capture_output=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        sys.stderr.write(f"TIMEOUT (>{timeout}s) {' '.join(args[:6])}\n")
        sys.exit(3)
    if r.returncode != 0 and not allow_fail:
        sys.stderr.write(f"FAIL {' '.join(args[:6])}\n")
        sys.stderr.write(r.stderr.decode(errors="replace")[:1000] + "\n")
        sys.exit(1)
    return r


def get_cloudrun_plaintext_env(name: str) -> Optional[str]:
    """Return the plaintext value of a Cloud Run env var, or None.

    Returns None if the env var is absent OR is bound from Secret
    Manager (valueFrom present, no value field). Never prints the
    returned value.
    """
    out = subprocess.check_output([
        GCLOUD, "run", "services", "describe", SERVICE,
        f"--project={PROJECT}", f"--region={REGION}",
        "--format=json(spec.template.spec.containers[0].env)",
    ], text=True)
    env_list = json.loads(out).get("spec", {}).get("template", {}).get(
        "spec", {}).get("containers", [{}])[0].get("env", [])
    for e in env_list:
        if e.get("name") == name and "value" in e:
            return e["value"]
    return None


def secret_has_versions(secret_name: str) -> bool:
    r = _run([
        GCLOUD, "secrets", "versions", "list", secret_name,
        f"--project={PROJECT}", "--format=value(name)",
        "--filter=state=ENABLED",
    ], allow_fail=True)
    if r.returncode != 0:
        return False  # secret likely doesn't exist
    return bool(r.stdout.decode().strip())


def secret_exists(secret_name: str) -> bool:
    r = _run([
        GCLOUD, "secrets", "describe", secret_name,
        f"--project={PROJECT}", "--format=value(name)",
    ], allow_fail=True)
    return r.returncode == 0


def create_secret_with_initial_version(secret_name: str,
                                       value_bytes: bytes,
                                       dry_run: bool) -> str:
    """Idempotent: create secret if missing, add version only if zero.

    Returns one of: 'created' | 'added-first-version' | 'skipped'.
    """
    if not secret_exists(secret_name):
        if dry_run:
            return "would-create"
        _run([
            GCLOUD, "secrets", "create", secret_name,
            f"--project={PROJECT}", "--replication-policy=automatic",
            "--data-file=-",
        ], input_bytes=value_bytes)
        return "created"

    if secret_has_versions(secret_name):
        return "skipped (versions exist)"

    if dry_run:
        return "would-add-first-version"

    _run([
        GCLOUD, "secrets", "versions", "add", secret_name,
        f"--project={PROJECT}", "--data-file=-",
    ], input_bytes=value_bytes)
    return "added-first-version"


def grant_runtime_sa_access(secret_name: str, dry_run: bool) -> str:
    """Grant Cloud Run runtime SA secretAccessor. Idempotent."""
    if dry_run:
        return "would-grant"
    r = _run([
        GCLOUD, "secrets", "add-iam-policy-binding", secret_name,
        f"--project={PROJECT}",
        f"--member=serviceAccount:{RUNTIME_SA}",
        "--role=roles/secretmanager.secretAccessor",
        "--condition=None",
    ], allow_fail=True)
    if r.returncode == 0:
        return "granted"
    err = r.stderr.decode(errors="replace")
    if "already" in err.lower() or "etag" in err.lower():
        return "already-bound"
    sys.stderr.write(f"WARN grant {secret_name}: {err[:300]}\n")
    return "warn"


def reset_sql_user_password(value_bytes: bytes, dry_run: bool) -> str:
    """Reset existing daena Cloud SQL user's password.

    gcloud sql users set-password supports --password=VALUE or
    --prompt-for-password. On Windows, --prompt-for-password reads
    from console (msvcrt) and ignores piped stdin -- so we use the
    --password=VALUE path. The password value is briefly visible in
    the gcloud subprocess argv (~1 sec). It is never printed to
    stdout/stderr/log.
    """
    if dry_run:
        return "would-reset"

    pw = value_bytes.decode()
    try:
        _run([
            GCLOUD, "sql", "users", "set-password", SQL_APP_USER,
            f"--instance={SQL_INSTANCE}", f"--project={PROJECT}",
            f"--password={pw}", "--quiet",
        ])
    finally:
        pw = None  # release local reference
    return "rotated"


def build_database_url(password: str) -> str:
    """Cloud Run Unix-socket Postgres URL via Cloud SQL Auth Proxy."""
    return (
        f"postgresql+asyncpg://{SQL_APP_USER}:{password}"
        f"@/{SQL_DATABASE}"
        f"?host=/cloudsql/{PROJECT}:{REGION}:{SQL_INSTANCE}"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="Plan only; do not call any mutating gcloud.")
    ap.add_argument("--skip-db-rotation", action="store_true",
                    help="Skip Cloud SQL password reset + DATABASE_URL "
                         "secret. Useful if DB rotation was done manually.")
    args = ap.parse_args()

    print("=== Daena Production Secret Setup ===")
    print(f"Project : {PROJECT}")
    print(f"Service : {SERVICE} ({REGION})")
    print(f"SQL inst: {SQL_INSTANCE}")
    print(f"SA      : {RUNTIME_SA}")
    print(f"Mode    : {'DRY-RUN' if args.dry_run else 'APPLY'}")
    print("SECURITY: this script never prints secret values.")
    print()

    # ── Safety: refuse to regenerate DAENA_KEK if env already has one ──
    existing_kek = get_cloudrun_plaintext_env("DAENA_KEK")
    if existing_kek is not None:
        sys.stderr.write(
            "ABORT: DAENA_KEK is already populated as a Cloud Run env "
            "var. Regenerating would orphan any tenant DEKs wrapped by "
            "the existing KEK. Founder approval required to proceed.\n"
        )
        existing_kek = None
        return 2
    existing_kek = None

    # ── Phase B: Secret Manager creation + IAM ──
    print("[Phase B] Secret Manager")
    for env_name, secret_name, kind in SECRET_PLAN:
        print(f"  {secret_name}")
        if kind == "move":
            value = get_cloudrun_plaintext_env(env_name)
            if value is None:
                print(f"    SKIP: {env_name} not present as plaintext "
                      f"in Cloud Run env (already a Secret Manager ref?)")
                # Still ensure secret exists for the future (empty)
                continue
            value_b = value.encode()
            value = None  # clear
        elif kind == "gen-hex32":
            value_b = secrets.token_hex(32).encode()
        else:
            sys.stderr.write(f"BUG: unknown source kind {kind}\n")
            return 1

        result = create_secret_with_initial_version(
            secret_name, value_b, args.dry_run,
        )
        value_b = None  # clear
        print(f"    secret: {result}")
        iam_result = grant_runtime_sa_access(secret_name, args.dry_run)
        print(f"    iam   : {iam_result}")

    # ── Phase C: Cloud SQL password rotation + DATABASE_URL secret ──
    if args.skip_db_rotation:
        print("\n[Phase C] SKIPPED via --skip-db-rotation")
    else:
        print("\n[Phase C] Cloud SQL password rotation + DATABASE_URL")

        if secret_has_versions(DATABASE_URL_SECRET):
            print(f"  {DATABASE_URL_SECRET}: SKIP (versions exist).")
            print(f"    To rotate: delete versions or pass --force-db (NYI).")
            print(f"    Then re-run.")
        else:
            # Generate password
            new_pw_b = secrets.token_urlsafe(48).encode()
            new_pw = new_pw_b.decode()

            # Reset Cloud SQL user password
            print(f"  daena (sql user): rotating password")
            r = reset_sql_user_password(new_pw_b, args.dry_run)
            print(f"    sql   : {r}")

            # Build DATABASE_URL and push
            url = build_database_url(new_pw)
            url_b = url.encode()
            new_pw = None
            new_pw_b = None
            url = None

            r = create_secret_with_initial_version(
                DATABASE_URL_SECRET, url_b, args.dry_run,
            )
            url_b = None
            print(f"  {DATABASE_URL_SECRET}")
            print(f"    secret: {r}")
            iam_result = grant_runtime_sa_access(
                DATABASE_URL_SECRET, args.dry_run,
            )
            print(f"    iam   : {iam_result}")

    # ── Final: enumerate Secret Manager (NAMES ONLY) ──
    print("\n[Verification] Secret Manager inventory (names only):")
    out = _run([
        GCLOUD, "secrets", "list", f"--project={PROJECT}",
        "--filter=name:daena-*", "--format=value(name)",
    ])
    for line in out.stdout.decode().splitlines():
        if line.strip():
            print(f"  {line.strip()}")

    print("\nDone. Run pwsh scripts/production_readiness_check.ps1 to "
          "verify. The Cloud Run env still uses plaintext until the "
          "operator binds via `gcloud run services update --update-secrets`.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
