"""
Human Relay Explorer: Manual copy/paste bridge for external LLMs.

NO browser automation, NO scraping, NO login automation.
User manually copies prompt, pastes response, Daena synthesizes.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)

# Storage for insight artifacts (simple JSON file for now)
STORAGE_FILE = Path("data/human_relay_insights.json")


class HumanRelayExplorer:
    """
    Human Relay Explorer: Generates prompts, ingests responses, synthesizes with Daena.
    
    NO automation - manual copy/paste only.
    """
    
    SUPPORTED_PROVIDERS = ["chatgpt", "gemini"]
    
    def __init__(self):
        """Initialize storage"""
        self._ensure_storage()
    
    def _ensure_storage(self):
        """Ensure storage directory and file exist"""
        storage_dir = STORAGE_FILE.parent
        storage_dir.mkdir(parents=True, exist_ok=True)
        if not STORAGE_FILE.exists():
            STORAGE_FILE.write_text("[]", encoding="utf-8")
    
    def generate_prompt(
        self,
        provider: str,
        task: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate a copy/paste-ready prompt for external LLM UI.
        
        Args:
            provider: "chatgpt" or "gemini"
            task: Task/question to ask
            context: Optional context (department, agent, etc.)
        
        Returns:
            {
                "provider": provider,
                "prompt_text": str,
                "response_format": str,
                "relay_id": str,
                "trace_id": str,
                "timestamp": ISO datetime,
            }
        """
        provider_lower = provider.lower()
        if provider_lower not in self.SUPPORTED_PROVIDERS:
            provider_lower = "chatgpt"
        
        # Build context string if provided
        context_str = ""
        if context:
            context_parts = []
            if context.get("department"):
                context_parts.append(f"Department: {context['department']}")
            if context.get("agent"):
                context_parts.append(f"Agent: {context['agent']}")
            if context.get("session_id"):
                context_parts.append(f"Session: {context['session_id']}")
            if context_parts:
                context_str = "\n".join(context_parts) + "\n\n"
        
        # Generate prompt text
        prompt_text = f"""TASK:
{task}

{context_str}Please provide your response in the following format:

REASONING:
[Your step-by-step reasoning process]

ASSUMPTIONS:
[Any assumptions you're making]

FINAL ANSWER:
[Your final answer or recommendation]

CONFIDENCE:
[Your confidence level: High/Medium/Low]"""
        
        # Generate IDs
        relay_id = str(uuid.uuid4())
        trace_id = str(uuid.uuid4())[:16]
        
        return {
            "provider": provider_lower,
            "prompt_text": prompt_text,
            "response_format": "REASONING / ASSUMPTIONS / FINAL ANSWER / CONFIDENCE",
            "relay_id": relay_id,
            "trace_id": trace_id,
            "timestamp": datetime.now().isoformat(),
        }
    
    def ingest_response(
        self,
        relay_id: str,
        provider: str,
        pasted_answer: str,
    ) -> Dict[str, Any]:
        """
        Ingest a pasted response from external LLM UI.
        
        Args:
            relay_id: Relay ID from generate_prompt
            provider: "chatgpt" or "gemini"
            pasted_answer: Raw response text pasted by user
        
        Returns:
            {
                "status": "ok",
                "stored_id": str,
                "parsed": {
                    "summary": str,
                    "key_points": List[str],
                    "reasoning": str,
                    "answer": str,
                    "confidence": str,
                },
                "trace_id": str,
                "timestamp": ISO datetime,
            }
        """
        # Parse the response
        parsed = self._parse_response(pasted_answer)
        
        # Store as insight artifact
        insight = {
            "id": str(uuid.uuid4()),
            "relay_id": relay_id,
            "provider": provider.lower(),
            "raw_text": pasted_answer,
            "parsed": parsed,
            "created_at": datetime.now().isoformat(),
        }
        
        # Load existing insights
        insights = []
        if STORAGE_FILE.exists():
            try:
                insights = json.loads(STORAGE_FILE.read_text(encoding="utf-8"))
            except Exception:
                insights = []
        
        # Add new insight
        insights.append(insight)
        
        # Save
        STORAGE_FILE.write_text(json.dumps(insights, indent=2), encoding="utf-8")
        
        return {
            "status": "ok",
            "stored_id": insight["id"],
            "parsed": parsed,
            "trace_id": str(uuid.uuid4())[:16],
            "timestamp": datetime.now().isoformat(),
        }
    
    def _parse_response(self, text: str) -> Dict[str, Any]:
        """Parse structured response text"""
        import re
        
        text = text.strip()
        
        # Extract sections
        reasoning = self._extract_section(text, ["REASONING:", "Reasoning:"])
        assumptions = self._extract_section(text, ["ASSUMPTIONS:", "Assumptions:"])
        answer = self._extract_section(text, ["FINAL ANSWER:", "Final Answer:", "Answer:"])
        confidence = self._extract_section(text, ["CONFIDENCE:", "Confidence:"])
        
        # If structured parsing failed, try to extract main answer
        if not answer:
            answer_patterns = [
                r"(?:final\s+)?answer[:\-]?\s*(.+?)(?:\n\n|\nREASONING|\nASSUMPTIONS|$)",
                r"conclusion[:\-]?\s*(.+?)(?:\n\n|\nREASONING|\nASSUMPTIONS|$)",
            ]
            for pattern in answer_patterns:
                match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
                if match:
                    answer = match.group(1).strip()
                    break
        
        # If still no answer, use first 200 chars
        if not answer:
            answer = text[:200] + ("..." if len(text) > 200 else "")
        
        # Extract key points (simple heuristic: bullet points or numbered lists)
        key_points = []
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith(("-", "*", "•", "1.", "2.", "3.")):
                key_points.append(line.lstrip("-*•1234567890. ")[:100])
        
        # Summary (first 300 chars of answer or reasoning)
        summary = (reasoning or answer or text)[:300]
        
        return {
            "summary": summary,
            "key_points": key_points[:5],  # Max 5 key points
            "reasoning": reasoning or "",
            "answer": answer,
            "confidence": confidence or "Unknown",
        }
    
    def _extract_section(self, text: str, markers: List[str]) -> str:
        """Extract a section marked by one of the markers"""
        import re
        
        for marker in markers:
            pattern = re.escape(marker) + r"\s*\n(.*?)(?=\n(?:REASONING|ASSUMPTIONS|FINAL ANSWER|CONFIDENCE|$))"
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()
        
        return ""
    
    async def synthesize(
        self,
        task: str,
        insight_ids: List[str],
        mode: str = "assist_only",
    ) -> Dict[str, Any]:
        """
        Synthesize external insights with Daena's brain.
        
        Args:
            task: Original task/question
            insight_ids: List of stored insight IDs to use
            mode: "assist_only" (Daena uses insights as reference, not truth)
        
        Returns:
            {
                "final_answer": str,
                "used_insights": List[Dict],
                "trace_id": str,
                "timestamp": ISO datetime,
            }
        """
        # Load insights
        insights = []
        if STORAGE_FILE.exists():
            try:
                all_insights = json.loads(STORAGE_FILE.read_text(encoding="utf-8"))
                insights = [i for i in all_insights if i.get("id") in insight_ids]
            except Exception as e:
                logger.warning(f"Failed to load insights: {e}")
        
        if not insights:
            return {
                "final_answer": "No insights found to synthesize.",
                "used_insights": [],
                "trace_id": str(uuid.uuid4())[:16],
                "timestamp": datetime.now().isoformat(),
            }
        
        # Build context for Daena brain
        insight_summaries = []
        for insight in insights:
            parsed = insight.get("parsed", {})
            insight_summaries.append({
                "provider": insight.get("provider"),
                "summary": parsed.get("summary", ""),
                "key_points": parsed.get("key_points", []),
                "answer": parsed.get("answer", ""),
            })
        
        # Call canonical Daena brain with insights as context
        from backend.daena_brain import daena_brain
        
        context = {
            "human_relay_mode": mode,
            "external_insights": insight_summaries,
            "task": task,
        }
        
        # Build prompt that includes insights as reference
        synthesis_prompt = f"""Task: {task}

External insights (for reference only, not as definitive truth):
"""
        for idx, insight in enumerate(insight_summaries, 1):
            synthesis_prompt += f"""
Insight {idx} (from {insight['provider']}):
- Summary: {insight['summary']}
- Key Points: {', '.join(insight['key_points'][:3])}
- Answer: {insight['answer'][:200]}
"""
        
        synthesis_prompt += "\nPlease synthesize these external insights with your own analysis and provide a final answer."
        
        # Call canonical brain
        brain_response = await daena_brain.process_message(synthesis_prompt, context)
        
        return {
            "final_answer": brain_response,
            "used_insights": insight_summaries,
            "trace_id": str(uuid.uuid4())[:16],
            "timestamp": datetime.now().isoformat(),
        }


# Global instance
human_relay_explorer = HumanRelayExplorer()









