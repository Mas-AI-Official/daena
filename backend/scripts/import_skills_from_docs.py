"""
Import skills from a local docs folder (DAENA_SKILL_IMPORT_PATH).

Scans recursively for *.py files. For each file:
- Uses ast to parse only (no execution).
- If SKILL_MANIFEST dict exists at module level, use it for metadata.
- Otherwise infer: name from filename, category=utility, risk=low, creator=founder,
  allowed_roles=["founder","daena"].

Creates or updates registry entries; does not execute skill code.

Usage:
  set DAENA_SKILL_IMPORT_PATH=D:\\Ideas\\Daena_old_upgrade_20251213\\docs\\2026-01-31\\new files
  python -m backend.scripts.import_skills_from_docs
"""

import ast
import os
import sys
from pathlib import Path


def _ast_value_to_python(node):
    """Convert AST constant/dict/list to Python value. Safe for literals only."""
    if node is None:
        return None
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, (ast.Str, ast.Num)):  # Python <3.8
        if isinstance(node, ast.Str):
            return node.s
        return node.n
    if isinstance(node, ast.Dict):
        return {_ast_value_to_python(k): _ast_value_to_python(v) for k, v in zip(node.keys, node.values)}
    if isinstance(node, ast.List):
        return [_ast_value_to_python(e) for e in node.elts]
    if isinstance(node, ast.ListComp):
        return []  # Do not evaluate comprehensions
    return None


def extract_skill_manifest(source: str, filepath: str) -> dict | None:
    """
    Parse Python source with ast and return SKILL_MANIFEST dict if present.
    Returns None if not found or parse error. Does not execute code.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "SKILL_MANIFEST" and isinstance(node.value, ast.Dict):
                    out = _ast_value_to_python(node.value)
                    if isinstance(out, dict):
                        return out
    return None


def infer_metadata(filepath: Path) -> dict:
    """Infer skill metadata from filename when SKILL_MANIFEST is absent."""
    name = filepath.stem
    if not name.replace("_", "").isalnum():
        name = "skill_" + name[:32].replace(" ", "_")
    return {
        "name": name,
        "display_name": name.replace("_", " ").title(),
        "description": f"Imported from {filepath.name}",
        "category": "utility",
        "creator": "founder",
        "risk_level": "low",
        "allowed_roles": ["founder", "daena"],
    }


def normalize_manifest(manifest: dict, filepath: Path) -> dict:
    """Normalize SKILL_MANIFEST keys to registry payload (name, display_name, category, creator, access, etc.)."""
    name = (manifest.get("name") or filepath.stem).strip()
    if not name.replace("_", "").replace("-", "").isalnum():
        name = "skill_" + name[:32].replace(" ", "_")
    access = manifest.get("access") or {}
    allowed_roles = access.get("allowed_roles") if isinstance(access, dict) else None
    if not allowed_roles:
        allowed_roles = manifest.get("allowed_roles", ["founder", "daena"])
    return {
        "name": name,
        "display_name": (manifest.get("display_name") or name.replace("_", " ").title()).strip(),
        "description": (manifest.get("description") or f"Imported from {filepath.name}").strip(),
        "category": (manifest.get("category") or "utility").strip().lower(),
        "creator": (manifest.get("creator") or "founder").strip().lower(),
        "risk_level": (manifest.get("risk_level") or manifest.get("risk") or "low").strip().lower(),
        "code_body": "",  # Filled from file read when creating (read-only; no execution)
        "access": {
            "allowed_roles": [r.strip().lower() for r in allowed_roles] if isinstance(allowed_roles, list) else ["founder", "daena"],
            "allowed_departments": [],
            "allowed_agents": [],
        },
        "enabled": True,
    }


def scan_and_import(root: Path) -> list[dict]:
    """Scan root for *.py, parse SKILL_MANIFEST or infer, return list of payloads (no registry write here)."""
    payloads = []
    for path in root.rglob("*.py"):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        manifest = extract_skill_manifest(text, str(path))
        if manifest and isinstance(manifest, dict):
            payload = normalize_manifest(manifest, path)
        else:
            payload = infer_metadata(path)
            payload["access"] = {"allowed_roles": ["founder", "daena"], "allowed_departments": [], "allowed_agents": []}
        try:
            payload["code_body"] = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            payload["code_body"] = "# Imported; source not read."
        payload["_filepath"] = str(path)
        payloads.append(payload)
    return payloads


def run_import():
    path_str = os.environ.get("DAENA_SKILL_IMPORT_PATH", "").strip()
    if not path_str:
        print("DAENA_SKILL_IMPORT_PATH not set; skipping skill import.")
        return 0
    root = Path(path_str)
    if not root.is_dir():
        print(f"DAENA_SKILL_IMPORT_PATH is not a directory: {root}")
        return 1
    payloads = scan_and_import(root)
    if not payloads:
        print("No .py files found under", root)
        return 0
    # Add project root so backend can be imported
    backend_root = Path(__file__).resolve().parent.parent.parent
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))
    try:
        from backend.services.skill_registry import get_skill_registry
    except ImportError:
        print("Could not import skill_registry; run from project root or set PYTHONPATH.")
        return 1
    registry = get_skill_registry()
    created, updated, errors = 0, 0, 0
    for p in payloads:
        p.pop("_filepath", None)
        payload = {k: v for k, v in p.items() if not k.startswith("_")}
        name = payload.get("name")
        if not name:
            errors += 1
            continue
        try:
            existing = registry.get_skill_by_name(name)
            if existing:
                registry.update_skill(existing["id"], {
                    "display_name": payload.get("display_name"),
                    "description": payload.get("description"),
                    "category": payload.get("category"),
                    "creator": payload.get("creator"),
                    "access": payload.get("access"),
                    "policy": {"risk_level": payload.get("risk_level", "low")},
                })
                updated += 1
            else:
                registry.create_skill(payload)
                created += 1
        except Exception as e:
            print(f"  Error {name}: {e}")
            errors += 1
    print(f"Import complete: {created} created, {updated} updated, {errors} errors.")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(run_import())
