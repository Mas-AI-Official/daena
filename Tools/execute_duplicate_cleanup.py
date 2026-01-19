#!/usr/bin/env python3
"""
Execute Duplicate Cleanup - Remove duplicates and consolidate docs
"""

import json
import shutil
from pathlib import Path
from datetime import datetime

root = Path(__file__).parent.parent
archive_dir = root / "docs" / "archive"
archive_dir.mkdir(parents=True, exist_ok=True)

# Load duplicate report
report_file = root / "reports" / "fast_duplicate_report.json"
with open(report_file) as f:
    report = json.load(f)

# Files to delete (verified safe)
files_to_delete = []

# Files to archive (documentation)
files_to_archive = []

# 1. Router duplicates - backend/routers/ appears unused
# safe_import_router uses routes.* not routers.*
obsolete_routers = [
    "backend/routers/health.py",  # Simple ping, routes/health.py has full implementation
    # Check others before deleting
]

# 2. Documentation consolidation
# Keep only essential, archive the rest
essential_docs = {
    "DAENA_2_HARDENING_COMPLETE.md",
    "docs/PHASE_STATUS_AND_NEXT_STEPS.md",
    "docs/CURRENT_SYSTEM_STATUS.md",
    "docs/DAENA_STRUCTURE_ANALYSIS_AND_UPGRADE_PLAN.md",
    "docs/NBMF_PRODUCTION_READINESS.md",
    "docs/NBMF_PATENT_PUBLICATION_ROADMAP.md",
}

print("Duplicate Cleanup Execution")
print("=" * 60)

# Archive old documentation
all_complete_files = report.get('complete_files', [])
all_summary_files = report.get('summary_files', [])
all_status_files = report.get('status_files', [])

archive_count = 0
for doc_file in all_complete_files + all_summary_files + all_status_files:
    doc_path = root / doc_file
    if doc_path.exists():
        # Skip essential files
        if any(doc_file.endswith(essential) or essential in doc_file for essential in essential_docs):
            continue
        
        # Archive it
        archive_path = archive_dir / Path(doc_file).name
        if not archive_path.exists():
            try:
                shutil.move(str(doc_path), str(archive_path))
                archive_count += 1
                print(f"Archived: {doc_file}")
            except Exception as e:
                print(f"⚠️  Could not archive {doc_file}: {e}")

print(f"\n✅ Archived {archive_count} documentation files to docs/archive/")
print(f"📁 Archive location: {archive_dir}")

# Save cleanup log
cleanup_log = {
    "timestamp": datetime.now().isoformat(),
    "archived_files": archive_count,
    "archive_location": str(archive_dir),
    "essential_files_kept": list(essential_docs)
}

log_file = root / "reports" / "cleanup_log.json"
with open(log_file, 'w') as f:
    json.dump(cleanup_log, f, indent=2)

print(f"\n📋 Cleanup log saved: {log_file}")
print("\n✅ Cleanup execution complete!")

