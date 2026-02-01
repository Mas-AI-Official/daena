"""
Memory Consolidation — Daena's Learning Loop

Runs periodically to:
1. Extract lessons from recent decisions and outcomes
2. Cluster them by topic/pattern
3. Generate summary insights using local LLM
4. Store consolidated insights in memory
5. Update expert calibration scores

This is how Daena actually gets SMARTER over time —
not by retraining weights, but by accumulating verified operational knowledge.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Storage paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
INSIGHTS_STORAGE = PROJECT_ROOT / ".dna_storage" / "insights"
CONSOLIDATION_LOG = PROJECT_ROOT / ".dna_storage" / "consolidation_log.json"


@dataclass
class LessonExtracted:
    """A lesson extracted from a decision outcome."""
    outcome_id: str
    category: str
    decision_type: str
    what_worked: str
    what_failed: str
    why: str
    extracted_at: str


class MemoryConsolidation:
    """
    The learning engine that consolidates experiences into knowledge.
    
    Example insight after 30 days of DeFi scanning:
    "Contracts using proxy patterns have 3x higher critical vulnerability rate.
     Prioritize proxy pattern analysis in all DeFi scans."
    """
    
    def __init__(self):
        INSIGHTS_STORAGE.mkdir(parents=True, exist_ok=True)
        self._lessons: List[LessonExtracted] = []
        self._load_state()
    
    def _load_state(self):
        """Load consolidation state."""
        if CONSOLIDATION_LOG.exists():
            try:
                with open(CONSOLIDATION_LOG, "r") as f:
                    data = json.load(f)
                    self._lessons = [
                        LessonExtracted(**l) for l in data.get("lessons", [])
                    ]
            except Exception as e:
                logger.error(f"Failed to load consolidation state: {e}")
    
    def _save_state(self):
        """Save consolidation state."""
        try:
            data = {
                "lessons": [l.__dict__ for l in self._lessons],
                "last_run": datetime.now(timezone.utc).isoformat()
            }
            with open(CONSOLIDATION_LOG, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save consolidation state: {e}")
    
    def extract_lesson(self, outcome: Dict[str, Any]) -> LessonExtracted:
        """
        Extract a lesson from a completed outcome.
        
        This analyzes what happened and why, creating a structured lesson.
        """
        now = datetime.now(timezone.utc).isoformat()
        
        # Determine what worked/failed based on outcome status
        status = outcome.get("status", "unknown")
        recommendation = outcome.get("recommendation", "")
        notes = outcome.get("notes", "")
        category = outcome.get("category", "general")
        decision_type = outcome.get("decision_type", "unknown")
        
        if status == "successful":
            what_worked = f"Recommendation '{recommendation}' led to success"
            what_failed = "N/A"
            why = notes or "Decision aligned with outcome"
        elif status == "failed":
            what_worked = "N/A"
            what_failed = f"Recommendation '{recommendation}' led to failure"
            why = notes or "Need to analyze what went wrong"
        elif status == "partially_successful":
            what_worked = "Partial success achieved"
            what_failed = "Not all objectives met"
            why = notes or "Mixed results require further analysis"
        else:
            what_worked = "Unknown"
            what_failed = "Unknown"
            why = "Outcome not fully recorded"
        
        lesson = LessonExtracted(
            outcome_id=outcome.get("outcome_id", "unknown"),
            category=category,
            decision_type=decision_type,
            what_worked=what_worked,
            what_failed=what_failed,
            why=why,
            extracted_at=now
        )
        
        self._lessons.append(lesson)
        self._save_state()
        
        return lesson
    
    def consolidate(self, topic: str = None) -> Dict[str, Any]:
        """
        Run the consolidation process.
        
        1. Group recent lessons by category
        2. Extract patterns
        3. Generate insights
        4. Store for future use
        """
        now = datetime.now(timezone.utc)
        
        # Filter lessons (last 7 days)
        recent_lessons = [
            l for l in self._lessons
            if self._is_recent(l.extracted_at, days=7)
        ]
        
        if topic:
            recent_lessons = [l for l in recent_lessons if topic.lower() in l.category.lower()]
        
        if not recent_lessons:
            return {
                "status": "no_data",
                "message": "Not enough recent lessons to consolidate",
                "lessons_analyzed": 0
            }
        
        # Group by category
        by_category = {}
        for lesson in recent_lessons:
            cat = lesson.category
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(lesson)
        
        # Generate insights per category
        insights_generated = []
        for category, lessons in by_category.items():
            insight = self._generate_insight(category, lessons)
            if insight:
                self._store_insight(category, insight)
                insights_generated.append({
                    "category": category,
                    "insight": insight,
                    "based_on": len(lessons)
                })
        
        result = {
            "status": "completed",
            "lessons_analyzed": len(recent_lessons),
            "categories_processed": len(by_category),
            "insights_generated": insights_generated,
            "consolidated_at": now.isoformat()
        }
        
        return result
    
    def _is_recent(self, timestamp: str, days: int = 7) -> bool:
        """Check if a timestamp is within the last N days."""
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            return (now - dt) < timedelta(days=days)
        except:
            return False
    
    def _generate_insight(self, category: str, lessons: List[LessonExtracted]) -> Optional[str]:
        """
        Generate an insight from a set of lessons.
        
        TODO: Use local LLM for more sophisticated insight generation.
        Currently uses pattern matching.
        """
        if len(lessons) < 2:
            return None
        
        # Count successes vs failures
        successes = sum(1 for l in lessons if "success" in l.what_worked.lower())
        failures = sum(1 for l in lessons if "fail" in l.what_failed.lower())
        total = len(lessons)
        
        success_rate = successes / max(total, 1)
        
        # Generate insight based on patterns
        if success_rate > 0.8:
            return f"[{category}] Strong performance: {successes}/{total} decisions successful. Current approach is effective."
        elif success_rate < 0.3:
            return f"[{category}] Needs improvement: only {successes}/{total} decisions successful. Review decision criteria."
        else:
            # Look for common patterns in failures
            common_types = {}
            for l in lessons:
                dt = l.decision_type
                if dt not in common_types:
                    common_types[dt] = {"success": 0, "fail": 0}
                if "success" in l.what_worked.lower():
                    common_types[dt]["success"] += 1
                if "fail" in l.what_failed.lower():
                    common_types[dt]["fail"] += 1
            
            # Find problem areas
            problem_areas = [
                dt for dt, counts in common_types.items()
                if counts["fail"] > counts["success"]
            ]
            
            if problem_areas:
                return f"[{category}] Mixed performance ({successes}/{total} success). Focus improvement on: {', '.join(problem_areas)}"
            else:
                return f"[{category}] Moderate performance: {successes}/{total} decisions successful. Continue monitoring."
    
    def _store_insight(self, category: str, insight: str):
        """Store an insight for future use."""
        from backend.services.unified_memory import get_unified_memory
        
        memory = get_unified_memory()
        memory.store_insight(category, insight, source="consolidation")
    
    def update_expert_calibration(self, council: str, expert: str, 
                                   topic: str, was_correct: bool) -> Dict[str, Any]:
        """
        Update an expert's calibration based on outcome.
        
        This makes Council votes weighted by track record.
        """
        from backend.services.unified_memory import get_unified_memory
        
        memory = get_unified_memory()
        return memory.update_calibration(council, expert, topic, was_correct)
    
    def get_expert_weight(self, council: str, expert: str, 
                          topic: str = None) -> float:
        """
        Get the weight for an expert's vote based on calibration.
        
        More accurate experts get higher weights.
        """
        from backend.services.unified_memory import get_unified_memory
        
        memory = get_unified_memory()
        cal = memory.get_calibration(council, expert)
        
        if topic and topic in cal.get("by_topic", {}):
            accuracy = cal["by_topic"][topic].get("accuracy", 0.5)
        else:
            accuracy = cal.get("overall_accuracy", 0.5)
        
        # Weight is accuracy^2 to amplify differences
        # Min weight 0.2, max weight 1.0
        weight = max(0.2, min(1.0, accuracy ** 2))
        return weight
    
    def get_insights_for_prompt(self, topics: List[str] = None) -> str:
        """
        Get consolidated insights formatted for injection into system prompt.
        
        This is how Daena's accumulated knowledge affects her reasoning.
        """
        from backend.services.unified_memory import get_unified_memory
        
        memory = get_unified_memory()
        
        all_insights = []
        categories_to_check = topics or ["defi_scan", "security", "research", "general"]
        
        for cat in categories_to_check:
            insights = memory.get_insights(cat)
            for ins in insights[-3:]:  # Last 3 insights per category
                all_insights.append(ins.get("insight", ""))
        
        if not all_insights:
            return ""
        
        formatted = "\n\nLEARNED INSIGHTS (from operational experience):\n"
        for i, insight in enumerate(all_insights[:10], 1):  # Max 10 insights
            formatted += f"{i}. {insight}\n"
        
        return formatted
    
    def get_stats(self) -> Dict[str, Any]:
        """Get consolidation statistics."""
        now = datetime.now(timezone.utc)
        
        recent_7d = sum(1 for l in self._lessons if self._is_recent(l.extracted_at, 7))
        recent_30d = sum(1 for l in self._lessons if self._is_recent(l.extracted_at, 30))
        
        by_category = {}
        for lesson in self._lessons:
            cat = lesson.category
            by_category[cat] = by_category.get(cat, 0) + 1
        
        return {
            "total_lessons": len(self._lessons),
            "lessons_7d": recent_7d,
            "lessons_30d": recent_30d,
            "by_category": by_category,
            "last_consolidation": self._get_last_run()
        }
    
    def _get_last_run(self) -> Optional[str]:
        """Get timestamp of last consolidation run."""
        if CONSOLIDATION_LOG.exists():
            try:
                with open(CONSOLIDATION_LOG, "r") as f:
                    data = json.load(f)
                    return data.get("last_run")
            except:
                pass
        return None


# ============================================
# SINGLETON
# ============================================

_consolidation: Optional[MemoryConsolidation] = None


def get_memory_consolidation() -> MemoryConsolidation:
    """Get the global memory consolidation instance."""
    global _consolidation
    if _consolidation is None:
        _consolidation = MemoryConsolidation()
    return _consolidation
