"""
Explorer Bridge: Human-in-the-loop consultation mode.

This service provides NO APIs, NO automation, NO scraping.
It only formats prompts and parses responses.

The human user:
1. Gets formatted prompt from Daena
2. Copies to ChatGPT/Gemini UI manually
3. Pastes response back
4. Daena parses and feeds into brain

This is a legal, safe alternative when APIs are unavailable or too costly.
"""

from __future__ import annotations

import re
from typing import Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ExplorerBridge:
    """
    Explorer Bridge: Formats prompts for external LLM UIs and parses responses.
    
    NO APIs, NO automation, NO scraping - human-in-the-loop only.
    """
    
    SUPPORTED_TARGETS = ["chatgpt", "gemini", "claude"]
    
    def build_prompt(
        self,
        task: str,
        target: str = "chatgpt",
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Build a formatted prompt for the user to paste into external LLM UI.
        
        Args:
            task: Task/question to ask
            target: "chatgpt", "gemini", or "claude"
            context: Optional context (department, agent, etc.)
        
        Returns:
            {
                "target": target,
                "formatted_prompt": str,
                "instructions": str,
                "response_format": str,
                "timestamp": ISO datetime,
            }
        """
        target_lower = target.lower()
        if target_lower not in self.SUPPORTED_TARGETS:
            target_lower = "chatgpt"
        
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
        
        # Format prompt for target
        formatted_prompt = f"""TASK:
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
        
        instructions = f"""
1. Copy the prompt below
2. Open {target_lower.upper()} in your browser
3. Paste the prompt into the chat
4. Copy the response
5. Paste it back into Daena
"""
        
        return {
            "target": target_lower,
            "formatted_prompt": formatted_prompt,
            "instructions": instructions.strip(),
            "response_format": "REASONING / ASSUMPTIONS / FINAL ANSWER / CONFIDENCE",
            "timestamp": datetime.now().isoformat(),
        }
    
    def parse_response(self, text: str, target: str = "chatgpt") -> Dict[str, Any]:
        """
        Parse a response pasted from external LLM UI.
        
        Args:
            text: Raw response text from user
            target: Which LLM UI it came from (for context)
        
        Returns:
            {
                "target": target,
                "reasoning": str,
                "assumptions": str,
                "answer": str,
                "confidence": str,
                "raw_text": str,
                "parsed_successfully": bool,
                "timestamp": ISO datetime,
            }
        """
        text = text.strip()
        raw_text = text
        
        # Try to extract structured sections
        reasoning = self._extract_section(text, ["REASONING:", "Reasoning:", "REASONING"])
        assumptions = self._extract_section(text, ["ASSUMPTIONS:", "Assumptions:", "ASSUMPTIONS"])
        answer = self._extract_section(text, ["FINAL ANSWER:", "Final Answer:", "FINAL ANSWER", "Answer:"])
        confidence = self._extract_section(text, ["CONFIDENCE:", "Confidence:", "CONFIDENCE"])
        
        # If structured parsing failed, try to extract the main answer
        if not answer:
            # Look for common patterns
            answer_patterns = [
                r"(?:final\s+)?answer[:\-]?\s*(.+?)(?:\n\n|\nREASONING|\nASSUMPTIONS|$)",
                r"conclusion[:\-]?\s*(.+?)(?:\n\n|\nREASONING|\nASSUMPTIONS|$)",
                r"recommendation[:\-]?\s*(.+?)(?:\n\n|\nREASONING|\nASSUMPTIONS|$)",
            ]
            for pattern in answer_patterns:
                match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
                if match:
                    answer = match.group(1).strip()
                    break
        
        # If still no answer, use the whole text (fallback)
        if not answer:
            answer = text[:500] + ("..." if len(text) > 500 else "")
        
        parsed_successfully = bool(reasoning or assumptions or (answer and len(answer) > 10))
        
        return {
            "target": target.lower(),
            "reasoning": reasoning or "",
            "assumptions": assumptions or "",
            "answer": answer,
            "confidence": confidence or "Unknown",
            "raw_text": raw_text,
            "parsed_successfully": parsed_successfully,
            "timestamp": datetime.now().isoformat(),
        }
    
    def _extract_section(self, text: str, markers: list[str]) -> str:
        """Extract a section marked by one of the markers."""
        for marker in markers:
            # Try exact match first
            pattern = re.escape(marker) + r"\s*\n(.*?)(?=\n(?:REASONING|ASSUMPTIONS|FINAL ANSWER|CONFIDENCE|$))"
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()
            
            # Try with colon variation
            pattern = re.escape(marker.rstrip(":")) + r":?\s*\n(.*?)(?=\n(?:REASONING|ASSUMPTIONS|FINAL ANSWER|CONFIDENCE|$))"
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()
        
        return ""
    
    def merge_with_daena_response(
        self,
        daena_response: str,
        explorer_response: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Merge explorer response with Daena's own response.
        
        Args:
            daena_response: Daena's response from brain
            explorer_response: Parsed response from explorer bridge
        
        Returns:
            {
                "synthesis": str,
                "daena_analysis": str,
                "external_consultation": Dict,
                "confidence": str,
                "timestamp": ISO datetime,
            }
        """
        external_answer = explorer_response.get("answer", "")
        external_reasoning = explorer_response.get("reasoning", "")
        external_confidence = explorer_response.get("confidence", "Unknown")
        
        # Build synthesis
        synthesis_parts = [
            "**Daena's Analysis:**",
            daena_response,
            "",
            f"**External Consultation ({explorer_response.get('target', 'unknown').upper()}):**",
        ]
        
        if external_reasoning:
            synthesis_parts.append(f"Reasoning: {external_reasoning}")
        
        synthesis_parts.append(f"Answer: {external_answer}")
        synthesis_parts.append(f"Confidence: {external_confidence}")
        
        synthesis_parts.extend([
            "",
            "**Synthesis:**",
            "After consulting external sources, I've integrated their perspective with my own analysis. ",
            "The final recommendation combines both viewpoints for a comprehensive answer.",
        ])
        
        return {
            "synthesis": "\n".join(synthesis_parts),
            "daena_analysis": daena_response,
            "external_consultation": {
                "target": explorer_response.get("target"),
                "answer": external_answer,
                "reasoning": external_reasoning,
                "confidence": external_confidence,
            },
            "confidence": external_confidence,
            "timestamp": datetime.now().isoformat(),
        }


# Global instance
explorer_bridge = ExplorerBridge()









