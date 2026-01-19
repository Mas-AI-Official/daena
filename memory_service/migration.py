from __future__ import annotations

from typing import Any, Dict, Optional

from .divergence_check import compare_records
from .ledger import log_event
from .router import MemoryRouter


def finalize_backfill(router: Optional[MemoryRouter] = None, limit: Optional[int] = None) -> Dict[str, Any]:
    r = router or MemoryRouter()
    legacy = r.legacy_store
    migrated = skipped = mismatches = errors = 0
    error_details: List[Dict[str, Any]] = []
    
    for idx, item_id in enumerate(legacy.list_ids()):
        if limit is not None and idx >= limit:
            break
        try:
            record = legacy.get_record(item_id)
            if not record:
                continue
            cls = record.get("cls", "*")
            payload = record.get("payload")
            if payload is None:
                continue
            if r.l2.exists(item_id, cls):
                skipped += 1
                continue
            
            # Attempt migration with error handling
            try:
                r.write_nbmf_only(item_id, cls, payload, record.get("meta", {}))
                nbmf_record = r.l2.get_record(item_id, cls)
                ok = compare_records(payload, nbmf_record)
                mismatches += 0 if ok else 1
                log_event(action="migrate", store="both", route="cutover", ref=item_id, extra={"ok": ok})
                migrated += 1
            except Exception as e:
                errors += 1
                error_details.append({"item_id": item_id, "cls": cls, "error": str(e)})
                log_event(
                    action="migrate_error",
                    store="legacy",
                    route="cutover",
                    ref=item_id,
                    extra={"cls": cls, "error": str(e)},
                )
        except Exception as e:
            # Error reading legacy record - skip it
            errors += 1
            error_details.append({"item_id": item_id, "error": str(e), "stage": "read"})
    
    result = {"migrated": migrated, "skipped": skipped, "mismatches": mismatches, "errors": errors}
    if errors > 0:
        result["error_details"] = error_details[:10]  # Limit to first 10 errors
    return result
