#!/bin/bash
# Daena Cloud Run entrypoint: schema bootstrap + alembic + uvicorn.
#
# Schema lifecycle:
#   1. On FIRST boot (alembic_version table missing), bootstrap the
#      schema via SQLAlchemy `Base.metadata.create_all`, then stamp
#      alembic to head. This skips running every historical migration
#      against an empty DB (some early migrations ALTER tables that
#      don't exist yet because they predate the table-creation pattern).
#   2. On SUBSEQUENT boots, run `alembic upgrade head` normally to
#      apply any new incremental migrations.
#
# After the schema step, exec uvicorn. The schema check is idempotent
# and safe under concurrent container starts (PostgreSQL advisory locks
# inside SQLAlchemy + idempotent CREATE TABLE IF NOT EXISTS).
set -e

cd /app

echo "[entrypoint] Checking schema state..."
SCHEMA_STATE=$(python3 -c "
import asyncio
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from app.core.database import engine

async def check():
    async with engine.begin() as conn:
        try:
            r = await conn.execute(text('SELECT version_num FROM alembic_version LIMIT 1'))
            v = r.scalar_one_or_none()
            print('versioned' if v else 'empty-version-table')
        except ProgrammingError:
            print('no-alembic-table')
        except Exception as e:
            print(f'error:{type(e).__name__}')

asyncio.run(check())
" 2>&1 | tail -1)

echo "[entrypoint] Schema state: $SCHEMA_STATE"

if [ "$SCHEMA_STATE" = "no-alembic-table" ] || [ "$SCHEMA_STATE" = "empty-version-table" ]; then
  echo "[entrypoint] First boot -- bootstrapping schema via SQLAlchemy..."
  python3 -c "
import asyncio
from app.core.database import engine
from app.models import Base  # noqa: F401  -- triggers all model imports

async def init():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

asyncio.run(init())
"
  echo "[entrypoint] Stamping alembic to head (skip historical migrations)..."
  python3 -m alembic -c migrations/alembic.ini stamp head
else
  echo "[entrypoint] Running alembic upgrade head..."
  python3 -m alembic -c migrations/alembic.ini upgrade head
fi

echo "[entrypoint] Starting uvicorn on port ${PORT:-8000}..."
exec python3 -m uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers 2 \
  --timeout-keep-alive 65 \
  --access-log \
  --log-level info
