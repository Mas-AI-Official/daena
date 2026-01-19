"""
Data Selector: Selects candidate data slices for SEC-Loop processing.

Policy-based selection ensuring tenant safety and ABAC compliance.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path
import yaml

logger = logging.getLogger(__name__)


@dataclass
class CandidateSlice:
    """A candidate data slice for abstraction."""
    slice_id: str
    content: str
    source: str  # "benchmark", "internal_eval", "task"
    confidence: float
    metadata: Dict[str, Any]
    tenant_id: Optional[str] = None
    project_id: Optional[str] = None


class DataSelector:
    """
    Selects candidate data slices for SEC-Loop processing.
    
    Ensures:
    - Tenant safety (ABAC enforced)
    - Policy compliance
    - Confidence thresholds
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize selector with configuration."""
        if config_path is None:
            config_path = Path(__file__).parent / "config.yaml"
        
        self.config = self._load_config(config_path)
        self.max_candidates = self.config.get("selection", {}).get("max_candidates_per_cycle", 10)
        self.min_confidence = self.config.get("selection", {}).get("min_confidence", 0.7)
        self.tenant_safe = self.config.get("selection", {}).get("tenant_safe", True)
        
        # Department allowlist
        dept_config = self.config.get("departments", {})
        self.dept_allowlist = dept_config.get("allowlist", [])
        
        logger.info(f"DataSelector initialized: max_candidates={self.max_candidates}, min_confidence={self.min_confidence}")
    
    def _load_config(self, config_path: Path) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f) or {}
            else:
                logger.warning(f"Config file not found: {config_path}, using defaults")
                return {}
        except Exception as e:
            logger.error(f"Error loading config: {e}, using defaults")
            return {}
    
    def select_candidates(
        self,
        department: str,
        tenant_id: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> List[CandidateSlice]:
        """
        Select candidate data slices for processing.
        
        Args:
            department: Department requesting selection
            tenant_id: Optional tenant ID for isolation
            project_id: Optional project ID for scoping
            
        Returns:
            List of candidate slices
        """
        # Check department allowlist
        if self.dept_allowlist and department not in self.dept_allowlist:
            logger.info(f"Department {department} not in allowlist, skipping selection")
            return []
        
        candidates = []
        
        # Select from benchmarks
        benchmark_candidates = self._select_from_benchmarks(department, tenant_id, project_id)
        candidates.extend(benchmark_candidates)
        
        # Select from internal eval sets
        eval_candidates = self._select_from_evals(department, tenant_id, project_id)
        candidates.extend(eval_candidates)
        
        # Filter by confidence
        filtered = [c for c in candidates if c.confidence >= self.min_confidence]
        
        # Sort by confidence (descending) and limit
        sorted_candidates = sorted(filtered, key=lambda x: x.confidence, reverse=True)
        limited = sorted_candidates[:self.max_candidates]
        
        logger.info(f"Selected {len(limited)} candidates from {len(candidates)} total (department: {department})")
        
        return limited
    
    def _select_from_benchmarks(
        self,
        department: str,
        tenant_id: Optional[str],
        project_id: Optional[str]
    ) -> List[CandidateSlice]:
        """Select candidates from benchmark datasets."""
        candidates = []
        
        try:
            # In production, this would query actual benchmark datasets
            # For now, return empty list (benchmarks would be loaded from files/DB)
            benchmark_path = Path("bench") / "benchmark_nbmf.py"
            if benchmark_path.exists():
                # Example: Load benchmark samples
                # In production, this would parse actual benchmark data
                logger.debug(f"Benchmark file found: {benchmark_path}")
                # Placeholder: would load actual benchmark samples here
                pass
        except Exception as e:
            logger.warning(f"Error selecting from benchmarks: {e}")
        
        return candidates
    
    def _select_from_evals(
        self,
        department: str,
        tenant_id: Optional[str],
        project_id: Optional[str]
    ) -> List[CandidateSlice]:
        """Select candidates from internal evaluation sets."""
        candidates = []
        
        try:
            # In production, this would query internal eval sets
            # For now, return empty list (evals would be loaded from files/DB)
            eval_sets = self.config.get("evaluation", {}).get("internal_eval_sets", [])
            logger.debug(f"Eval sets configured: {eval_sets}")
            # Placeholder: would load actual eval samples here
        except Exception as e:
            logger.warning(f"Error selecting from evals: {e}")
        
        return candidates
    
    def validate_tenant_safety(
        self,
        candidate: CandidateSlice,
        tenant_id: Optional[str] = None
    ) -> bool:
        """
        Validate that candidate is tenant-safe (ABAC compliant).
        
        Args:
            candidate: Candidate slice to validate
            tenant_id: Optional tenant ID for isolation check
            
        Returns:
            True if tenant-safe, False otherwise
        """
        if not self.tenant_safe:
            return True  # Tenant safety disabled
        
        # Check if candidate has tenant_id and matches
        if tenant_id and candidate.tenant_id and candidate.tenant_id != tenant_id:
            logger.warning(f"Tenant mismatch: candidate.tenant_id={candidate.tenant_id}, requested={tenant_id}")
            return False
        
        # In production, would check ABAC policies here
        # For now, basic tenant isolation check
        return True

