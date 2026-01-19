from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict

from .crypto import read_secure_json


def _dir_stats(path: Path) -> Dict[str, Any]:
    total_bytes = 0
    count = 0
    if not path.exists():
        return {"files": 0, "bytes": 0}
    for file in path.glob("**/*"):
        if file.is_file():
            count += 1
            total_bytes += file.stat().st_size
    return {"files": count, "bytes": total_bytes}


def _update_usage(
    target: Dict[str, Any],
    file_path: Path,
    payload: Dict[str, Any],
) -> None:
    meta = payload.get("meta", {}) if isinstance(payload, dict) else {}
    cls = payload.get("cls") or meta.get("cls") or "unknown"
    tenant = meta.get("tenant_id", "unknown")
    compression = (meta.get("compression", {}) or {}).get("profile", "unassigned")

    target["records"] += 1
    size = file_path.stat().st_size
    target["bytes"] += size
    target["by_class"][cls] += 1
    target["by_tenant"][tenant] += 1
    target["bytes_by_tenant"][tenant] += size
    target["compression_profiles"][compression] += 1


def collect_memory_stats(l2_root: str = ".l2_store", l3_root: str = ".l3_store") -> Dict[str, Any]:
    stats: Dict[str, Any] = {
        "l2": {
            "records": 0,
            "bytes": 0,
            "by_class": Counter(),
            "by_tenant": Counter(),
            "bytes_by_tenant": defaultdict(int),
            "compression_profiles": Counter(),
        },
        "l3": {
            "records": 0,
            "bytes": 0,
            "by_class": Counter(),
            "by_tenant": Counter(),
            "bytes_by_tenant": defaultdict(int),
            "compression_profiles": Counter(),
        },
    }

    l2_path = Path(l2_root) / "records"
    l3_path = Path(l3_root) / "records"

    if l2_path.exists():
        for file in l2_path.glob("*.json"):
            try:
                data = read_secure_json(file)
            except Exception:
                continue
            _update_usage(stats["l2"], file, data)

    if l3_path.exists():
        for file in l3_path.glob("*.json"):
            try:
                data = read_secure_json(file)
            except Exception:
                continue
            _update_usage(stats["l3"], file, data)

    for tier in ("l2", "l3"):
        stats[tier]["by_class"] = dict(stats[tier]["by_class"])
        stats[tier]["by_tenant"] = dict(stats[tier]["by_tenant"])
        stats[tier]["bytes_by_tenant"] = dict(stats[tier]["bytes_by_tenant"])
        stats[tier]["compression_profiles"] = dict(stats[tier]["compression_profiles"])
        stats[tier].update(_dir_stats(Path(l2_root if tier == "l2" else l3_root)))

    total_records = stats["l2"].get("records", 0) + stats["l3"].get("records", 0)
    total_bytes = stats["l2"].get("bytes", 0) + stats["l3"].get("bytes", 0)
    stats["totals"] = {
        "records": total_records,
        "bytes": total_bytes,
    }
    return stats
