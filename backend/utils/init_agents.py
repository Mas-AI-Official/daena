"""
Initialize all 48 agents in the sunflower registry
8 Departments × 6 Agents = 48 Total Agents
"""
from backend.utils.sunflower_registry import sunflower_registry
import logging

logger = logging.getLogger(__name__)

# Agent roles for each department (6 per department)
AGENT_ROLES = ["Advisor A", "Advisor B", "Scout Internal", "Scout External", "Synth", "Executor"]

# Department data
DEPARTMENTS = [
    {
        "id": "engineering",
        "name": "Engineering",
        "color": "#4169E1",
        "description": "Software development and technical infrastructure"
    },
    {
        "id": "product",
        "name": "Product",
        "color": "#FF1493",
        "description": "Product strategy and roadmap"
    },
    {
        "id": "sales",
        "name": "Sales",
        "color": "#FF8C00",
        "description": "Revenue generation and client acquisition"
    },
    {
        "id": "marketing",
        "name": "Marketing",
        "color": "#FF8C00",
        "description": "Brand awareness and customer engagement"
    },
    {
        "id": "finance",
        "name": "Finance",
        "color": "#00CED1",
        "description": "Financial planning and budget management"
    },
    {
        "id": "hr",
        "name": "HR",
        "color": "#FF1493",
        "description": "Human resources and talent management"
    },
    {
        "id": "legal",
        "name": "Legal",
        "color": "#9370DB",
        "description": "Legal compliance and contracts"
    },
    {
        "id": "customer",
        "name": "Customer",
        "color": "#32CD32",
        "description": "Customer success and support"
    }
]

# Agent names (48 unique names)
AGENT_NAMES = {
    "engineering": ["Alex CodeMaster", "Emma BuildPro", "Noah DevOps", "Sophia TechLead", "Liam Backend", "Olivia Frontend"],
    "product": ["Ava Strategy", "Ethan Roadmap", "Mia ProductViz", "Lucas Innovator", "Amelia UXMaster", "Mason Metrics"],
    "sales": ["Morgan Closer", "Charlotte Deal", "Benjamin Revenue", "Harper Pipeline", "Logan ClientPro", "Ella Convert"],
    "marketing": ["DaVinci Creative", "Sofia Brand", "Jackson Campaign", "Aria Growth", "Carter SEO", "Layla Social"],
    "finance": ["Penny Wise", "Sebastian Budget", "Chloe Analytics", "Oliver Forecast", "Zoe Accounting", "Henry Capital"],
    "hr": ["Scarlett People", "Daniel Culture", "Grace Talent", "Matthew Recruiter", "Lily Learning", "Owen Benefits"],
    "legal": ["Sarah Shield", "William Contracts", "Victoria Compliance", "James Policy", "Hannah IP", "Ryan Risk"],
    "customer": ["Fix-It Felix", "Evelyn Support", "Michael Success", "Abigail Advocate", "Alexander Solutions", "Emily Happiness"]
}

def initialize_all_agents():
    """Initialize all 48 agents in the sunflower registry"""
    try:
        # First, register all 8 departments
        for idx, dept in enumerate(DEPARTMENTS):
            try:
                sunflower_registry.register_department(
                    dept_id=dept["id"],
                    name=dept["name"],
                    sunflower_index=idx + 1,
                    description=dept["description"],
                    color=dept["color"]
                )
                logger.info(f"✅ Registered department: {dept['name']}")
            except ValueError as e:
                logger.debug(f"Department {dept['name']} already registered: {e}")
        
        # Then, register all 48 agents (6 per department)
        agent_counter = 1
        for dept in DEPARTMENTS:
            dept_id = dept["id"]
            agent_names = AGENT_NAMES.get(dept_id, [])
            
            for idx, role in enumerate(AGENT_ROLES):
                agent_name = agent_names[idx] if idx < len(agent_names) else f"{dept['name']} {role}"
                agent_id = f"{dept_id}_{role.lower().replace(' ', '_')}_{agent_counter}"
                
                try:
                    sunflower_registry.register_agent(
                        agent_id=agent_id,
                        name=agent_name,
                        role=role,
                        department_id=dept_id
                    )
                    logger.info(f"✅ Registered agent {agent_counter}/48: {agent_name} ({dept['name']} - {role})")
                    agent_counter += 1
                except ValueError as e:
                    logger.debug(f"Agent {agent_name} already registered: {e}")
                    agent_counter += 1
        
        logger.info(f"🎉 Successfully initialized all 48 agents across 8 departments!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize agents: {e}")
        return False

# Auto-initialize when imported
initialize_all_agents()
