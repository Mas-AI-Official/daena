#!/usr/bin/env python
from __future__ import annotations

import argparse
import base64
import os
import secrets
from pathlib import Path
from typing import Any, Dict, List, Tuple

from memory_service import crypto
from memory_service.crypto import read_secure_json, write_secure_json
from memory_service.kms import KeyManagementService
from memory_service.ledger import log_event


def _collect_paths(root: Path) -> List[Path]:
    if not root.exists():
        return []
    return [path for path in root.rglob("*.json") if path.is_file()]


def _read_records(paths: List[Path]) -> List[Tuple[Path, Any]]:
    records: List[Tuple[Path, Any]] = []
    for path in paths:
        data = read_secure_json(path)
        records.append((path, data))
    return records


def _write_records(records: List[Tuple[Path, Any]]) -> tuple[int, List[Path], List[Tuple[Path, Exception]]]:
    """Write records and return (success_count, successful_paths, failed_paths)."""
    successful_paths: List[Path] = []
    failed_paths: List[Tuple[Path, Exception]] = []
    
    for path, data in records:
        try:
            write_secure_json(path, data)
            successful_paths.append(path)
        except Exception as e:
            failed_paths.append((path, e))
    
    return len(successful_paths), successful_paths, failed_paths


def _default_key() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii").rstrip("=")


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Rotate the Daena NBMF encryption key and rewrap stored records."
    )
    parser.add_argument("--new-key", help="Base64/hex/plaintext material for the new key.")
    parser.add_argument("--l2", default=".l2_store", type=Path, help="L2 store directory.")
    parser.add_argument("--l3", default=".l3_store", type=Path, help="L3 store directory.")
    parser.add_argument("--dry-run", action="store_true", help="Scan records without rewriting.")
    parser.add_argument("--kms-log", type=Path, default=Path(".kms/kms_log.jsonl"), help="Optional path to append rotation metadata.")
    parser.add_argument("--kms-endpoint", help="Optional HTTP endpoint to forward rotation metadata.")
    parser.add_argument("--manifest-dir", type=Path, help="Directory for rotation manifests (defaults to alongside kms log).")
    parser.add_argument("--key-id", default="nbmf-memory", help="Logical identifier for the rotated key.")
    parser.add_argument("--operator", help="Operator identifier for rotation manifest.")
    parser.add_argument("--signing-key", help="Signing key (base64/hex/plain) for manifest HMAC; falls back to DAENA_KMS_SIGNING_KEY.")
    args = parser.parse_args(argv)

    old_key = os.getenv("DAENA_MEMORY_AES_KEY")
    if not old_key:
        parser.error("DAENA_MEMORY_AES_KEY must be set to decrypt existing records before rotation.")

    crypto.refresh()

    l2_records = _collect_paths(args.l2 / "records")
    l3_records = _collect_paths(args.l3 / "records")
    l3_artifacts = _collect_paths(args.l3)
    scan_targets = {p for p in l2_records + l3_records + l3_artifacts}

    if not scan_targets:
        print("No encrypted records found; rotation skipped.")
        return 0

    print(f"Discovered {len(scan_targets)} encrypted JSON objects; reading with current key...")
    records = _read_records(sorted(scan_targets))

    if args.dry_run:
        print("Dry-run complete. Records decrypted successfully with existing key.")
        return 0

    new_key = args.new_key or _default_key()
    os.environ["DAENA_MEMORY_AES_KEY"] = new_key
    crypto.refresh()

    print("Re-encrypting records with new key...")
    success_count, successful_paths, failed_paths = _write_records(records)
    
    if failed_paths:
        print(f"\nERROR: {len(failed_paths)} records failed to re-encrypt.")
        print("The system is in an inconsistent state:")
        print(f"  - {len(successful_paths)} records encrypted with NEW key")
        print(f"  - {len(failed_paths)} records still encrypted with OLD key")
        print("\nOptions:")
        print("  1. Restore from backup")
        print("  2. Manually fix failed records")
        print("  3. Continue (NOT RECOMMENDED - data loss risk)")
        
        response = input("\nContinue anyway? (yes/no): ").strip().lower()
        if response != "yes":
            # Rollback: re-encrypt successful records with old key
            print("Rolling back successful records to old key...")
            os.environ["DAENA_MEMORY_AES_KEY"] = old_key
            crypto.refresh()
            for path in successful_paths:
                try:
                    # Re-read and re-encrypt with old key
                    data = read_secure_json(path)
                    write_secure_json(path, data)
                except Exception as e:
                    print(f"Warning: Rollback failed for {path}: {e}")
            print("Rollback complete. System restored to original state.")
            return 1
    
    print(f"Successfully re-encrypted {len(successful_paths)} records.")

    kms = KeyManagementService(
        log_path=args.kms_log,
        manifest_dir=args.manifest_dir,
        endpoint=args.kms_endpoint,
    )
    kms_entry = kms.record_rotation(new_key, key_id=args.key_id, metadata={"count": len(records)})

    signing_key = args.signing_key or os.getenv("DAENA_KMS_SIGNING_KEY")
    operator = args.operator or os.getenv("DAENA_OPERATOR")
    manifest, manifest_path = kms.create_manifest(
        key_material=new_key,
        key_id=args.key_id,
        operator=operator,
        signing_key=signing_key,
        metadata={"records_rotated": len(records)},
    )
    log_event(
        action="kms_rotation",
        ref=args.key_id,
        store="nbmf",
        route="kms",
        extra={"records_rotated": len(records), "forward_error": kms_entry.get("forward_error")},
    )

    log_event(
        action="kms_manifest",
        ref=manifest["manifest_id"],
        store="nbmf",
        route="kms",
        extra={
            "manifest_hash": manifest["manifest_hash"],
            "prev_manifest_hash": manifest.get("prev_manifest_hash"),
            "signature": manifest.get("signature"),
        },
    )

    print("Rotation manifest written to", manifest_path)
    print(
        f"Rotation complete. Set DAENA_MEMORY_AES_KEY to the new value for runtime:\n{new_key}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

