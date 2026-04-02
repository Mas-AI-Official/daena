"""Claude Code Orchestration Skill: teaches Daena how to use Claude Code
as the brain that orchestrates all other runtimes in parallel.

This skill encodes the knowledge of:
- How to spawn parallel Claude Code subagents
- How to delegate tasks across runtimes (Codex, Gemini CLI, Ollama)
- How to use Agent Teams for multi-agent coordination
- How to use the GSD framework for structured execution
- How to chain tools for complex multi-step operations

Daena uses this skill when:
- A task requires multiple runtimes working in parallel
- The task is complex enough to benefit from decomposition
- AGI mode is active and the heartbeat needs to execute work
- The user asks for something that spans multiple domains

BACKGROUND PATH ONLY -- orchestration planning uses LLM calls
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


# ── Runtime Capability Matrix ──
# Each runtime has strengths. The orchestrator assigns subtasks
# to the runtime best suited for each task type.

RUNTIME_CAPABILITIES: dict[str, dict[str, float]] = {
    "claude_code": {
        "complex_reasoning": 1.0,
        "code_generation": 0.95,
        "code_review": 0.95,
        "architecture": 1.0,
        "file_operations": 0.9,
        "git_operations": 0.95,
        "multi_step_planning": 1.0,
        "debugging": 0.95,
        "testing": 0.9,
        "documentation": 0.9,
    },
    "codex": {
        "code_generation": 1.0,
        "code_execution": 1.0,
        "sandbox_execution": 1.0,
        "file_operations": 0.95,
        "testing": 0.95,
        "debugging": 0.9,
        "complex_reasoning": 0.8,
    },
    "gemini_cli": {
        "web_research": 1.0,
        "deep_research": 1.0,
        "document_analysis": 0.95,
        "summarization": 0.95,
        "multi_modal": 0.9,
        "complex_reasoning": 0.85,
        "code_generation": 0.8,
    },
    "ollama": {
        "fast_response": 1.0,
        "cheap_tasks": 1.0,
        "simple_reasoning": 0.9,
        "code_generation": 0.7,
        "classification": 0.85,
        "summarization": 0.8,
    },
}

# ── Parallel Execution Patterns ──

@dataclass
class OrchestratedTask:
    """A task decomposed for multi-runtime parallel execution."""
    id: str
    description: str
    task_type: str
    assigned_runtime: str
    fallback_runtime: str = "ollama"
    priority: int = 1  # 1=highest
    dependencies: list[str] = field(default_factory=list)
    result: str = ""
    status: str = "pending"


def select_best_runtime(
    task_type: str,
    available_runtimes: list[str],
) -> str:
    """Select the best runtime for a task type based on capability scores.

    Args:
        task_type: Type of task (e.g., "code_generation", "web_research")
        available_runtimes: List of runtime IDs that are currently online

    Returns:
        Runtime ID of the best match
    """
    best_runtime = "ollama"  # Default fallback
    best_score = 0.0

    for rid in available_runtimes:
        caps = RUNTIME_CAPABILITIES.get(rid, {})
        score = caps.get(task_type, 0.0)
        if score > best_score:
            best_score = score
            best_runtime = rid

    return best_runtime


def decompose_for_parallel_execution(
    task: str,
    available_runtimes: list[str],
) -> list[OrchestratedTask]:
    """Decompose a complex task into subtasks for parallel execution.

    Uses keyword analysis to identify subtask types, then assigns
    each to the optimal runtime.

    This is a deterministic fast-path. For LLM-based decomposition,
    use SwarmPlanner instead.
    """
    import uuid

    subtasks: list[OrchestratedTask] = []

    # Keyword-based task type detection
    task_lower = task.lower()

    # Research subtask
    if any(kw in task_lower for kw in ["research", "find", "search", "look up", "investigate", "study"]):
        subtasks.append(OrchestratedTask(
            id=str(uuid.uuid4())[:8],
            description=f"Research: {task[:200]}",
            task_type="web_research",
            assigned_runtime=select_best_runtime("web_research", available_runtimes),
            priority=1,
        ))

    # Code generation subtask
    if any(kw in task_lower for kw in ["code", "implement", "build", "create", "write", "fix", "debug"]):
        subtasks.append(OrchestratedTask(
            id=str(uuid.uuid4())[:8],
            description=f"Implement: {task[:200]}",
            task_type="code_generation",
            assigned_runtime=select_best_runtime("code_generation", available_runtimes),
            priority=2,
        ))

    # Testing subtask
    if any(kw in task_lower for kw in ["test", "verify", "validate", "check"]):
        subtasks.append(OrchestratedTask(
            id=str(uuid.uuid4())[:8],
            description=f"Test: {task[:200]}",
            task_type="testing",
            assigned_runtime=select_best_runtime("testing", available_runtimes),
            priority=3,
        ))

    # Documentation subtask
    if any(kw in task_lower for kw in ["document", "readme", "update docs", "write docs"]):
        subtasks.append(OrchestratedTask(
            id=str(uuid.uuid4())[:8],
            description=f"Document: {task[:200]}",
            task_type="documentation",
            assigned_runtime=select_best_runtime("documentation", available_runtimes),
            priority=3,
        ))

    # If no specific subtasks detected, use primary runtime for everything
    if not subtasks:
        subtasks.append(OrchestratedTask(
            id=str(uuid.uuid4())[:8],
            description=task[:200],
            task_type="complex_reasoning",
            assigned_runtime=select_best_runtime("complex_reasoning", available_runtimes),
            priority=1,
        ))

    return subtasks


# ── Claude Code Feature Catalog ──
# These are the known capabilities that Daena can invoke via Claude Code.

CLAUDE_CODE_FEATURES = {
    "subagents": {
        "description": "Spawn child Claude instances for parallel work",
        "how": "The Agent tool in Claude Code spawns a subagent with its own context window",
        "daena_use": "SwarmExecutor uses this to run subtasks in parallel",
    },
    "agent_teams": {
        "description": "2-16 agents sharing a codebase with git coordination",
        "how": "Environment variable CLAUDE_CODE_AGENT_TEAMS=1",
        "daena_use": "Could coordinate multiple runtimes on a shared project",
    },
    "gsd_framework": {
        "description": "Get Shit Done: 33 commands for planning/execution",
        "how": "/gsd:plan-phase, /gsd:execute-phase, /gsd:debug",
        "daena_use": "Structured task execution with verification",
    },
    "ultraplan": {
        "description": "Remote long-horizon planning with 30-min think time",
        "how": "Offloads planning to a Cloud Container Runtime session",
        "daena_use": "Background path for complex architectural decisions",
    },
    "auto_mode": {
        "description": "LLM classifier auto-approves low-risk actions",
        "how": "--permission-mode auto",
        "daena_use": "Maps directly to Daena's CriticalityClassifier",
    },
    "dangerously_skip_permissions": {
        "description": "Bypass all permission prompts (sandbox only)",
        "how": "--dangerously-skip-permissions flag",
        "daena_use": "Used by ClaudeSession when AGI mode is active",
    },
    "coordinator_mode": {
        "description": "Transforms Claude Code into a multi-agent coordinator",
        "how": "CLAUDE_CODE_COORDINATOR_MODE=1 (unreleased)",
        "daena_use": "When available, could replace SwarmExecutor for Claude-native orchestration",
    },
    "oh_my_claudecode_ultrapilot": {
        "description": "3-5 parallel Claude Code instances in isolated git worktrees",
        "how": "Plugin: oh-my-claudecode, mode: ultrapilot",
        "daena_use": "Massively parallel code generation for multi-file changes",
    },
}


def get_orchestration_system_prompt(
    available_runtimes: list[str],
    agi_mode: bool = False,
) -> str:
    """Build a system prompt that teaches the LLM how to orchestrate runtimes.

    Injected into the chat orchestrator when the task is complex and
    multiple runtimes are available.
    """
    runtime_list = "\n".join(
        f"  - {rid}: best at {', '.join(k for k, v in RUNTIME_CAPABILITIES.get(rid, {}).items() if v >= 0.9)}"
        for rid in available_runtimes
    )

    return f"""You are orchestrating multiple AI runtimes in parallel.

AVAILABLE RUNTIMES:
{runtime_list}

ORCHESTRATION RULES:
1. Break complex tasks into subtasks that can run in parallel
2. Assign each subtask to the runtime best suited for it
3. Claude Code handles: complex reasoning, architecture, multi-step planning
4. Codex handles: code execution, sandboxed testing
5. Gemini CLI handles: deep research, web search, document analysis
6. Ollama handles: fast/cheap tasks, classification, simple queries
7. When a runtime fails, automatically retry with the next best runtime
8. Never wait for one subtask when another can proceed independently
9. Combine results from all runtimes into a unified response
{"10. AGI MODE ACTIVE: Execute all non-critical actions autonomously. Only pause for Hard Law violations." if agi_mode else ""}

PARALLEL EXECUTION PATTERN:
- Identify independent subtasks that can run simultaneously
- Assign each to the optimal runtime
- Wait for all to complete (or timeout)
- Synthesize results into a single coherent response
"""
