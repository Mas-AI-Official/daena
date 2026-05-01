#!/bin/bash
# Daena Cloud Run entrypoint: run schema migrations before serving.
#
# alembic upgrade head is idempotent -- a no-op when the schema is
# already at head. PostgreSQL advisory locks inside Alembic serialize
# concurrent container starts so only one container runs the migration.
#
# Failure here surfaces as container start failure -> Cloud Run rejects
# the new revision -> traffic stays on the previous revision. This is
# the desired safety net for production migrations.
set -e

cd /app

echo "[entrypoint] Running alembic upgrade head..."
python3 -m alembic -c migrations/alembic.ini upgrade head

echo "[entrypoint] Starting uvicorn on port ${PORT:-8000}..."
exec python3 -m uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers 2 \
  --timeout-keep-alive 65 \
  --access-log \
  --log-level info
