#!/bin/bash
# Corruption-tolerant DB repair using sqlite3 `.recover`.
# Previous .dump approach failed because sqlite3 detected corruption
# and emitted a trailing ROLLBACK, which rolled back the whole
# transaction when replayed. `.recover` walks raw pages instead and
# rebuilds structure from readable cells -- works even when .dump fails.
set -euo pipefail

cd "$(dirname "$0")"

BACKUP=$(ls -t daena_dev2.db.corrupted-backup-* 2>/dev/null | head -1)
if [ -z "$BACKUP" ]; then
    echo "FATAL: no corrupted-backup file found"
    exit 1
fi

WORK=/tmp/daena-recover-$$
mkdir -p "$WORK"
cp "$BACKUP" "$WORK/src.db"
cd "$WORK"

echo "=== .recover (corruption-tolerant dump) ==="
sqlite3 src.db '.recover' > recover.sql 2> recover.err || true
echo "  sql lines: $(wc -l < recover.sql)"
echo "  recover errors: $(wc -l < recover.err)"
echo "  last line of output:"
tail -1 recover.sql

echo ""
echo "=== replay into fresh DB ==="
rm -f fresh.db
sqlite3 fresh.db < recover.sql 2> replay.err || true
echo "  replay errors: $(wc -l < replay.err)"
if [ -s replay.err ]; then
    head -5 replay.err
fi

echo ""
echo "=== integrity check ==="
sqlite3 fresh.db 'PRAGMA integrity_check' | head -3

echo ""
echo "=== total tables ==="
sqlite3 fresh.db 'SELECT COUNT(*) FROM sqlite_master WHERE type="table"'

echo ""
echo "=== row counts ==="
for T in chat_sessions users tasks chat_messages project_pipeline user_quotas agents departments; do
    N=$(sqlite3 fresh.db "SELECT COUNT(*) FROM $T" 2>&1 || echo MISSING)
    printf "  %-22s %s\n" "$T" "$N"
done

echo ""
echo "=== fresh.db size ==="
ls -la fresh.db

echo ""
echo "=== copy to Windows ==="
ORIG_DB=/mnt/d/Ideas/Daena/backend/daena_dev2.db
rm -f "$ORIG_DB"
cp fresh.db "$ORIG_DB"
chmod 644 "$ORIG_DB"
sync
ls -la "$ORIG_DB"

echo ""
echo "=== final check on Windows side ==="
sqlite3 "$ORIG_DB" 'PRAGMA integrity_check' | head -1
sqlite3 "$ORIG_DB" 'PRAGMA journal_mode'
sqlite3 "$ORIG_DB" "SELECT 'chat_sessions:'||COUNT(*) FROM chat_sessions"
sqlite3 "$ORIG_DB" "SELECT 'users:'||COUNT(*) FROM users"

rm -rf "$WORK"
echo ""
echo "DONE."
