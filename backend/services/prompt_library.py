"""
Prompt Library Service (Phase E).

Manages prompt templates per domain with versioning, evaluation scores, and improvement loop.
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
class PromptTemplate:
    """A prompt template with metadata"""
    id: str
    domain: str  # e.g., "marketing", "ads", "security", "code", "sales", "ops"
    name: str
    version: str
    template: str  # The actual prompt template
    variables: List[str] = field(default_factory=list)  # Variables in template
    evaluation_score: float = 0.0  # 0.0-1.0
    usage_count: int = 0
    success_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PromptOutcome:
    """Outcome of using a prompt template"""
    prompt_id: str
    task: str
    result: str
    metrics: Dict[str, Any]  # e.g., {"accuracy": 0.95, "latency_ms": 200}
    success: bool
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class PromptLibrary:
    """
    Prompt Library with versioning, evaluation, and improvement loop.
    
    Features:
    - Templates per domain
    - Versioning
    - Evaluation scores
    - Improvement loop (store outcomes, propose upgrades)
    - A/B testing support
    """
    
    def __init__(self, storage_path: Optional[Path] = None):
        if storage_path is None:
            storage_path = Path("data/prompt_library")
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.templates_file = self.storage_path / "templates.json"
        self.outcomes_file = self.storage_path / "outcomes.json"
        self.templates: Dict[str, PromptTemplate] = {}
        self.outcomes: List[PromptOutcome] = []
        
        self._load_templates()
        self._load_outcomes()
        self._seed_default_templates()
    
    def _seed_default_templates(self):
        """Seed default prompt templates if none exist"""
        if self.templates:
            return
        
        default_templates = [
            {
                "id": "marketing-001",
                "domain": "marketing",
                "name": "Marketing Campaign Prompt",
                "version": "1.0.0",
                "template": "Create a marketing campaign for {product} targeting {audience}. Focus on {key_message}.",
                "variables": ["product", "audience", "key_message"],
            },
            {
                "id": "code-001",
                "domain": "code",
                "name": "Code Review Prompt",
                "version": "1.0.0",
                "template": "Review this code for {language}: {code}. Check for {focus_areas}.",
                "variables": ["language", "code", "focus_areas"],
            },
            {
                "id": "sales-001",
                "domain": "sales",
                "name": "Sales Pitch Prompt",
                "version": "1.0.0",
                "template": "Create a sales pitch for {product} to {customer_type}. Emphasize {value_proposition}.",
                "variables": ["product", "customer_type", "value_proposition"],
            },
        ]
        
        for template_data in default_templates:
            template = PromptTemplate(**template_data)
            self.templates[template.id] = template
        
        self._save_templates()
        logger.info(f"Seeded {len(default_templates)} default prompt templates")
    
    def register_template(
        self,
        domain: str,
        name: str,
        template: str,
        version: str = "1.0.0",
        variables: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PromptTemplate:
        """Register a new prompt template"""
        template_id = f"{domain}-{len([t for t in self.templates.values() if t.domain == domain]) + 1:03d}"
        
        prompt_template = PromptTemplate(
            id=template_id,
            domain=domain,
            name=name,
            version=version,
            template=template,
            variables=variables or [],
            metadata=metadata or {}
        )
        
        self.templates[template_id] = prompt_template
        self._save_templates()
        
        logger.info(f"Registered prompt template: {template_id} ({domain})")
        return prompt_template
    
    def get_template(self, template_id: str) -> Optional[PromptTemplate]:
        """Get a prompt template by ID"""
        return self.templates.get(template_id)
    
    def list_templates(self, domain: Optional[str] = None) -> List[PromptTemplate]:
        """List prompt templates, optionally filtered by domain"""
        templates = list(self.templates.values())
        if domain:
            templates = [t for t in templates if t.domain == domain]
        return sorted(templates, key=lambda t: t.evaluation_score, reverse=True)
    
    def render_template(self, template_id: str, variables: Dict[str, Any]) -> str:
        """Render a prompt template with variables"""
        template = self.templates.get(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")
        
        rendered = template.template
        for var in template.variables:
            value = variables.get(var, f"{{{var}}}")
            rendered = rendered.replace(f"{{{var}}}", str(value))
        
        # Update usage count
        template.usage_count += 1
        template.updated_at = datetime.utcnow().isoformat()
        self._save_templates()
        
        return rendered
    
    def record_outcome(
        self,
        prompt_id: str,
        task: str,
        result: str,
        metrics: Dict[str, Any],
        success: bool
    ) -> PromptOutcome:
        """Record the outcome of using a prompt template"""
        outcome = PromptOutcome(
            prompt_id=prompt_id,
            task=task,
            result=result,
            metrics=metrics,
            success=success
        )
        
        self.outcomes.append(outcome)
        
        # Update template statistics
        template = self.templates.get(prompt_id)
        if template:
            if success:
                template.success_count += 1
            # Recalculate evaluation score
            if template.usage_count > 0:
                template.evaluation_score = template.success_count / template.usage_count
        
        self._save_templates()
        self._save_outcomes()
        
        return outcome
    
    def propose_upgrade(
        self,
        template_id: str,
        improved_template: str,
        reason: str,
        evidence: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Propose an upgrade to a prompt template.
        
        This goes through governance pipeline before becoming official.
        """
        template = self.templates.get(template_id)
        if not template:
            return {"error": "Template not found"}
        
        # Create new version
        version_parts = template.version.split(".")
        new_version = f"{version_parts[0]}.{int(version_parts[1]) + 1}.0"
        
        proposal = {
            "template_id": template_id,
            "current_version": template.version,
            "proposed_version": new_version,
            "current_template": template.template,
            "improved_template": improved_template,
            "reason": reason,
            "evidence": evidence or {},
            "proposed_at": datetime.utcnow().isoformat(),
        }
        
        # Store proposal (would go through governance in production)
        proposals_file = self.storage_path / "proposals.json"
        proposals = []
        if proposals_file.exists():
            proposals = json.loads(proposals_file.read_text(encoding="utf-8"))
        proposals.append(proposal)
        proposals_file.write_text(
            json.dumps(proposals, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        
        logger.info(f"Proposed upgrade for {template_id}: {template.version} -> {new_version}")
        
        return {
            "status": "proposed",
            "proposal": proposal,
            "message": "Upgrade proposal created. Awaiting governance review."
        }
    
    def approve_upgrade(self, proposal_id: str, approved_by: str) -> Dict[str, Any]:
        """Approve and apply a prompt upgrade (governance-gated)"""
        proposals_file = self.storage_path / "proposals.json"
        if not proposals_file.exists():
            return {"error": "No proposals found"}
        
        proposals = json.loads(proposals_file.read_text(encoding="utf-8"))
        
        # Find proposal (using index as ID for simplicity)
        try:
            idx = int(proposal_id)
            if idx < 0 or idx >= len(proposals):
                return {"error": "Proposal not found"}
            proposal = proposals[idx]
        except (ValueError, IndexError):
            return {"error": "Invalid proposal ID"}
        
        template_id = proposal["template_id"]
        template = self.templates.get(template_id)
        if not template:
            return {"error": "Template not found"}
        
        # Apply upgrade
        template.template = proposal["improved_template"]
        template.version = proposal["proposed_version"]
        template.updated_at = datetime.utcnow().isoformat()
        template.metadata["upgrade_history"] = template.metadata.get("upgrade_history", [])
        template.metadata["upgrade_history"].append({
            "from_version": proposal["current_version"],
            "to_version": proposal["proposed_version"],
            "approved_by": approved_by,
            "approved_at": datetime.utcnow().isoformat(),
            "reason": proposal["reason"]
        })
        
        # Remove proposal
        proposals.pop(idx)
        proposals_file.write_text(
            json.dumps(proposals, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        
        self._save_templates()
        
        logger.info(f"Approved upgrade for {template_id}: {proposal['current_version']} -> {proposal['proposed_version']}")
        
        return {
            "status": "approved",
            "template_id": template_id,
            "new_version": proposal["proposed_version"],
            "approved_by": approved_by
        }
    
    def get_best_template(self, domain: str) -> Optional[PromptTemplate]:
        """Get the best template for a domain (highest evaluation score)"""
        domain_templates = [t for t in self.templates.values() if t.domain == domain]
        if not domain_templates:
            return None
        return max(domain_templates, key=lambda t: t.evaluation_score)
    
    def _load_templates(self):
        """Load templates from disk"""
        if self.templates_file.exists():
            try:
                data = json.loads(self.templates_file.read_text(encoding="utf-8"))
                for template_data in data:
                    template = PromptTemplate(**template_data)
                    self.templates[template.id] = template
            except Exception as e:
                logger.warning(f"Could not load templates: {e}")
    
    def _save_templates(self):
        """Save templates to disk"""
        try:
            data = [asdict(t) for t in self.templates.values()]
            self.templates_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
        except Exception as e:
            logger.warning(f"Could not save templates: {e}")
    
    def _load_outcomes(self):
        """Load outcomes from disk"""
        if self.outcomes_file.exists():
            try:
                data = json.loads(self.outcomes_file.read_text(encoding="utf-8"))
                for outcome_data in data:
                    outcome = PromptOutcome(**outcome_data)
                    self.outcomes.append(outcome)
            except Exception as e:
                logger.warning(f"Could not load outcomes: {e}")
    
    def _save_outcomes(self):
        """Save outcomes to disk"""
        try:
            data = [asdict(o) for o in self.outcomes[-1000:]]  # Keep last 1000
            self.outcomes_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
        except Exception as e:
            logger.warning(f"Could not save outcomes: {e}")


# Global instance
prompt_library = PromptLibrary()





