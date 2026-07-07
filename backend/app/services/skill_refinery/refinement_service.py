"""Refinement service: 3-pass pipeline (gap finder, improver, critic).

Takes a T1_DRAFT skill and runs three sequential LLM passes:
    Pass 1 - Gap Finder: identifies missing steps, outdated info
    Pass 2 - Improver: proposes fixes, modern alternatives
    Pass 3 - Critic: validates improvements, assigns confidence

Output: refined skill at T2_REFINED maturity with confidence score.
Each pass calls Ollama directly (Phase 2 constraint).

Circuit breaker: semaphore limits concurrency, emergency stop halts
all running refinements, daily cost tracker enforces token budget.
"""

from __future__ import annotations

import asyncio
import json
from datetime import date
from pathlib import Path

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Circuit breaker constants ──

REFINEMENT_TIMEOUT = 60  # seconds max per individual LLM pass
MAX_TOKENS_PER_PASS = 2000
MAX_CONCURRENT_REFINEMENTS = 3

_refinement_semaphore = asyncio.Semaphore(MAX_CONCURRENT_REFINEMENTS)
_emergency_stop = asyncio.Event()  # Set to stop all running refinements

# ── Daily cost tracking ──
#
# Persisted to disk so the daily budget survives process restarts; an
# in-memory-only counter resets to zero on every restart and silently
# defeats the circuit breaker. Fail-open: persistence errors are logged
# (Rule 17) but never block refinement.

DAILY_REFINEMENT_TOKEN_LIMIT = 100_000  # tokens per day
_COST_RETENTION_DAYS = 7
_COST_FILE = (
    Path(__file__).resolve().parents[3] / "var" / "skill_refinery" / "daily_cost.json"
)


def _load_daily_cost() -> dict[str, float]:
    """Load the persisted daily cost map, empty on first run or error."""
    try:
        raw = json.loads(_COST_FILE.read_text(encoding="utf-8"))
        return {str(k): float(v) for k, v in raw.items()}
    except FileNotFoundError:
        return {}
    except Exception as exc:
        logger.warning("refinement.daily_cost_load_failed", error=str(exc))
        return {}


def _save_daily_cost() -> None:
    """Persist the daily cost map atomically (tmp write + replace)."""
    try:
        _COST_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = _COST_FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(_daily_cost), encoding="utf-8")
        tmp.replace(_COST_FILE)
    except Exception as exc:
        logger.warning("refinement.daily_cost_save_failed", error=str(exc))


_daily_cost: dict[str, float] = _load_daily_cost()  # key: "YYYY-MM-DD", value: estimated tokens


def _track_cost(tokens: int) -> None:
    """Track daily refinement token usage and persist it."""
    today = date.today().isoformat()
    _daily_cost[today] = _daily_cost.get(today, 0) + tokens
    if len(_daily_cost) > _COST_RETENTION_DAYS:
        for key in sorted(_daily_cost)[:-_COST_RETENTION_DAYS]:
            del _daily_cost[key]
    _save_daily_cost()


def get_daily_cost() -> dict:
    """Get today's refinement cost stats."""
    today = date.today().isoformat()
    used = _daily_cost.get(today, 0)
    return {
        "date": today,
        "tokens_used": used,
        "limit": DAILY_REFINEMENT_TOKEN_LIMIT,
        "remaining": max(0, DAILY_REFINEMENT_TOKEN_LIMIT - used),
        "paused": used >= DAILY_REFINEMENT_TOKEN_LIMIT,
    }


# ── Emergency stop controls ──


def trigger_emergency_stop() -> None:
    """Set the emergency stop flag to abort all running refinements."""
    _emergency_stop.set()
    logger.warning("refinement.emergency_stop_triggered")


def clear_emergency_stop() -> None:
    """Clear the emergency stop flag to resume refinements."""
    _emergency_stop.clear()
    logger.info("refinement.emergency_stop_cleared")


def is_emergency_stopped() -> bool:
    """Check if emergency stop is active."""
    return _emergency_stop.is_set()


# ── Prompt templates ──


_GAP_FINDER_PROMPT = """\
You are a skill quality auditor for the Daena platform.

Analyze the following skill and identify gaps, missing steps,
outdated information, and vague instructions.

SKILL TO AUDIT:
{skill_json}

Respond with a JSON object:
{{
  "missing_steps": ["step that should exist but doesn't"],
  "outdated_items": ["anything that references old tools/versions"],
  "vague_items": ["instructions that are too vague to follow"],
  "assumptions": ["things the skill assumes the user already knows"],
  "overall_quality": "LOW" or "MEDIUM" or "HIGH"
}}

Respond with ONLY the JSON. No explanation."""


_IMPROVER_PROMPT = """\
You are a skill improvement specialist for the Daena platform.

Given the original skill and the gap report, produce an improved
version of the skill with all gaps addressed.

ORIGINAL SKILL:
{skill_json}

GAP REPORT:
{gap_report}

Respond with a JSON object containing the improved skill:
{{
  "steps": ["improved ordered steps"],
  "patterns": ["updated patterns and best practices"],
  "anti_patterns": ["updated things to avoid"],
  "failure_modes": ["updated failure modes"],
  "improvements_by_daena": ["list of what you changed and why"]
}}

Respond with ONLY the JSON. No explanation."""


_CRITIC_PROMPT = """\
You are a skill validation critic for the Daena platform.

Compare the improved skill against the original and assess whether
the improvements are genuine, accurate, and reliable.

ORIGINAL SKILL:
{original_json}

IMPROVED SKILL:
{improved_json}

Evaluate and respond with a JSON object:
{{
  "is_better": true or false,
  "hallucinated_steps": ["any steps that seem fabricated"],
  "conflicts": ["any conflicts with known best practices"],
  "confidence": 0.0 to 1.0 (overall reliability of the improved skill),
  "verdict": "APPROVE" or "NEEDS_WORK" or "REJECT",
  "notes": "brief explanation"
}}

Respond with ONLY the JSON. No explanation."""


async def _call_llm(prompt: str) -> str:
    """Call Ollama's chat endpoint for a refinement pass.

    Enforces per-call timeout, emergency stop check, and daily
    token budget tracking.
    """
    if _emergency_stop.is_set():
        logger.warning("refinement.emergency_stop_active")
        return ""

    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            coro = client.post(
                f"{settings.ollama_base_url}/api/chat",
                json={
                    "model": settings.ollama_default_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {"temperature": 0.3, "num_predict": MAX_TOKENS_PER_PASS},
                },
            )
            resp = await asyncio.wait_for(coro, timeout=REFINEMENT_TIMEOUT)
            resp.raise_for_status()
            result = resp.json().get("message", {}).get("content", "")

            # Track cost
            _track_cost(len(result) // 4)  # rough token estimate

            # Check daily limit
            today = date.today().isoformat()
            if _daily_cost.get(today, 0) >= DAILY_REFINEMENT_TOKEN_LIMIT:
                logger.warning("refinement.daily_limit_reached")

            return result
    except TimeoutError:
        logger.error("refinement.llm_timeout", timeout=REFINEMENT_TIMEOUT)
        return ""
    except Exception as exc:
        logger.error("refinement.llm_call_failed", error=str(exc))
        return ""


def _parse_json(text: str) -> dict:
    """Parse JSON from LLM response, handling markdown fences."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("refinement.json_parse_failed", preview=text[:200])
        return {}


def _skill_to_json_str(skill: dict) -> str:
    """Serialize a skill dict to compact JSON for prompt injection."""
    subset = {
        k: skill.get(k)
        for k in (
            "title", "domain", "subdomains", "steps", "patterns",
            "anti_patterns", "failure_modes", "confidence",
        )
        if skill.get(k)
    }
    return json.dumps(subset, indent=2)


async def refine_skill(draft_skill: dict) -> dict:
    """Run the 3-pass refinement pipeline on a draft skill.

    Uses a semaphore to limit concurrent refinements and checks
    the emergency stop flag between passes.

    Args:
        draft_skill: Skill dict (from SkillStore._to_dict).

    Returns:
        Dict with:
            refined: updated skill fields (steps, patterns, etc.)
            gap_report: output from Pass 1
            improvements: output from Pass 2
            critic_verdict: output from Pass 3
            confidence: final confidence score
    """
    async with _refinement_semaphore:
        skill_json = _skill_to_json_str(draft_skill)

        # ── Pass 1: Gap Finder ──
        logger.info("refinement.pass1_gap_finder", skill_id=draft_skill.get("skill_id"))
        gap_prompt = _GAP_FINDER_PROMPT.format(skill_json=skill_json)
        gap_raw = await _call_llm(gap_prompt)
        gap_report = _parse_json(gap_raw)

        if not gap_report:
            return {
                "refined": draft_skill,
                "gap_report": {},
                "improvements": {},
                "critic_verdict": {
                    "verdict": "REJECT", "confidence": 0.0,
                    "notes": "Gap finder returned no output",
                },
                "confidence": 0.0,
            }

        # Check emergency stop between passes
        if _emergency_stop.is_set():
            logger.warning(
                "refinement.aborted_between_passes",
                skill_id=draft_skill.get("skill_id"),
                after_pass=1,
            )
            return {
                "refined": draft_skill,
                "gap_report": gap_report,
                "improvements": {},
                "critic_verdict": {
                    "verdict": "REJECT", "confidence": 0.0,
                    "notes": "Emergency stop: aborted after Pass 1",
                },
                "confidence": 0.0,
            }

        # ── Pass 2: Improver ──
        logger.info("refinement.pass2_improver", skill_id=draft_skill.get("skill_id"))
        improve_prompt = _IMPROVER_PROMPT.format(
            skill_json=skill_json,
            gap_report=json.dumps(gap_report, indent=2),
        )
        improve_raw = await _call_llm(improve_prompt)
        improvements = _parse_json(improve_raw)

        if not improvements:
            return {
                "refined": draft_skill,
                "gap_report": gap_report,
                "improvements": {},
                "critic_verdict": {
                    "verdict": "REJECT", "confidence": 0.0,
                    "notes": "Improver returned no output",
                },
                "confidence": 0.0,
            }

        # Check emergency stop between passes
        if _emergency_stop.is_set():
            logger.warning(
                "refinement.aborted_between_passes",
                skill_id=draft_skill.get("skill_id"),
                after_pass=2,
            )
            return {
                "refined": draft_skill,
                "gap_report": gap_report,
                "improvements": improvements,
                "critic_verdict": {
                    "verdict": "REJECT", "confidence": 0.0,
                    "notes": "Emergency stop: aborted after Pass 2",
                },
                "confidence": 0.0,
            }

        # ── Pass 3: Critic ──
        logger.info("refinement.pass3_critic", skill_id=draft_skill.get("skill_id"))
        improved_skill = {**draft_skill, **improvements}
        critic_prompt = _CRITIC_PROMPT.format(
            original_json=skill_json,
            improved_json=_skill_to_json_str(improved_skill),
        )
        critic_raw = await _call_llm(critic_prompt)
        critic_verdict = _parse_json(critic_raw)

        import contextlib

        confidence = 0.0
        with contextlib.suppress(TypeError, ValueError):
            confidence = max(0.0, min(1.0, float(critic_verdict.get("confidence", 0.0))))

        # Build final refined skill
        refined = dict(draft_skill)
        if critic_verdict.get("verdict") in ("APPROVE", "NEEDS_WORK"):
            refined["steps"] = improvements.get(
                "steps", draft_skill.get("steps", []),
            )
            refined["patterns"] = improvements.get(
                "patterns", draft_skill.get("patterns", []),
            )
            refined["anti_patterns"] = improvements.get(
                "anti_patterns", draft_skill.get("anti_patterns", []),
            )
            refined["failure_modes"] = improvements.get(
                "failure_modes", draft_skill.get("failure_modes", []),
            )
            refined["improvements_by_daena"] = improvements.get(
                "improvements_by_daena", [],
            )
            refined["confidence"] = confidence

        logger.info(
            "refinement.complete",
            skill_id=draft_skill.get("skill_id"),
            verdict=critic_verdict.get("verdict", "UNKNOWN"),
            confidence=confidence,
        )

        result = {
            "refined": refined,
            "gap_report": gap_report,
            "improvements": improvements,
            "critic_verdict": critic_verdict,
            "confidence": confidence,
        }

        # ── NBMF: record skill refinement outcome as experience ──
        # This runs fire-and-forget; failures are logged, not raised.
        try:
            from app.services.skill_refinery._nbmf_hook import record_skill_outcome
            await record_skill_outcome(draft_skill, result)
        except Exception:
            logger.debug("refinement.nbmf_hook_failed", exc_info=True)

        return result
