"""Budget and rate limiting service for Daena cells."""
import time
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from backend.utils.sunflower_registry import sunflower_registry

logger = logging.getLogger(__name__)

@dataclass
class BudgetConfig:
    """Budget configuration for a cell."""
    cell_id: str
    tokens_per_minute: int
    burst_limit: int
    backoff_multiplier: float = 1.5
    max_backoff_minutes: int = 60

@dataclass
class BudgetUsage:
    """Current budget usage for a cell."""
    cell_id: str
    tokens_used: int
    last_reset: datetime
    backoff_until: Optional[datetime] = None
    consecutive_exhaustions: int = 0

class BudgetService:
    """Budget and rate limiting service."""
    
    def __init__(self):
        self.budgets: Dict[str, BudgetConfig] = {}
        self.usage: Dict[str, BudgetUsage] = {}
        self.default_tokens_per_minute = 1000
        self.default_burst_limit = 2000
        
        # Initialize budgets for all cells
        self._initialize_budgets()
    
    def _initialize_budgets(self):
        """Initialize budgets for all registered cells."""
        # Department budgets (higher limits)
        for dept_id in sunflower_registry.departments:
            self.budgets[dept_id] = BudgetConfig(
                cell_id=dept_id,
                tokens_per_minute=2000,
                burst_limit=4000
            )
        
        # Agent budgets (standard limits)
        for agent_id in sunflower_registry.agents:
            self.budgets[agent_id] = BudgetConfig(
                cell_id=agent_id,
                tokens_per_minute=500,
                burst_limit=1000
            )
        
        # Project budgets (variable limits)
        for project_id in sunflower_registry.projects:
            self.budgets[project_id] = BudgetConfig(
                cell_id=project_id,
                tokens_per_minute=800,
                burst_limit=1600
            )
        
        logger.info(f"Initialized budgets for {len(self.budgets)} cells")
    
    def check_budget(self, cell_id: str, tokens_requested: int = 1) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if a cell has budget available.
        
        Returns:
            Tuple of (allowed, details)
        """
        if cell_id not in self.budgets:
            # Create default budget for unknown cell
            self.budgets[cell_id] = BudgetConfig(
                cell_id=cell_id,
                tokens_per_minute=self.default_tokens_per_minute,
                burst_limit=self.default_burst_limit
            )
        
        budget_config = self.budgets[cell_id]
        
        # Initialize usage if not exists
        if cell_id not in self.usage:
            self.usage[cell_id] = BudgetUsage(
                cell_id=cell_id,
                tokens_used=0,
                last_reset=datetime.now()
            )
        
        usage = self.usage[cell_id]
        current_time = datetime.now()
        
        # Check if in backoff period
        if usage.backoff_until and current_time < usage.backoff_until:
            remaining_backoff = (usage.backoff_until - current_time).total_seconds()
            return False, {
                "allowed": False,
                "reason": "budget_exhausted_backoff",
                "backoff_remaining_seconds": int(remaining_backoff),
                "backoff_until": usage.backoff_until.isoformat(),
                "consecutive_exhaustions": usage.consecutive_exhaustions
            }
        
        # Reset tokens if minute has passed
        if (current_time - usage.last_reset).total_seconds() >= 60:
            usage.tokens_used = 0
            usage.last_reset = current_time
        
        # Check if within limits
        if usage.tokens_used + tokens_requested <= budget_config.tokens_per_minute:
            usage.tokens_used += tokens_requested
            return True, {
                "allowed": True,
                "tokens_remaining": budget_config.tokens_per_minute - usage.tokens_used,
                "tokens_used": usage.tokens_used,
                "reset_in_seconds": 60 - (current_time - usage.last_reset).total_seconds()
            }
        
        # Check burst limit
        if usage.tokens_used + tokens_requested <= budget_config.burst_limit:
            usage.tokens_used += tokens_requested
            return True, {
                "allowed": True,
                "tokens_remaining": budget_config.burst_limit - usage.tokens_used,
                "tokens_used": usage.tokens_used,
                "burst_used": True,
                "reset_in_seconds": 60 - (current_time - usage.last_reset).total_seconds()
            }
        
        # Budget exhausted - apply backoff
        usage.consecutive_exhaustions += 1
        backoff_minutes = min(
            budget_config.max_backoff_minutes,
            budget_config.backoff_multiplier ** usage.consecutive_exhaustions
        )
        usage.backoff_until = current_time + timedelta(minutes=backoff_minutes)
        
        logger.warning(f"Budget exhausted for {cell_id}: {tokens_requested} tokens requested, "
                      f"{usage.tokens_used} used, backoff for {backoff_minutes} minutes")
        
        return False, {
            "allowed": False,
            "reason": "budget_exhausted",
            "tokens_requested": tokens_requested,
            "tokens_used": usage.tokens_used,
            "budget_limit": budget_config.tokens_per_minute,
            "burst_limit": budget_config.burst_limit,
            "backoff_minutes": backoff_minutes,
            "backoff_until": usage.backoff_until.isoformat(),
            "consecutive_exhaustions": usage.consecutive_exhaustions
        }
    
    def route_to_synth(self, cell_id: str, message: str) -> Dict[str, Any]:
        """Route message to department synth when budget is exhausted."""
        # Find department for this cell
        dept_id = None
        if cell_id in sunflower_registry.agents:
            agent_data = sunflower_registry.agents[cell_id]
            dept_id = agent_data.get("department_id")
        elif cell_id in sunflower_registry.projects:
            project_data = sunflower_registry.projects[cell_id]
            dept_id = project_data.get("department_id")
        
        if dept_id:
            synth_id = f"{dept_id}_synth"
            if synth_id in sunflower_registry.agents:
                return {
                    "routed": True,
                    "original_cell": cell_id,
                    "synth_cell": synth_id,
                    "message": f"Budget exhausted, routed to {synth_id}: {message}",
                    "timestamp": datetime.now().isoformat()
                }
        
        return {
            "routed": False,
            "reason": "no_synth_available",
            "message": f"Budget exhausted for {cell_id}, no synth available"
        }
    
    def get_budget_status(self, cell_id: str) -> Dict[str, Any]:
        """Get current budget status for a cell."""
        if cell_id not in self.budgets:
            return {"error": "Cell not found"}
        
        budget_config = self.budgets[cell_id]
        usage = self.usage.get(cell_id)
        
        if not usage:
            return {
                "cell_id": cell_id,
                "budget": {
                    "tokens_per_minute": budget_config.tokens_per_minute,
                    "burst_limit": budget_config.burst_limit,
                    "backoff_multiplier": budget_config.backoff_multiplier,
                    "max_backoff_minutes": budget_config.max_backoff_minutes
                },
                "usage": {
                    "tokens_used": 0,
                    "tokens_remaining": budget_config.tokens_per_minute,
                    "last_reset": datetime.now().isoformat(),
                    "backoff_until": None,
                    "consecutive_exhaustions": 0
                }
            }
        
        current_time = datetime.now()
        reset_in_seconds = max(0, 60 - (current_time - usage.last_reset).total_seconds())
        
        return {
            "cell_id": cell_id,
            "budget": {
                "tokens_per_minute": budget_config.tokens_per_minute,
                "burst_limit": budget_config.burst_limit,
                "backoff_multiplier": budget_config.backoff_multiplier,
                "max_backoff_minutes": budget_config.max_backoff_minutes
            },
            "usage": {
                "tokens_used": usage.tokens_used,
                "tokens_remaining": budget_config.tokens_per_minute - usage.tokens_used,
                "last_reset": usage.last_reset.isoformat(),
                "reset_in_seconds": int(reset_in_seconds),
                "backoff_until": usage.backoff_until.isoformat() if usage.backoff_until else None,
                "consecutive_exhaustions": usage.consecutive_exhaustions,
                "in_backoff": usage.backoff_until and current_time < usage.backoff_until
            }
        }
    
    def get_all_budgets(self) -> Dict[str, Any]:
        """Get status of all budgets."""
        all_statuses = {}
        total_cells = len(self.budgets)
        cells_in_backoff = 0
        total_tokens_used = 0
        
        for cell_id in self.budgets:
            status = self.get_budget_status(cell_id)
            all_statuses[cell_id] = status
            
            if status.get("usage", {}).get("in_backoff", False):
                cells_in_backoff += 1
            
            total_tokens_used += status.get("usage", {}).get("tokens_used", 0)
        
        return {
            "summary": {
                "total_cells": total_cells,
                "cells_in_backoff": cells_in_backoff,
                "total_tokens_used": total_tokens_used,
                "backoff_percentage": round(cells_in_backoff / total_cells * 100, 2) if total_cells > 0 else 0
            },
            "cells": all_statuses
        }
    
    def reset_budget(self, cell_id: str) -> Dict[str, Any]:
        """Reset budget for a cell (admin function)."""
        if cell_id not in self.usage:
            return {"error": "Cell not found"}
        
        usage = self.usage[cell_id]
        usage.tokens_used = 0
        usage.last_reset = datetime.now()
        usage.backoff_until = None
        usage.consecutive_exhaustions = 0
        
        logger.info(f"Budget reset for {cell_id}")
        
        return {
            "success": True,
            "message": f"Budget reset for {cell_id}",
            "timestamp": datetime.now().isoformat()
        }
    
    def update_budget_config(self, cell_id: str, tokens_per_minute: int, 
                           burst_limit: int) -> Dict[str, Any]:
        """Update budget configuration for a cell."""
        if cell_id not in self.budgets:
            return {"error": "Cell not found"}
        
        old_config = self.budgets[cell_id]
        self.budgets[cell_id] = BudgetConfig(
            cell_id=cell_id,
            tokens_per_minute=tokens_per_minute,
            burst_limit=burst_limit,
            backoff_multiplier=old_config.backoff_multiplier,
            max_backoff_minutes=old_config.max_backoff_minutes
        )
        
        logger.info(f"Budget config updated for {cell_id}: {tokens_per_minute} tokens/min, {burst_limit} burst")
        
        return {
            "success": True,
            "message": f"Budget config updated for {cell_id}",
            "old_config": {
                "tokens_per_minute": old_config.tokens_per_minute,
                "burst_limit": old_config.burst_limit
            },
            "new_config": {
                "tokens_per_minute": tokens_per_minute,
                "burst_limit": burst_limit
            },
            "timestamp": datetime.now().isoformat()
        }

# Global budget service instance
budget_service = BudgetService() 