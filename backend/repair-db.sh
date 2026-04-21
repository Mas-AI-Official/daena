#!/bin/bash
# One-shot SQLite corruption repair.
#
# The DB became btree-corrupt after WAL mode succeeded briefly on WSL
# drvfs and then tripped on the next write. This script dumps the
# corrupted file to SQL (skipping unreadable rows), replays into a
# fresh DB in /tmp (WSL-native FS, no drvfs flake), and copies back.
#
# Safe to run with the backend STOPPED. Leaves the corrupted backup
# in place with a timestamped .corrupted-backup-* name.
set -euo pipefail

cd "$(dirname "$0")"

BACKUP=$(ls -t daena_dev2.db.corrupted-backup-* 2>/dev/null | head -1)
if [ -z "$BACKUP" ]; then
    echo "FATAL: no corrupted-backup file found next to daena_dev2.db"
    exit 1
fi
echo "Using backup: $BACKUP"

# Work in /tmp (native ext4, no drvfs)
WORK=/tmp/daena-repair-$$
mkdir -p "$WORK"
cp "$BACKUP" "$WORK/corrupted.db"

echo "=== dump (readable rows only) ==="
sqlite3 "$WORK/corrupted.db" ".dump" > "$WORK/rec.sql" 2> "$WORK/dump.err" || true
SQL_LINES=$(wc -l < "$WORK/rec.sql")
DUMP_ERR_LINES=$(wc -l < "$WORK/dump.err")
echo "  sql lines: $SQL_LINES"
echo "  dump errors: $DUMP_ERR_LINES"
if [ "$DUMP_ERR_LINES" -gt 0 ]; then
    head -3 "$WORK/dump.err"
fi

echo ""
echo "=== replay into fresh DB ==="
rm -f "$WORK/fresh.db"
sqlite3 "$WORK/fresh.db" < "$WORK/rec.sql" 2> "$WORK/replay.err" || true
REPLAY_ERR_LINES=$(wc -l < "$WORK/replay.err")
echo "  row-insert failures: $REPLAY_ERR_LINES"
if [ "$REPLAY_ERR_LINES" -gt 0 ]; then
    head -5 "$WORK/replay.err"
fi

echo ""
echo "=== integrity check (fresh) ==="
sqlite3 "$WORK/fresh.db" "PRAGMA integrity_check" | head -3

echo ""
echo "=== key tables ==="
for T in chat_sessions users tasks chat_messages project_pipeline; do
    N=$(sqlite3 "$WORK/fresh.db" "SELECT COUNT(*) FROM $T" 2>/dev/null || echo "MISSING")
    printf "  %-20s %s\n" "$T" "$N"
done

echo ""
echo "=== copy back to Windows ==="
cp "$WORK/fresh.db" ./daena_dev2.db
chmod 644 ./daena_dev2.db
sync
ls -la ./daena_dev2.db

echo ""
echo "=== final integrity (on Windows copy) ==="
sqlite3 ./daena_dev2.db "PRAGMA integrity_check" | head -3

echo ""
echo "=== journal mode (should be 'delete' = rollback) ==="
sqlite3 ./daena_dev2.db "PRAGMA journal_mode"

echo ""
echo "DONE. Corrupted backup preserved at: $BACKUP"
rm -rf "$WORK"
