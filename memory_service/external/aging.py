"""
Aging utilities for NBMF memory tiers.

The scheduler inspects records in the warm store (L2) and applies the
configured actions (tighten compression, summarise & demote to cold
storage) once their age crosses the thresholds defined in
`memory_policy.aging`.
"""

from __future__ import annotations

import time
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional

from .ledger import log_event
from .router import MemoryRouter

SECONDS_IN_DAY = 86400.0


def _matched_targets(targets: Optional[Iterable[str]], cls: str) -> bool:
    if not targets:
        return True
    return cls in targets


def _ensure_list(meta: Dict[str, Any], key: str) -> List[str]:
    value = meta.setdefault(key, [])
    if isinstance(value, list):
        return value
    new_value = list(value)
    meta[key] = new_value
    return new_value


def apply_aging(router: MemoryRouter, now: Optional[float] = None, *, dry_run: bool = False) -> Dict[str, int]:
    """
    Apply policy-driven aging actions and return a counter of applied actions.
    """
    policy = router.config.get("memory_policy", {})
    actions = policy.get("aging", [])
    if not isinstance(actions, list) or not actions:
        return {}

    now_ts = now or time.time()
    stats: Counter[str] = Counter()

    for item_id, cls, record in router.l2.iter_records():
        meta = dict(record.get("meta", {}))
        created_at = meta.get("created_at")
        if not isinstance(created_at, (int, float)):
            continue
        age_days = (now_ts - created_at) / SECONDS_IN_DAY
        for action_cfg in actions:
            action = action_cfg.get("action")
            threshold = action_cfg.get("after_days", 0)
            targets = action_cfg.get("targets")
            if age_days < threshold or not _matched_targets(targets, cls):
                continue
            applied = _ensure_list(meta, "aging_applied")
            if action in applied:
                continue

            if action == "tighten_compression":
                if dry_run:
                    stats[action] += 1
                    continue
                compression = meta.setdefault("compression", {})
                settings = compression.get("settings")
                if not isinstance(settings, dict):
                    settings = {}
                level = int(settings.get("zstd_level", 17))
                settings["zstd_level"] = min(level + 2, 22)
                settings["delta"] = True
                compression["settings"] = settings
                meta["retain_raw"] = False
                applied.append(action)
                router.l2.put_record(item_id, cls, record["payload"], meta)
                log_event(
                    action="aging_tighten",
                    ref=item_id,
                    store="nbmf",
                    route="aging",
                    extra={"cls": cls, "zstd_level": settings["zstd_level"]},
                )
                stats[action] += 1

            elif action == "summarize_pack":
                if dry_run:
                    stats[action] += 1
                    continue
                summary_text = str(record["payload"])
                summary_payload = {
                    "summary": summary_text[:1024],
                    "original_type": type(record["payload"]).__name__,
                }
                cold_meta = dict(meta)
                cold_ref = router.l3.put_record(item_id, cls, record["payload"], cold_meta)
                meta["cold_storage_ref"] = cold_ref
                meta["retain_raw"] = False
                applied.append(action)
                router.l2.put_record(item_id, cls, summary_payload, meta)
                log_event(
                    action="aging_summarize",
                    ref=item_id,
                    store="nbmf",
                    route="aging",
                    extra={"cls": cls, "cold_ref": cold_ref},
                )
                stats[action] += 1

    return dict(stats)
