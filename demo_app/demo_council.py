"""
Demo Council - Lightweight Prompt-Based Council for AI Tinkerers Demo

Three roles that evaluate each response:
- Security: Evaluate threats/risks
- Reliability: Assess uptime/performance concerns
- Product: User experience feedback

Each returns: critique bullets + vote + confidence score
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class CouncilVote(Enum):
    """Council member vote options."""
    APPROVE = "approve"
    REJECT = "reject"
    ABSTAIN = "abstain"


@dataclass
class CouncilRoleOutput:
    """Output from a single council role."""
    role: str
    persona: str
    critiques: List[str]  # 3 bullet points
    vote: CouncilVote
    confidence: float  # 0.0 to 1.0
    reasoning: str


@dataclass
class CouncilMergeResult:
    """Merged result from all council roles."""
    final_decision: CouncilVote
    consensus_confidence: float
    role_outputs: List[CouncilRoleOutput]
    merge_summary: str
    conflicts: List[str]


# Council role configurations
DEMO_COUNCIL_ROLES = {
    "security": {
        "persona": "Security Analyst",
        "focus": "threats, vulnerabilities, data protection, access control",
        "icon": "🔒",
        "color": "#ef4444"  # red
    },
    "reliability": {
        "persona": "Site Reliability Engineer", 
        "focus": "uptime, performance, scalability, error handling",
        "icon": "⚙️",
        "color": "#3b82f6"  # blue
    },
    "product": {
        "persona": "Product Manager",
        "focus": "user experience, business value, feature completeness",
        "icon": "📊",
        "color": "#10b981"  # green
    }
}


def _build_council_prompt(role: str, config: dict, prompt: str, response: str) -> str:
    """Build the prompt for a council role evaluation."""
    return f"""You are a {config['persona']} evaluating an AI response from the perspective of {config['focus']}.

USER PROMPT: {prompt}

AI RESPONSE: {response}

Evaluate this response and provide:
1. THREE specific critique points (bullets)
2. Your VOTE: approve, reject, or abstain
3. Your CONFIDENCE (0.0 to 1.0)
4. Brief reasoning (1-2 sentences)

Format your response as:
CRITIQUE 1: [first critique]
CRITIQUE 2: [second critique]
CRITIQUE 3: [third critique]
VOTE: [approve/reject/abstain]
CONFIDENCE: [0.0-1.0]
REASONING: [your reasoning]
"""


def _parse_council_response(role: str, config: dict, raw_response: str) -> CouncilRoleOutput:
    """Parse raw LLM response into structured council output."""
    lines = raw_response.strip().split('\n')
    
    critiques = []
    vote = CouncilVote.ABSTAIN
    confidence = 0.5
    reasoning = ""
    
    for line in lines:
        line = line.strip()
        if line.startswith("CRITIQUE"):
            # Extract critique text after the colon
            if ":" in line:
                critique_text = line.split(":", 1)[1].strip()
                if critique_text:
                    critiques.append(critique_text)
        elif line.startswith("VOTE:"):
            vote_str = line.split(":", 1)[1].strip().lower()
            if "approve" in vote_str:
                vote = CouncilVote.APPROVE
            elif "reject" in vote_str:
                vote = CouncilVote.REJECT
            else:
                vote = CouncilVote.ABSTAIN
        elif line.startswith("CONFIDENCE:"):
            try:
                conf_str = line.split(":", 1)[1].strip()
                confidence = float(conf_str)
                confidence = max(0.0, min(1.0, confidence))
            except ValueError:
                confidence = 0.5
        elif line.startswith("REASONING:"):
            reasoning = line.split(":", 1)[1].strip()
    
    # Ensure we have 3 critiques
    while len(critiques) < 3:
        critiques.append("No additional concerns noted.")
    
    return CouncilRoleOutput(
        role=role,
        persona=config["persona"],
        critiques=critiques[:3],
        vote=vote,
        confidence=confidence,
        reasoning=reasoning or "Standard evaluation criteria applied."
    )


async def evaluate_with_council(
    prompt: str,
    response: str,
    llm_generate_func=None
) -> CouncilMergeResult:
    """
    Run prompt-based council evaluation.
    
    Args:
        prompt: Original user prompt
        response: AI-generated response to evaluate
        llm_generate_func: Async function to generate LLM responses (optional)
        
    Returns:
        CouncilMergeResult with all role outputs and merged decision
    """
    role_outputs = []
    
    for role, config in DEMO_COUNCIL_ROLES.items():
        council_prompt = _build_council_prompt(role, config, prompt, response)
        
        if llm_generate_func:
            try:
                raw_response = await llm_generate_func(council_prompt)
            except Exception as e:
                logger.warning(f"Council role {role} failed: {e}")
                raw_response = f"CRITIQUE 1: Unable to evaluate\nCRITIQUE 2: System temporarily unavailable\nCRITIQUE 3: Defaulting to abstain\nVOTE: abstain\nCONFIDENCE: 0.3\nREASONING: Evaluation service unavailable"
        else:
            # Demo mode - generate mock evaluations
            raw_response = _generate_mock_evaluation(role, response)
        
        role_output = _parse_council_response(role, config, raw_response)
        role_outputs.append(role_output)
    
    # Merge results
    merge_result = _merge_council_votes(role_outputs)
    
    return merge_result


def _generate_mock_evaluation(role: str, response: str) -> str:
    """Generate mock council evaluation for demo purposes."""
    mock_responses = {
        "security": """CRITIQUE 1: Response does not expose sensitive credentials or API keys
CRITIQUE 2: No injection vulnerabilities detected in the output format
CRITIQUE 3: Appropriate access boundaries maintained in the explanation
VOTE: approve
CONFIDENCE: 0.92
REASONING: Response follows security best practices and doesn't leak sensitive information.""",
        
        "reliability": """CRITIQUE 1: Response generated within acceptable latency bounds
CRITIQUE 2: No cascading failure risks identified in the approach
CRITIQUE 3: Fallback mechanisms properly described for error scenarios
VOTE: approve
CONFIDENCE: 0.88
REASONING: System demonstrated reliable operation with appropriate error handling.""",
        
        "product": """CRITIQUE 1: Clear and user-friendly explanation provided
CRITIQUE 2: Response addresses the user's actual intent effectively
CRITIQUE 3: Good balance of technical depth and accessibility
VOTE: approve
CONFIDENCE: 0.95
REASONING: Response delivers strong user value and aligns with product goals."""
    }
    
    return mock_responses.get(role, mock_responses["product"])


def _merge_council_votes(role_outputs: List[CouncilRoleOutput]) -> CouncilMergeResult:
    """Merge individual council votes into final decision."""
    approve_count = sum(1 for r in role_outputs if r.vote == CouncilVote.APPROVE)
    reject_count = sum(1 for r in role_outputs if r.vote == CouncilVote.REJECT)
    
    # Weighted average confidence
    total_confidence = sum(r.confidence for r in role_outputs)
    avg_confidence = total_confidence / len(role_outputs) if role_outputs else 0.5
    
    # Determine final decision
    if reject_count >= 2:
        final_decision = CouncilVote.REJECT
    elif approve_count >= 2:
        final_decision = CouncilVote.APPROVE
    else:
        final_decision = CouncilVote.ABSTAIN
    
    # Find conflicts
    conflicts = []
    votes = [r.vote for r in role_outputs]
    if CouncilVote.APPROVE in votes and CouncilVote.REJECT in votes:
        conflicts.append("Split decision between approve and reject")
    
    # Generate summary
    vote_summary = ", ".join([f"{r.role}: {r.vote.value}" for r in role_outputs])
    merge_summary = f"Council decision: {final_decision.value.upper()} (votes: {vote_summary})"
    
    return CouncilMergeResult(
        final_decision=final_decision,
        consensus_confidence=avg_confidence,
        role_outputs=role_outputs,
        merge_summary=merge_summary,
        conflicts=conflicts
    )


def council_result_to_dict(result: CouncilMergeResult) -> Dict[str, Any]:
    """Convert council result to JSON-serializable dict."""
    return {
        "final_decision": result.final_decision.value,
        "consensus_confidence": result.consensus_confidence,
        "merge_summary": result.merge_summary,
        "conflicts": result.conflicts,
        "role_outputs": [
            {
                "role": r.role,
                "persona": r.persona,
                "critiques": r.critiques,
                "vote": r.vote.value,
                "confidence": r.confidence,
                "reasoning": r.reasoning,
                "icon": DEMO_COUNCIL_ROLES[r.role]["icon"],
                "color": DEMO_COUNCIL_ROLES[r.role]["color"]
            }
            for r in result.role_outputs
        ]
    }
