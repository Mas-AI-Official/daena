"""One-shot cleanup for the Codex stderr leak (QA finding OBS-0004).

The pre-fix `codex.py:131-132` yielded raw stderr into the SSE chat stream,
which was persisted as ChatMessage.content rows. This script scrubs the
leaked content from those rows in-place so a session export / share does
not leak workdir / model / provider / session-id.

Pattern matched: any chunk that starts with `[stderr: OpenAI Codex` and
runs to the matching `]`. We do NOT delete the row -- the assistant's real
answer text (e.g. "alive") usually appears BEFORE the leaked stderr in the
same content blob, and deleting the whole row would lose that answer.
Instead we cut the leaked portion out.

Run from the backend project root:

    .venv\\Scripts\\python.exe -m scripts.cleanup_codex_stderr_leak [--dry-run]

The script defaults to --dry-run for safety. Re-run with --apply to
actually update the rows. Always back up the database first.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from typing import TYPE_CHECKING

from sqlalchemy import select, update

from app.core.database import async_session_maker
from app.core.logging import get_logger
from app.models.chat import ChatMessage

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = get_logger(__name__)

# Multiline-aware: starts at "[stderr: OpenAI Codex", consumes until the
# next unescaped "]" (the Codex banner has no nested brackets in stderr,
# so this is safe). The 500-char cap from codex.py:132 means each leaked
# chunk is at most ~600 chars including framing.
LEAK_PATTERN = re.compile(
    r"\n?\[stderr: OpenAI Codex[^\]]*?\]",
    flags=re.DOTALL,
)


def scrub(content: str) -> str:
    """Strip [stderr: OpenAI Codex...] chunks from a content blob."""
    return LEAK_PATTERN.sub("", content).strip()


async def main(*, apply: bool) -> int:
    """Find leaked rows, optionally update them, return count touched."""
    async with async_session_maker() as session:
        # Postgres uses LIKE; SQLite is case-sensitive by default but the
        # leaked text is already case-exact, so LIKE works on both.
        stmt = select(ChatMessage).where(
            ChatMessage.content.like("%[stderr: OpenAI Codex%"),
        )
        result = await session.execute(stmt)
        rows: Sequence[ChatMessage] = result.scalars().all()

        if not rows:
            print("No leaked rows found. Database is clean.")
            return 0

        print(f"Found {len(rows)} leaked row(s):")
        for row in rows:
            scrubbed = scrub(row.content)
            removed = len(row.content) - len(scrubbed)
            preview_before = row.content[:80].replace("\n", " ")
            preview_after = scrubbed[:80].replace("\n", " ")
            print(f"  id={row.id}  -{removed} chars")
            print(f"    BEFORE: {preview_before!r}")
            print(f"    AFTER : {preview_after!r}")

            if apply:
                await session.execute(
                    update(ChatMessage)
                    .where(ChatMessage.id == row.id)
                    .values(content=scrubbed),
                )

        if apply:
            await session.commit()
            print(f"\n[APPLIED] {len(rows)} rows scrubbed and committed.")
        else:
            print(f"\n[DRY RUN] {len(rows)} rows would be scrubbed. Re-run with --apply to commit.")

        return len(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually update rows. Without this flag, runs in dry-run mode.",
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(main(apply=args.apply)) and 0 or 0)
