
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import or_
from backend.database import SessionLocal, Precedent, QuintessencePattern

logger = logging.getLogger(__name__)

class PrecedentEngine:
    """Handles storage and retrieval of past decisions for THE QUINTESSENCE."""

    def __init__(self):
        pass

    def save_precedent(self, data: Dict) -> str:
        """Save a new decision as a precedent."""
        db = SessionLocal()
        try:
            pid = data.get("id") or f"prec_{uuid.uuid4().hex[:8]}"
            precedent = Precedent(
                id=pid,
                problem_summary=data["problem_summary"],
                domain=data["domain"],
                quintessence_consulted=data.get("experts", []),
                expert_conclusions=data.get("conclusions", {}),
                baseline_consensus=data.get("baseline"),
                final_decision=data["final_decision"],
                rationale=data["rationale"],
                confidence=data.get("confidence", 0.0),
                pattern_type=data.get("pattern_type"),
                abstract_principle=data.get("principle"),
                tags=data.get("tags", []),
                cross_domain_potential=data.get("potential", 0.5)
            )
            db.add(precedent)
            db.commit()
            logger.info(f"Saved precedent {pid}")
            return pid
        finally:
            db.close()

    def find_similar(self, query: str, domain: Optional[str] = None) -> List[Dict]:
        """Find similar precedents based on keywords and domain."""
        db = SessionLocal()
        try:
            q = db.query(Precedent)
            if domain:
                q = q.filter(Precedent.domain == domain)
            
            # Simple keyword match for now
            keywords = query.lower().split()
            filters = []
            for word in keywords:
                filters.append(Precedent.problem_summary.ilike(f"%{word}%"))
                filters.append(Precedent.rationale.ilike(f"%{word}%"))
            
            if filters:
                q = q.filter(or_(*filters))
            
            results = q.limit(5).all()
            return [self._to_dict(p) for p in results]
        finally:
            db.close()

    def find_cross_domain(self, pattern_type: str, exclude_domain: str) -> List[Dict]:
        """Retrieve precedents with matching patterns from other domains."""
        db = SessionLocal()
        try:
            results = db.query(Precedent).filter(
                Precedent.pattern_type == pattern_type,
                Precedent.domain != exclude_domain
            ).limit(3).all()
            return [self._to_dict(p) for p in results]
        finally:
            db.close()

    def _to_dict(self, p: Precedent) -> Dict:
        return {
            "id": p.id,
            "problem_summary": p.problem_summary,
            "domain": p.domain,
            "final_decision": p.final_decision,
            "rationale": p.rationale,
            "confidence": p.confidence,
            "pattern_type": p.pattern_type,
            "created_at": p.created_at.isoformat() if p.created_at else None
        }

# Singleton
_engine = None
def get_precedent_engine():
    global _engine
    if not _engine:
        _engine = PrecedentEngine()
    return _engine
