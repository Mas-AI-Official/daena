"""
Daena Council Configuration - Single Source of Truth
Defines the canonical 8 departments × 6 agents structure.
"""

from dataclasses import dataclass
from typing import Dict, List, Literal

# ============================================================================
# CANONICAL COUNCIL STRUCTURE
# ============================================================================

@dataclass(frozen=True)
class CouncilConfig:
    """Canonical council configuration - single source of truth."""
    
    TOTAL_DEPARTMENTS: int = 8
    AGENTS_PER_DEPARTMENT: int = 6
    TOTAL_AGENTS: int = 48
    
    # Department slugs (must be exactly 8)
    DEPARTMENT_SLUGS: tuple = (
        "engineering",
        "product",
        "sales",
        "marketing",
        "finance",
        "hr",
        "legal",
        "customer"
    )
    
    # Department display names
    DEPARTMENT_NAMES: Dict[str, str] = None
    
    # Agent roles (must be exactly 6)
    AGENT_ROLES: tuple = (
        "advisor_a",        # Senior Advisor
        "advisor_b",        # Strategy Advisor
        "scout_internal",   # Internal Scout
        "scout_external",   # External Scout
        "synth",            # Knowledge Synthesizer
        "executor"          # Action Executor
    )
    
    def __post_init__(self):
        """Initialize department names if not provided."""
        if self.DEPARTMENT_NAMES is None:
            object.__setattr__(self, 'DEPARTMENT_NAMES', {
                "engineering": "Engineering & Technology",
                "product": "Product & Innovation",
                "sales": "Sales & Business Development",
                "marketing": "Marketing & Brand",
                "finance": "Finance & Accounting",
                "hr": "Human Resources",
                "legal": "Legal & Compliance",
                "customer": "Customer Success"
            })
    
    def validate_structure(self, departments: int, agents: int, roles_per_dept: int) -> Dict[str, bool]:
        """Validate actual structure against canonical config."""
        return {
            "departments_valid": departments == self.TOTAL_DEPARTMENTS,
            "agents_valid": agents == self.TOTAL_AGENTS,
            "roles_valid": roles_per_dept == self.AGENTS_PER_DEPARTMENT,
            "structure_valid": (
                departments == self.TOTAL_DEPARTMENTS and
                agents == self.TOTAL_AGENTS and
                roles_per_dept == self.AGENTS_PER_DEPARTMENT
            )
        }
    
    def get_expected_counts(self) -> Dict[str, int]:
        """Get expected counts for validation."""
        return {
            "departments": self.TOTAL_DEPARTMENTS,
            "agents": self.TOTAL_AGENTS,
            "roles_per_department": self.AGENTS_PER_DEPARTMENT
        }


# Global singleton instance
COUNCIL_CONFIG = CouncilConfig()


# ============================================================================
# TYPE DEFINITIONS (for Pydantic/TypeScript generation)
# ============================================================================

DepartmentSlug = Literal[
    "engineering", "product", "sales", "marketing",
    "finance", "hr", "legal", "customer"
]

AgentRole = Literal[
    "advisor_a", "advisor_b",
    "scout_internal", "scout_external",
    "synth", "executor"
]


# ============================================================================
# EXPORT COMPATIBILITY (for existing code)
# ============================================================================

# For backward compatibility with constants.py
DEPARTMENT_NAMES = list(COUNCIL_CONFIG.DEPARTMENT_SLUGS)
DEPARTMENT_DISPLAY_NAMES = COUNCIL_CONFIG.DEPARTMENT_NAMES
AGENT_ROLES = list(COUNCIL_CONFIG.AGENT_ROLES)
MAX_AGENTS_PER_DEPARTMENT = COUNCIL_CONFIG.AGENTS_PER_DEPARTMENT
TOTAL_DEPARTMENTS = COUNCIL_CONFIG.TOTAL_DEPARTMENTS
MAX_TOTAL_AGENTS = COUNCIL_CONFIG.TOTAL_AGENTS

