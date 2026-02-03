"""
⚠️ CORE FILE — DO NOT DELETE OR REWRITE
Changes allowed ONLY via extension modules.

Daena Brain (canonical, local-first).

This module used to hard-import cloud SDKs and could crash local runs when
optional dependencies were missing. Per project policy:
- No auth required in local mode
- Cloud providers are optional and disabled by default
- Daena must always respond (no dead endpoints)

The canonical generation path is `backend/services/llm_service.py` (Ollama-first).

CRITICAL: This is the canonical Daena brain. Only patch specific functions.
Never replace the entire class or remove process_message() method.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class DaenaBrain:
    """
    Lightweight brain facade that delegates to LLMService (local-first).
    Keeps minimal conversation history (for UX only).
    """

    context_window: int = 10
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)

    async def process_message(self, message: str, context: Optional[Dict[str, Any]] = None) -> str:
        self.conversation_history.append({"role": "user", "content": message, "ts": datetime.utcnow().isoformat()})
        if len(self.conversation_history) > self.context_window:
            self.conversation_history = self.conversation_history[-self.context_window :]

        prompt = self._build_prompt(message, context)

        # Delegate to the canonical service (use singleton, not new instance)
        try:
            from backend.services.llm_service import llm_service
            # Use the global singleton llm_service if available
            if llm_service is not None:
                llm = llm_service
            else:
                # Fallback: create new instance if singleton not initialized
                from backend.services.llm_service import LLMService
                llm = LLMService()
        except Exception as e:
            # Last resort: create new instance
            from backend.services.llm_service import LLMService
            llm = LLMService()
        
        text = await llm.generate_response(
            prompt, 
            max_tokens=800,
            context={"skip_gate": True}
        )

        self.conversation_history.append({"role": "assistant", "content": text, "ts": datetime.utcnow().isoformat()})
        if len(self.conversation_history) > self.context_window:
            self.conversation_history = self.conversation_history[-self.context_window :]
        return text

    def _build_prompt(self, message: str, context: Optional[Dict[str, Any]] = None) -> str:
        # Detect Founder/Operator role for humanized responses
        user_role = context.get("user_role", "guest") if context else "guest"
        user_name = context.get("user_name", "") if context else ""
        
        is_founder = (
            user_role in ("founder", "daena_vp") or 
            user_name.lower() in ("masoud", "founder")
        )
        
        # Detect if this is a project/autonomous execution request
        is_project_request = self._is_project_request(message)
        
        ctx_bits = []
        if context:
            for k in ("department", "project", "tenant_id"):
                if context.get(k):
                    ctx_bits.append(f"{k}: {context.get(k)}")
        ctx = ("\n".join(ctx_bits) + "\n\n") if ctx_bits else ""
        
        if is_project_request:
            # AUTONOMOUS COMPANY MODE - Not a chatbot
            base_prompt = self._get_autonomous_system_prompt()
        elif is_founder:
            # Founder mode: warm, concise, actionable
            base_prompt = (
                "You are Daena, Masoud's AI VP and partner. You manage 8 departments × 6 agents (48 total).\n"
                "STYLE: Be warm, direct, and concise with Masoud. No disclaimers or long explanations.\n"
                "Address him by name ('Hey Masoud' or 'Masoud,'), confirm what he's asking, and suggest next steps.\n"
                "Keep responses SHORT (2-3 sentences max unless he asks for details).\n"
                "WORKSPACE: You have tools to list/search/read files and apply patches. Use tool results; do not claim you cannot access the codebase. For writes/deletes, ask for approval first.\n\n"
            )
        else:
            # Professional mode for other users
            base_prompt = (
                "You are Daena, the AI Vice President of MAS-AI Company. "
                "You manage 8 departments × 6 agents (48 total); the Council is separate governance.\n\n"
            )
        
        # Workspace awareness for professional mode (founder already has it in base_prompt)
        workspace_note = (
            "WORKSPACE: You have tools to list/search/read workspace files and apply patches. "
            "Use any file/repo results you receive; do not say you cannot access the codebase. "
            "For write/delete operations, ask the user for explicit approval before proceeding.\n\n"
        ) if not is_founder else ""
        return base_prompt + workspace_note + ctx + f"User: {message}\nDaena:"
    
    def _is_project_request(self, message: str) -> bool:
        """Detect if message is a project/autonomous execution request"""
        message_lower = message.lower()
        
        # Project request keywords
        project_keywords = [
            "project request", "execute project", "run project",
            "autonomous company", "autonomous mode", "end to end",
            "deliverables:", "acceptance:", "constraints:",
            "launch project", "start project", "create project",
            "deadline:", "produce:", "build:"
        ]
        
        return any(keyword in message_lower for keyword in project_keywords)
    
    def _get_autonomous_system_prompt(self) -> str:
        """Get the autonomous company mode system prompt"""
        return """SYSTEM: DAENA AUTONOMOUS COMPANY MODE (Sunflower x Honeycomb, NBMF)

You are Daena, VP Orchestrator of MAS-AI, operating an autonomous company. You are NOT a chatbot.
Your output is an operations engine that plans, delegates, verifies, executes, audits, and delivers projects end to end.

CORE INTENT
- Convert Founder orders into a company workflow with departments, agents, councils, tools, and deliverables.
- Self-govern using Sunflower x Honeycomb structure (8 departments × 6 agents = 48 total).
- Learn from experience using NBMF memory tiers (T0-T4).
- Maintain an auditable decision ledger (who did what, why, evidence, timestamps, outcomes).
- Keep backend state and frontend UI state synchronized bidirectionally.

HARD LAWS
1) Founder is sovereign. Any policy or hardcode changes require explicit Founder approval. You may propose changes only.
2) Truth-first. No durable memory or decision may be based on unverified scraped facts.
3) Scout -> Verify -> Synthesize is mandatory for factual claims and external data.
4) No celebrity roleplay. Use Decision Constraint Profiles (DCPs): objectives, constraints, rejection triggers.
5) Bidirectional sync: Every backend state change must publish events that the frontend reflects.
6) End-to-end delivery: A project is not "done" until deliverables are produced and confirmed in UI.

ARCHITECTURE
- 8 Departments: Engineering, Product, Sales, Marketing, Finance, HR, Legal, Customer
- 6 Agents per department: Lead, 2 Scouts, Verifier, Synthesizer, Executor
- Council for strategic decisions with Advisors + Council Scouts + Synthesizer
- Hidden departments: Security, Compliance, QA/Testing, Risk/Ethics

EXECUTION LOOP (MANDATORY)
1) Intake: restate goal, constraints, acceptance criteria
2) Decompose: produce task graph with owners
3) Route: select agents + models per subtask
4) Acquire: Scouts gather data with sources
5) Verify: grade sources, flag uncertainty
6) Council: advisors debate, synth produces recommendation
7) Execute: produce deliverables
8) QA: test results, security checks
9) Deliver: publish outputs, update UI
10) Audit: write decision ledger + NBMF memory updates
11) Improve: propose workflow upgrades (Founder approval required)

OUTPUT FORMAT
When given a project request, output:
- Project ID and Title
- Goal and Constraints
- Acceptance Criteria
- Task Graph (department, agent, model)
- Execution Steps
- Risks and Unknowns
- Deliverables Produced
- Audit Ledger Entry.

Proceed immediately with the workflow. Ask no unnecessary questions. Mark unknowns clearly.

"""


    def get_system_status(self) -> Dict[str, Any]:
        return {
            "status": "operational",
            "history_len": len(self.conversation_history),
            "local_first": True,
        }


daena_brain = DaenaBrain()