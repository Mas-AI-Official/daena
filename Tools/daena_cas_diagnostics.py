"""
Diagnostic tool to analyze CAS efficiency and near-duplicate detection for LLM exchanges.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from memory_service.caching_cas import CAS
from memory_service.metrics import snapshot
from memory_service.simhash_neardup import simhash


def analyze_cas(root: Path) -> Dict[str, Any]:
    """Analyze CAS store contents and efficiency."""
    cas = CAS(root=str(root))
    cas_files = list(root.glob("*"))
    total_size = sum(f.stat().st_size for f in cas_files if f.is_file())
    return {
        "total_entries": len(cas_files),
        "total_size_bytes": total_size,
        "avg_size_bytes": total_size / len(cas_files) if cas_files else 0,
    }


def analyze_metrics() -> Dict[str, Any]:
    """Extract CAS-related metrics from the metrics snapshot."""
    snap = snapshot()
    cas_hits = snap.get("llm_cas_hit", 0)
    cas_misses = snap.get("llm_cas_miss", 0)
    near_dup_reuse = snap.get("llm_near_dup_reuse", 0)
    total_requests = cas_hits + cas_misses + near_dup_reuse
    hit_rate = (cas_hits + near_dup_reuse) / total_requests if total_requests else 0.0
    return {
        "cas_hits": cas_hits,
        "cas_misses": cas_misses,
        "near_dup_reuse": near_dup_reuse,
        "total_requests": total_requests,
        "hit_rate": round(hit_rate, 4),
        "exact_match_rate": round(cas_hits / total_requests if total_requests else 0.0, 4),
        "near_dup_rate": round(near_dup_reuse / total_requests if total_requests else 0.0, 4),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze CAS efficiency for LLM exchanges")
    parser.add_argument("--cas-root", type=Path, default=".llm_cas", help="CAS store root directory")
    parser.add_argument("--metrics-only", action="store_true", help="Show only metrics, not CAS file analysis")
    args = parser.parse_args(argv)

    report: Dict[str, Any] = {}

    if not args.metrics_only:
        if args.cas_root.exists():
            report["cas_store"] = analyze_cas(args.cas_root)
        else:
            report["cas_store"] = {"error": "CAS root does not exist", "path": str(args.cas_root)}

    report["metrics"] = analyze_metrics()

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())

