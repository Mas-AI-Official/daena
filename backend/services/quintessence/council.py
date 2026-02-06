from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import json
from .experts import EXPERT_PERSONAS

@dataclass
class DeliberationResult:
    decision: str
    rationale: str
    confidence: float
    expert_conclusions: Dict[str, Any]
    precedent_id: str
    trace: Dict[str, Any]

class QuintessenceCouncil:
    """
    THE QUINTESSENCE - Supreme Council of 5 Expert Personas
    
    Decision flow:
    1. Risk triage → Route to appropriate council
    2. Baseline multi-LLM consensus (Daena's view)
    3. Parallel consultation with all 5 experts
    4. Daena synthesizes all perspectives
    5. Governed final decision
    6. Save as precedent for learning
    """
    
    def __init__(self, llm_router, precedent_engine, governance):
        self.llm_router = llm_router
        self.precedent_engine = precedent_engine
        self.governance = governance
        self.experts = EXPERT_PERSONAS
    
    async def deliberate(
        self, 
        problem: str, 
        domain: str, 
        risk_level: str = "high"
    ) -> DeliberationResult:
        """
        Invoke THE QUINTESSENCE for high-stakes decisions
        """
        
        # Step 1: Check precedents
        precedents = await self.precedent_engine.find_similar(problem, domain)
        
        # Step 2: Baseline consensus (Daena's own view)
        baseline = await self.llm_router.route_with_consensus(
            prompt=problem,
            strategy="consensus"
        )
        
        # Step 3: Parallel expert consultation
        expert_conclusions = {}
        
        for expert_id, expert in self.experts.items():
            # Check if expert is relevant to domain
            if domain not in expert["domains"] and domain != "general":
                continue
            
            # Translate problem to expert's worldview
            translated = self._translate_for_expert(problem, expert)
            
            # Query LLMs as this expert
            conclusion = await self._consult_expert(expert, translated)
            expert_conclusions[expert_id] = conclusion
        
        # Step 4: Daena's supreme synthesis
        final_decision = await self._synthesize(
            problem=problem,
            baseline=baseline,
            expert_conclusions=expert_conclusions,
            precedents=precedents
        )
        
        # Step 5: Governance check
        assessment = await self.governance.assess({
            "type": "quintessence_decision",
            "decision": final_decision,
            "risk_level": risk_level
        })
        
        # Step 6: Save as precedent
        precedent_id = await self.precedent_engine.save({
            "problem": problem,
            "domain": domain,
            "quintessence_consulted": list(expert_conclusions.keys()),
            "expert_conclusions": expert_conclusions,
            "baseline": baseline,
            "final_decision": final_decision,
            "confidence": final_decision["confidence"],
        })
        
        return DeliberationResult(
            decision=final_decision["decision"],
            rationale=final_decision["rationale"],
            confidence=final_decision["confidence"],
            expert_conclusions=expert_conclusions,
            precedent_id=precedent_id,
            trace=self._generate_trace(
                problem, baseline, expert_conclusions, final_decision
            )
        )
    
    def _translate_for_expert(self, problem: str, expert: dict) -> str:
        """Translate problem into expert's worldview"""
        return f"""
        {expert["thinking_style"]}
        
        Problem to analyze:
        {problem}
        
        Respond as {expert["name"]} would. What is your expert conclusion?
        """
    
    async def _consult_expert(self, expert: dict, translated: str) -> dict:
        """Consult an expert persona via multi-LLM"""
        
        responses = []
        for model in expert["llm_models"]:
            try:
                response = await self.llm_router.query(model, translated)
                responses.append(response)
            except Exception as e:
                print(f"[QUINTESSENCE] Model {model} failed: {e}")
        
        # Synthesize expert's view from multiple LLMs
        synthesis = await self.llm_router.synthesize_responses(responses)
        
        return {
            "expert": expert["name"],
            "conclusion": synthesis,
            "models_consulted": expert["llm_models"],
            "raw_responses": responses,
        }
    
    async def _synthesize(
        self,
        problem: str,
        baseline: str,
        expert_conclusions: dict,
        precedents: list
    ) -> dict:
        """Daena synthesizes all expert opinions into final decision"""
        
        synthesis_prompt = f"""
        You are DAENA, synthesizing expert opinions for:
        
        Problem: {problem}
        
        Your baseline view: {baseline}
        
        Expert conclusions:
        {json.dumps(expert_conclusions, indent=2)}
        
        Similar precedents:
        {json.dumps([p["decision"] for p in precedents[:3]], indent=2)}
        
        Synthesize a final decision that:
        1. Weighs all expert perspectives
        2. Considers precedents
        3. Provides clear rationale
        4. Identifies risks and mitigations
        5. Suggests next steps
        
        Return as JSON:
        {{
            "decision": "your final decision",
            "rationale": "why this decision",
            "confidence": 0.0-1.0,
            "risks": ["risk1", "risk2"],
            "mitigations": ["mitigation1", "mitigation2"],
            "next_steps": ["step1", "step2"]
        }}
        """
        
        result = await self.llm_router.route_with_consensus(
            prompt=synthesis_prompt,
            strategy="best"
        )
        
        # Ensure json result
        if isinstance(result, str):
            try:
                # Find JSON block
                import re
                match = re.search(r'\{.*\}', result, re.DOTALL)
                if match:
                    return json.loads(match.group(0))
                return json.loads(result)
            except:
                return {
                    "decision": result, 
                    "rationale": "Parsing failed", 
                    "confidence": 0.5,
                    "risks": [],
                    "mitigations": [],
                    "next_steps": []
                }
        return result

    def _generate_trace(self, problem, baseline, expert_conclusions, final_decision):
        """Generate a trace summary of deliberation"""
        return {
            "problem": problem,
            "baseline": baseline,
            "experts": list(expert_conclusions.keys()),
            "decision": final_decision
        }
