"""
Autonomous Council Service
===========================
Enables the Council to operate without human approval using LLM Consensus.
Ensures safety for autonomous action execution.
"""

import logging
import asyncio
import json
from typing import Dict, Any, List, Optional
from backend.services.llm_router import get_llm_router
from backend.services.governance_loop import get_governance_loop

logger = logging.getLogger(__name__)

class AutonomousCouncil:
    def __init__(self):
        self.router = get_llm_router()
        self.governance = get_governance_loop()
        
    async def consult(self, action_request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform an autonomous multi-LLM consultation.
        Replaces manual human approval for medium-risk tasks when in autopilot.
        """
        logger.info(f"Council: Autonomous consultation for {action_request.get('action_type')}")
        
        # 1. Prepare Consultation prompt
        prompt = f"""
        Governance Consultation Request:
        Action: {action_request.get('action_type')}
        Description: {action_request.get('description')}
        Parameters: {json.dumps(action_request.get('parameters'))}
        
        You are part of the Daena Council of 8 Department Leads. 
        Evaluate if this action is safe, aligned with company goals, and does not pose security risks.
        Respond with:
        RECOMMENDATION: (APPROVE/DENY/REVIEW)
        CONFIDENCE: (0.0-1.0)
        REASONING: ...
        """
        
        # 2. Use Council Mode for autonomous reliability
        try:
            # Multi-model consultation
            council_output = await self.router.council_mode(prompt)
            text = council_output["text"]
            
            # 3. Parse recommendation
            recommendation = "REVIEW"
            if "APPROVE" in text: recommendation = "APPROVE"
            elif "DENY" in text: recommendation = "DENY"
            
            # Heuristic: if consensus says APPROVE but confidence might be implied by advisor agreement
            # We'll just parse the synthesized text
            
            confidence = 0.5
            if "CONFIDENCE:" in text:
                try: confidence = float(text.split("CONFIDENCE:")[1].split()[0])
                except: pass

            logger.info(f"Council Mode Recommendation: {recommendation} ({confidence})")
            
            return {
                "recommendation": recommendation,
                "confidence": confidence,
                "consensus_text": text,
                "advisors": council_output.get("advisors", []),
                "autonomous": True
            }
        except Exception as e:
            logger.error(f"Council autonomous consultation failed: {e}")
            return {"recommendation": "REVIEW", "confidence": 0, "error": str(e)}

# Singleton
_council = None

def get_autonomous_council():
    global _council
    if not _council:
        _council = AutonomousCouncil()
    return _council
