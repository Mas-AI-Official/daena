# Routes package initialization
# Consolidated 2026-02-04

__all__ = [
    "agents",
    "departments", 
    "projects",
    "daena",
    "agent_builder",
    "cmp_voting",
    "councils",
    "honey_knowledge",
    "voice_service",
    "founder_panel",
    "task_timeline",
    "consultation",
    "monitoring",
    "data_sources",
    "workflows",
    "security",
    "users",
    "tasks",
    "notifications",
    "health",
    "model_registry",
    "brain"
]

# Note: Individual routers should be imported in main.py using safe_import_router
# to handle potential missing dependencies gracefully.
