"""
Tool Playbooks Service (Phase F).

Manages reusable sequences of tool executions (playbooks) and converts
documentation into executable playbooks.
"""

import json
import os
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


@dataclass
class PlaybookStep:
    """A single step in a playbook"""
    tool_name: str
    args: Dict[str, Any]
    description: str = ""
    expected_output: Optional[str] = None
    retry_on_failure: bool = False
    max_retries: int = 3


@dataclass
class ToolPlaybook:
    """A reusable sequence of tool executions"""
    id: str
    name: str
    description: str
    category: str  # e.g., "web_scraping", "automation", "data_extraction"
    steps: List[PlaybookStep] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    success_count: int = 0
    failure_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    created_from_doc: Optional[str] = None  # Path to source doc if converted
    metadata: Dict[str, Any] = field(default_factory=dict)


class ToolPlaybookLibrary:
    """
    Tool Playbook Library with doc-to-playbook conversion.
    
    Features:
    - Store reusable tool sequences
    - Convert documentation to playbooks
    - Track playbook success/failure rates
    - Execute playbooks with error handling
    """
    
    def __init__(self, storage_path: Optional[Path] = None):
        if storage_path is None:
            storage_path = Path("data/tool_playbooks")
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.playbooks_file = self.storage_path / "playbooks.json"
        self.executions_file = self.storage_path / "executions.json"
        self.playbooks: Dict[str, ToolPlaybook] = {}
        self.executions: List[Dict[str, Any]] = []
        
        self._load_playbooks()
        self._seed_default_playbooks()
    
    def _seed_default_playbooks(self):
        """Seed default playbooks if none exist"""
        if self.playbooks:
            return
        
        default_playbooks = [
            {
                "id": "web-scrape-001",
                "name": "Basic Web Scraping",
                "description": "Scrape a webpage and extract text",
                "category": "web_scraping",
                "steps": [
                    {
                        "tool_name": "web_scrape_bs4",
                        "args": {"url": "{url}", "extract": "text"},
                        "description": "Scrape the webpage",
                    }
                ],
                "tags": ["web", "scraping", "basic"],
            },
            {
                "id": "browser-automation-001",
                "name": "Browser Navigation and Click",
                "description": "Navigate to a URL and click an element",
                "category": "automation",
                "steps": [
                    {
                        "tool_name": "browser_automation_selenium",
                        "args": {
                            "url": "{url}",
                            "steps": [
                                {"action": "click", "selector": "{selector}"}
                            ]
                        },
                        "description": "Navigate and click",
                    }
                ],
                "tags": ["browser", "automation", "selenium"],
            },
        ]
        
        for pb_data in default_playbooks:
            steps = [PlaybookStep(**step) for step in pb_data.pop("steps")]
            playbook = ToolPlaybook(**pb_data, steps=steps)
            self.playbooks[playbook.id] = playbook
        
        self._save_playbooks()
        logger.info(f"Seeded {len(default_playbooks)} default playbooks")
    
    def create_playbook(
        self,
        name: str,
        description: str,
        category: str,
        steps: List[Dict[str, Any]],
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ToolPlaybook:
        """Create a new playbook"""
        playbook_id = f"{category}-{len([p for p in self.playbooks.values() if p.category == category]) + 1:03d}"
        
        playbook_steps = [PlaybookStep(**step) for step in steps]
        
        playbook = ToolPlaybook(
            id=playbook_id,
            name=name,
            description=description,
            category=category,
            steps=playbook_steps,
            tags=tags or [],
            metadata=metadata or {}
        )
        
        self.playbooks[playbook_id] = playbook
        self._save_playbooks()
        
        logger.info(f"Created playbook: {playbook_id} ({category})")
        return playbook
    
    def get_playbook(self, playbook_id: str) -> Optional[ToolPlaybook]:
        """Get a playbook by ID"""
        return self.playbooks.get(playbook_id)
    
    def list_playbooks(self, category: Optional[str] = None) -> List[ToolPlaybook]:
        """List playbooks, optionally filtered by category"""
        playbooks = list(self.playbooks.values())
        if category:
            playbooks = [p for p in playbooks if p.category == category]
        return sorted(playbooks, key=lambda p: p.success_count / max(1, p.success_count + p.failure_count), reverse=True)
    
    async def execute_playbook(
        self,
        playbook_id: str,
        variables: Dict[str, Any],
        trace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a playbook with variable substitution.
        
        Returns execution results for each step.
        """
        playbook = self.playbooks.get(playbook_id)
        if not playbook:
            return {"error": "Playbook not found"}
        
        from backend.services.cmp_service import run_cmp_tool_action
        from backend.services.execution_layer_config import get_execution_config
        
        cfg = get_execution_config()
        max_steps = int(cfg.get("max_steps_per_run", 50))
        max_retries = int(cfg.get("max_retries_per_tool", 3))
        
        results = []
        execution_id = f"exec-{datetime.utcnow().isoformat()}"
        
        for i, step in enumerate(playbook.steps):
            if i >= max_steps:
                logger.warning(f"Playbook stopped: max_steps_per_run ({max_steps}) reached")
                break
            # Substitute variables in args
            step_args = self._substitute_variables(step.args, variables)
            
            # Execute tool
            try:
                result = await run_cmp_tool_action(
                    tool_name=step.tool_name,
                    args=step_args,
                    department=None,
                    agent_id=None,
                    reason=f"playbook:{playbook_id}:step:{i}",
                    trace_id=trace_id or execution_id,
                )
                
                success = result.get("status") == "ok"
                results.append({
                    "step_index": i,
                    "tool_name": step.tool_name,
                    "description": step.description,
                    "success": success,
                    "result": result,
                    "error": result.get("error") if not success else None,
                })
                
                # Retry logic (capped by config max_retries_per_tool)
                if not success and step.retry_on_failure:
                    allowed_retries = min(step.max_retries, max_retries)
                    for retry in range(allowed_retries):
                        logger.info(f"Retrying step {i} (attempt {retry + 1}/{allowed_retries})")
                        result = await run_cmp_tool_action(
                            tool_name=step.tool_name,
                            args=step_args,
                            department=None,
                            agent_id=None,
                            reason=f"playbook:{playbook_id}:step:{i}:retry:{retry}",
                            trace_id=trace_id or execution_id,
                        )
                        if result.get("status") == "ok":
                            results[-1]["success"] = True
                            results[-1]["result"] = result
                            results[-1]["error"] = None
                            break
                
                # Stop on failure if not retrying
                if not success and not step.retry_on_failure:
                    break
                    
            except Exception as e:
                logger.error(f"Error executing playbook step {i}: {e}")
                results.append({
                    "step_index": i,
                    "tool_name": step.tool_name,
                    "description": step.description,
                    "success": False,
                    "error": str(e),
                })
                break
        
        # Record execution
        all_success = all(r.get("success", False) for r in results)
        if all_success:
            playbook.success_count += 1
        else:
            playbook.failure_count += 1
        
        playbook.updated_at = datetime.utcnow().isoformat()
        self._save_playbooks()
        
        execution_record = {
            "execution_id": execution_id,
            "playbook_id": playbook_id,
            "timestamp": datetime.utcnow().isoformat(),
            "success": all_success,
            "results": results,
            "variables": variables,
        }
        self.executions.append(execution_record)
        self._save_executions()
        
        return {
            "execution_id": execution_id,
            "playbook_id": playbook_id,
            "success": all_success,
            "steps_executed": len(results),
            "steps_total": len(playbook.steps),
            "results": results,
        }
    
    def _substitute_variables(self, args: Dict[str, Any], variables: Dict[str, Any]) -> Dict[str, Any]:
        """Substitute variables in args (recursive)"""
        if isinstance(args, dict):
            return {k: self._substitute_variables(v, variables) for k, v in args.items()}
        elif isinstance(args, list):
            return [self._substitute_variables(item, variables) for item in args]
        elif isinstance(args, str) and args.startswith("{") and args.endswith("}"):
            var_name = args[1:-1]
            return variables.get(var_name, args)
        else:
            return args
    
    def convert_doc_to_playbook(
        self,
        doc_path: str,
        name: str,
        category: str,
        tool_mapping: Optional[Dict[str, str]] = None
    ) -> ToolPlaybook:
        """
        Convert documentation to a playbook.
        
        Parses documentation for tool sequences and creates a playbook.
        """
        doc_file = Path(doc_path)
        if not doc_file.exists():
            raise ValueError(f"Documentation file not found: {doc_path}")
        
        content = doc_file.read_text(encoding="utf-8")
        
        # Simple parser: look for tool mentions and sequences
        # In production, this would use NLP or structured parsing
        steps = []
        
        # Look for common patterns
        lines = content.split("\n")
        current_step = None
        
        for line in lines:
            line_lower = line.lower()
            
            # Detect tool mentions
            if "scrape" in line_lower or "web_scrape" in line_lower:
                steps.append(PlaybookStep(
                    tool_name="web_scrape_bs4",
                    args={"url": "{url}", "extract": "text"},
                    description=line.strip(),
                ))
            elif "browser" in line_lower or "selenium" in line_lower:
                steps.append(PlaybookStep(
                    tool_name="browser_automation_selenium",
                    args={"url": "{url}", "steps": []},
                    description=line.strip(),
                ))
            elif "desktop" in line_lower or "click" in line_lower:
                steps.append(PlaybookStep(
                    tool_name="desktop_automation_pyautogui",
                    args={"action": "click", "x": "{x}", "y": "{y}"},
                    description=line.strip(),
                ))
        
        if not steps:
            # Default: create a generic playbook
            steps = [PlaybookStep(
                tool_name="web_scrape_bs4",
                args={"url": "{url}"},
                description="Extracted from documentation",
            )]
        
        playbook = self.create_playbook(
            name=name,
            description=f"Converted from {doc_path}",
            category=category,
            steps=[asdict(s) for s in steps],
            metadata={"source_doc": doc_path, "converted_at": datetime.utcnow().isoformat()}
        )
        
        playbook.created_from_doc = doc_path
        self._save_playbooks()
        
        logger.info(f"Converted doc {doc_path} to playbook {playbook.id}")
        return playbook
    
    def _load_playbooks(self):
        """Load playbooks from disk"""
        if self.playbooks_file.exists():
            try:
                data = json.loads(self.playbooks_file.read_text(encoding="utf-8"))
                for pb_data in data:
                    steps = [PlaybookStep(**s) for s in pb_data.pop("steps", [])]
                    playbook = ToolPlaybook(**pb_data, steps=steps)
                    self.playbooks[playbook.id] = playbook
            except Exception as e:
                logger.warning(f"Could not load playbooks: {e}")
    
    def _save_playbooks(self):
        """Save playbooks to disk"""
        try:
            data = []
            for pb in self.playbooks.values():
                pb_dict = asdict(pb)
                pb_dict["steps"] = [asdict(s) for s in pb.steps]
                data.append(pb_dict)
            self.playbooks_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
        except Exception as e:
            logger.warning(f"Could not save playbooks: {e}")
    
    def _save_executions(self):
        """Save executions to disk (keep last 1000)"""
        try:
            data = self.executions[-1000:]
            self.executions_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
        except Exception as e:
            logger.warning(f"Could not save executions: {e}")


# Global instance
tool_playbook_library = ToolPlaybookLibrary()





