"""
Daena Decision Maker - Smart decision making for departments and agents
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from enum import Enum
import random

logger = logging.getLogger(__name__)

class DecisionType(Enum):
    RESOURCE_ALLOCATION = "resource_allocation"
    PROCESS_OPTIMIZATION = "process_optimization"
    STRATEGIC_PIVOT = "strategic_pivot"
    TEAM_COORDINATION = "team_coordination"
    QUALITY_IMPROVEMENT = "quality_improvement"
    COST_OPTIMIZATION = "cost_optimization"
    INNOVATION_INITIATIVE = "innovation_initiative"
    CRISIS_MANAGEMENT = "crisis_management"

class DecisionPriority(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class DaenaDecisionMaker:
    """Smart decision maker for Daena AI VP"""
    
    def __init__(self, agent_manager):
        self.agent_manager = agent_manager
        self.decision_history = []
        self.current_priorities = {
            "Engineering": ["code_quality", "system_performance", "security"],
            "Marketing": ["brand_awareness", "lead_generation", "content_quality"],
            "Sales": ["revenue_growth", "customer_acquisition", "deal_velocity"],
            "Finance": ["cost_control", "revenue_optimization", "cash_flow"],
            "HR": ["team_morale", "recruitment", "performance"],
            "Customer Success": ["customer_satisfaction", "retention", "onboarding"],
            "Product": ["user_experience", "feature_development", "market_fit"],
            "Operations": ["efficiency", "process_optimization", "quality_control"]
        }
        
    async def analyze_situation(self) -> Dict[str, Any]:
        """Analyze current business situation and identify opportunities"""
        analysis = {
            "timestamp": datetime.utcnow().isoformat(),
            "departments_status": {},
            "opportunities": [],
            "challenges": [],
            "recommendations": []
        }
        
        # Analyze each department
        for department in self.current_priorities.keys():
            dept_status = self.agent_manager.get_department_status(department)
            analysis["departments_status"][department] = dept_status
            
            # Identify opportunities and challenges
            opportunities, challenges = await self._analyze_department(department, dept_status)
            analysis["opportunities"].extend(opportunities)
            analysis["challenges"].extend(challenges)
        
        # Generate recommendations
        analysis["recommendations"] = await self._generate_recommendations(analysis)
        
        return analysis
    
    async def _analyze_department(self, department: str, status: Dict[str, Any]) -> tuple:
        """Analyze a specific department for opportunities and challenges"""
        opportunities = []
        challenges = []
        
        # Analyze based on department priorities
        priorities = self.current_priorities.get(department, [])
        
        for priority in priorities:
            if department == "Engineering":
                if priority == "code_quality" and status.get("success_rate", 0) < 90:
                    challenges.append({
                        "department": department,
                        "issue": "Code quality below target",
                        "priority": priority,
                        "impact": "high"
                    })
                elif priority == "system_performance":
                    opportunities.append({
                        "department": department,
                        "opportunity": "Performance optimization needed",
                        "priority": priority,
                        "impact": "medium"
                    })
            
            elif department == "Marketing":
                if priority == "lead_generation":
                    opportunities.append({
                        "department": department,
                        "opportunity": "Expand lead generation campaigns",
                        "priority": priority,
                        "impact": "high"
                    })
            
            elif department == "Sales":
                if priority == "revenue_growth":
                    challenges.append({
                        "department": department,
                        "issue": "Revenue growth needs improvement",
                        "priority": priority,
                        "impact": "critical"
                    })
            
            elif department == "Finance":
                if priority == "cost_control":
                    opportunities.append({
                        "department": department,
                        "opportunity": "Identify cost optimization opportunities",
                        "priority": priority,
                        "impact": "medium"
                    })
        
        return opportunities, challenges
    
    async def _generate_recommendations(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate smart recommendations based on analysis"""
        recommendations = []
        
        # Critical challenges get immediate attention
        critical_challenges = [c for c in analysis["challenges"] if c.get("impact") == "critical"]
        for challenge in critical_challenges:
            recommendations.append({
                "type": "immediate_action",
                "department": challenge["department"],
                "action": f"Address {challenge['issue']}",
                "priority": "critical",
                "reasoning": f"Critical issue affecting {challenge['department']} department",
                "agents_involved": self._get_relevant_agents(challenge["department"])
            })
        
        # High-impact opportunities
        high_opportunities = [o for o in analysis["opportunities"] if o.get("impact") == "high"]
        for opportunity in high_opportunities:
            recommendations.append({
                "type": "strategic_initiative",
                "department": opportunity["department"],
                "action": f"Pursue {opportunity['opportunity']}",
                "priority": "high",
                "reasoning": f"High-impact opportunity in {opportunity['department']}",
                "agents_involved": self._get_relevant_agents(opportunity["department"])
            })
        
        # Process optimization opportunities
        if len(analysis["departments_status"]) > 0:
            avg_success_rate = sum(
                dept.get("success_rate", 0) for dept in analysis["departments_status"].values()
            ) / len(analysis["departments_status"])
            
            if avg_success_rate < 85:
                recommendations.append({
                    "type": "process_optimization",
                    "department": "Operations",
                    "action": "Implement cross-department efficiency improvements",
                    "priority": "medium",
                    "reasoning": f"Average success rate ({avg_success_rate:.1f}%) below target",
                    "agents_involved": self._get_relevant_agents("Operations")
                })
        
        return recommendations
    
    def _get_relevant_agents(self, department: str) -> List[str]:
        """Get relevant agents for a department"""
        dept_agents = [
            agent_id for agent_id, agent in self.agent_manager.agents.items()
            if agent.department == department and agent.is_active
        ]
        return dept_agents[:3]  # Return top 3 agents
    
    async def make_decision(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Make a smart decision based on context"""
        decision = {
            "id": f"dec_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            "timestamp": datetime.utcnow().isoformat(),
            "context": context,
            "analysis": await self.analyze_situation(),
            "decision": {},
            "implementation_plan": [],
            "expected_outcomes": []
        }
        
        # Determine decision type based on context
        if "crisis" in context.get("situation", "").lower():
            decision_type = DecisionType.CRISIS_MANAGEMENT
        elif "optimization" in context.get("situation", "").lower():
            decision_type = DecisionType.PROCESS_OPTIMIZATION
        elif "resource" in context.get("situation", "").lower():
            decision_type = DecisionType.RESOURCE_ALLOCATION
        else:
            decision_type = DecisionType.STRATEGIC_PIVOT
        
        # Generate decision based on type
        if decision_type == DecisionType.CRISIS_MANAGEMENT:
            decision["decision"] = await self._make_crisis_decision(context)
        elif decision_type == DecisionType.PROCESS_OPTIMIZATION:
            decision["decision"] = await self._make_optimization_decision(context)
        elif decision_type == DecisionType.RESOURCE_ALLOCATION:
            decision["decision"] = await self._make_resource_decision(context)
        else:
            decision["decision"] = await self._make_strategic_decision(context)
        
        # Generate implementation plan
        decision["implementation_plan"] = await self._generate_implementation_plan(decision)
        
        # Predict outcomes
        decision["expected_outcomes"] = await self._predict_outcomes(decision)
        
        self.decision_history.append(decision)
        return decision
    
    async def _make_crisis_decision(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Make a crisis management decision"""
        return {
            "type": "crisis_management",
            "action": "Immediate response protocol activation",
            "priority": DecisionPriority.CRITICAL.value,
            "departments_involved": ["Operations", "Engineering", "Customer Success"],
            "timeframe": "immediate",
            "resources_required": ["emergency_budget", "additional_agents", "system_access"],
            "communication_plan": "Immediate notification to all stakeholders"
        }
    
    async def _make_optimization_decision(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Make a process optimization decision"""
        return {
            "type": "process_optimization",
            "action": "Implement efficiency improvements",
            "priority": DecisionPriority.HIGH.value,
            "departments_involved": ["Operations", "Engineering"],
            "timeframe": "2_weeks",
            "resources_required": ["analysis_tools", "optimization_agents"],
            "communication_plan": "Weekly progress updates"
        }
    
    async def _make_resource_decision(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Make a resource allocation decision"""
        return {
            "type": "resource_allocation",
            "action": "Reallocate resources for maximum impact",
            "priority": DecisionPriority.MEDIUM.value,
            "departments_involved": ["Finance", "Operations"],
            "timeframe": "1_week",
            "resources_required": ["budget_analysis", "resource_tracking"],
            "communication_plan": "Department head notifications"
        }
    
    async def _make_strategic_decision(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Make a strategic decision"""
        return {
            "type": "strategic_pivot",
            "action": "Strategic direction adjustment",
            "priority": DecisionPriority.HIGH.value,
            "departments_involved": ["Product", "Marketing", "Sales"],
            "timeframe": "1_month",
            "resources_required": ["market_research", "strategy_agents"],
            "communication_plan": "Quarterly strategic review"
        }
    
    async def _generate_implementation_plan(self, decision: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate implementation plan for a decision"""
        plan = []
        
        decision_data = decision["decision"]
        departments = decision_data.get("departments_involved", [])
        
        for department in departments:
            plan.append({
                "department": department,
                "actions": [
                    f"Analyze current {department.lower()} processes",
                    f"Identify improvement opportunities",
                    f"Implement {decision_data['action'].lower()}",
                    f"Monitor progress and adjust"
                ],
                "timeline": decision_data.get("timeframe", "1_week"),
                "success_metrics": [
                    "Process efficiency improvement",
                    "Cost reduction",
                    "Quality enhancement"
                ]
            })
        
        return plan
    
    async def _predict_outcomes(self, decision: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Predict expected outcomes of a decision"""
        outcomes = []
        
        decision_data = decision["decision"]
        
        if decision_data["type"] == "crisis_management":
            outcomes.extend([
                {"metric": "response_time", "expected_improvement": "50%"},
                {"metric": "stakeholder_satisfaction", "expected_improvement": "25%"},
                {"metric": "system_stability", "expected_improvement": "75%"}
            ])
        elif decision_data["type"] == "process_optimization":
            outcomes.extend([
                {"metric": "efficiency", "expected_improvement": "20%"},
                {"metric": "cost_savings", "expected_improvement": "15%"},
                {"metric": "quality", "expected_improvement": "10%"}
            ])
        elif decision_data["type"] == "resource_allocation":
            outcomes.extend([
                {"metric": "roi", "expected_improvement": "25%"},
                {"metric": "productivity", "expected_improvement": "18%"},
                {"metric": "utilization", "expected_improvement": "30%"}
            ])
        else:  # strategic_pivot
            outcomes.extend([
                {"metric": "market_position", "expected_improvement": "35%"},
                {"metric": "revenue_growth", "expected_improvement": "40%"},
                {"metric": "competitive_advantage", "expected_improvement": "50%"}
            ])
        
        return outcomes
    
    async def assign_tasks_to_agents(self, decision: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Assign specific tasks to agents based on decision"""
        tasks = []
        
        implementation_plan = decision.get("implementation_plan", [])
        
        for plan_item in implementation_plan:
            department = plan_item["department"]
            actions = plan_item["actions"]
            
            # Get agents for this department
            dept_agents = [
                agent_id for agent_id, agent in self.agent_manager.agents.items()
                if agent.department == department and agent.is_active
            ]
            
            # Assign tasks to agents
            for i, action in enumerate(actions):
                if i < len(dept_agents):
                    agent_id = dept_agents[i]
                    task_result = await self.agent_manager.assign_task_to_specific_agent(
                        agent_id=agent_id,
                        task_title=f"Implement: {action}",
                        task_description=f"Execute {action} for {department} department as part of strategic decision",
                        task_type="optimization",
                        priority="high"
                    )
                    tasks.append(task_result)
        
        return tasks
    
    def get_decision_history(self) -> List[Dict[str, Any]]:
        """Get decision history"""
        return self.decision_history
    
    def get_department_priorities(self) -> Dict[str, List[str]]:
        """Get current department priorities"""
        return self.current_priorities
    
    def update_department_priorities(self, department: str, priorities: List[str]):
        """Update priorities for a department"""
        self.current_priorities[department] = priorities
        logger.info(f"Updated priorities for {department}: {priorities}") 