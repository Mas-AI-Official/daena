"""Swarm orchestration: task decomposition and parallel execution.

The SwarmPlanner decomposes complex tasks into subtasks with typed
dependencies, routes each to the optimal runtime via the Mind Selection
Engine, and estimates costs. The SwarmExecutor runs independent subtasks
in parallel respecting the dependency DAG, with fallback and governance.
"""

from app.services.swarm.executor import SwarmExecutor
from app.services.swarm.planner import SubTask, SwarmPlanner

__all__ = ["SubTask", "SwarmPlanner", "SwarmExecutor"]
