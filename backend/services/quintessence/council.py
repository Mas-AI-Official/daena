
import logging
import asyncio
from typing import Dict, List, Any, Optional
from backend.services.llm_router import get_router
from backend.services.quintessence.experts import EXPERT_PROFILES
from backend.services.quintessence.precedent_engine import get_precedent_engine

logger = logging.getLogger(__name__)

class QuintessenceCouncil:
    """Orchestrates Tier 2: THE QUINTESSENCE Supreme Deliberation."""

    def __init__(self):
        self.router = get_router()
        self.engine = get_precedent_engine()

    async def supreme_deliberation(self, problem: str, domain: str) -> Dict[str, Any]:
        """
        Run the complete Quintessence deliberation flow:
        1. Multi-LLM Baseline
        2. Precedent Recall
        3. Parallel Expert Consultations
        4. Supreme Synthesis
        """
        logger.info(f"Invoking THE QUINTESSENCE for: {problem[:50]}...")
        
        # 1. Baseline Consensus (Tier 1)
        baseline_task = self.router.council_mode(problem)
        
        # 2. Precedent Retrieval
        precedents = self.engine.find_similar(problem, domain)
        
        # 3. Parallel Expert Deliberation
        expert_tasks = []
        for expert_id in EXPERT_PROFILES:
            expert_tasks.append(self._consult_expert(expert_id, problem))
        
        # Gather all
        baseline, *expert_results = await asyncio.gather(baseline_task, *expert_tasks)
        
        expert_conclusions = {}
        for i, expert_id in enumerate(EXPERT_PROFILES):
            expert_conclusions[expert_id] = expert_results[i]

        # 4. Supreme Synthesis
        synthesis_prompt = f"""
        YOU ARE DAENA, AI VP. SYNTHESIZE THE SUPREME DECISION.
        
        PROBLEM: {problem}
        DOMAIN: {domain}
        
        PREVIOUS PRECEDENTS: {precedents}
        BASELINE CONSENSUS: {baseline.get('text')}
        
        EXPERT PERSPECTIVES:
        """
        for eid, res in expert_conclusions.items():
            profile = EXPERT_PROFILES[eid]
            synthesis_prompt += f"\n--- {profile['name']} ({profile['title']}) ---\n{res}\n"

        synthesis_prompt += "\nProduce a FINAL GOVERNED DECISION with Rationale, Confidence (0-1), Risks, and Next Steps."
        
        final_response = await self.router.generate(synthesis_prompt, complexity="critical")
        
        # Save results as precedent
        precedent_id = self.engine.save_precedent({
            "problem_summary": problem,
            "domain": domain,
            "experts": list(EXPERT_PROFILES.keys()),
            "conclusions": expert_conclusions,
            "baseline": baseline.get("text"),
            "final_decision": final_response.get("text"),
            "rationale": "Synthesized from Multi-Council deliberation",
            "confidence": 0.95,
            "tags": [domain, "quintessence"]
        })

        return {
            "decision": final_response.get("text"),
            "precedent_id": precedent_id,
            "experts": expert_conclusions,
            "baseline": baseline,
            "precedents_found": len(precedents)
        }

    async def _consult_expert(self, expert_id: str, problem: str) -> str:
        """Consult a specific expert persona."""
        profile = EXPERT_PROFILES[expert_id]
        
        # Step A: Translation
        translation = await self.router.generate(
            f"{profile['translation_prompt']}\n\nORIGINAL QUERY: {problem}",
            complexity="medium"
        )
        expert_query = translation.get("text")
        
        # Step B: Expert Inquiry (Multi-LLM)
        expert_consult = await self.router.council_mode(
            f"Think as {profile['name']} ({profile['title']}). Thinking Style: {profile['thinking_style']}\n\nProblem: {expert_query}"
        )
        
        return expert_consult.get("text")

# Singleton
_council = None
def get_quintessence_council():
    global _council
    if not _council:
        _council = QuintessenceCouncil()
    return _council
