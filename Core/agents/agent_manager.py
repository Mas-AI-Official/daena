"""
Agent Manager - Coordinates all agents and assigns real tasks
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from .agent_executor import AgentExecutor, TaskType, TaskStatus

logger = logging.getLogger(__name__)

class AgentManager:
    """Manages all agents and coordinates their activities"""
    
    def __init__(self):
        self.agents: Dict[str, AgentExecutor] = {}
        self.departments = {
            "Engineering": ["CodeMaster AI", "DevOps Agent", "QA Tester", "Architecture AI", "Security Scanner", "Performance Monitor"],
            "Marketing": ["Content Creator", "Social Media AI", "SEO Optimizer", "Ad Campaign Manager"],
            "Sales": ["Lead Hunter", "Deal Closer", "Proposal Generator"],
            "Finance": ["Budget Analyzer", "Revenue Forecaster"],
            "HR": ["Recruiter AI", "Employee Satisfaction"],
            "Customer Success": ["Support Bot", "Success Manager", "Feedback Analyzer"],
            "Product": ["Strategy AI", "UX Research", "Feature Prioritizer"],
            "Operations": ["Process Optimizer", "Quality Controller"]
        }
        # Don't initialize agents immediately - wait for live data
        self._agents_initialized = False
    
    def _initialize_agents(self):
        """Initialize all agents with their capabilities from live data"""
        try:
            # Try to get live agent count from sunflower registry - use multiple import paths
            sunflower_registry = None
            try:
                # Try relative import first (when called from Core)
                from ..utils.sunflower_registry import sunflower_registry
            except ImportError:
                try:
                    # Try absolute import (when called from backend)
                    import sys
                    import os
                    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
                    from utils.sunflower_registry import sunflower_registry
                except ImportError:
                    try:
                        # Try direct import from project root
                        import sys
                        import os
                        project_root = os.path.join(os.path.dirname(__file__), '..', '..')
                        if project_root not in sys.path:
                            sys.path.insert(0, project_root)
                        from backend.utils.sunflower_registry import sunflower_registry
                    except ImportError:
                        pass
            
            if sunflower_registry and hasattr(sunflower_registry, 'agents'):
                live_agent_count = len(sunflower_registry.agents)
                live_dept_count = len(sunflower_registry.departments)
                
                if live_agent_count > 0:
                    logger.info(f"Using live data: {live_agent_count} agents across {live_dept_count} departments")
                    # Don't create duplicate agents if live data exists
                    return
        except Exception as e:
            logger.debug(f"Could not access sunflower registry: {e}")
        
        # Fallback to default initialization if no live data
        agent_counter = 1
        
        for department, agent_names in self.departments.items():
            for agent_name in agent_names:
                agent_id = f"agent_{agent_counter:03d}"
                
                # Define capabilities based on department
                capabilities = self._get_department_capabilities(department)
                
                agent = AgentExecutor(
                    agent_id=agent_id,
                    name=agent_name,
                    department=department,
                    capabilities=capabilities
                )
                
                self.agents[agent_id] = agent
                agent_counter += 1
        
        logger.info(f"Initialized {len(self.agents)} agents across {len(self.departments)} departments (fallback mode)")
    
    def refresh_from_live_data(self):
        """Refresh agent data from live sunflower registry after seeding"""
        try:
            # Try to get live agent count from sunflower registry
            sunflower_registry = None
            try:
                # Try relative import first (when called from Core)
                from backend.utils.sunflower_registry import sunflower_registry
            except ImportError:
                try:
                    # Try absolute import (when called from backend)
                    import sys
                    import os
                    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
                    from utils.sunflower_registry import sunflower_registry
                except ImportError:
                    pass
            
            if sunflower_registry and hasattr(sunflower_registry, 'agents'):
                live_agent_count = len(sunflower_registry.agents)
                live_dept_count = len(sunflower_registry.departments)
                
                if live_agent_count > 0:
                    logger.info(f"Refreshed: Now using live data: {live_agent_count} agents across {live_dept_count} departments")
                    # Clear old agents and use live data
                    self.agents.clear()
                    return True
        except Exception as e:
            logger.debug(f"Could not refresh from sunflower registry: {e}")
        
        return False
    
    def get_live_agent_count(self) -> int:
        """Get the current live agent count from sunflower registry"""
        try:
            # Try to get live agent count from sunflower registry
            sunflower_registry = None
            try:
                # Try relative import first (when called from Core)
                from backend.utils.sunflower_registry import sunflower_registry
            except ImportError:
                try:
                    # Try absolute import (when called from backend)
                    import sys
                    import os
                    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
                    from utils.sunflower_registry import sunflower_registry
                except ImportError:
                    pass
            
            if sunflower_registry and hasattr(sunflower_registry, 'agents'):
                return len(sunflower_registry.agents)
        except Exception as e:
            logger.debug(f"Could not get live agent count: {e}")
        
        # Fallback to local count
        return len(self.agents)
    
    def get_live_department_info(self) -> dict:
        """Get live department information from sunflower registry"""
        try:
            # Try to get live department info from sunflower registry
            sunflower_registry = None
            try:
                # Try relative import first (when called from Core)
                from backend.utils.sunflower_registry import sunflower_registry
            except ImportError:
                try:
                    # Try absolute import (when called from backend)
                    import sys
                    import os
                    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
                    from utils.sunflower_registry import sunflower_registry
                except ImportError:
                    pass
            
            if sunflower_registry and hasattr(sunflower_registry, 'departments'):
                dept_info = {}
                for dept in sunflower_registry.departments:
                    dept_id = dept.get('id', dept.get('slug', 'unknown'))
                    dept_info[dept_id] = {
                        'name': dept.get('name', 'Unknown'),
                        'agents_count': dept.get('agents_count', 0),
                        'description': dept.get('description', '')
                    }
                return dept_info
        except Exception as e:
            logger.debug(f"Could not get live department info: {e}")
        
        # Fallback to local info
        return {dept: {'name': dept, 'agents_count': len(agents), 'description': ''} 
                for dept, agents in self.departments.items()}
    
    def get_live_agent_roles(self) -> dict:
        """Get live agent roles from sunflower registry"""
        try:
            # Try to get live agent roles from sunflower registry
            sunflower_registry = None
            try:
                # Try relative import first (when called from Core)
                from ..utils.sunflower_registry import sunflower_registry
            except ImportError:
                try:
                    # Try absolute import (when called from backend)
                    import sys
                    import os
                    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
                    from utils.sunflower_registry import sunflower_registry
                except ImportError:
                    pass
            
            if sunflower_registry and hasattr(sunflower_registry, 'agents'):
                agent_roles = {}
                for agent in sunflower_registry.agents:
                    agent_id = agent.get('id', 'unknown')
                    agent_roles[agent_id] = {
                        'name': agent.get('name', 'Unknown'),
                        'role': agent.get('role', 'Unknown'),
                        'department': agent.get('department', 'Unknown')
                    }
                return agent_roles
        except Exception as e:
            logger.debug(f"Could not get live agent roles: {e}")
        
        # Fallback to local info
        return {}
    
    def get_agents(self) -> Dict[str, AgentExecutor]:
        """Get agents, initializing with live data if available"""
        if not self._agents_initialized:
            self._try_initialize_with_live_data()
        
        return self.agents
    
    def _try_initialize_with_live_data(self):
        """Try to initialize agents with live data from database"""
        try:
            # Try to get live agent count from sunflower registry
            sunflower_registry = None
            try:
                # Try direct import from project root
                import sys
                import os
                project_root = os.path.join(os.path.dirname(__file__), '..', '..')
                if project_root not in sys.path:
                    sys.path.insert(0, project_root)
                from backend.utils.sunflower_registry import sunflower_registry
            except ImportError:
                pass
            
            if sunflower_registry and hasattr(sunflower_registry, 'agents'):
                live_agent_count = len(sunflower_registry.agents)
                if live_agent_count > 0:
                    logger.info(f"Using live data: {live_agent_count} agents from database")
                    self._agents_initialized = True
                    return  # Don't create fallback agents
        except Exception as e:
            logger.debug(f"Could not access sunflower registry: {e}")
        
        # Fallback to default initialization
        if not self._agents_initialized:
            self._initialize_agents()
            self._agents_initialized = True
    
    def _get_department_capabilities(self, department: str) -> List[str]:
        """Get capabilities for agents in a specific department"""
        capabilities_map = {
            "Engineering": ["code_review", "system_design", "testing", "optimization", "monitoring"],
            "Marketing": ["content_creation", "social_media", "seo", "campaign_management", "analysis"],
            "Sales": ["lead_generation", "deal_management", "proposal_creation", "relationship_building"],
            "Finance": ["budget_analysis", "forecasting", "financial_reporting", "cost_optimization"],
            "HR": ["recruitment", "employee_management", "performance_tracking", "wellness_monitoring"],
            "Customer Success": ["support", "onboarding", "feedback_analysis", "retention"],
            "Product": ["strategy", "research", "prioritization", "roadmap_planning"],
            "Operations": ["process_optimization", "quality_control", "efficiency_monitoring", "automation"]
        }
        return capabilities_map.get(department, ["general"])
    
    async def assign_task(self, department: str, task_title: str, task_description: str, 
                         task_type: TaskType, priority: str = "medium") -> Dict[str, Any]:
        """Assign a task to an appropriate agent in the department"""
        # Find available agents in the department
        department_agents = [
            agent for agent in self.agents.values() 
            if agent.department == department and agent.is_active
        ]
        
        if not department_agents:
            return {"status": "error", "message": f"No active agents in {department} department"}
        
        # Select the best agent based on current workload
        selected_agent = min(department_agents, key=lambda a: len([t for t in a.tasks if t.status == TaskStatus.IN_PROGRESS]))
        
        # Create and assign the task
        task = selected_agent.add_task(task_title, task_description, task_type, priority)
        
        # Execute the task
        result = await selected_agent.perform_task(task)
        
        return {
            "status": "assigned",
            "agent_id": selected_agent.agent_id,
            "agent_name": selected_agent.name,
            "task_id": task.id,
            "result": result
        }
    
    async def assign_task_to_specific_agent(self, agent_id: str, task_title: str, 
                                          task_description: str, task_type: TaskType, 
                                          priority: str = "medium") -> Dict[str, Any]:
        """Assign a task to a specific agent"""
        if agent_id not in self.agents:
            return {"status": "error", "message": f"Agent {agent_id} not found"}
        
        agent = self.agents[agent_id]
        if not agent.is_active:
            return {"status": "error", "message": f"Agent {agent_id} is not active"}
        
        task = agent.add_task(task_title, task_description, task_type, priority)
        result = await agent.perform_task(task)
        
        return {
            "status": "assigned",
            "agent_id": agent_id,
            "agent_name": agent.name,
            "task_id": task.id,
            "result": result
        }
    
    def get_agent_status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific agent"""
        if agent_id not in self.agents:
            return None
        return self.agents[agent_id].get_status()
    
    def get_department_status(self, department: str) -> Dict[str, Any]:
        """Get status of all agents in a department"""
        department_agents = [
            agent for agent in self.agents.values() 
            if agent.department == department
        ]
        
        if not department_agents:
            return {"status": "error", "message": f"No agents found in {department} department"}
        
        total_tasks = sum(len(agent.tasks) for agent in department_agents)
        completed_tasks = sum(len([t for t in agent.tasks if t.status == TaskStatus.COMPLETED]) 
                            for agent in department_agents)
        active_tasks = sum(len([t for t in agent.tasks if t.status == TaskStatus.IN_PROGRESS]) 
                          for agent in department_agents)
        
        avg_success_rate = sum(agent.performance_metrics["success_rate"] for agent in department_agents) / len(department_agents)
        
        return {
            "department": department,
            "total_agents": len(department_agents),
            "active_agents": len([a for a in department_agents if a.is_active]),
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "active_tasks": active_tasks,
            "success_rate": round(avg_success_rate * 100, 2),
            "agents": [agent.get_status() for agent in department_agents]
        }
    
    def get_all_agents_status(self) -> Dict[str, Any]:
        """Get status of all agents"""
        total_agents = len(self.agents)
        active_agents = len([a for a in self.agents.values() if a.is_active])
        
        total_tasks = sum(len(agent.tasks) for agent in self.agents.values())
        completed_tasks = sum(len([t for t in agent.tasks if t.status == TaskStatus.COMPLETED]) 
                            for agent in self.agents.values())
        
        avg_success_rate = sum(agent.performance_metrics["success_rate"] for agent in self.agents.values()) / total_agents if total_agents > 0 else 0
        
        return {
            "total_agents": total_agents,
            "active_agents": active_agents,
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "success_rate": round(avg_success_rate * 100, 2),
            "departments": list(self.departments.keys()),
            "agents": {agent_id: agent.get_status() for agent_id, agent in self.agents.items()}
        }
    
    async def stop_all_agents(self):
        """Stop all agents gracefully"""
        logger.info(f"Stopping {len(self.agents)} agents...")
        stop_tasks = []
        for agent_id, agent in self.agents.items():
            if hasattr(agent, 'stop'):
                stop_tasks.append(agent.stop())
        
        if stop_tasks:
            await asyncio.gather(*stop_tasks, return_exceptions=True)
        
        logger.info("All agents stopped")
    
    async def run_agent_cycle(self, agent_id: str) -> Dict[str, Any]:
        """Run a cycle for a specific agent (process pending tasks)"""
        if agent_id not in self.agents:
            return {"status": "error", "message": f"Agent {agent_id} not found"}
        
        agent = self.agents[agent_id]
        pending_tasks = [t for t in agent.tasks if t.status == TaskStatus.PENDING]
        
        if not pending_tasks:
            return {"status": "no_tasks", "message": f"No pending tasks for agent {agent_id}"}
        
        results = []
        for task in pending_tasks[:3]:  # Process up to 3 tasks per cycle
            result = await agent.perform_task(task)
            results.append({
                "task_id": task.id,
                "task_title": task.title,
                "result": result
            })
        
        return {
            "status": "completed",
            "agent_id": agent_id,
            "agent_name": agent.name,
            "tasks_processed": len(results),
            "results": results
        }
    
    async def run_department_cycle(self, department: str) -> Dict[str, Any]:
        """Run a cycle for all agents in a department"""
        department_agents = [
            agent for agent in self.agents.values() 
            if agent.department == department and agent.is_active
        ]
        
        if not department_agents:
            return {"status": "error", "message": f"No active agents in {department} department"}
        
        results = []
        for agent in department_agents:
            agent_result = await self.run_agent_cycle(agent.agent_id)
            results.append(agent_result)
        
        return {
            "status": "completed",
            "department": department,
            "agents_processed": len(results),
            "results": results
        }
    
    def add_sample_tasks(self):
        """Add sample tasks to demonstrate agent functionality"""
        sample_tasks = [
            {
                "department": "Engineering",
                "title": "Code Review for API Endpoint",
                "description": "Review the new user authentication API endpoint for security and performance",
                "task_type": TaskType.ANALYSIS,
                "priority": "high"
            },
            {
                "department": "Marketing",
                "title": "Create Q1 Marketing Report",
                "description": "Generate comprehensive marketing performance report for Q1 2025",
                "task_type": TaskType.REPORT,
                "priority": "medium"
            },
            {
                "department": "Sales",
                "title": "Follow up with Enterprise Lead",
                "description": "Send follow-up email to TechCorp regarding their AI solution inquiry",
                "task_type": TaskType.EMAIL,
                "priority": "high"
            },
            {
                "department": "Finance",
                "title": "Budget Optimization Analysis",
                "description": "Analyze current budget allocation and identify optimization opportunities",
                "task_type": TaskType.ANALYSIS,
                "priority": "medium"
            },
            {
                "department": "Operations",
                "title": "Process Optimization Review",
                "description": "Review current workflow processes and identify automation opportunities",
                "task_type": TaskType.OPTIMIZATION,
                "priority": "medium"
            }
        ]
        
        for task_data in sample_tasks:
            # Find an appropriate agent
            department_agents = [
                agent for agent in self.agents.values() 
                if agent.department == task_data["department"]
            ]
            if department_agents:
                selected_agent = department_agents[0]
                selected_agent.add_task(
                    task_data["title"],
                    task_data["description"],
                    task_data["task_type"],
                    task_data["priority"]
                )
        
        logger.info(f"Added {len(sample_tasks)} sample tasks to agents") 