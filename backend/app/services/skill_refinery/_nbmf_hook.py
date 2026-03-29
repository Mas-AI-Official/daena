"""NBMF hook for skill refinement outcome tracking.

Records skill refinement results (approve, reject, confidence) as agent
experiences in quarantine. Over time, the promotion pipeline validates
which refinement patterns are reliable.

IMPORTANT: This stores SKILL OUTCOMES (what was refined, verdict,
confidence), never user content or tenant data.
"""

from __future__ import annotations

from app.core.logging import get_logger

logger = get_logger(__name__)


async def record_skill_outcome(
    draft_skill: dict,
    result: dict,
) -> None:
    """Write a SKILL_OUTCOME experience to NBMF (fire-and-forget).

    This is called from refine_skill() after the 3-pass pipeline
    completes. It stores the refinement decision (not the skill content).

    Args:
        draft_skill: Original skill dict before refinement.
        result: Refinement result with verdict and confidence.
    """
    # Lazy import to avoid circular dependency at module load
    from app.core.database import async_session_factory

    skill_id = draft_skill.get("skill_id") or draft_skill.get("name", "unknown")
    domain = draft_skill.get("domain", "general")
    verdict = result.get("critic_verdict", {}).get("verdict", "UNKNOWN")
    confidence = result.get("confidence", 0.0)
    success = verdict in ("APPROVE", "NEEDS_WORK")

    content = (
        f"Skill: {skill_id}\n"
        f"Domain: {domain}\n"
        f"Verdict: {verdict}\n"
        f"Confidence: {confidence}\n"
        f"Gaps found: {bool(result.get('gap_report'))}\n"
        f"Improvements applied: {bool(result.get('improvements'))}"
    )
    summary = f"Refined '{skill_id}' ({domain}): {verdict} @ {confidence:.2f}"

    try:
        async with async_session_factory() as db:
            from app.services.memory import MemoryService

            mem = MemoryService(db)

            # Need tenant_id and user_id. Skills are tenant-scoped.
            # Use the skill's tenant_id if available, otherwise skip.
            tenant_id = draft_skill.get("tenant_id")
            if not tenant_id:
                logger.debug("nbmf_hook.no_tenant_id, skipping experience write")
                return

            from uuid import UUID
            tid = UUID(str(tenant_id))

            await mem.store_experience(
                tenant_id=tid,
                user_id=tid,  # system action, use tenant as actor
                agent_id=tid,  # skill governance department
                content=content,
                content_type="SKILL_OUTCOME",
                summary=summary,
                skill_id=str(skill_id),
                success_flag=success,
                confidence=float(confidence),
                tags=["skill_refinery", domain, verdict.lower()],
                metadata={
                    "verdict": verdict,
                    "gap_report_present": bool(result.get("gap_report")),
                },
            )
            await db.commit()
            logger.info(
                "nbmf_hook.skill_outcome_recorded",
                skill_id=skill_id,
                verdict=verdict,
            )
    except Exception:
        logger.debug("nbmf_hook.write_failed", exc_info=True)
