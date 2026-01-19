#!/usr/bin/env python3
"""
Sunflower Hive Mind Architecture for Daena
Connects all agents and departments in a sunflower pattern for optimal communication
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
import torch
import os

class SunflowerHiveMind:
    def __init__(self):
        self.owner_name = "Masoud"
        self.owner_nickname = "Mas"
        self.hive_center = "Daena_Core"
        self.sunflower_layers = 3
        self.agents_per_layer = 8
        self.departments = [
            "Engineering", "Marketing", "Sales", "Operations", 
            "Finance", "Human_Resources", "Legal", "Research"
        ]
        self.councils = [
            "Strategic_Council", "Technical_Council", "Creative_Council", 
            "Financial_Council", "Operational_Council"
        ]
        self.setup_logging()
        self.initialize_hive_structure()
        
        print("🌻 Sunflower Hive Mind Architecture")
        print("=" * 60)
        print(f"👤 Owner: {self.owner_name} ({self.owner_nickname})")
        print(f"🎯 Hive Center: {self.hive_center}")
        print(f"🌻 Sunflower Layers: {self.sunflower_layers}")
        print(f"🤖 Agents per Layer: {self.agents_per_layer}")
        print(f"🏢 Departments: {len(self.departments)}")
        print(f"👥 Councils: {len(self.councils)}")
        print()
    
    def setup_logging(self):
        """Setup logging for hive mind"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/sunflower_hive_mind.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('SunflowerHiveMind')
    
    def initialize_hive_structure(self):
        """Initialize the sunflower hive mind structure"""
        self.hive_structure = {
            "center": {
                "name": self.hive_center,
                "type": "core",
                "connections": [],
                "capabilities": ["ultimate_brain", "decision_making", "coordination"],
                "status": "active"
            },
            "layers": {},
            "departments": {},
            "councils": {},
            "connections": {},
            "communication_patterns": {}
        }
        
        # Initialize sunflower layers
        for layer in range(1, self.sunflower_layers + 1):
            self.hive_structure["layers"][f"layer_{layer}"] = {
                "agents": [],
                "connections": [],
                "radius": layer * 100,
                "angle_offset": 360 / self.agents_per_layer
            }
        
        # Initialize departments
        for dept in self.departments:
            self.hive_structure["departments"][dept] = {
                "agents": [],
                "council": self.get_department_council(dept),
                "connections": [],
                "status": "active",
                "performance_metrics": {}
            }
        
        # Initialize councils
        for council in self.councils:
            self.hive_structure["councils"][council] = {
                "members": [],
                "decisions": [],
                "authority_level": self.get_council_authority(council),
                "status": "active"
            }
    
    def get_department_council(self, department: str) -> str:
        """Get the council responsible for a department"""
        council_mapping = {
            "Engineering": "Technical_Council",
            "Marketing": "Creative_Council", 
            "Sales": "Strategic_Council",
            "Operations": "Operational_Council",
            "Finance": "Financial_Council",
            "Human_Resources": "Operational_Council",
            "Legal": "Strategic_Council",
            "Research": "Technical_Council"
        }
        return council_mapping.get(department, "Strategic_Council")
    
    def get_council_authority(self, council: str) -> int:
        """Get authority level for a council (1-5, 5 being highest)"""
        authority_levels = {
            "Strategic_Council": 5,
            "Technical_Council": 4,
            "Creative_Council": 3,
            "Financial_Council": 4,
            "Operational_Council": 3
        }
        return authority_levels.get(council, 3)
    
    async def create_agent(self, agent_name: str, agent_type: str, capabilities: List[str], 
                          department: str = None, layer: int = 1) -> Dict[str, Any]:
        """Create a new agent in the sunflower hive mind"""
        agent = {
            "name": agent_name,
            "type": agent_type,
            "capabilities": capabilities,
            "department": department,
            "layer": layer,
            "connections": [],
            "status": "active",
            "created_at": datetime.now().isoformat(),
            "performance_metrics": {
                "tasks_completed": 0,
                "success_rate": 1.0,
                "response_time": 0.0,
                "collaboration_score": 0.0
            }
        }
        
        # Add to appropriate layer
        layer_key = f"layer_{layer}"
        if layer_key in self.hive_structure["layers"]:
            self.hive_structure["layers"][layer_key]["agents"].append(agent)
        
        # Add to department if specified
        if department and department in self.hive_structure["departments"]:
            self.hive_structure["departments"][department]["agents"].append(agent)
        
        # Create connections to center and other agents
        await self.create_agent_connections(agent)
        
        self.logger.info(f"Created agent: {agent_name} in {department} department, layer {layer}")
        return agent
    
    async def create_agent_connections(self, agent: Dict[str, Any]):
        """Create connections for an agent in the sunflower pattern"""
        agent_name = agent["name"]
        layer = agent["layer"]
        
        # Connect to center
        center_connection = {
            "from": agent_name,
            "to": self.hive_center,
            "type": "radial",
            "strength": 1.0,
            "bandwidth": "high"
        }
        
        if agent_name not in self.hive_structure["connections"]:
            self.hive_structure["connections"][agent_name] = []
        
        self.hive_structure["connections"][agent_name].append(center_connection)
        
        # Connect to other agents in same layer (sunflower pattern)
        layer_key = f"layer_{layer}"
        if layer_key in self.hive_structure["layers"]:
            layer_agents = self.hive_structure["layers"][layer_key]["agents"]
            
            for other_agent in layer_agents:
                if other_agent["name"] != agent_name:
                    # Calculate angle-based connection strength
                    angle_diff = self.calculate_angle_difference(agent, other_agent)
                    connection_strength = max(0.1, 1.0 - (angle_diff / 180.0))
                    
                    layer_connection = {
                        "from": agent_name,
                        "to": other_agent["name"],
                        "type": "lateral",
                        "strength": connection_strength,
                        "bandwidth": "medium"
                    }
                    
                    self.hive_structure["connections"][agent_name].append(layer_connection)
        
        # Connect to department council
        if agent.get("department"):
            department = agent["department"]
            council = self.get_department_council(department)
            
            council_connection = {
                "from": agent_name,
                "to": council,
                "type": "hierarchical",
                "strength": 0.8,
                "bandwidth": "high"
            }
            
            self.hive_structure["connections"][agent_name].append(council_connection)
    
    def calculate_angle_difference(self, agent1: Dict[str, Any], agent2: Dict[str, Any]) -> float:
        """Calculate angle difference between two agents for connection strength"""
        # Simple hash-based angle calculation
        angle1 = hash(agent1["name"]) % 360
        angle2 = hash(agent2["name"]) % 360
        diff = abs(angle1 - angle2)
        return min(diff, 360 - diff)
    
    async def create_department_agents(self):
        """Create specialized agents for each department"""
        print("🏢 Creating department agents...")
        
        department_agents = {
            "Engineering": [
                ("CodeMaster", "developer", ["coding", "architecture", "optimization"]),
                ("SystemArchitect", "architect", ["system_design", "scalability", "integration"]),
                ("DevOpsEngineer", "devops", ["deployment", "automation", "monitoring"]),
                ("SecurityExpert", "security", ["security", "compliance", "threat_analysis"])
            ],
            "Marketing": [
                ("BrandManager", "brand", ["brand_strategy", "positioning", "messaging"]),
                ("ContentCreator", "content", ["content_creation", "copywriting", "design"]),
                ("SocialMediaManager", "social", ["social_media", "engagement", "analytics"]),
                ("GrowthHacker", "growth", ["growth_strategy", "acquisition", "optimization"])
            ],
            "Sales": [
                ("SalesManager", "sales", ["sales_strategy", "pipeline", "forecasting"]),
                ("AccountExecutive", "account", ["client_management", "negotiation", "closing"]),
                ("SalesDevelopment", "sdr", ["prospecting", "qualification", "outreach"]),
                ("CustomerSuccess", "success", ["onboarding", "retention", "expansion"])
            ],
            "Operations": [
                ("OperationsManager", "ops", ["process_optimization", "efficiency", "coordination"]),
                ("ProjectManager", "project", ["project_management", "timeline", "delivery"]),
                ("QualityAssurance", "qa", ["quality_control", "testing", "standards"]),
                ("SupplyChain", "supply", ["inventory", "logistics", "procurement"])
            ],
            "Finance": [
                ("FinancialAnalyst", "analyst", ["financial_analysis", "modeling", "reporting"]),
                ("BudgetManager", "budget", ["budgeting", "forecasting", "cost_control"]),
                ("InvestmentAdvisor", "investment", ["investment_strategy", "roi", "risk"]),
                ("ComplianceOfficer", "compliance", ["regulatory_compliance", "audit", "risk"])
            ],
            "Human_Resources": [
                ("TalentAcquisition", "recruitment", ["hiring", "sourcing", "interviewing"]),
                ("CultureManager", "culture", ["culture_building", "engagement", "wellness"]),
                ("LearningDevelopment", "learning", ["training", "development", "skills"]),
                ("PerformanceManager", "performance", ["performance_management", "feedback", "reviews"])
            ],
            "Legal": [
                ("LegalCounsel", "legal", ["legal_advice", "contracts", "compliance"]),
                ("IntellectualProperty", "ip", ["patents", "trademarks", "copyright"]),
                ("RegulatoryExpert", "regulatory", ["regulations", "licensing", "compliance"]),
                ("RiskManager", "risk", ["risk_assessment", "mitigation", "insurance"])
            ],
            "Research": [
                ("ResearchScientist", "research", ["research", "analysis", "innovation"]),
                ("DataScientist", "data", ["data_analysis", "ml", "ai"]),
                ("MarketResearcher", "market", ["market_research", "trends", "insights"]),
                ("InnovationLead", "innovation", ["innovation", "r&d", "prototyping"])
            ]
        }
        
        created_agents = []
        
        for department, agents in department_agents.items():
            print(f"🏢 Creating {department} agents...")
            
            for agent_name, agent_type, capabilities in agents:
                agent = await self.create_agent(
                    agent_name=agent_name,
                    agent_type=agent_type,
                    capabilities=capabilities,
                    department=department,
                    layer=1
                )
                created_agents.append(agent)
        
        print(f"✅ Created {len(created_agents)} department agents")
        return created_agents
    
    async def create_council_members(self):
        """Create council members for decision making"""
        print("👥 Creating council members...")
        
        council_members = {
            "Strategic_Council": [
                ("StrategicAdvisor", "strategy", ["strategic_planning", "vision", "goals"]),
                ("MarketAnalyst", "market", ["market_analysis", "competitive_intelligence", "trends"]),
                ("BusinessArchitect", "business", ["business_architecture", "transformation", "optimization"])
            ],
            "Technical_Council": [
                ("ChiefTechnologyOfficer", "cto", ["technology_strategy", "architecture", "innovation"]),
                ("LeadArchitect", "architect", ["system_architecture", "design_patterns", "scalability"]),
                ("SecurityChief", "security", ["security_strategy", "compliance", "risk_management"])
            ],
            "Creative_Council": [
                ("CreativeDirector", "creative", ["creative_direction", "brand_identity", "design"]),
                ("ContentStrategist", "content", ["content_strategy", "storytelling", "engagement"]),
                ("InnovationDesigner", "innovation", ["design_thinking", "innovation", "user_experience"])
            ],
            "Financial_Council": [
                ("ChiefFinancialOfficer", "cfo", ["financial_strategy", "planning", "risk"]),
                ("InvestmentDirector", "investment", ["investment_strategy", "capital_allocation", "roi"]),
                ("FinancialController", "controller", ["financial_control", "reporting", "compliance"])
            ],
            "Operational_Council": [
                ("ChiefOperatingOfficer", "coo", ["operational_strategy", "efficiency", "execution"]),
                ("ProcessOptimizer", "process", ["process_optimization", "automation", "quality"]),
                ("ResourceManager", "resources", ["resource_allocation", "capacity_planning", "coordination"])
            ]
        }
        
        created_members = []
        
        for council, members in council_members.items():
            print(f"👥 Creating {council} members...")
            
            for member_name, member_type, capabilities in members:
                member = await self.create_agent(
                    agent_name=member_name,
                    agent_type=member_type,
                    capabilities=capabilities,
                    department=None,
                    layer=2  # Council members in layer 2
                )
                
                # Add to council
                self.hive_structure["councils"][council]["members"].append(member)
                created_members.append(member)
        
        print(f"✅ Created {len(created_members)} council members")
        return created_members
    
    async def establish_communication_patterns(self):
        """Establish optimal communication patterns in the sunflower hive mind"""
        print("🌻 Establishing sunflower communication patterns...")
        
        # Radial communication (center to all agents)
        self.hive_structure["communication_patterns"]["radial"] = {
            "type": "center_outward",
            "pattern": "star",
            "efficiency": "high",
            "latency": "low"
        }
        
        # Lateral communication (agents in same layer)
        self.hive_structure["communication_patterns"]["lateral"] = {
            "type": "peer_to_peer",
            "pattern": "mesh",
            "efficiency": "medium",
            "latency": "medium"
        }
        
        # Hierarchical communication (agents to councils)
        self.hive_structure["communication_patterns"]["hierarchical"] = {
            "type": "upward_downward",
            "pattern": "tree",
            "efficiency": "high",
            "latency": "low"
        }
        
        # Cross-department communication
        self.hive_structure["communication_patterns"]["cross_department"] = {
            "type": "inter_department",
            "pattern": "network",
            "efficiency": "medium",
            "latency": "medium"
        }
        
        print("✅ Communication patterns established")
    
    async def activate_hive_mind(self):
        """Activate the complete sunflower hive mind"""
        print("🚀 Activating Sunflower Hive Mind...")
        
        try:
            # Create department agents
            await self.create_department_agents()
            
            # Create council members
            await self.create_council_members()
            
            # Establish communication patterns
            await self.establish_communication_patterns()
            
            # Save hive mind structure
            self.save_hive_mind_structure()
            
            print("🎉 Sunflower Hive Mind Activated!")
            print(f"🤖 Total Agents: {self.count_total_agents()}")
            print(f"🏢 Departments: {len(self.departments)}")
            print(f"👥 Councils: {len(self.councils)}")
            print(f"🔗 Connections: {self.count_total_connections()}")
            print("🌻 Ready for ultimate brain integration!")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error activating hive mind: {e}")
            print(f"❌ Failed to activate hive mind: {e}")
            return False
    
    def count_total_agents(self) -> int:
        """Count total agents in the hive mind"""
        total = 0
        for layer_key, layer_data in self.hive_structure["layers"].items():
            total += len(layer_data["agents"])
        return total
    
    def count_total_connections(self) -> int:
        """Count total connections in the hive mind"""
        total = 0
        for agent_connections in self.hive_structure["connections"].values():
            total += len(agent_connections)
        return total
    
    def save_hive_mind_structure(self):
        """Save the hive mind structure to file"""
        try:
            os.makedirs("data", exist_ok=True)
            with open("data/sunflower_hive_mind_structure.json", "w") as f:
                json.dump(self.hive_structure, f, indent=2)
            print("💾 Hive mind structure saved")
        except Exception as e:
            self.logger.error(f"Error saving hive mind structure: {e}")
    
    async def get_agent_network(self, agent_name: str) -> Dict[str, Any]:
        """Get the network of connections for a specific agent"""
        if agent_name in self.hive_structure["connections"]:
            return {
                "agent": agent_name,
                "connections": self.hive_structure["connections"][agent_name],
                "total_connections": len(self.hive_structure["connections"][agent_name])
            }
        return {"agent": agent_name, "connections": [], "total_connections": 0}
    
    async def get_department_network(self, department: str) -> Dict[str, Any]:
        """Get the network of a specific department"""
        if department in self.hive_structure["departments"]:
            dept_data = self.hive_structure["departments"][department]
            return {
                "department": department,
                "agents": dept_data["agents"],
                "council": dept_data["council"],
                "total_agents": len(dept_data["agents"])
            }
        return {"department": department, "agents": [], "council": None, "total_agents": 0}

# Global instance
sunflower_hive = None

async def initialize_sunflower_hive():
    """Initialize the sunflower hive mind globally"""
    global sunflower_hive
    sunflower_hive = SunflowerHiveMind()
    return sunflower_hive

async def get_sunflower_hive():
    """Get the global sunflower hive mind instance"""
    global sunflower_hive
    if sunflower_hive is None:
        sunflower_hive = await initialize_sunflower_hive()
    return sunflower_hive 