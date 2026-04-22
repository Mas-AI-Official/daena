"""Soul Maker: self-evolving personas for Daena's 10 Department Minds.

Parallel to SkillRefinery but operates on Department Soul files. Runs a
3-pass pipeline (gap finder / improver / critic), optionally fed by a
web-research pass for the domain so souls stay current as the AI field
moves. Founder approval is required before any proposed soul revision
overwrites the live file (T3 promotion governance).
"""

from app.services.soul_maker.refinement import (
    SoulRefinementResult,
    refine_department_soul,
)
from app.services.soul_maker.research import fetch_domain_best_practices
from app.services.soul_maker.store import (
    approve_proposal,
    get_proposal,
    list_proposals,
    reject_proposal,
)

__all__ = [
    "SoulRefinementResult",
    "approve_proposal",
    "fetch_domain_best_practices",
    "get_proposal",
    "list_proposals",
    "refine_department_soul",
    "reject_proposal",
]
