"""
Outcome Tracker for Daena AI VP

Tracks the outcomes of decision recommendations to create a feedback loop.
This allows Daena to learn from what works and what doesn't.

Part of the Learning Loop system (DAENA_FULL_POWER.md Part 3).

Created: 2026-01-31
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class OutcomeStatus(str, Enum):
    """Status of a tracked outcome"""
    PENDING = "pending"          # Decision made, awaiting outcome
    SUCCESSFUL = "successful"    # Outcome was positive
    FAILED = "failed"            # Outcome was negative
    PARTIAL = "partial"          # Partially successful
    UNKNOWN = "unknown"          # Could not determine outcome
    EXPIRED = "expired"          # Tracking window expired


class DecisionCategory(str, Enum):
    """Categories of decisions being tracked"""
    DEFI_SCAN = "defi_scan"
    RESEARCH = "research"
    COUNCIL_VOTE = "council_vote"
    TOOL_EXECUTION = "tool_execution"
    FILE_OPERATION = "file_operation"
    APPROVAL = "approval"
    GENERAL = "general"


@dataclass
class TrackedOutcome:
    """A decision outcome being tracked"""
    outcome_id: str
    decision_type: str
    category: str
    recommendation: str
    agent_id: str = "daena"
    council_result: Optional[Dict[str, Any]] = None
    created_at: str = ""
    outcome_status: str = OutcomeStatus.PENDING.value
    outcome_recorded_at: Optional[str] = None
    outcome_notes: str = ""
    feedback_score: Optional[float] = None  # 1-5 rating from user
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()


@dataclass
class ExpertScore:
    """Calibration score for an expert/council member"""
    expert_id: str
    domain: str
    total_recommendations: int = 0
    successful_outcomes: int = 0
    failed_outcomes: int = 0
    accuracy_score: float = 50.0  # Start at neutral
    last_updated: str = ""
    
    def __post_init__(self):
        if not self.last_updated:
            self.last_updated = datetime.utcnow().isoformat()
    
    def update_score(self, was_successful: bool) -> None:
        """Update score based on outcome"""
        self.total_recommendations += 1
        if was_successful:
            self.successful_outcomes += 1
        else:
            self.failed_outcomes += 1
        
        # Calculate accuracy
        if self.total_recommendations > 0:
            self.accuracy_score = (self.successful_outcomes / self.total_recommendations) * 100
        
        self.last_updated = datetime.utcnow().isoformat()


class OutcomeTracker:
    """
    Tracks decision outcomes and calibrates expert accuracy.
    
    For every recommendation Daena or her Council makes, we track:
    1. What was recommended
    2. What the outcome was
    3. Which experts contributed
    4. Whether it was successful
    
    This builds a feedback loop that allows Daena to:
    - Weight expert opinions by past accuracy
    - Learn from mistakes
    - Improve over time
    """
    
    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path(".ledger/outcomes.json")
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.outcomes: Dict[str, TrackedOutcome] = {}
        self.expert_scores: Dict[str, ExpertScore] = {}
        
        self._load()
        logger.info("Outcome Tracker initialized")
    
    def _load(self) -> None:
        """Load tracked data from disk"""
        try:
            if self.storage_path.exists():
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                
                for oid, adata in data.get("outcomes", {}).items():
                    self.outcomes[oid] = TrackedOutcome(**adata)
                
                for eid, edata in data.get("expert_scores", {}).items():
                    self.expert_scores[eid] = ExpertScore(**edata)
                
                logger.info(f"Loaded {len(self.outcomes)} outcomes, {len(self.expert_scores)} expert scores")
        except Exception as e:
            logger.warning(f"Could not load outcome data: {e}")
    
    def _save(self) -> None:
        """Save tracked data to disk"""
        try:
            data = {
                "outcomes": {oid: asdict(o) for oid, o in self.outcomes.items()},
                "expert_scores": {eid: asdict(e) for eid, e in self.expert_scores.items()},
                "last_updated": datetime.utcnow().isoformat()
            }
            with open(self.storage_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save outcome data: {e}")
    
    def track_decision(
        self,
        outcome_id: str,
        decision_type: str,
        category: str,
        recommendation: str,
        agent_id: str = "daena",
        council_result: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> TrackedOutcome:
        """
        Start tracking a new decision for its outcome.
        
        Args:
            outcome_id: Unique ID for this outcome (e.g., task_id, scan_id)
            decision_type: Type of decision (e.g., "audit_recommendation")
            category: Category of the decision
            recommendation: What was recommended
            agent_id: Which agent made the recommendation
            council_result: If council voted, include the vote result
            metadata: Additional context
        
        Returns:
            The tracked outcome object
        """
        outcome = TrackedOutcome(
            outcome_id=outcome_id,
            decision_type=decision_type,
            category=category,
            recommendation=recommendation,
            agent_id=agent_id,
            council_result=council_result,
            metadata=metadata or {}
        )
        
        self.outcomes[outcome_id] = outcome
        self._save()
        
        logger.info(f"Tracking decision: {outcome_id} ({decision_type})")
        return outcome
    
    def record_outcome(
        self,
        outcome_id: str,
        status: OutcomeStatus,
        notes: str = "",
        feedback_score: Optional[float] = None
    ) -> bool:
        """
        Record the actual outcome of a tracked decision.
        
        Args:
            outcome_id: ID of the outcome to update
            status: The outcome status
            notes: Any notes about the outcome
            feedback_score: User rating 1-5 (optional)
        
        Returns:
            True if recorded successfully
        """
        if outcome_id not in self.outcomes:
            logger.warning(f"Outcome not found: {outcome_id}")
            return False
        
        outcome = self.outcomes[outcome_id]
        outcome.outcome_status = status.value
        outcome.outcome_recorded_at = datetime.utcnow().isoformat()
        outcome.outcome_notes = notes
        
        if feedback_score is not None:
            outcome.feedback_score = max(1.0, min(5.0, feedback_score))
        
        # Update expert scores if council was involved
        if outcome.council_result:
            was_successful = status in [OutcomeStatus.SUCCESSFUL, OutcomeStatus.PARTIAL]
            self._update_expert_scores(outcome.council_result, was_successful)
        
        self._save()
        logger.info(f"Outcome recorded: {outcome_id} = {status.value}")
        return True
    
    def _update_expert_scores(self, council_result: Dict[str, Any], was_successful: bool) -> None:
        """Update expert calibration scores based on outcome"""
        votes = council_result.get("votes", [])
        domain = council_result.get("domain", "general")
        
        for vote in votes:
            expert_id = vote.get("expert_id", vote.get("agent_id", "unknown"))
            vote_aligned = vote.get("aligned_with_outcome", True)  # Did they vote for what happened?
            
            if expert_id not in self.expert_scores:
                self.expert_scores[expert_id] = ExpertScore(expert_id=expert_id, domain=domain)
            
            # Expert was right if they voted for the action that was successful
            # Or voted against an action that failed
            expert_was_correct = (vote_aligned and was_successful) or (not vote_aligned and not was_successful)
            self.expert_scores[expert_id].update_score(expert_was_correct)
    
    def get_expert_accuracy(self, expert_id: str) -> Optional[float]:
        """Get accuracy score for an expert"""
        if expert_id in self.expert_scores:
            return self.expert_scores[expert_id].accuracy_score
        return None
    
    def get_top_experts(self, domain: Optional[str] = None, limit: int = 10) -> List[ExpertScore]:
        """Get top-performing experts"""
        experts = list(self.expert_scores.values())
        
        if domain:
            experts = [e for e in experts if e.domain == domain]
        
        # Filter to experts with at least 5 recommendations
        experts = [e for e in experts if e.total_recommendations >= 5]
        
        return sorted(experts, key=lambda e: e.accuracy_score, reverse=True)[:limit]
    
    def get_pending_outcomes(self, limit: int = 50) -> List[TrackedOutcome]:
        """Get outcomes still pending resolution"""
        pending = [o for o in self.outcomes.values() if o.outcome_status == OutcomeStatus.PENDING.value]
        return sorted(pending, key=lambda o: o.created_at, reverse=True)[:limit]
    
    def expire_old_outcomes(self, days: int = 30) -> int:
        """Mark old pending outcomes as expired"""
        expired_count = 0
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        for outcome in self.outcomes.values():
            if outcome.outcome_status == OutcomeStatus.PENDING.value:
                try:
                    created = datetime.fromisoformat(outcome.created_at)
                    if created < cutoff:
                        outcome.outcome_status = OutcomeStatus.EXPIRED.value
                        outcome.outcome_recorded_at = datetime.utcnow().isoformat()
                        expired_count += 1
                except Exception:
                    pass
        
        if expired_count:
            self._save()
            logger.info(f"Expired {expired_count} old outcomes")
        
        return expired_count
    
    def get_stats(self) -> Dict[str, Any]:
        """Get outcome tracking statistics"""
        outcomes = list(self.outcomes.values())
        experts = list(self.expert_scores.values())
        
        if not outcomes:
            return {"total_tracked": 0}
        
        status_counts = {}
        for status in OutcomeStatus:
            status_counts[status.value] = len([o for o in outcomes if o.outcome_status == status.value])
        
        category_counts = {}
        for cat in DecisionCategory:
            category_counts[cat.value] = len([o for o in outcomes if o.category == cat.value])
        
        # Calculate success rate
        resolved = [o for o in outcomes if o.outcome_status in [
            OutcomeStatus.SUCCESSFUL.value, 
            OutcomeStatus.FAILED.value,
            OutcomeStatus.PARTIAL.value
        ]]
        
        success_rate = 0.0
        if resolved:
            successes = len([o for o in resolved if o.outcome_status == OutcomeStatus.SUCCESSFUL.value])
            success_rate = (successes / len(resolved)) * 100
        
        return {
            "total_tracked": len(outcomes),
            "pending": status_counts.get(OutcomeStatus.PENDING.value, 0),
            "resolved": len(resolved),
            "success_rate": round(success_rate, 1),
            "status_breakdown": status_counts,
            "category_breakdown": category_counts,
            "experts_calibrated": len(experts),
            "top_expert_accuracy": max([e.accuracy_score for e in experts], default=0)
        }
    
    def get_insights(self) -> List[str]:
        """Generate insights from outcome data"""
        insights = []
        stats = self.get_stats()
        
        if stats["total_tracked"] < 10:
            return ["Not enough data yet. Track more decisions to generate insights."]
        
        # Success rate insight
        rate = stats.get("success_rate", 0)
        if rate >= 80:
            insights.append(f"🎯 High success rate: {rate}% of resolved decisions had positive outcomes")
        elif rate >= 60:
            insights.append(f"📊 Moderate success rate: {rate}% - room for improvement")
        else:
            insights.append(f"⚠️ Low success rate: {rate}% - recommend reviewing decision criteria")
        
        # Expert calibration insight
        experts = self.get_top_experts(limit=3)
        if experts:
            top = experts[0]
            insights.append(
                f"🏆 Top expert: {top.expert_id} with {top.accuracy_score:.0f}% accuracy "
                f"({top.total_recommendations} recommendations)"
            )
        
        # Pending outcomes insight
        pending = stats.get("pending", 0)
        if pending > 20:
            insights.append(f"⏳ {pending} decisions pending outcome - consider reviewing and recording results")
        
        return insights


# Global instance
_outcome_tracker: Optional[OutcomeTracker] = None


def get_outcome_tracker() -> OutcomeTracker:
    """Get or create the global Outcome Tracker instance"""
    global _outcome_tracker
    if _outcome_tracker is None:
        _outcome_tracker = OutcomeTracker()
    return _outcome_tracker
