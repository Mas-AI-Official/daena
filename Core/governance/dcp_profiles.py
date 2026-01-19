"""
Decision Constraint Profiles (DCPs)
Define advisor archetypes via objectives, constraints, and rejection criteria.

LAW 3 — NO COSPLAY INTELLIGENCE:
Agents do not "act like" celebrities. Expert behavior is modeled via DCPs:
objectives, constraints, rejection rules, blind spots.
"""

from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)


class DecisionConstraintProfile(BaseModel):
    """
    A DCP defines an advisor's decision-making framework
    
    Components:
    - Objective function: what it maximizes
    - Constraints: what it refuses
    - Rejection triggers: hard "no" signals
    - Blind spots: declared weaknesses
    - Mandatory questions: always asks these
    """
    name: str
    description: str
    objective_function: str  # What this advisor optimizes for
    constraints: List[str]  # Hard boundaries
    rejection_triggers: List[str]  # Signals for hard "no"
    blind_spots: List[str]  # Known weaknesses
    mandatory_questions: List[str]  # Always asks these
    weight: float = 1.0  # Influence in council (0.5-1.5)


class DCPProfileManager:
    """
    Manages Decision Constraint Profiles
    Provides pre-built archetypes for councils
    """
    
    def __init__(self):
        """Initialize with default DCP archetypes"""
        self.profiles = self._initialize_default_profiles()
        logger.info(f"✅ DCP Profile Manager initialized with {len(self.profiles)} archetypes")
    
    def _initialize_default_profiles(self) -> Dict[str, DecisionConstraintProfile]:
        """Create default advisor archetypes"""
        
        return {
            "first_principles": DecisionConstraintProfile(
                name="First-Principles Optimizer",
                description="Questions assumptions, seeks root causes, builds from fundamentals",
                objective_function="Maximize clarity and minimize hidden assumptions",
                constraints=[
                    "Never accept 'because everyone does it' as justification",
                    "Must trace every claim to first principles",
                    "Refuses solutions based on analogy alone"
                ],
                rejection_triggers=[
                    "Circular reasoning",
                    "Appeal to authority without evidence",
                    "Hidden assumptions in problem statement"
                ],
                blind_spots=[
                    "May over-analyze simple problems",
                    "Can miss social/political realities",
                    "May dismiss valid heuristics"
                ],
                mandatory_questions=[
                    "What are we actually trying to solve?",
                    "What assumptions are we making?",
                    "Can we break this down further?",
                    "What would this look like if we started from scratch?"
                ],
                weight=1.2
            ),
            
            "long_term_flywheel": DecisionConstraintProfile(
                name="Long-Term Flywheel Builder",
                description="Optimizes for compound effects, sustainable growth, and network effects",
                objective_function="Maximize long-term leverage and compound growth",
                constraints=[
                    "Must show path to self-sustaining growth",
                    "Rejects short-term gains that harm future optionality",
                    "Requires clear flywheel dynamics"
                ],
                rejection_triggers=[
                    "No clear compounding mechanism",
                    "Sacrifices future for present",
                    "Linear growth with no leverage"
                ],
                blind_spots=[
                    "May undervalue quick wins",
                    "Can miss urgent opportunities",
                    "May over-optimize for scale"
                ],
                mandatory_questions=[
                    "What makes this stronger over time?",
                    "Where are the network effects?",
                    "What compounds?",
                    "How does this improve our position in 5 years?"
                ],
                weight=1.3
            ),
            
            "risk_minimizer": DecisionConstraintProfile(
                name="Risk Minimizer",
                description="Identifies failure modes, seeks robustness, values safety margins",
                objective_function="Minimize downside risk and irreversible damage",
                constraints=[
                    "Must have clear rollback plan",
                    "Rejects high-stakes irreversible decisions without redundancy",
                    "Requires safety margins on critical metrics"
                ],
                rejection_triggers=[
                    "Single point of failure",
                    "No rollback plan",
                    "Irreversible with high uncertainty"
                ],
                blind_spots=[
                    "May be overly conservative",
                    "Can miss asymmetric upside",
                    "May over-index on known risks"
                ],
                mandatory_questions=[
                    "What could go wrong?",
                    "What's irreversible?",
                    "Do we have a rollback plan?",
                    "What are the second-order effects?"
                ],
                weight=1.1
            ),
            
            "speed_leverage": DecisionConstraintProfile(
                name="Speed & Leverage Maximizer",
                description="Seeks force multipliers, automation, and rapid iteration",
                objective_function="Maximize value per unit of effort and time",
                constraints=[
                    "Must show clear leverage (1 hour → 10x impact)",
                    "Rejects manual processes that could be automated",
                    "Requires rapid feedback loops"
                ],
                rejection_triggers=[
                    "Linear scaling only",
                    "No automation potential",
                    "Slow feedback loops"
                ],
                blind_spots=[
                    "May under-invest in foundations",
                    "Can miss important details",
                    "May over-automate too early"
                ],
                mandatory_questions=[
                    "How do we 10x this?",
                    "What's the force multiplier?",
                    "Can we automate this?",
                    "How fast can we iterate?"
                ],
                weight=1.0
            ),
            
            "user_market_obsession": DecisionConstraintProfile(
                name="User/Market Obsession",
                description="Centers on user needs, market validation, and real-world adoption",
                objective_function="Maximize customer satisfaction and market fit",
                constraints=[
                    "Must validate with real users",
                    "Rejects solutions users didn't ask for",
                    "Requires measurable user benefit"
                ],
                rejection_triggers=[
                    "No user research",
                    "Solving theoretical problems",
                    "No clear user benefit"
                ],
                blind_spots=[
                    "May miss long-term vision",
                    "Can be overly reactive to feedback",
                    "May dismiss innovative ideas users don't understand yet"
                ],
                mandatory_questions=[
                    "Who is this for?",
                    "What problem does this solve for them?",
                    "How do we know they want this?",
                    "What's the evidence from real users?"
                ],
                weight=1.2
            ),
            
            "systems_thinker": DecisionConstraintProfile(
                name="Systems Thinker",
                description="Maps interdependencies, feedback loops, and emergent behavior",
                objective_function="Maximize understanding of system dynamics",
                constraints=[
                    "Must map key feedback loops",
                    "Rejects local optimization that harms global system",
                    "Requires understanding of second-order effects"
                ],
                rejection_triggers=[
                    "Ignores system dynamics",
                    "Local optimization without global view",
                    "Missing critical dependencies"
                ],
                blind_spots=[
                    "May over-complicate simple problems",
                    "Can get lost in analysis",
                    "May miss need for decisive action"
                ],
                mandatory_questions=[
                    "What are the feedback loops?",
                    "What are the unintended consequences?",
                    "How does this interact with the rest of the system?",
                    "What emerges at scale?"
                ],
                weight=1.1
            )
        }
    
    def get_profile(self, name: str) -> Optional[DecisionConstraintProfile]:
        """Get a DCP by name"""
        return self.profiles.get(name)
    
    def list_profiles(self) -> List[str]:
        """List all available DCP names"""
        return list(self.profiles.keys())
    
    def add_custom_profile(self, profile: DecisionConstraintProfile) -> bool:
        """
        Add a custom DCP
        
        Args:
            profile: Custom DecisionConstraintProfile
        
        Returns:
            True if added, False if already exists
        """
        if profile.name.lower().replace(" ", "_") in self.profiles:
            logger.warning(f"Profile {profile.name} already exists")
            return False
        
        self.profiles[profile.name.lower().replace(" ", "_")] = profile
        logger.info(f"✅ Added custom DCP: {profile.name}")
        return True
    
    def get_council_profiles(
        self,
        council_type: str = "default",
        count: int = 5
    ) -> List[DecisionConstraintProfile]:
        """
        Get a balanced set of DCPs for a council
        
        Args:
            council_type: Type of council (default, technical, business, etc.)
            count: Number of advisors
        
        Returns:
            List of DecisionConstraintProfiles
        """
        if council_type == "default":
            # Balanced default council
            profile_names = [
                "first_principles",
                "long_term_flywheel",
                "risk_minimizer",
                "speed_leverage",
                "user_market_obsession"
            ]
        elif council_type == "technical":
            # Technical decision council
            profile_names = [
                "first_principles",
                "systems_thinker",
                "risk_minimizer",
                "speed_leverage",
                "long_term_flywheel"
            ]
        elif council_type == "business":
            # Business decision council
            profile_names = [
                "user_market_obsession",
                "long_term_flywheel",
                "risk_minimizer",
                "speed_leverage",
                "first_principles"
            ]
        else:
            # Default fallback
            profile_names = list(self.profiles.keys())[:count]
        
        return [self.profiles[name] for name in profile_names[:count]]
    
    def evaluate_decision(
        self,
        decision: str,
        profiles: List[DecisionConstraintProfile],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluate a decision against multiple DCPs
        
        Args:
            decision: The proposed decision
            profiles: List of DCPs to evaluate against
            context: Decision context
        
        Returns:
            Evaluation summary with scores and recommendations
        """
        evaluations = {}
        
        for profile in profiles:
            # Check rejection triggers
            rejections = []
            for trigger in profile.rejection_triggers:
                # Simple keyword matching (in production, use NLP)
                if any(word.lower() in decision.lower() for word in trigger.split()):
                    rejections.append(trigger)
            
            # Generate questions
            questions = profile.mandatory_questions
            
            evaluations[profile.name] = {
                "weight": profile.weight,
                "rejections": rejections,
                "questions": questions,
                "blind_spots": profile.blind_spots,
                "verdict": "rejected" if rejections else "needs_review"
            }
        
        # Summary
        total_rejections = sum(len(e["rejections"]) for e in evaluations.values())
        all_questions = []
        for e in evaluations.values():
            all_questions.extend(e["questions"])
        
        return {
            "decision": decision,
            "evaluations": evaluations,
            "summary": {
                "total_advisors": len(profiles),
                "total_rejections": total_rejections,
                "key_questions": list(set(all_questions)),  # Unique questions
                "recommended_action": "revise" if total_rejections > 0 else "proceed_with_review"
            }
        }


# Global instance
dcp_manager = DCPProfileManager()
