"""
⚠️ CORE FILE — DO NOT DELETE OR REWRITE
Changes allowed ONLY via extension modules.

Sunflower registry for Daena's organizational structure.

CRITICAL: This is the canonical agent and department registry (8×6 structure).
Only patch specific functions. Never replace the entire class or remove registry initialization.
"""
from typing import Dict, List, Optional, Tuple
import logging
from .sunflower import sunflower_xy, get_neighbor_indices

logger = logging.getLogger(__name__)

class SunflowerRegistry:
    """Registry for managing sunflower-based organizational structure."""
    
    def __init__(self):
        self.departments: Dict[str, Dict] = {}
        self.agents: Dict[str, Dict] = {}
        self.projects: Dict[str, Dict] = {}
        self.cells: Dict[str, Dict] = {}
        self.adjacency_cache: Dict[str, List[str]] = {}
        
    def register_department(self, dept_id: str, name: str, sunflower_index: int, 
                          description: str = "", color: str = "#0066cc") -> Dict:
        """Register a department with sunflower coordinates."""
        if dept_id in self.departments:
            raise ValueError(f"Department {dept_id} already registered")
            
        # Generate sunflower coordinates
        x, y = sunflower_xy(sunflower_index, n=8, scale=100)
        
        # Format: D{n} where n is sunflower_index
        cell_id = f"D{sunflower_index}"
        
        dept_data = {
            "id": dept_id,
            "name": name,
            "sunflower_index": sunflower_index,
            "coordinates": {"x": x, "y": y},
            "description": description,
            "color": color,
            "agents": [],
            "projects": [],
            "cell_id": cell_id
        }
        
        self.departments[dept_id] = dept_data
        self.cells[cell_id] = dept_data
        
        return dept_data
        
    def register_agent(self, agent_id: str, name: str, role: str, 
                      department_id: str, sunflower_index: int = None) -> Dict:
        """Register an agent with sunflower coordinates."""
        if agent_id in self.agents:
            raise ValueError(f"Agent {agent_id} already registered")
            
        if department_id not in self.departments:
            raise ValueError(f"Department {department_id} not found")
            
        dept = self.departments[department_id]
        dept_sunflower = dept["sunflower_index"]
        
        # Generate agent sunflower index relative to department
        if sunflower_index is None:
            # Auto-assign based on department position
            agent_count = len(dept["agents"])
            sunflower_index = dept_sunflower * 10 + agent_count + 1
            
        # Generate coordinates relative to department
        x, y = sunflower_xy(sunflower_index, n=8, scale=20)
        dept_x, dept_y = dept["coordinates"]["x"], dept["coordinates"]["y"]
        
        # Format: A{role} for agent cell ID
        cell_id = f"A{role}"
        
        agent_data = {
            "id": agent_id,
            "name": name,
            "role": role,
            "department_id": department_id,
            "sunflower_index": sunflower_index,
            "coordinates": {
                "x": dept_x + x,
                "y": dept_y + y,
                "relative_x": x,
                "relative_y": y
            },
            "cell_id": cell_id
        }
        
        self.agents[agent_id] = agent_data
        self.cells[cell_id] = agent_data
        
        # Add to department
        dept["agents"].append(agent_id)
        
        return agent_data
    
    def register_project(self, project_id: str, name: str, department_id: str,
                        sunflower_index: int = None) -> Dict:
        """Register a project with sunflower coordinates."""
        if project_id in self.projects:
            raise ValueError(f"Project {project_id} already registered")
            
        if department_id not in self.departments:
            raise ValueError(f"Department {department_id} not found")
            
        dept = self.departments[department_id]
        dept_sunflower = dept["sunflower_index"]
        
        # Generate project sunflower index relative to department
        if sunflower_index is None:
            # Auto-assign based on department position
            project_count = len(dept.get("projects", []))
            sunflower_index = dept_sunflower * 100 + project_count + 1
            
        # Generate coordinates relative to department
        x, y = sunflower_xy(sunflower_index, n=8, scale=30)
        dept_x, dept_y = dept["coordinates"]["x"], dept["coordinates"]["y"]
        
        # Format: C{x} for project cell ID
        cell_id = f"C{project_id}"
        
        project_data = {
            "id": project_id,
            "name": name,
            "department_id": department_id,
            "sunflower_index": sunflower_index,
            "coordinates": {
                "x": dept_x + x,
                "y": dept_y + y,
                "relative_x": x,
                "relative_y": y
            },
            "cell_id": cell_id,
            "status": "active"
        }
        
        self.projects[project_id] = project_data
        self.cells[cell_id] = project_data
        
        # Add to department
        if "projects" not in dept:
            dept["projects"] = []
        dept["projects"].append(project_id)
        
        return project_data
        
    def get_neighbors(self, cell_id: str, max_neighbors: int = 6) -> List[str]:
        """Get neighboring cells for a given cell."""
        if cell_id not in self.adjacency_cache:
            # Calculate neighbors based on sunflower coordinates
            if cell_id in self.cells:
                cell = self.cells[cell_id]
                if "sunflower_index" in cell:
                    # For departments, find neighboring departments
                    if cell_id.startswith("D"):
                        dept_indices = [dept["sunflower_index"] for dept in self.departments.values()]
                        neighbor_indices = get_neighbor_indices(
                            cell["sunflower_index"], 
                            len(dept_indices), 
                            max_neighbors
                        )
                        neighbors = [f"D{idx}" for idx in neighbor_indices]
                    else:
                        # For agents/projects, find neighbors within department
                        dept_id = cell.get("department_id")
                        if dept_id and dept_id in self.departments:
                            dept = self.departments[dept_id]
                            dept_agents = [self.agents[aid] for aid in dept["agents"] if aid in self.agents]
                            dept_projects = [self.projects[pid] for pid in dept.get("projects", []) if pid in self.projects]
                            
                            all_cells = dept_agents + dept_projects
                            cell_indices = [c["sunflower_index"] for c in all_cells]
                            
                            if cell["sunflower_index"] in cell_indices:
                                idx = cell_indices.index(cell["sunflower_index"])
                                neighbor_indices = get_neighbor_indices(
                                    idx + 1, 
                                    len(cell_indices), 
                                    max_neighbors
                                )
                                neighbors = [all_cells[idx-1]["cell_id"] for idx in neighbor_indices if idx > 0 and idx <= len(all_cells)]
                            else:
                                neighbors = []
                        else:
                            neighbors = []
                    self.adjacency_cache[cell_id] = neighbors
                else:
                    self.adjacency_cache[cell_id] = []
            else:
                self.adjacency_cache[cell_id] = []
        
        return self.adjacency_cache[cell_id]
    
    def get_department_by_id(self, dept_id: str) -> Optional[Dict]:
        """Get department by ID."""
        return self.departments.get(dept_id)
    
    def get_agent_by_id(self, agent_id: str) -> Optional[Dict]:
        """Get agent by ID."""
        return self.agents.get(agent_id)
    
    def get_project_by_id(self, project_id: str) -> Optional[Dict]:
        """Get project by ID."""
        return self.projects.get(project_id)
    
    def get_cell_by_id(self, cell_id: str) -> Optional[Dict]:
        """Get cell by ID (department, agent, or project)."""
        return self.cells.get(cell_id)
    
    def get_department_agents(self, dept_id: str) -> List[Dict]:
        """Get all agents for a department."""
        if dept_id not in self.departments:
            return []
        return [self.agents[aid] for aid in self.departments[dept_id]["agents"] if aid in self.agents]
    
    def get_department_projects(self, dept_id: str) -> List[Dict]:
        """Get all projects for a department."""
        if dept_id not in self.departments:
            return []
        return [self.projects[pid] for pid in self.departments[dept_id].get("projects", []) if pid in self.projects]
    
    def rebuild_adjacency(self):
        """Rebuild adjacency cache for all cells."""
        self.adjacency_cache.clear()
        for cell_id in self.cells:
            self.get_neighbors(cell_id)
    
    def get_stats(self) -> Dict:
        """Get registry statistics."""
        return {
            "departments": len(self.departments),
            "agents": len(self.agents),
            "projects": len(self.projects),
            "cells": len(self.cells),
            "adjacency_cache_size": len(self.adjacency_cache)
        }
    
    def populate_from_database(self, db_session):
        """Populate the sunflower registry from database data."""
        try:
            from backend.database import Department, Agent
            
            # Clear existing data
            self.departments.clear()
            self.agents.clear()
            self.cells.clear()
            self.adjacency_cache.clear()
            
            # Get all departments
            db_departments = db_session.query(Department).all()
            for db_dept in db_departments:
                try:
                    self.register_department(
                        db_dept.slug,
                        db_dept.name,
                        db_dept.sunflower_index,
                        db_dept.description or "",
                        db_dept.color or "#0066cc"
                    )
                    logger.info(f"Registered department: {db_dept.name}")
                except ValueError as e:
                    logger.debug(f"Department {db_dept.name} already registered: {e}")
            
            # Get all agents - handle missing columns gracefully
            try:
                db_agents = db_session.query(Agent).all()
            except Exception as e:
                # If columns are missing, try to add them or query without them
                if "no such column" in str(e).lower() or "tenant_id" in str(e) or "project_id" in str(e):
                    logger.warning("⚠️ Database columns missing - attempting to fix...")
                    try:
                        # Try to add missing columns
                        from sqlalchemy import text
                        error_str = str(e).lower()
                        
                        if "tenant_id" in error_str and "project_id" not in error_str:
                            try:
                                db_session.execute(text("ALTER TABLE agents ADD COLUMN tenant_id VARCHAR(100)"))
                                db_session.commit()
                                logger.info("✅ tenant_id column added")
                            except Exception as fix_error:
                                if "duplicate column" not in str(fix_error).lower():
                                    logger.warning(f"⚠️ Could not add tenant_id: {fix_error}")
                        
                        if "project_id" in error_str:
                            try:
                                db_session.execute(text("ALTER TABLE agents ADD COLUMN project_id INTEGER"))
                                db_session.commit()
                                logger.info("✅ project_id column added")
                            except Exception as fix_error:
                                if "duplicate column" not in str(fix_error).lower():
                                    logger.warning(f"⚠️ Could not add project_id: {fix_error}")
                        
                        # Retry query
                        db_agents = db_session.query(Agent).all()
                    except Exception as fix_error:
                        logger.warning(f"⚠️ Could not fix columns: {fix_error}")
                        # Query without problematic columns by selecting specific columns
                        from sqlalchemy import text
                        db_agents = []
                        # Get column list first
                        result = db_session.execute(text("PRAGMA table_info(agents)"))
                        available_columns = [row[1] for row in result]
                        
                        # Build SELECT query with only available columns
                        select_cols = []
                        for col in ["id", "name", "department", "department_id", "status", "type", "role", 
                                   "capabilities", "description", "is_active", "sunflower_index", "cell_id", 
                                   "brain_model_id", "training_status", "performance_score", "created_at", "updated_at"]:
                            if col in available_columns:
                                select_cols.append(f"agents.{col}")
                        
                        # Add optional columns if they exist
                        if "tenant_id" in available_columns:
                            select_cols.append("agents.tenant_id")
                        if "project_id" in available_columns:
                            select_cols.append("agents.project_id")
                        
                        query = f"SELECT {', '.join(select_cols)} FROM agents"
                        result = db_session.execute(text(query))
                        
                        for row in result:
                            # Create a simple object with the row data
                            class AgentRow:
                                def __init__(self, row_data, col_names):
                                    for i, col_name in enumerate(col_names):
                                        setattr(self, col_name, row_data[i])
                                    # Set defaults for missing columns
                                    if not hasattr(self, 'tenant_id'):
                                        self.tenant_id = None
                                    if not hasattr(self, 'project_id'):
                                        self.project_id = None
                            
                            db_agents.append(AgentRow(row, [col.replace('agents.', '') for col in select_cols]))
                        logger.info("✅ Queried agents with available columns only")
                else:
                    raise
            
            for db_agent in db_agents:
                try:
                    self.register_agent(
                        db_agent.id,
                        db_agent.name,
                        db_agent.role or "specialist",
                        db_agent.department,
                        db_agent.sunflower_index
                    )
                    logger.info(f"Registered agent: {db_agent.name}")
                except ValueError as e:
                    logger.debug(f"Agent {db_agent.name} already registered: {e}")
            
            # Rebuild adjacency
            self.rebuild_adjacency()
            logger.info(f"Sunflower registry populated: {len(self.departments)} departments, {len(self.agents)} agents")
            
        except Exception as e:
            logger.exception(f"Error populating sunflower registry: {e}")
    
    def get_daena_structure_info(self) -> Dict:
        """Get information about Daena's own structure and capabilities."""
        import os
        import sys
        from pathlib import Path
        
        # Get Daena's root directory
        daena_root = Path(__file__).parent.parent.parent
        
        structure_info = {
            "daena_identity": {
                "name": "Daena",
                "title": "AI Vice President",
                "company": "MAS-AI Company",
                "creator": "Masoud Masoori",
                "structure_type": "Sunflower-Honeycomb Architecture"
            },
            "system_structure": {
                "total_departments": len(self.departments),
                "total_agents": len(self.agents),
                "total_projects": len(self.projects),
                "total_cells": len(self.cells)
            },
            "folder_structure": {
                "root_directory": str(daena_root),
                "backend": str(daena_root / "backend"),
                "core": str(daena_root / "Core"),
                "agents": str(daena_root / "Agents"),
                "frontend": str(daena_root / "frontend"),
                "data": str(daena_root / "data"),
                "models": str(daena_root / "models"),
                "logs": str(daena_root / "logs")
            },
            "capabilities": {
                "ai_providers": ["OpenAI", "Azure OpenAI", "Google Gemini", "Anthropic Claude"],
                "voice_integration": True,
                "file_processing": True,
                "deep_search": True,
                "agent_management": True,
                "department_coordination": True,
                "project_management": True
            },
            "departments_detail": {}
        }
        
        # Add department details
        for dept_id, dept_data in self.departments.items():
            agents_in_dept = [aid for aid in dept_data["agents"] if aid in self.agents]
            structure_info["departments_detail"][dept_id] = {
                "name": dept_data["name"],
                "description": dept_data["description"],
                "agent_count": len(agents_in_dept),
                "agents": [self.agents[aid]["name"] for aid in agents_in_dept if aid in self.agents],
                "sunflower_index": dept_data["sunflower_index"],
                "coordinates": dept_data["coordinates"]
            }
        
        return structure_info

# Global sunflower registry instance
sunflower_registry = SunflowerRegistry()

def get_counts() -> Dict:
    """Get current counts from the global sunflower registry."""
    return sunflower_registry.get_stats() 