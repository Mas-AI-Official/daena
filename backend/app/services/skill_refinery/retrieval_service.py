"""Skill retrieval: keyword-based search for relevant skills.

Used at Stage 7.5 of the chat_orchestrator pipeline to inject
evidence-backed patterns into system prompts.

Phase 2 uses keyword matching against title, domain, steps, and
patterns.  Phase 3+ will add pgvector/embedding-based retrieval.
"""

from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.skill import MATURITY_TIERS, RefinedSkill

logger = get_logger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*", re.ASCII)

_STOPWORDS: frozenset[str] = frozenset(
    {
        "a", "an", "the", "is", "are", "was", "were", "be", "been",
        "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "can", "to", "of", "in",
        "for", "on", "with", "at", "by", "from", "as", "into", "through",
        "and", "or", "but", "not", "if", "so", "than", "too", "very",
        "just", "about", "up", "it", "its", "i", "me", "my", "we",
        "you", "your", "he", "she", "they", "them", "this", "that",
        "what", "which", "who", "how", "when", "where", "why",
    }
)


def _tokenize(text: str) -> set[str]:
    """Extract keyword tokens from text."""
    return {
        w for w in _TOKEN_RE.findall(text.lower())
        if w not in _STOPWORDS and len(w) > 1
    }


def _score_skill(
    skill: RefinedSkill,
    query_tokens: set[str],
) -> float:
    """Score a skill's relevance to the query.

    Searches across title, domain, subdomains, steps, patterns,
    and embedding_text.  Returns 0.0-1.0.
    """
    searchable = " ".join(filter(None, [
        skill.title or "",
        skill.domain or "",
        " ".join(skill.subdomains or []),
        " ".join(skill.steps or []),
        " ".join(skill.patterns or []),
        skill.embedding_text or "",
    ]))

    skill_tokens = _tokenize(searchable)
    if not skill_tokens or not query_tokens:
        return 0.0

    overlap = len(query_tokens & skill_tokens)
    denom = len(query_tokens) + 0.5 * len(skill_tokens) - 0.5 * overlap
    keyword_score = (overlap / denom) if denom > 0 else 0.0

    # Blend with confidence (skills with higher confidence rank higher)
    confidence = skill.confidence or 0.0
    return 0.7 * min(keyword_score, 1.0) + 0.3 * confidence


async def search_skills(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    query: str,
    domain: str | None = None,
    top_k: int = 5,
    min_maturity: int = MATURITY_TIERS["T2_REFINED"],
) -> list[dict]:
    """Search for relevant skills matching a query.

    Only returns skills at T2_REFINED or above (production-safe).
    Lower-maturity skills are excluded from runtime injection
    per the quarantine protocol.

    Args:
        db: Async database session.
        tenant_id: Tenant UUID.
        query: User's message or intent description.
        domain: Optional domain filter.
        top_k: Maximum skills to return.
        min_maturity: Minimum maturity tier (default T2).

    Returns:
        List of skill dicts sorted by relevance, up to top_k.
    """
    stmt = (
        select(RefinedSkill)
        .where(
            RefinedSkill.tenant_id == tenant_id,
            RefinedSkill.maturity >= min_maturity,
            RefinedSkill.archived_at.is_(None),
        )
    )
    if domain:
        stmt = stmt.where(RefinedSkill.domain == domain)

    result = await db.execute(stmt)
    candidates = list(result.scalars().all())

    if not candidates:
        return []

    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    scored = [
        (skill, _score_skill(skill, query_tokens))
        for skill in candidates
    ]
    scored.sort(key=lambda pair: -pair[1])

    # Filter out zero-relevance skills
    top = [
        (skill, score)
        for skill, score in scored[:top_k]
        if score > 0.01
    ]

    from app.services.skill_refinery.skill_store import SkillStore

    return [
        {**SkillStore._to_dict(skill), "_relevance_score": round(score, 4)}
        for skill, score in top
    ]


def format_evidence_block(skills: list[dict]) -> str:
    """Format retrieved skills as an evidence block for system prompt.

    Follows the format from skill-refinery-spec.md Section 6:
    EVIDENCE-BACKED PATTERNS (from N analyzed sources, avg confidence X.XX):
    - pattern 1
    - pattern 2
    """
    if not skills:
        return ""

    source_count = len(skills)
    avg_confidence = sum(s.get("confidence", 0) for s in skills) / source_count

    lines = []
    for skill in skills:
        for pattern in (skill.get("patterns") or []):
            lines.append(f"- {pattern}")
        for step in (skill.get("steps") or [])[:3]:
            lines.append(f"- {step}")

    if not lines:
        return ""

    header = (
        f"EVIDENCE-BACKED PATTERNS "
        f"(from {source_count} analyzed source{'s' if source_count != 1 else ''}, "
        f"confidence {avg_confidence:.2f}):"
    )

    body = "\n".join(lines)
    footer = "Apply these patterns when evaluating the user's request."
    return f"\n\n{header}\n{body}\n\n{footer}"
