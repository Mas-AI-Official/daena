"""Feed trust-promoted agent experiences into a tenant-scoped ragx collection.

This closes the recall half of the NBMF write-back loop (Phase 3 item 9, G2).
The write-back path (chat Stage 10.5 -> memory.store_experience) lands an
experience in the DB tier as quarantined tier-0; ``memory.validate_quarantined``
later promotes it once trust crosses threshold. At the moment of promotion we
also index the experience here so a later CMD turn recalls it SEMANTICALLY via
ragx (Stage 6.1), not only by keyword. No second vector store is built inside
Daena (N1): ragx owns the embeddings, exactly as ``dept_knowledge_ingest`` does
for EXE artifacts.

Design constraints honoured here (mirrors dept_knowledge_ingest, with one
deliberate divergence):
  * SESSION-FREE. Unlike dept_knowledge_ingest this never opens a DB session.
    The scheduler receives PLAIN values captured at promotion time inside
    ``validate_quarantined``. That is the race guard: promotion only flushes
    (``is_quarantined=False``), it does not commit, so a task that re-read the
    row could observe either the pre- or post-flush state depending on timing.
    By passing copied scalars we depend on nothing in the DB and cannot race.
  * NON-SENSITIVE ONLY. The caller filters ``is_sensitive`` before scheduling,
    so no PII / credentials ever reach this external store (plaintext markdown
    on disk + embeddings in ragx). Sensitive experiences stay keyword-only in
    the local DB tier. This module assumes its input is already clean.
  * DETERMINISTIC + IDEMPOTENT. The markdown is keyed only on persisted values
    (the experience id and its ``created_at``, never ``now()``) at a stable
    per-experience path, so re-indexing the same experience is a no-op: identical
    bytes -> identical SHA -> ragx skips it.
  * Isolation is by collection NAME (ragx has no metadata filter). The target is
    the single tenant-scoped ``experience_collection_name`` -- the tenant hex
    prefix guarantees two tenants never share a collection (Rule 9 leak guard).
  * Fails OPEN (ADR-001 / Rule 17): every failure is logged, none is raised into
    the promotion path. A ragx outage leaves the file on disk for a later cron
    re-index; it never breaks trust promotion.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import UUID

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.ragx_bridge import RAGX_URL, experience_collection_name

logger = get_logger(__name__)

# Indexing is a background write; give ragx room to chew on a file without ever
# blocking anything user-visible (this never runs on the request path).
_INDEX_TIMEOUT_S = 15.0

# Keep a strong reference to in-flight fire-and-forget tasks. asyncio only holds
# a weak reference to tasks created via create_task; without this set a task can
# be garbage-collected mid-run. Discarded in the done callback.
_INFLIGHT: set[asyncio.Task] = set()


def schedule_experience_ingest(
    *,
    tenant_id: UUID,
    experience_id: UUID,
    content: str,
    summary: str | None,
    tags: list[str],
    created_at,
) -> None:
    """Fire-and-forget schedule of ``ingest_experience`` on the running loop.

    Never raises into the caller: trust promotion has already flushed by the
    time this runs, so ingestion must never be able to turn a successful
    promotion into a failure. Receives plain values (no ORM instance / session)
    so it depends on nothing that a concurrent commit could change.
    """
    coro = ingest_experience(
        tenant_id=tenant_id,
        experience_id=experience_id,
        content=content,
        summary=summary,
        tags=tags,
        created_at=created_at,
    )
    try:
        task = asyncio.create_task(coro)
        _INFLIGHT.add(task)
        task.add_done_callback(_INFLIGHT.discard)
    except RuntimeError:
        # No running event loop (e.g. called from a sync context). Nothing to
        # schedule; skip silently rather than crash the caller. Close the
        # never-scheduled coroutine so it cannot warn as un-awaited.
        coro.close()
        logger.debug("experience_ingest_no_loop", exc_info=True)
    except Exception:
        coro.close()
        logger.debug("experience_ingest_schedule_failed", exc_info=True)


async def ingest_experience(
    *,
    tenant_id: UUID,
    experience_id: UUID,
    content: str,
    summary: str | None,
    tags: list[str],
    created_at,
) -> None:
    """Write a deterministic markdown file for one promoted experience and index
    it into the tenant's ragx experience collection. Fails open (never raises).

    No DB session: everything needed was captured at promotion time. The caller
    guarantees the experience is NON-sensitive.
    """
    try:
        collection = experience_collection_name(tenant_id)

        body = _render_markdown(
            experience_id=experience_id,
            summary=summary,
            content=content,
            tags=tags,
            created_at=created_at,
        )
        path = _experience_dir() / collection / f"exp-{experience_id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")

        indexed = await _index_path(collection, path)
        if indexed:
            logger.info(
                "experience_indexed",
                collection=collection,
                experience_id=str(experience_id),
            )
    except Exception:
        logger.warning("experience_ingest_failed", exc_info=True)


async def _index_path(collection: str, path: Path) -> bool:
    """POST the file path to ragx for indexing. Fails open: logs and returns
    False on any HTTP failure so a ragx outage never breaks ingest. ragx
    auto-creates the collection on first index, so no pre-registration needed.
    Note: the collection is in the URL path here; the body carries sources."""
    url = f"{RAGX_URL}/collections/{collection}/index"
    try:
        async with httpx.AsyncClient(timeout=_INDEX_TIMEOUT_S) as client:
            resp = await client.post(url, json={"sources": [str(path)]})
        if resp.status_code != 200:
            logger.warning(
                "experience_index_http_error",
                collection=collection,
                status=resp.status_code,
            )
            return False
        return True
    except httpx.RequestError:
        logger.warning(
            "experience_index_unreachable", collection=collection, exc_info=True
        )
        return False


def _render_markdown(
    *,
    experience_id: UUID,
    summary: str | None,
    content: str,
    tags: list[str],
    created_at,
) -> str:
    """Render a deterministic summary. Content is keyed only on persisted values
    (no ``now()``) so the file SHA is stable across retries -> idempotent index."""
    when = created_at.isoformat() if created_at is not None else ""
    tag_line = ", ".join(t for t in (tags or []) if t) or "(none)"
    lines = [
        f"# Experience {experience_id}",
        "",
        f"- created_at: {when}",
        f"- tags: {tag_line}",
        "",
    ]
    if summary:
        lines += ["## Summary", "", summary.strip(), ""]
    lines += ["## Detail", "", _content_preview(content), ""]
    return "\n".join(lines)


def _content_preview(content: str, max_chars: int = 2000) -> str:
    """Compact, deterministic text rendering of experience content for indexing."""
    text = (content or "").strip()
    if not text:
        return "(empty)"
    if len(text) > max_chars:
        text = text[:max_chars] + "\n... (truncated)"
    return text


def _experience_dir() -> Path:
    """Base directory for experience knowledge files. Honours an optional
    ``experience_knowledge_dir`` setting; otherwise backend/var/experience.
    var/ is a durable artifact dir (never deleted), correct for these files."""
    configured = getattr(get_settings(), "experience_knowledge_dir", None)
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2] / "var" / "experience"


def merge_experience_lines(
    keyword_lines: list[str],
    semantic_lines: list[str],
    limit: int = 5,
) -> list[str]:
    """Merge keyword-recall lines with ragx semantic-recall lines for Stage 6.1.

    Pure and side-effect free. Keyword lines come first (they are the local,
    always-available fallback per Rule 17); semantic lines fill the remainder.
    Deduplicates on normalised text (case- and whitespace-insensitive) so the
    same experience surfaced by both paths is shown once, and caps the total at
    ``limit`` to keep the prompt focused (recall rots past a small budget).
    """
    merged: list[str] = []
    seen: set[str] = set()
    for line in [*keyword_lines, *semantic_lines]:
        norm = " ".join((line or "").split()).lower()
        if not norm or norm in seen:
            continue
        seen.add(norm)
        merged.append(line)
        if len(merged) >= limit:
            break
    return merged
