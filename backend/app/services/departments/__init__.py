"""Department runtime layer.

DepartmentAgent wraps a department with its runtime context (working
directory, permitted paths, memory scope, governance policy, skill
priors) and exposes the six conceptual roles (MIND, EYES, HANDS, VOICE,
SHIELD, MEMORY) as methods on a single agent object.

The roles are FACETS of one department, not six separate runtime
processes. The physical action tools (File, Terminal, Browser, MCP,
VisionBrowser, WebCrawler, VulnScanner) live in a shared singleton pool
under ``app.services.daenabot`` and are called by every department
with department-scoped context.

See ``docs/ARCHITECTURE.md`` Section 11 for the Mythos-gap plan and
the operator-mandated architecture: 10 departments + 1 shared DaenaBot
pool + 1 shared NBMF memory, with the 6 roles as methods not processes.
"""

from app.services.departments.department_agent import (
    DepartmentAgent,
    DepartmentContext,
    SecurityLens,
)

__all__ = ["DepartmentAgent", "DepartmentContext", "SecurityLens"]
