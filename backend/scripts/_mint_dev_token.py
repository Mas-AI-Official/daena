"""One-shot dev token mint for hotfix verification probes.

Reads the first founder/admin user from sqlite and prints a JWT to stdout.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.database import async_session_factory  # type: ignore  # noqa: E402
from app.core.security import create_access_token  # type: ignore  # noqa: E402
from sqlalchemy import select  # type: ignore  # noqa: E402

from app.models.identity import User  # type: ignore  # noqa: E402


async def main() -> None:
    async with async_session_factory() as db:
        result = await db.execute(select(User).order_by(User.created_at.asc()).limit(1))
        user = result.scalar_one_or_none()
        if user is None:
            print("ERROR: no users in db", file=sys.stderr)
            sys.exit(2)
        token = create_access_token(
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            role=str(user.role),
            email=str(user.email or ""),
            display_name=str(user.display_name or ""),
        )
        print(token)


if __name__ == "__main__":
    asyncio.run(main())
