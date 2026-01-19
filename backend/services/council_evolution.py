"""
Council Automatic Evolution System.

Tracks outcomes and automatically improves council performance.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CouncilEvolution:
    """
    Automatic evolution and improvement of council performance.
    
    Features:
    - Outcome tracking (success/failure of decisions)
    - Performance metrics (accuracy, speed, consensus)
    - Automatic adjustments (persona weights, thresholds)
    - Learning from feedback
    """
    
    def __init__(self):
        # department -> {outcomes}
        self.outcomes: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        
        # department -> {metrics}
        self.performance_metrics: Dict[str, Dict[str, float]] = defaultdict(dict)
        
        # department -> {adjustments}
        self.evolution_history: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        
        # Track feedback
        self.feedback_history: List[Dict[str, Any]] = []
    
    def record_outcome(
        self,
        department: str,
        round_id: str,
        outcome: str,
        success: bool,
        metrics: Dict[str, Any] = None
    ):
        """
        Record outcome of a council round.
        
        Args:
            department: Department name
            round_id: Council round ID
            outcome: Outcome description
            success: Whether the outcome was successful
            metrics: Performance metrics
        """
        outcome_record = {
            "round_id": round_id,
            "outcome": outcome,
            "success": success,
            "timestamp": time.time(),
            "metrics": metrics or {}
        }
        self.outcomes[department].append(outcome_record)
        
        # Update performance metrics
        self._update_metrics(department, success, metrics)
        
        logger.info(f"Recorded outcome for {department}: {outcome} ({'SUCCESS' if success else 'FAILURE'})")
    
    def _update_metrics(self, department: str, success: bool, metrics: Dict[str, Any] = None):
        """Update performance metrics for a department."""
        if department not in self.performance_metrics:
            self.performance_metrics[department] = {
                "success_rate": 0.0,
                "total_rounds": 0,
                "avg_duration": 0.0,
                "avg_consensus": 0.0
            }
        
        perf = self.performance_metrics[department]
        perf["total_rounds"] += 1
        
        # Update success rate
        total = perf["total_rounds"]
        current_success_rate = perf["success_rate"]
        new_success_rate = ((current_success_rate * (total - 1)) + (1.0 if success else 0.0)) / total
        perf["success_rate"] = new_success_rate
        
        # Update other metrics
        if metrics:
            if "duration_sec" in metrics:
                current_avg = perf["avg_duration"]
                perf["avg_duration"] = ((current_avg * (total - 1)) + metrics["duration_sec"]) / total
            
            if "consensus" in metrics:
                current_avg = perf["avg_consensus"]
                perf["avg_consensus"] = ((current_avg * (total - 1)) + metrics["consensus"]) / total
    
    def get_performance_metrics(self, department: str) -> Dict[str, float]:
        """Get performance metrics for a department."""
        return self.performance_metrics.get(department, {
            "success_rate": 0.0,
            "total_rounds": 0,
            "avg_duration": 0.0,
            "avg_consensus": 0.0
        })
    
    def evolve_council(self, department: str) -> Dict[str, Any]:
        """
        Automatically evolve council based on outcomes.
        
        Returns adjustments to make.
        """
        outcomes = self.outcomes.get(department, [])
        if len(outcomes) < 5:  # Need at least 5 outcomes to evolve
            return {"evolved": False, "reason": "insufficient_data"}
        
        metrics = self.performance_metrics.get(department, {})
        success_rate = metrics.get("success_rate", 0.0)
        
        adjustments = {
            "evolved": True,
            "department": department,
            "timestamp": time.time(),
            "adjustments": []
        }
        
        # If success rate is low, suggest adjustments
        if success_rate < 0.6:
            adjustments["adjustments"].append({
                "type": "increase_consensus_threshold",
                "reason": f"Low success rate ({success_rate:.2%})",
                "suggestion": "Require higher consensus before committing"
            })
        
        # If duration is high, suggest optimizations
        avg_duration = metrics.get("avg_duration", 0.0)
        if avg_duration > 120.0:  # More than 2 minutes
            adjustments["adjustments"].append({
                "type": "reduce_phase_timeouts",
                "reason": f"High average duration ({avg_duration:.1f}s)",
                "suggestion": "Reduce phase timeouts to speed up rounds"
            })
        
        # Record evolution
        self.evolution_history[department].append(adjustments)
        
        logger.info(f"Council evolution for {department}: {len(adjustments['adjustments'])} adjustments")
        
        return adjustments
    
    def record_feedback(
        self,
        department: str,
        round_id: str,
        feedback_type: str,
        feedback_value: float,
        comments: str = ""
    ):
        """
        Record feedback on council performance.
        
        Args:
            department: Department name
            round_id: Council round ID
            feedback_type: Type of feedback (quality, speed, consensus, etc.)
            feedback_value: Feedback value (0.0 to 1.0)
            comments: Optional comments
        """
        feedback = {
            "department": department,
            "round_id": round_id,
            "feedback_type": feedback_type,
            "feedback_value": feedback_value,
            "comments": comments,
            "timestamp": time.time()
        }
        self.feedback_history.append(feedback)
        
        # Use feedback to update metrics
        if feedback_type == "quality":
            # Treat as success/failure
            self.record_outcome(
                department,
                round_id,
                f"Feedback: {comments}",
                feedback_value >= 0.7,
                {"feedback_quality": feedback_value}
            )
        
        logger.info(f"Recorded feedback for {department}/{round_id}: {feedback_type}={feedback_value:.2f}")
    
    def get_evolution_summary(self, department: str) -> Dict[str, Any]:
        """Get evolution summary for a department."""
        return {
            "department": department,
            "performance": self.get_performance_metrics(department),
            "total_outcomes": len(self.outcomes.get(department, [])),
            "evolution_count": len(self.evolution_history.get(department, [])),
            "recent_evolutions": self.evolution_history.get(department, [])[-5:]
        }


# Global instance
council_evolution = CouncilEvolution()

