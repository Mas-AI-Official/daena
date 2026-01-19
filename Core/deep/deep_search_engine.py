#!/usr/bin/env python3
"""
Deep Search Engine for Daena Core
Provides recursive analysis, project planning, and strategic roadmap building
"""

import os
import json
import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass

# Import existing Core components
from Core.llm.enhanced_local_brain_integration import get_enhanced_brain
from Core.llm.voting.vote_engine import vote_on_responses
from Core.llm.fallback.fallback_strategy_kernel import fallback_handler

@dataclass
class SearchBreadcrumb:
    step: int
    query: str
    response_summary: str
    models_used: List[str]
    timestamp: str

@dataclass
class DeepSearchResult:
    query: str
    depth: int
    rounds: List[Dict[str, Any]]
    final_analysis: str
    breadcrumbs: List[SearchBreadcrumb]
    project_roadmap: Optional[str] = None
    strategic_insights: Optional[List[str]] = None
    timestamp: str = ""

class DeepSearchEngine:
    def __init__(self):
        self.enhanced_brain = None
        self.search_memory = []
        self.project_plans = []
        self.research_breadcrumbs = []
        self.setup_logging()
        
    def setup_logging(self):
        """Setup logging for deep search"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/deep_search.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('DeepSearchEngine')
    
    async def initialize(self):
        """Initialize the deep search engine"""
        self.enhanced_brain = await get_enhanced_brain()
        print("🔍 Deep Search Engine Initialized")
        print("=" * 40)
    
    async def deep_search_analysis(self, query: str, depth: int = 3, search_type: str = "general") -> DeepSearchResult:
        """
        Perform deep search analysis with recursive LLM querying
        """
        if not self.enhanced_brain:
            await self.initialize()
        
        self.logger.info(f"🔍 Starting deep search for: {query}")
        print(f"🔍 Daena starting deep search analysis...")
        print(f"📝 Query: {query}")
        print(f"🔢 Depth: {depth}")
        print(f"🎯 Type: {search_type}")
        
        search_result = DeepSearchResult(
            query=query,
            depth=depth,
            rounds=[],
            final_analysis="",
            breadcrumbs=[],
            timestamp=datetime.now().isoformat()
        )
        
        current_query = query
        
        for round_num in range(depth):
            self.logger.info(f"🔄 Deep search round {round_num + 1}/{depth}")
            print(f"🔄 Round {round_num + 1}/{depth}: {current_query[:80]}...")
            
            # Get consensus response from enhanced brain
            consensus_result = await self.enhanced_brain.consensus_decision(
                current_query, 
                use_deep_search=True
            )
            
            # Store round results
            round_result = {
                "round": round_num + 1,
                "query": current_query,
                "response": consensus_result['decision'],
                "models_used": consensus_result['models_used'],
                "confidence": consensus_result['confidence'],
                "timestamp": datetime.now().isoformat()
            }
            
            search_result.rounds.append(round_result)
            
            # Create breadcrumb
            breadcrumb = SearchBreadcrumb(
                step=round_num + 1,
                query=current_query,
                response_summary=consensus_result['decision'][:200] + "...",
                models_used=consensus_result['models_used'],
                timestamp=datetime.now().isoformat()
            )
            search_result.breadcrumbs.append(breadcrumb)
            
            # Generate follow-up query for next round
            if round_num < depth - 1:
                follow_up_query = await self._generate_follow_up_query(
                    consensus_result['decision'], 
                    query, 
                    round_num + 1, 
                    depth,
                    search_type
                )
                current_query = follow_up_query
                
                self.logger.info(f"📝 Follow-up query: {current_query}")
        
        # Generate final synthesis
        final_analysis = await self._generate_final_synthesis(search_result, search_type)
        search_result.final_analysis = final_analysis
        
        # Store in memory
        self.search_memory.append(search_result)
        self._save_search_memory()
        
        self.logger.info(f"✅ Deep search completed. Final analysis generated.")
        print(f"✅ Deep search completed!")
        print(f"📊 Rounds processed: {len(search_result.rounds)}")
        print(f"🧠 Models used: {', '.join(set([m for r in search_result.rounds for m in r['models_used']]))}")
        
        return search_result
    
    async def _generate_follow_up_query(self, current_response: str, original_query: str, 
                                      round_num: int, total_rounds: int, search_type: str) -> str:
        """Generate follow-up query for next round"""
        
        follow_up_prompt = f"""
        Based on this analysis: {current_response}
        
        Original Query: {original_query}
        Round: {round_num} of {total_rounds}
        Search Type: {search_type}
        
        Generate a follow-up question to deepen the analysis. Focus on:
        """
        
        if search_type == "project_planning":
            follow_up_prompt += """
        1. Technical feasibility and implementation details
        2. Resource requirements and timeline
        3. Risk assessment and mitigation strategies
        4. Market analysis and competitive positioning
        5. Success metrics and KPIs
        """
        elif search_type == "strategic_analysis":
            follow_up_prompt += """
        1. Strategic implications and long-term impact
        2. Competitive advantages and market positioning
        3. Resource allocation and investment requirements
        4. Risk assessment and contingency planning
        5. Implementation roadmap and milestones
        """
        else:  # general
            follow_up_prompt += """
        1. Unanswered aspects and gaps in analysis
        2. Potential risks or opportunities
        3. Strategic implications and next steps
        4. Implementation considerations
        5. Additional research areas
        """
        
        follow_up_prompt += """
        
        Provide only the follow-up question (max 100 words):
        """
        
        # Use enhanced brain to generate follow-up
        result = await self.enhanced_brain.make_decision(follow_up_prompt)
        return result['decision'].strip()
    
    async def _generate_final_synthesis(self, search_result: DeepSearchResult, search_type: str) -> str:
        """Generate final synthesis of deep search results"""
        
        synthesis_prompt = f"""
        Synthesize the following deep search analysis into a comprehensive report:
        
        Original Query: {search_result.query}
        Search Type: {search_type}
        Analysis Rounds: {len(search_result.rounds)}
        
        Analysis Rounds:
        {json.dumps([{
            'round': r['round'],
            'query': r['query'],
            'response': r['response'],
            'models_used': r['models_used']
        } for r in search_result.rounds], indent=2)}
        
        Provide a structured final analysis with:
        """
        
        if search_type == "project_planning":
            synthesis_prompt += """
        1. Executive Summary
        2. Project Overview and Objectives
        3. Market Analysis and Opportunity Assessment
        4. Technical Feasibility and Requirements
        5. Resource Requirements and Timeline
        6. Risk Assessment and Mitigation
        7. Success Metrics and KPIs
        8. Implementation Roadmap
        9. Recommendations and Next Steps
        """
        elif search_type == "strategic_analysis":
            synthesis_prompt += """
        1. Executive Summary
        2. Strategic Context and Background
        3. Key Findings and Insights
        4. Strategic Implications
        5. Competitive Analysis
        6. Risk Assessment
        7. Strategic Recommendations
        8. Implementation Plan
        9. Success Metrics
        """
        else:  # general
            synthesis_prompt += """
        1. Executive Summary
        2. Key Findings
        3. Detailed Analysis
        4. Strategic Recommendations
        5. Risk Assessment
        6. Implementation Considerations
        7. Next Steps
        """
        
        # Use enhanced brain to generate synthesis
        result = await self.enhanced_brain.make_decision(synthesis_prompt)
        return result['decision']
    
    async def project_planning_mode(self, project_idea: str) -> Dict[str, Any]:
        """
        Enter project planning mode with comprehensive analysis
        """
        if not self.enhanced_brain:
            await self.initialize()
        
        self.logger.info(f"📋 Entering project planning mode for: {project_idea}")
        print(f"📋 Daena entering project planning mode...")
        print(f"💡 Project: {project_idea}")
        
        planning_stages = [
            "market_analysis",
            "technical_feasibility", 
            "resource_requirements",
            "timeline_development",
            "risk_assessment",
            "success_metrics"
        ]
        
        planning_results = {
            "project": project_idea,
            "stages": {},
            "roadmap": "",
            "timestamp": datetime.now().isoformat()
        }
        
        for stage in planning_stages:
            self.logger.info(f"📊 Planning stage: {stage}")
            print(f"📊 Stage: {stage}")
            
            stage_prompt = self._get_stage_prompt(stage, project_idea)
            stage_result = await self.enhanced_brain.make_decision(stage_prompt)
            
            planning_results["stages"][stage] = {
                "analysis": stage_result['decision'],
                "models_used": stage_result['models_used'],
                "confidence": stage_result['confidence'],
                "timestamp": datetime.now().isoformat()
            }
        
        # Generate comprehensive roadmap
        roadmap_prompt = f"""
        Create a comprehensive project roadmap based on this analysis:
        
        Project: {project_idea}
        
        Stage Analysis:
        {json.dumps(planning_results['stages'], indent=2)}
        
        Provide a detailed implementation roadmap with:
        1. Phase 1: Foundation (Months 1-3)
        2. Phase 2: Development (Months 4-9)
        3. Phase 3: Launch (Months 10-12)
        4. Success Metrics & KPIs
        5. Resource Allocation
        6. Risk Mitigation Strategies
        7. Timeline and Milestones
        """
        
        roadmap_result = await self.enhanced_brain.make_decision(roadmap_prompt)
        planning_results["roadmap"] = roadmap_result['decision']
        
        # Store project plan
        self.project_plans.append(planning_results)
        self._save_project_plans()
        
        self.logger.info(f"✅ Project planning completed. Roadmap generated.")
        print(f"✅ Project planning completed!")
        print(f"📋 Stages analyzed: {len(planning_results['stages'])}")
        print(f"🗺️ Roadmap generated: {len(planning_results['roadmap'])} characters")
        
        return planning_results
    
    def _get_stage_prompt(self, stage: str, project: str) -> str:
        """Get stage-specific prompt for project planning"""
        stage_prompts = {
            "market_analysis": f"Analyze the market opportunity for: {project}. Consider market size, competition, customer segments, growth potential, and market trends.",
            "technical_feasibility": f"Assess technical feasibility for: {project}. Consider technology requirements, complexity, implementation challenges, and technical risks.",
            "resource_requirements": f"Determine resource requirements for: {project}. Consider team size, budget, infrastructure, timeline, and external dependencies.",
            "timeline_development": f"Develop a realistic timeline for: {project}. Consider dependencies, milestones, critical path, and potential bottlenecks.",
            "risk_assessment": f"Identify and assess risks for: {project}. Consider technical, market, financial, operational, and regulatory risks.",
            "success_metrics": f"Define success metrics and KPIs for: {project}. Consider both leading and lagging indicators, and measurement methods."
        }
        return stage_prompts.get(stage, f"Analyze {stage} for project: {project}")
    
    async def strategic_roadmap_builder(self, strategic_goal: str) -> Dict[str, Any]:
        """
        Build strategic roadmap for long-term goals
        """
        if not self.enhanced_brain:
            await self.initialize()
        
        self.logger.info(f"🗺️ Building strategic roadmap for: {strategic_goal}")
        print(f"🗺️ Daena building strategic roadmap...")
        print(f"🎯 Goal: {strategic_goal}")
        
        # Perform deep search for strategic analysis
        deep_search_result = await self.deep_search_analysis(
            strategic_goal, 
            depth=4, 
            search_type="strategic_analysis"
        )
        
        # Build strategic roadmap
        roadmap_prompt = f"""
        Based on this strategic analysis, create a comprehensive strategic roadmap:
        
        Strategic Goal: {strategic_goal}
        
        Analysis: {deep_search_result.final_analysis}
        
        Create a strategic roadmap with:
        1. Vision and Mission Alignment
        2. Strategic Pillars and Objectives
        3. 3-Year Strategic Plan
        4. Annual Goals and Milestones
        5. Resource Requirements and Investment
        6. Risk Management Strategy
        7. Success Metrics and KPIs
        8. Implementation Timeline
        9. Governance and Oversight
        """
        
        roadmap_result = await self.enhanced_brain.make_decision(roadmap_prompt)
        
        strategic_roadmap = {
            "goal": strategic_goal,
            "analysis": deep_search_result.final_analysis,
            "roadmap": roadmap_result['decision'],
            "breadcrumbs": [b.__dict__ for b in deep_search_result.breadcrumbs],
            "timestamp": datetime.now().isoformat()
        }
        
        return strategic_roadmap
    
    def _save_search_memory(self):
        """Save search memory to file"""
        memory_path = 'logs/deep_search_memory.jsonl'
        os.makedirs('logs', exist_ok=True)
        
        with open(memory_path, 'w') as f:
            for search in self.search_memory:
                f.write(json.dumps(search.__dict__, default=str) + '\n')
    
    def _save_project_plans(self):
        """Save project plans to file"""
        plans_path = 'logs/project_plans.jsonl'
        os.makedirs('logs', exist_ok=True)
        
        with open(plans_path, 'w') as f:
            for plan in self.project_plans:
                f.write(json.dumps(plan) + '\n')
    
    def get_search_history(self) -> List[Dict[str, Any]]:
        """Get search history"""
        return [search.__dict__ for search in self.search_memory]
    
    def get_project_plans(self) -> List[Dict[str, Any]]:
        """Get project plans history"""
        return self.project_plans

# Global instance for easy access
deep_search_engine = None

async def initialize_deep_search_engine():
    """Initialize the deep search engine globally"""
    global deep_search_engine
    deep_search_engine = DeepSearchEngine()
    await deep_search_engine.initialize()
    return deep_search_engine

async def get_deep_search_engine():
    """Get the global deep search engine instance"""
    global deep_search_engine
    if deep_search_engine is None:
        deep_search_engine = await initialize_deep_search_engine()
    return deep_search_engine 