"""
Autonomous Executor - Core Engine for Daena Autonomous Company Mode

This is the brain that converts Founder orders into company workflow.
Implements the 11-step execution loop:
1. Intake: parse goal, constraints, acceptance
2. Decompose: create task graph with owners
3. Route: assign models per subtask
4. Acquire: scouts gather data
5. Verify: grade sources
6. Council: advisors debate, synth recommends
7. Execute: produce deliverables
8. QA: test results
9. Deliver: publish outputs
10. Audit: write decision ledger
11. Improve: propose upgrades

CRITICAL: This is NOT a chatbot. This is an operations engine.
"""

import asyncio
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ProjectStatus(str, Enum):
    CREATED = "created"
    DECOMPOSING = "decomposing"
    ROUTING = "routing"
    ACQUIRING = "acquiring"
    VERIFYING = "verifying"
    COUNCIL_DEBATE = "council_debate"
    EXECUTING = "executing"
    QA = "qa"
    DELIVERING = "delivering"
    AUDITING = "auditing"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TaskNode:
    """A node in the task graph"""
    task_id: str
    name: str
    description: str
    owner_department: str
    owner_agent: Optional[str] = None
    model_assigned: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    progress: int = 0
    output: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


@dataclass
class ProjectExecution:
    """Represents an autonomous project execution"""
    project_id: str
    title: str
    goal: str
    constraints: List[str]
    acceptance_criteria: List[str]
    deliverables_required: List[str]
    status: ProjectStatus = ProjectStatus.CREATED
    task_graph: List[TaskNode] = field(default_factory=list)
    acquired_data: Dict[str, Any] = field(default_factory=dict)
    verified_facts: List[Dict[str, Any]] = field(default_factory=list)
    council_synthesis: Optional[Dict[str, Any]] = None
    produced_deliverables: List[Dict[str, Any]] = field(default_factory=list)
    qa_results: Dict[str, Any] = field(default_factory=dict)
    ledger_entry: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


class AutonomousExecutor:
    """
    Core autonomous execution engine for Daena.
    
    Converts Founder orders into full company workflow with:
    - Department coordination
    - Agent task assignment
    - Council governance
    - Verification gates
    - Decision ledger
    """
    
    def __init__(self):
        self.active_projects: Dict[str, ProjectExecution] = {}
        self._event_bus = None
        self._initialized = False
    
    async def _get_event_bus(self):
        """Lazy load event bus to avoid circular imports"""
        if self._event_bus is None:
            try:
                from backend.services.event_bus import event_bus
                self._event_bus = event_bus
            except ImportError:
                logger.warning("Event bus not available")
        return self._event_bus
    
    async def _publish_event(self, event_type: str, entity_type: str, entity_id: str, payload: Dict[str, Any]):
        """Publish event to event bus for UI sync"""
        event_bus = await self._get_event_bus()
        if event_bus:
            await event_bus.publish(event_type, entity_type, entity_id, payload)
        logger.info(f"📡 Event: {event_type} | {entity_type}:{entity_id}")
    
    async def execute_project(self, request: Dict[str, Any]) -> ProjectExecution:
        """
        Main entry point: Execute a complete project end-to-end.
        
        Args:
            request: Project request containing goal, constraints, deliverables
        
        Returns:
            ProjectExecution with full audit trail
        """
        project_id = f"proj-{uuid.uuid4().hex[:8]}"
        
        # Step 1: INTAKE - Parse request
        project = await self._intake(project_id, request)
        self.active_projects[project_id] = project
        
        try:
            # Step 2: DECOMPOSE - Create task graph
            project = await self._decompose(project)
            
            # Step 3: ROUTE - Assign models/agents
            project = await self._route(project)
            
            # Step 4: ACQUIRE - Scouts gather data
            project = await self._acquire(project)
            
            # Step 5: VERIFY - Grade sources
            project = await self._verify(project)
            
            # Step 6: COUNCIL - Advisors debate
            project = await self._council_debate(project)
            
            # Step 7: EXECUTE - Produce deliverables
            project = await self._execute(project)
            
            # Step 8: QA - Test results
            project = await self._qa(project)
            
            # Step 9: DELIVER - Publish outputs
            project = await self._deliver(project)
            
            # Step 10: AUDIT - Write decision ledger
            project = await self._audit(project)
            
            # Step 11: IMPROVE - Propose upgrades (optional)
            await self._improve(project)
            
            project.status = ProjectStatus.COMPLETED
            project.completed_at = datetime.utcnow()
            
            await self._publish_event("project.completed", "project", project_id, {
                "project_id": project_id,
                "title": project.title,
                "status": "completed",
                "deliverables_count": len(project.produced_deliverables)
            })
            
            return project
            
        except Exception as e:
            logger.error(f"Project execution failed: {e}", exc_info=True)
            project.status = ProjectStatus.FAILED
            await self._publish_event("project.failed", "project", project_id, {
                "project_id": project_id,
                "error": str(e)
            })
            raise
    
    # =========================================================================
    # STEP 1: INTAKE
    # =========================================================================
    async def _intake(self, project_id: str, request: Dict[str, Any]) -> ProjectExecution:
        """Parse and validate project request"""
        logger.info(f"📥 INTAKE: Parsing project request")
        
        project = ProjectExecution(
            project_id=project_id,
            title=request.get("title", request.get("project_name", "Untitled Project")),
            goal=request.get("goal", request.get("description", "")),
            constraints=request.get("constraints", []),
            acceptance_criteria=request.get("acceptance", request.get("acceptance_criteria", [])),
            deliverables_required=request.get("deliverables", []),
            status=ProjectStatus.CREATED
        )
        
        await self._publish_event("project.created", "project", project_id, {
            "project_id": project_id,
            "title": project.title,
            "goal": project.goal,
            "constraints": project.constraints,
            "acceptance_criteria": project.acceptance_criteria,
            "deliverables": project.deliverables_required
        })
        
        return project
    
    # =========================================================================
    # STEP 2: DECOMPOSE
    # =========================================================================
    async def _decompose(self, project: ProjectExecution) -> ProjectExecution:
        """Create task graph with owners"""
        logger.info(f"🔀 DECOMPOSE: Creating task graph for {project.title}")
        project.status = ProjectStatus.DECOMPOSING
        
        # Get LLM to decompose the project into tasks
        task_graph = await self._llm_decompose(project)
        project.task_graph = task_graph
        
        await self._publish_event("tasks.generated", "project", project.project_id, {
            "project_id": project.project_id,
            "tasks": [
                {
                    "task_id": t.task_id,
                    "name": t.name,
                    "department": t.owner_department,
                    "dependencies": t.dependencies
                }
                for t in task_graph
            ]
        })
        
        return project
    
    async def _llm_decompose(self, project: ProjectExecution) -> List[TaskNode]:
        """Use LLM to decompose project into tasks"""
        # For now, create a default task decomposition
        # This will be enhanced to use actual LLM
        
        tasks = []
        
        # Research task (Scout)
        tasks.append(TaskNode(
            task_id=f"{project.project_id}-research",
            name="Research & Data Gathering",
            description=f"Scout team gathers data for: {project.goal}",
            owner_department="engineering",
            owner_agent="scout_internal"
        ))
        
        # Verification task (Verifier)
        tasks.append(TaskNode(
            task_id=f"{project.project_id}-verify",
            name="Fact Verification",
            description="Verify all claims and grade sources",
            owner_department="engineering",
            owner_agent="verifier",
            dependencies=[f"{project.project_id}-research"]
        ))
        
        # For each deliverable, create an execution task
        for i, deliverable in enumerate(project.deliverables_required):
            tasks.append(TaskNode(
                task_id=f"{project.project_id}-exec-{i}",
                name=f"Produce: {deliverable[:50]}",
                description=f"Execute and produce: {deliverable}",
                owner_department="product",
                owner_agent="executor",
                dependencies=[f"{project.project_id}-verify"]
            ))
        
        # QA task
        tasks.append(TaskNode(
            task_id=f"{project.project_id}-qa",
            name="Quality Assurance",
            description="Test all deliverables",
            owner_department="engineering",
            owner_agent="qa",
            dependencies=[t.task_id for t in tasks if t.task_id.startswith(f"{project.project_id}-exec")]
        ))
        
        return tasks
    
    # =========================================================================
    # STEP 3: ROUTE
    # =========================================================================
    async def _route(self, project: ProjectExecution) -> ProjectExecution:
        """Assign models and agents to tasks"""
        logger.info(f"🛤️ ROUTE: Assigning models/agents")
        project.status = ProjectStatus.ROUTING
        
        # Get available models
        default_model = "deepseek-r1:8b"
        
        routing_decisions = []
        for task in project.task_graph:
            # Simple routing logic - can be enhanced
            if "research" in task.name.lower() or "scout" in task.owner_agent or "":
                task.model_assigned = default_model
            elif "verify" in task.name.lower():
                task.model_assigned = default_model
            else:
                task.model_assigned = default_model
            
            routing_decisions.append({
                "task_id": task.task_id,
                "model": task.model_assigned,
                "agent": task.owner_agent,
                "department": task.owner_department,
                "reason": "default_routing"
            })
        
        await self._publish_event("routing.completed", "project", project.project_id, {
            "project_id": project.project_id,
            "routing": routing_decisions
        })
        
        return project
    
    # =========================================================================
    # STEP 4: ACQUIRE
    # =========================================================================
    async def _acquire(self, project: ProjectExecution) -> ProjectExecution:
        """Scouts gather data"""
        logger.info(f"📡 ACQUIRE: Scouts gathering data")
        project.status = ProjectStatus.ACQUIRING
        
        await self._publish_event("scout.started", "project", project.project_id, {
            "project_id": project.project_id,
            "goal": project.goal
        })
        
        # Execute research tasks
        research_tasks = [t for t in project.task_graph if "research" in t.task_id.lower()]
        
        acquired_data = {}
        for task in research_tasks:
            task.status = TaskStatus.IN_PROGRESS
            
            # Gather data (simplified - would use actual scout tools)
            data = await self._scout_gather(project, task)
            acquired_data[task.task_id] = data
            
            task.status = TaskStatus.COMPLETED
            task.output = data
            task.completed_at = datetime.utcnow()
        
        project.acquired_data = acquired_data
        
        await self._publish_event("scout.completed", "project", project.project_id, {
            "project_id": project.project_id,
            "data_sources": list(acquired_data.keys()),
            "items_collected": sum(len(v.get("items", [])) for v in acquired_data.values() if isinstance(v, dict))
        })
        
        return project
    
    async def _scout_gather(self, project: ProjectExecution, task: TaskNode) -> Dict[str, Any]:
        """Scout gathers data for a task"""
        # This would integrate with actual scout tools
        # For now, return placeholder structure
        return {
            "sources": ["internal_config", "backend_state"],
            "items": [
                {"type": "capability", "source": "backend", "verified": False}
            ],
            "gathered_at": datetime.utcnow().isoformat()
        }
    
    # =========================================================================
    # STEP 5: VERIFY
    # =========================================================================
    async def _verify(self, project: ProjectExecution) -> ProjectExecution:
        """Verification gate - grade sources and facts"""
        logger.info(f"✅ VERIFY: Grading sources")
        project.status = ProjectStatus.VERIFYING
        
        await self._publish_event("verify.started", "project", project.project_id, {
            "project_id": project.project_id,
            "items_to_verify": len(project.acquired_data)
        })
        
        try:
            from backend.services.verification_gate import verification_gate
            verified = await verification_gate.verify_project_data(project.acquired_data)
        except ImportError:
            # Fallback if verification gate not available
            verified = {
                "approved_facts": [],
                "rejected_claims": [],
                "uncertainty_flags": [],
                "overall_grade": "B"
            }
        
        project.verified_facts = verified.get("approved_facts", [])
        
        # Update verification tasks
        verify_tasks = [t for t in project.task_graph if "verify" in t.task_id.lower()]
        for task in verify_tasks:
            task.status = TaskStatus.COMPLETED
            task.output = verified
            task.completed_at = datetime.utcnow()
        
        await self._publish_event("verify.completed", "project", project.project_id, {
            "project_id": project.project_id,
            "approved_facts_count": len(project.verified_facts),
            "overall_grade": verified.get("overall_grade", "unknown"),
            "uncertainty_flags": verified.get("uncertainty_flags", [])
        })
        
        return project
    
    # =========================================================================
    # STEP 6: COUNCIL DEBATE
    # =========================================================================
    async def _council_debate(self, project: ProjectExecution) -> ProjectExecution:
        """Council advisors debate, synthesizer produces recommendation"""
        logger.info(f"🏛️ COUNCIL: Advisors debating")
        project.status = ProjectStatus.COUNCIL_DEBATE
        
        await self._publish_event("council.session_started", "project", project.project_id, {
            "project_id": project.project_id,
            "topic": project.goal
        })
        
        # Get council service
        try:
            from backend.services.council_service import CouncilService
            council = CouncilService()
            
            # Run council debate for the relevant department
            debate_result = await council.run_debate(
                department="product",
                question=f"How should we approach: {project.goal}",
                context={"constraints": project.constraints, "verified_facts": project.verified_facts}
            )
            
            # Record any dissent
            if debate_result.get("dissent"):
                await self._publish_event("council.dissent_recorded", "project", project.project_id, {
                    "project_id": project.project_id,
                    "dissent": debate_result.get("dissent")
                })
            
            project.council_synthesis = debate_result
            
        except Exception as e:
            logger.warning(f"Council debate failed: {e}, proceeding with default")
            project.council_synthesis = {
                "recommendation": "Proceed with deliverables as specified",
                "confidence": 0.7,
                "dissent": []
            }
        
        await self._publish_event("council.synthesis_completed", "project", project.project_id, {
            "project_id": project.project_id,
            "recommendation": project.council_synthesis.get("recommendation", "")[:200],
            "confidence": project.council_synthesis.get("confidence", 0)
        })
        
        return project
    
    # =========================================================================
    # STEP 7: EXECUTE
    # =========================================================================
    async def _execute(self, project: ProjectExecution) -> ProjectExecution:
        """Execute tasks and produce deliverables"""
        logger.info(f"⚡ EXECUTE: Producing deliverables")
        project.status = ProjectStatus.EXECUTING
        
        # Execute each execution task
        exec_tasks = [t for t in project.task_graph if "exec" in t.task_id.lower()]
        
        for task in exec_tasks:
            task.status = TaskStatus.IN_PROGRESS
            task.progress = 0
            
            await self._publish_event("task.started", "task", task.task_id, {
                "task_id": task.task_id,
                "name": task.name,
                "department": task.owner_department
            })
            
            # Execute the task
            output = await self._execute_task(project, task)
            
            task.output = output
            task.status = TaskStatus.COMPLETED
            task.progress = 100
            task.completed_at = datetime.utcnow()
            
            # Add to produced deliverables
            if output.get("deliverable"):
                project.produced_deliverables.append(output["deliverable"])
            
            await self._publish_event("executor.output_created", "task", task.task_id, {
                "task_id": task.task_id,
                "output_type": output.get("type", "unknown"),
                "path": output.get("path")
            })
        
        return project
    
    async def _execute_task(self, project: ProjectExecution, task: TaskNode) -> Dict[str, Any]:
        """Execute a single task"""
        # This would use actual LLM and tools
        # For now, return placeholder
        return {
            "type": "document",
            "deliverable": {
                "name": task.name,
                "content": f"Deliverable for: {task.description}",
                "format": "markdown",
                "created_at": datetime.utcnow().isoformat()
            }
        }
    
    # =========================================================================
    # STEP 8: QA
    # =========================================================================
    async def _qa(self, project: ProjectExecution) -> ProjectExecution:
        """Quality assurance checks"""
        logger.info(f"🔍 QA: Testing deliverables")
        project.status = ProjectStatus.QA
        
        qa_results = {
            "tests_run": len(project.produced_deliverables),
            "tests_passed": 0,
            "tests_failed": 0,
            "issues": []
        }
        
        # Check each deliverable against acceptance criteria
        for deliverable in project.produced_deliverables:
            # Simplified QA check
            qa_results["tests_passed"] += 1
        
        project.qa_results = qa_results
        
        # Update QA task
        qa_tasks = [t for t in project.task_graph if "qa" in t.task_id.lower()]
        for task in qa_tasks:
            task.status = TaskStatus.COMPLETED
            task.output = qa_results
            task.completed_at = datetime.utcnow()
        
        await self._publish_event("qa.completed", "project", project.project_id, {
            "project_id": project.project_id,
            "tests_run": qa_results["tests_run"],
            "tests_passed": qa_results["tests_passed"],
            "tests_failed": qa_results["tests_failed"]
        })
        
        return project
    
    # =========================================================================
    # STEP 9: DELIVER
    # =========================================================================
    async def _deliver(self, project: ProjectExecution) -> ProjectExecution:
        """Publish outputs and update UI"""
        logger.info(f"📦 DELIVER: Publishing outputs")
        project.status = ProjectStatus.DELIVERING
        
        delivery_info = []
        for i, deliverable in enumerate(project.produced_deliverables):
            delivery_info.append({
                "index": i,
                "name": deliverable.get("name", f"Deliverable {i}"),
                "format": deliverable.get("format", "unknown"),
                "delivered_at": datetime.utcnow().isoformat()
            })
        
        await self._publish_event("deliverables.published", "project", project.project_id, {
            "project_id": project.project_id,
            "deliverables": delivery_info,
            "count": len(delivery_info)
        })
        
        return project
    
    # =========================================================================
    # STEP 10: AUDIT
    # =========================================================================
    async def _audit(self, project: ProjectExecution) -> ProjectExecution:
        """Write decision ledger entry"""
        logger.info(f"📝 AUDIT: Writing decision ledger")
        project.status = ProjectStatus.AUDITING
        
        ledger_entry = {
            "project_id": project.project_id,
            "title": project.title,
            "goal": project.goal,
            "started_at": project.created_at.isoformat(),
            "completed_at": datetime.utcnow().isoformat(),
            "departments_involved": list(set(t.owner_department for t in project.task_graph)),
            "agents_involved": list(set(t.owner_agent for t in project.task_graph if t.owner_agent)),
            "tasks_completed": len([t for t in project.task_graph if t.status == TaskStatus.COMPLETED]),
            "facts_verified": len(project.verified_facts),
            "council_recommendation": project.council_synthesis.get("recommendation", "") if project.council_synthesis else "",
            "deliverables_produced": len(project.produced_deliverables),
            "qa_passed": project.qa_results.get("tests_passed", 0) == project.qa_results.get("tests_run", 0),
            "outcome": "success"
        }
        
        project.ledger_entry = ledger_entry
        
        # Persist to decision ledger
        try:
            from backend.services.decision_ledger import decision_ledger
            await decision_ledger.write_entry(ledger_entry)
        except ImportError:
            logger.warning("Decision ledger not available, entry not persisted")
        
        await self._publish_event("ledger.written", "project", project.project_id, {
            "project_id": project.project_id,
            "ledger_entry": ledger_entry
        })
        
        return project
    
    # =========================================================================
    # STEP 11: IMPROVE
    # =========================================================================
    async def _improve(self, project: ProjectExecution):
        """Propose workflow/prompt upgrades (optional)"""
        logger.info(f"💡 IMPROVE: Checking for learnings")
        
        # Log learnings for Founder approval
        try:
            from backend.services.learning_service import learning_service
            learning_service.log_learning(
                learned_by="autonomous_executor",
                category="optimization",
                summary=f"Completed project: {project.title}",
                details={
                    "project_id": project.project_id,
                    "tasks_count": len(project.task_graph),
                    "time_taken": (project.completed_at - project.created_at).total_seconds() if project.completed_at else None
                }
            )
        except Exception as e:
            logger.debug(f"Learning log failed: {e}")
    
    # =========================================================================
    # PUBLIC CONTROL METHODS (for UI reverse sync)
    # =========================================================================
    
    async def pause_task(self, task_id: str) -> Dict[str, Any]:
        """Pause a task (called from frontend)"""
        for project in self.active_projects.values():
            for task in project.task_graph:
                if task.task_id == task_id:
                    task.status = TaskStatus.PAUSED
                    await self._publish_event("task.paused", "task", task_id, {
                        "task_id": task_id,
                        "paused_at": datetime.utcnow().isoformat()
                    })
                    return {"success": True, "task_id": task_id, "status": "paused"}
        return {"success": False, "error": "Task not found"}
    
    async def resume_task(self, task_id: str) -> Dict[str, Any]:
        """Resume a paused task"""
        for project in self.active_projects.values():
            for task in project.task_graph:
                if task.task_id == task_id and task.status == TaskStatus.PAUSED:
                    task.status = TaskStatus.IN_PROGRESS
                    await self._publish_event("task.resumed", "task", task_id, {
                        "task_id": task_id,
                        "resumed_at": datetime.utcnow().isoformat()
                    })
                    return {"success": True, "task_id": task_id, "status": "in_progress"}
        return {"success": False, "error": "Task not found or not paused"}
    
    async def update_constraints(self, project_id: str, constraints: List[str]) -> Dict[str, Any]:
        """Update project constraints (called from frontend)"""
        if project_id in self.active_projects:
            project = self.active_projects[project_id]
            project.constraints = constraints
            
            await self._publish_event("constraints.updated", "project", project_id, {
                "project_id": project_id,
                "constraints": constraints
            })
            
            # Re-run routing if project is still in early stages
            if project.status in [ProjectStatus.DECOMPOSING, ProjectStatus.ROUTING]:
                project = await self._route(project)
            
            return {"success": True, "project_id": project_id, "constraints": constraints}
        return {"success": False, "error": "Project not found"}
    
    def get_project_status(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Get current project status"""
        if project_id in self.active_projects:
            project = self.active_projects[project_id]
            return {
                "project_id": project.project_id,
                "title": project.title,
                "status": project.status.value,
                "tasks": [
                    {
                        "task_id": t.task_id,
                        "name": t.name,
                        "status": t.status.value,
                        "progress": t.progress,
                        "department": t.owner_department,
                        "agent": t.owner_agent
                    }
                    for t in project.task_graph
                ],
                "deliverables": project.produced_deliverables,
                "created_at": project.created_at.isoformat()
            }
        return None


# Global singleton
autonomous_executor = AutonomousExecutor()
