# CURSOR PROMPT 5: TWO-TIER COUNCIL SYSTEM

You are working in the Mas-AI-Official/daena repository. Implement the two-tier council deliberation system for enhanced decision-making.

## GOAL
Create a council system where:
- **Tier 1**: LLM Consensus Council (3+ models vote on same prompt)
- **Tier 2**: Persona Expert Council (Jobs, Dalio, Munger personas each consult their own LLM stack)
- **Tier 3**: Daena synthesizes both councils' outputs into final decision

## ARCHITECTURE

```
User Query
    ↓
┌─────────────────────────────────────────────┐
│           TIER 1: LLM CONSENSUS             │
│                                             │
│  Same Prompt → Multiple Models              │
│                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │ Qwen2.5  │  │ Llama3.3 │  │  Claude  │ │
│  │  14B     │  │   70B    │  │  Sonnet  │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘ │
│       │             │             │        │
│       └─────────────┴─────────────┘        │
│                     ↓                       │
│              Vote & Consensus               │
└─────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────┐
│        TIER 2: PERSONA EXPERT COUNCIL       │
│                                             │
│  Different Methodologies                    │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │  Steve Jobs Persona                 │   │
│  │  Focus: UX, Innovation              │   │
│  │  Consults: Qwen2.5, Claude          │   │
│  └─────────────────────────────────────┘   │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │  Ray Dalio Persona                  │   │
│  │  Focus: Strategy, Risk Management   │   │
│  │  Consults: Llama3.3, GPT-4          │   │
│  └─────────────────────────────────────┘   │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │  Charlie Munger Persona             │   │
│  │  Focus: First Principles            │   │
│  │  Consults: Claude, Gemini           │   │
│  └─────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────┐
│         TIER 3: DAENA SYNTHESIS             │
│                                             │
│  Merges:                                    │
│  - LLM consensus conclusion                 │
│  - Expert persona opinions                  │
│  - Daena's own reasoning                    │
│  - NBMF memory context                      │
│                                             │
│  Output: Final Decision + Confidence        │
└─────────────────────────────────────────────┘
```

## ACTIONS

### A) Create backend/services/llm_consensus_council.py:

```python
import asyncio
from typing import List, Dict
import hashlib
from backend.services.nbmf_memory import NBMFMemory
from backend.integrations.llm_router import LLMRouter

class LLMConsensusCouncil:
    """
    Tier 1: Query multiple LLMs with same prompt and vote
    """
    
    def __init__(self, models: List[str] = None):
        if models is None:
            models = [
                "qwen2.5-coder:14b-instruct",
                "llama3.3:70b-q4_K_M",
                "claude-3-5-sonnet-latest"
            ]
        self.models = models
        self.llm_router = LLMRouter()
        self.nbmf = NBMFMemory()
    
    async def vote(self, prompt: str, context: Dict = None) -> Dict:
        """
        Query all models in parallel and calculate consensus
        
        Returns:
            {
                "individual_responses": [...],
                "consensus": "...",
                "confidence": 0.85,
                "voting_details": {...}
            }
        """
        # Check NBMF cache first
        cache_key = self._get_cache_key(prompt)
        cached = await self.nbmf.read(cache_key)
        if cached:
            return cached
        
        # Query all models in parallel
        tasks = [
            self._query_model(model, prompt, context)
            for model in self.models
        ]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out errors
        valid_responses = [
            r for r in responses
            if not isinstance(r, Exception)
        ]
        
        if not valid_responses:
            return {
                "error": "All models failed",
                "individual_responses": responses
            }
        
        # Calculate consensus
        consensus_result = self._calculate_consensus(valid_responses)
        
        # Cache result
        await self.nbmf.write(cache_key, consensus_result)
        
        return consensus_result
    
    async def _query_model(self, model: str, prompt: str, context: Dict) -> Dict:
        """Query a single model"""
        try:
            response = await self.llm_router.query(
                model=model,
                prompt=prompt,
                context=context
            )
            
            return {
                "model": model,
                "response": response,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "model": model,
                "error": str(e)
            }
    
    def _calculate_consensus(self, responses: List[Dict]) -> Dict:
        """
        Calculate consensus from multiple responses
        Uses semantic similarity + voting
        """
        # Extract text responses
        texts = [r["response"] for r in responses if "response" in r]
        
        # Simple voting: Most common response
        # TODO: Implement semantic similarity clustering
        from collections import Counter
        vote_counts = Counter(texts)
        most_common = vote_counts.most_common(1)[0]
        
        consensus_text = most_common[0]
        votes = most_common[1]
        confidence = votes / len(texts)
        
        return {
            "individual_responses": responses,
            "consensus": consensus_text,
            "confidence": confidence,
            "voting_details": {
                "total_responses": len(responses),
                "consensus_votes": votes,
                "vote_distribution": dict(vote_counts)
            }
        }
    
    def _get_cache_key(self, prompt: str) -> str:
        """Generate cache key from prompt"""
        return f"council_consensus_{hashlib.md5(prompt.encode()).hexdigest()}"
```

### B) Create backend/services/persona_expert_council.py:

```python
from typing import Dict, List
import asyncio
from backend.integrations.llm_router import LLMRouter

class PersonaExpert:
    """Base class for persona experts"""
    
    def __init__(self, name: str, focus_areas: List[str], preferred_models: List[str]):
        self.name = name
        self.focus_areas = focus_areas
        self.preferred_models = preferred_models
        self.llm_router = LLMRouter()
    
    async def analyze(self, question: str, context: Dict) -> Dict:
        """
        Analyze question through persona's lens
        """
        # Build persona-specific prompt
        persona_prompt = self._build_persona_prompt(question, context)
        
        # Consult multiple models
        responses = []
        for model in self.preferred_models:
            try:
                response = await self.llm_router.query(model, persona_prompt)
                responses.append({"model": model, "response": response})
            except Exception as e:
                responses.append({"model": model, "error": str(e)})
        
        # Synthesize responses through persona filter
        final_opinion = self._synthesize(responses)
        
        return {
            "expert": self.name,
            "focus_areas": self.focus_areas,
            "raw_responses": responses,
            "opinion": final_opinion,
            "confidence": self._calculate_confidence(responses)
        }
    
    def _build_persona_prompt(self, question: str, context: Dict) -> str:
        """Override in subclass"""
        raise NotImplementedError
    
    def _synthesize(self, responses: List[Dict]) -> str:
        """Synthesize responses through persona lens"""
        # Default: Pick best response
        valid = [r for r in responses if "response" in r]
        if not valid:
            return "Unable to form opinion - all queries failed"
        
        return valid[0]["response"]
    
    def _calculate_confidence(self, responses: List[Dict]) -> float:
        """Calculate confidence in opinion"""
        valid = [r for r in responses if "response" in r]
        return len(valid) / len(responses)


class SteveJobsPersona(PersonaExpert):
    """Steve Jobs: Focus on UX, Innovation, Simplicity"""
    
    def __init__(self):
        super().__init__(
            name="Steve Jobs",
            focus_areas=["User Experience", "Innovation", "Simplicity", "Design"],
            preferred_models=["qwen2.5-coder:14b-instruct", "claude-3-5-sonnet-latest"]
        )
    
    def _build_persona_prompt(self, question: str, context: Dict) -> str:
        return f"""
You are Steve Jobs. Analyze this question through your lens of:
- User experience comes first
- Simplicity is the ultimate sophistication
- Innovation distinguishes leaders from followers
- Design is how it works, not just how it looks

Question: {question}

Context: {context}

Provide your recommendation focusing on what creates the best user experience.
"""


class RayDalioPersona(PersonaExpert):
    """Ray Dalio: Focus on Strategy, Risk Management, Principles"""
    
    def __init__(self):
        super().__init__(
            name="Ray Dalio",
            focus_areas=["Strategy", "Risk Management", "Principles", "Systems Thinking"],
            preferred_models=["llama3.3:70b-q4_K_M", "gpt-4o"]
        )
    
    def _build_persona_prompt(self, question: str, context: Dict) -> str:
        return f"""
You are Ray Dalio. Analyze this question through your principles:
- Truth is the foundation of good decisions
- Radical transparency and idea meritocracy
- Think of problems as machines to understand
- Balance risk vs reward systematically

Question: {question}

Context: {context}

Provide your recommendation based on principles and risk management.
"""


class CharlieMungerPersona(PersonaExpert):
    """Charlie Munger: Focus on First Principles, Mental Models"""
    
    def __init__(self):
        super().__init__(
            name="Charlie Munger",
            focus_areas=["First Principles", "Mental Models", "Rationality", "Long-term Thinking"],
            preferred_models=["claude-3-5-sonnet-latest", "gemini-2.0-flash"]
        )
    
    def _build_persona_prompt(self, question: str, context: Dict) -> str:
        return f"""
You are Charlie Munger. Analyze this question using mental models:
- Invert, always invert
- Use a latticework of mental models
- Avoid the Lollapalooza effect (multiple biases compounding)
- Think long-term

Question: {question}

Context: {context}

Provide your recommendation based on first principles and mental models.
"""


class PersonaExpertCouncil:
    """
    Tier 2: Consult expert personas
    """
    
    def __init__(self):
        self.experts = {
            "steve_jobs": SteveJobsPersona(),
            "ray_dalio": RayDalioPersona(),
            "charlie_munger": CharlieMungerPersona()
        }
    
    async def consult(self, question: str, context: Dict) -> Dict:
        """
        Get opinions from all expert personas
        """
        # Query all experts in parallel
        tasks = [
            expert.analyze(question, context)
            for expert in self.experts.values()
        ]
        
        expert_opinions = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out errors
        valid_opinions = [
            op for op in expert_opinions
            if not isinstance(op, Exception)
        ]
        
        return {
            "expert_opinions": valid_opinions,
            "total_experts": len(self.experts),
            "successful_consultations": len(valid_opinions)
        }
```

### C) Create backend/services/daena_synthesis.py:

```python
from backend.services.llm_consensus_council import LLMConsensusCouncil
from backend.services.persona_expert_council import PersonaExpertCouncil
from backend.integrations.llm_router import LLMRouter
from backend.services.nbmf_memory import NBMFMemory

class DaenaSynthesis:
    """
    Tier 3: Daena synthesizes all council inputs
    """
    
    def __init__(self):
        self.llm_council = LLMConsensusCouncil()
        self.expert_council = PersonaExpertCouncil()
        self.llm_router = LLMRouter()
        self.nbmf = NBMFMemory()
    
    async def decide(self, question: str, context: Dict = None) -> Dict:
        """
        Make final decision by synthesizing all councils
        """
        if context is None:
            context = {}
        
        # 1. Get LLM consensus
        llm_result = await self.llm_council.vote(question, context)
        
        # 2. Get expert opinions
        expert_result = await self.expert_council.consult(question, context)
        
        # 3. Query NBMF for relevant memories
        memories = await self.nbmf.search(question, top_k=5)
        
        # 4. Daena's own synthesis
        synthesis_prompt = self._build_synthesis_prompt(
            question, 
            llm_result,
            expert_result,
            memories
        )
        
        final_decision = await self.llm_router.query(
            model="qwen2.5-coder:14b-instruct",
            prompt=synthesis_prompt
        )
        
        # 5. Store decision in NBMF
        await self.nbmf.write(f"decision_{question}", {
            "question": question,
            "llm_consensus": llm_result,
            "expert_opinions": expert_result,
            "final_decision": final_decision,
            "timestamp": datetime.now().isoformat()
        })
        
        return {
            "question": question,
            "llm_consensus": llm_result,
            "expert_opinions": expert_result,
            "final_decision": final_decision,
            "confidence": self._calculate_overall_confidence(llm_result, expert_result)
        }
    
    def _build_synthesis_prompt(self, question, llm_result, expert_result, memories):
        """Build prompt for final synthesis"""
        return f"""
You are Daena, synthesizing multiple council inputs to make a final decision.

Original Question: {question}

LLM Consensus Council says:
{llm_result.get('consensus', 'N/A')}
Confidence: {llm_result.get('confidence', 0)}

Expert Council Opinions:
{self._format_expert_opinions(expert_result)}

Relevant Memories:
{self._format_memories(memories)}

Synthesize all inputs and provide:
1. Final decision
2. Reasoning
3. Confidence level (0-1)
4. Potential risks/caveats
"""
    
    def _format_expert_opinions(self, expert_result):
        """Format expert opinions for prompt"""
        lines = []
        for opinion in expert_result.get("expert_opinions", []):
            lines.append(f"- {opinion['expert']}: {opinion['opinion']}")
        return "\n".join(lines)
    
    def _format_memories(self, memories):
        """Format memories for prompt"""
        if not memories:
            return "No relevant memories found"
        return "\n".join([f"- {m}" for m in memories[:3]])
    
    def _calculate_overall_confidence(self, llm_result, expert_result):
        """Calculate overall confidence"""
        llm_conf = llm_result.get("confidence", 0)
        expert_count = expert_result.get("successful_consultations", 0)
        expert_conf = expert_count / max(expert_result.get("total_experts", 1), 1)
        
        return (llm_conf + expert_conf) / 2
```

### D) Create backend/routes/council.py:

```python
from fastapi import APIRouter
from pydantic import BaseModel
from backend.services.daena_synthesis import DaenaSynthesis

router = APIRouter(prefix="/api/v1/council", tags=["Council"])

synthesis_engine = DaenaSynthesis()

class CouncilRequest(BaseModel):
    question: str
    context: dict = {}

@router.post("/decide")
async def council_decision(request: CouncilRequest):
    """
    Submit question to full council deliberation
    """
    result = await synthesis_engine.decide(request.question, request.context)
    return result

@router.get("/history")
async def get_decision_history(limit: int = 10):
    """
    Get history of council decisions
    """
    # TODO: Query NBMF for past decisions
    return {"decisions": [], "total": 0}
```

### E) Update backend/main.py to register council routes:

```python
from backend.routes.council import router as council_router

# Add to main.py
app.include_router(council_router)
```

### F) Create frontend/templates/councils.html (update):

```html
<div class="council-interface">
    <h2>Council Deliberation</h2>
    
    <div class="question-input">
        <textarea id="council-question" placeholder="Enter your question..."></textarea>
        <button onclick="submitToCouncil()">Submit to Council</button>
    </div>
    
    <div id="council-result" style="display:none;">
        <h3>Deliberation Results</h3>
        
        <div class="llm-consensus">
            <h4>LLM Consensus Council</h4>
            <p id="llm-consensus-text"></p>
            <span class="confidence" id="llm-confidence"></span>
        </div>
        
        <div class="expert-opinions">
            <h4>Expert Council</h4>
            <div id="expert-opinions-list"></div>
        </div>
        
        <div class="final-decision">
            <h4>Daena's Final Decision</h4>
            <p id="final-decision-text"></p>
            <span class="overall-confidence" id="overall-confidence"></span>
        </div>
    </div>
</div>

<script>
async function submitToCouncil() {
    const question = document.getElementById('council-question').value;
    
    const response = await fetch('http://localhost:8000/api/v1/council/decide', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({question: question, context: {}})
    });
    
    const result = await response.json();
    displayCouncilResult(result);
}

function displayCouncilResult(result) {
    document.getElementById('council-result').style.display = 'block';
    
    // LLM Consensus
    document.getElementById('llm-consensus-text').textContent = 
        result.llm_consensus.consensus;
    document.getElementById('llm-confidence').textContent = 
        `Confidence: ${(result.llm_consensus.confidence * 100).toFixed(1)}%`;
    
    // Expert Opinions
    const expertList = document.getElementById('expert-opinions-list');
    expertList.innerHTML = '';
    result.expert_opinions.expert_opinions.forEach(opinion => {
        const div = document.createElement('div');
        div.innerHTML = `<strong>${opinion.expert}:</strong> ${opinion.opinion}`;
        expertList.appendChild(div);
    });
    
    // Final Decision
    document.getElementById('final-decision-text').textContent = 
        result.final_decision;
    document.getElementById('overall-confidence').textContent = 
        `Confidence: ${(result.confidence * 100).toFixed(1)}%`;
}
</script>
```

## DELIVERABLE

1. All council service files
2. Council API routes
3. Frontend visualization
4. Unit tests
5. Integration with existing Daena decision pipeline

## TESTING CHECKLIST

- [ ] Submit question to LLM Consensus Council → Get consensus from 3 models
- [ ] Submit question to Expert Council → Get opinions from Jobs, Dalio, Munger
- [ ] Submit to full synthesis → Get final decision
- [ ] Check NBMF → Decision should be cached
- [ ] Frontend shows all council results clearly
- [ ] Confidence scores make sense (0-1 range)
- [ ] Errors handled gracefully (e.g. if one model fails)
