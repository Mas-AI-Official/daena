"""
Smart Decision Maker - Daena's intelligent decision-making system
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from enum import Enum
from pydantic import BaseModel
import random

logger = logging.getLogger(__name__)

class DecisionType(str, Enum):
    STRATEGIC = "strategic"
    OPERATIONAL = "operational"
    TACTICAL = "tactical"
    CRISIS = "crisis"
    OPTIMIZATION = "optimization"
    RESOURCE_ALLOCATION = "resource_allocation"

class DepartmentRole(str, Enum):
    ENGINEERING = "engineering"
    MARKETING = "marketing"
    SALES = "sales"
    FINANCE = "finance"
    HR = "hr"
    CUSTOMER_SUCCESS = "customer_success"
    PRODUCT = "product"
    OPERATIONS = "operations"

class AgentRole(str, Enum):
    # Engineering
    CODE_MASTER = "code_master"
    DEVOPS = "devops"
    QA_TESTER = "qa_tester"
    ARCHITECT = "architect"
    SECURITY = "security"
    PERFORMANCE = "performance"
    
    # Marketing
    CONTENT_CREATOR = "content_creator"
    SOCIAL_MEDIA = "social_media"
    SEO_OPTIMIZER = "seo_optimizer"
    AD_CAMPAIGN = "ad_campaign"
    
    # Sales
    LEAD_HUNTER = "lead_hunter"
    DEAL_CLOSER = "deal_closer"
    PROPOSAL_GENERATOR = "proposal_generator"
    
    # Finance
    BUDGET_ANALYZER = "budget_analyzer"
    REVENUE_FORECASTER = "revenue_forecaster"
    
    # HR
    RECRUITER = "recruiter"
    EMPLOYEE_SATISFACTION = "employee_satisfaction"
    
    # Customer Success
    SUPPORT_BOT = "support_bot"
    SUCCESS_MANAGER = "success_manager"
    FEEDBACK_ANALYZER = "feedback_analyzer"
    
    # Product
    STRATEGY_AI = "strategy_ai"
    UX_RESEARCH = "ux_research"
    FEATURE_PRIORITIZER = "feature_prioritizer"
    
    # Operations
    PROCESS_OPTIMIZER = "process_optimizer"
    QUALITY_CONTROLLER = "quality_controller"

class SmartDecisionMaker:
    """Daena's intelligent decision-making system"""
    
    def __init__(self, agent_manager):
        self.agent_manager = agent_manager
        self.department_priorities = {
            DepartmentRole.ENGINEERING: 0.9,  # High priority for development
            DepartmentRole.PRODUCT: 0.85,      # High priority for strategy
            DepartmentRole.SALES: 0.8,         # High priority for revenue
            DepartmentRole.MARKETING: 0.75,    # Medium-high priority
            DepartmentRole.FINANCE: 0.7,       # Medium priority
            DepartmentRole.CUSTOMER_SUCCESS: 0.65,  # Medium priority
            DepartmentRole.OPERATIONS: 0.6,    # Medium priority
            DepartmentRole.HR: 0.5             # Lower priority
        }
        
        self.agent_capabilities = self._define_agent_capabilities()
        self.decision_history = []
        
    def _define_agent_capabilities(self) -> Dict[str, List[str]]:
        """Define what each agent role can do"""
        return {
            # Engineering Agents
            AgentRole.CODE_MASTER: ["code_review", "system_design", "architecture", "technical_decisions"],
            AgentRole.DEVOPS: ["deployment", "infrastructure", "monitoring", "automation"],
            AgentRole.QA_TESTER: ["testing", "quality_assurance", "bug_tracking", "test_automation"],
            AgentRole.ARCHITECT: ["system_design", "scalability", "technical_strategy", "architecture_reviews"],
            AgentRole.SECURITY: ["security_audit", "vulnerability_assessment", "compliance", "security_policies"],
            AgentRole.PERFORMANCE: ["performance_optimization", "monitoring", "bottleneck_analysis", "scaling"],
            
            # Marketing Agents
            AgentRole.CONTENT_CREATOR: ["content_creation", "copywriting", "brand_messaging", "content_strategy"],
            AgentRole.SOCIAL_MEDIA: ["social_media_management", "engagement", "campaign_creation", "analytics"],
            AgentRole.SEO_OPTIMIZER: ["seo_optimization", "keyword_research", "content_optimization", "analytics"],
            AgentRole.AD_CAMPAIGN: ["campaign_management", "ad_creation", "budget_optimization", "roi_analysis"],
            
            # Sales Agents
            AgentRole.LEAD_HUNTER: ["lead_generation", "prospecting", "qualification", "lead_scoring"],
            AgentRole.DEAL_CLOSER: ["negotiation", "deal_structure", "closing_strategies", "relationship_building"],
            AgentRole.PROPOSAL_GENERATOR: ["proposal_creation", "pricing_strategy", "value_proposition", "presentation"],
            
            # Finance Agents
            AgentRole.BUDGET_ANALYZER: ["budget_analysis", "cost_optimization", "financial_planning", "expense_tracking"],
            AgentRole.REVENUE_FORECASTER: ["revenue_forecasting", "financial_modeling", "trend_analysis", "predictions"],
            
            # HR Agents
            AgentRole.RECRUITER: ["talent_acquisition", "candidate_screening", "interview_coordination", "onboarding"],
            AgentRole.EMPLOYEE_SATISFACTION: ["employee_engagement", "culture_management", "performance_tracking", "wellness"],
            
            # Customer Success Agents
            AgentRole.SUPPORT_BOT: ["customer_support", "troubleshooting", "knowledge_base", "ticket_management"],
            AgentRole.SUCCESS_MANAGER: ["customer_onboarding", "success_planning", "relationship_management", "retention"],
            AgentRole.FEEDBACK_ANALYZER: ["feedback_collection", "sentiment_analysis", "improvement_suggestions", "trends"],
            
            # Product Agents
            AgentRole.STRATEGY_AI: ["product_strategy", "market_analysis", "competitive_research", "roadmap_planning"],
            AgentRole.UX_RESEARCH: ["user_research", "usability_testing", "design_insights", "user_journey_mapping"],
            AgentRole.FEATURE_PRIORITIZER: ["feature_prioritization", "backlog_management", "user_story_creation", "sprint_planning"],
            
            # Operations Agents
            AgentRole.PROCESS_OPTIMIZER: ["process_improvement", "workflow_optimization", "efficiency_analysis", "automation"],
            AgentRole.QUALITY_CONTROLLER: ["quality_management", "standards_enforcement", "audit_processes", "continuous_improvement"]
        }
    
    async def make_strategic_decision(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Make a strategic decision based on current context"""
        logger.info("Daena making strategic decision...")
        
        # Analyze current situation
        situation_analysis = await self._analyze_situation(context)
        
        # Identify key priorities
        priorities = await self._identify_priorities(situation_analysis)
        
        # Generate strategic options
        options = await self._generate_strategic_options(priorities)
        
        # Evaluate options
        evaluation = await self._evaluate_options(options, context)
        
        # Make decision
        decision = await self._make_final_decision(evaluation)
        
        # Assign tasks to relevant agents
        task_assignments = await self._assign_strategic_tasks(decision)
        
        return {
            "decision_type": "strategic",
            "decision": decision,
            "reasoning": evaluation["reasoning"],
            "impact": evaluation["impact"],
            "task_assignments": task_assignments,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def _analyze_situation(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze current business situation"""
        return {
            "revenue_status": context.get("revenue", 0),
            "customer_count": context.get("customers", 0),
            "development_stage": context.get("stage", "prototype"),
            "agent_performance": context.get("agent_performance", {}),
            "department_health": context.get("department_health", {}),
            "market_conditions": context.get("market_conditions", "competitive"),
            "resource_availability": context.get("resources", "limited")
        }
    
    async def _identify_priorities(self, situation: Dict[str, Any]) -> List[str]:
        """Identify key business priorities"""
        priorities = []
        
        if situation["revenue_status"] == 0:
            priorities.append("revenue_generation")
        
        if situation["customer_count"] == 0:
            priorities.append("customer_acquisition")
        
        if situation["development_stage"] == "prototype":
            priorities.append("product_development")
            priorities.append("beta_testing_preparation")
        
        if situation["resource_availability"] == "limited":
            priorities.append("resource_optimization")
        
        return priorities
    
    async def _generate_strategic_options(self, priorities: List[str]) -> List[Dict[str, Any]]:
        """Generate strategic options based on priorities"""
        options = []
        
        for priority in priorities:
            if priority == "revenue_generation":
                options.extend([
                    {
                        "id": "rev_1",
                        "title": "Focus on B2B Sales",
                        "description": "Prioritize enterprise customers with higher LTV",
                        "departments": ["Sales", "Marketing", "Product"],
                        "expected_impact": "high",
                        "timeframe": "3-6 months"
                    },
                    {
                        "id": "rev_2", 
                        "title": "Launch Freemium Model",
                        "description": "Attract users with free tier, convert to paid",
                        "departments": ["Product", "Marketing", "Sales"],
                        "expected_impact": "medium",
                        "timeframe": "2-4 months"
                    }
                ])
            
            elif priority == "customer_acquisition":
                options.extend([
                    {
                        "id": "cust_1",
                        "title": "Content Marketing Campaign",
                        "description": "Create valuable content to attract prospects",
                        "departments": ["Marketing", "Content"],
                        "expected_impact": "medium",
                        "timeframe": "1-3 months"
                    },
                    {
                        "id": "cust_2",
                        "title": "Partnership Strategy",
                        "description": "Form strategic partnerships for customer acquisition",
                        "departments": ["Sales", "Marketing"],
                        "expected_impact": "high",
                        "timeframe": "3-6 months"
                    }
                ])
            
            elif priority == "product_development":
                options.extend([
                    {
                        "id": "prod_1",
                        "title": "MVP Feature Development",
                        "description": "Focus on core features for beta launch",
                        "departments": ["Engineering", "Product"],
                        "expected_impact": "high",
                        "timeframe": "1-2 months"
                    },
                    {
                        "id": "prod_2",
                        "title": "User Experience Optimization",
                        "description": "Improve user interface and experience",
                        "departments": ["Product", "Engineering"],
                        "expected_impact": "medium",
                        "timeframe": "2-3 months"
                    }
                ])
        
        return options
    
    async def _evaluate_options(self, options: List[Dict[str, Any]], context: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate strategic options"""
        best_option = None
        best_score = 0
        
        for option in options:
            score = self._calculate_option_score(option, context)
            if score > best_score:
                best_score = score
                best_option = option
        
        return {
            "selected_option": best_option,
            "score": best_score,
            "reasoning": f"Selected {best_option['title']} based on current priorities and resource availability",
            "impact": best_option["expected_impact"] if best_option else "medium"
        }
    
    def _calculate_option_score(self, option: Dict[str, Any], context: Dict[str, Any]) -> float:
        """Calculate score for a strategic option"""
        score = 0
        
        # Impact score
        impact_scores = {"high": 3, "medium": 2, "low": 1}
        score += impact_scores.get(option["expected_impact"], 1)
        
        # Department priority score
        for dept in option["departments"]:
            dept_priority = self.department_priorities.get(DepartmentRole(dept.lower()), 0.5)
            score += dept_priority
        
        # Resource availability adjustment
        if context.get("resources") == "limited":
            if "Engineering" in option["departments"]:
                score *= 0.8  # Reduce score for engineering-heavy options
            if "Marketing" in option["departments"]:
                score *= 0.9  # Slightly reduce marketing options
        
        return score
    
    async def _make_final_decision(self, evaluation: Dict[str, Any]) -> Dict[str, Any]:
        """Make the final strategic decision"""
        option = evaluation["selected_option"]
        
        return {
            "id": f"decision_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            "title": option["title"],
            "description": option["description"],
            "type": "strategic",
            "impact": option["expected_impact"],
            "departments_involved": option["departments"],
            "timeframe": option["timeframe"],
            "status": "approved",
            "created_at": datetime.utcnow().isoformat()
        }
    
    async def _assign_strategic_tasks(self, decision: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Assign tasks to relevant agents based on strategic decision"""
        task_assignments = []
        
        for department in decision["departments_involved"]:
            # Get agents in this department
            dept_agents = [
                agent for agent in self.agent_manager.agents.values()
                if agent.department.lower() == department.lower()
            ]
            
            if dept_agents:
                # Assign tasks based on department
                if department == "Engineering":
                    task_assignments.extend([
                        {
                            "agent_id": dept_agents[0].agent_id,
                            "task_title": f"Implement {decision['title']}",
                            "task_description": f"Develop technical implementation for {decision['description']}",
                            "task_type": "development",
                            "priority": "high"
                        }
                    ])
                
                elif department == "Marketing":
                    task_assignments.extend([
                        {
                            "agent_id": dept_agents[0].agent_id,
                            "task_title": f"Create Marketing Plan for {decision['title']}",
                            "task_description": f"Develop marketing strategy and campaigns for {decision['description']}",
                            "task_type": "strategy",
                            "priority": "high"
                        }
                    ])
                
                elif department == "Sales":
                    task_assignments.extend([
                        {
                            "agent_id": dept_agents[0].agent_id,
                            "task_title": f"Develop Sales Strategy for {decision['title']}",
                            "task_description": f"Create sales approach and target customer segments for {decision['description']}",
                            "task_type": "strategy",
                            "priority": "high"
                        }
                    ])
                
                elif department == "Product":
                    task_assignments.extend([
                        {
                            "agent_id": dept_agents[0].agent_id,
                            "task_title": f"Product Strategy for {decision['title']}",
                            "task_description": f"Define product roadmap and feature priorities for {decision['description']}",
                            "task_type": "strategy",
                            "priority": "high"
                        }
                    ])
        
        return task_assignments
    
    async def manage_department_workload(self, department: str) -> Dict[str, Any]:
        """Manage workload and priorities for a specific department"""
        dept_agents = [
            agent for agent in self.agent_manager.agents.values()
            if agent.department.lower() == department.lower()
        ]
        
        if not dept_agents:
            return {"status": "error", "message": f"No agents found in {department} department"}
        
        # Analyze current workload
        total_tasks = sum(len(agent.tasks) for agent in dept_agents)
        active_tasks = sum(len([t for t in agent.tasks if t.status == "in_progress"]) for agent in dept_agents)
        completed_tasks = sum(len([t for t in agent.tasks if t.status == "completed"]) for agent in dept_agents)
        
        # Calculate efficiency
        efficiency = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
        # Determine if department needs help
        needs_help = efficiency < 70 or active_tasks > len(dept_agents) * 2
        
        recommendations = []
        if needs_help:
            if efficiency < 70:
                recommendations.append("Consider redistributing tasks among agents")
                recommendations.append("Provide additional training for underperforming agents")
            if active_tasks > len(dept_agents) * 2:
                recommendations.append("Reduce task load or add more agents")
                recommendations.append("Prioritize high-impact tasks")
        
        return {
            "department": department,
            "total_agents": len(dept_agents),
            "total_tasks": total_tasks,
            "active_tasks": active_tasks,
            "completed_tasks": completed_tasks,
            "efficiency": round(efficiency, 2),
            "needs_help": needs_help,
            "recommendations": recommendations
        }
    
    async def optimize_agent_roles(self) -> Dict[str, Any]:
        """Optimize agent role assignments based on performance"""
        optimizations = []
        
        for agent in self.agent_manager.agents.values():
            # Analyze agent performance
            success_rate = agent.performance_metrics.get("success_rate", 0)
            tasks_completed = agent.performance_metrics.get("tasks_completed", 0)
            
            if success_rate < 0.7 and tasks_completed > 5:
                # Agent underperforming, suggest role adjustment
                current_capabilities = agent.capabilities
                suggested_capabilities = self._suggest_capability_improvements(current_capabilities)
                
                optimizations.append({
                    "agent_id": agent.agent_id,
                    "agent_name": agent.name,
                    "department": agent.department,
                    "current_success_rate": success_rate,
                    "suggested_improvements": suggested_capabilities,
                    "action": "role_optimization"
                })
        
        return {
            "total_agents_analyzed": len(self.agent_manager.agents),
            "optimizations_needed": len(optimizations),
            "optimizations": optimizations
        }
    
    def _suggest_capability_improvements(self, current_capabilities: List[str]) -> List[str]:
        """Suggest capability improvements for underperforming agents"""
        all_capabilities = []
        for capabilities in self.agent_capabilities.values():
            all_capabilities.extend(capabilities)
        
        # Find capabilities not currently possessed
        missing_capabilities = [cap for cap in all_capabilities if cap not in current_capabilities]
        
        # Return top 3 most valuable missing capabilities
        return missing_capabilities[:3]
    
    def get_decision_history(self) -> List[Dict[str, Any]]:
        """Get history of decisions made"""
        return self.decision_history 