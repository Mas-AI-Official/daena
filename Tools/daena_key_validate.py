#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List

from memory_service.kms import KeyManagementService


def _load_manifest_paths(manifest_dir: Path) -> List[Path]:
    if not manifest_dir.exists():
        return []
    return sorted(p for p in manifest_dir.glob("*.json") if p.is_file())


def validate_chain(manifest_dir: Path, signing_key: str | None) -> int:
    kms = KeyManagementService(manifest_dir=manifest_dir)
    previous_hash: str | None = None
    success = True
    for path in _load_manifest_paths(manifest_dir):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if previous_hash and manifest.get("prev_manifest_hash") != previous_hash:
            print(f"✗ Chain break: {path.name} does not reference previous hash {previous_hash}")
            success = False
        if not KeyManagementService.verify_manifest(manifest, signing_key):
            print(f"✗ Verification failed for {path.name}")
            success = False
        previous_hash = manifest.get("manifest_hash")
    if success:
        count = len(_load_manifest_paths(manifest_dir))
        print(f"✓ Manifest chain verified ({count} entries)")
        return 0
    return 1


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate NBMF key rotation manifest chain.")
    parser.add_argument("--manifest-dir", type=Path, default=Path(".kms/manifests"))
    parser.add_argument("--signing-key", help="Signing key for verifying manifest signatures (base64/hex/plaintext).")
    args = parser.parse_args(argv)
    signing_key = args.signing_key or None
    return validate_chain(args.manifest_dir, signing_key)


if __name__ == "__main__":
    raise SystemExit(main())

