"""Causal Reasoning Graph -- verifies the STRUCTURE of reasoning, not just facts.

Beyond Mythos: Mythos verifies individual claims (nodes). Laevateinn also
verifies the logical connections between claims (edges) and checks for
missing claims that would change the conclusion (completeness).

The composition fallacy is one of the most common reasoning errors:
    Step 1: Python is fast for development (TRUE)
    Step 2: This project needs to be fast (TRUE)
    Step 3: Therefore use Python (WRONG -- conflating dev speed with runtime speed)

Each step is correct, but the composition is invalid because "fast" means
different things in Step 1 vs Step 2. Mythos can't catch this. CRG can.

Integration: runs after RDE (Stage 4) to verify the reasoning structure
before the Validation Gauntlet (Stage 5).
"""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING

from app.core.logging import get_logger
from app.services.laevateinn.types import (
    CausalEdge,
    CausalGraphResult,
    CausalNode,
    ComputeProfile,
    Difficulty,
)

if TYPE_CHECKING:
    from app.services.llm_service import LLMService

logger = get_logger(__name__)

_DECOMPOSE_PROMPT = (
    "Decompose this answer into its individual claims and logical connections.\n\n"
    "Question: {query}\n"
    "Answer: {answer}\n\n"
    "For each claim, output:\n"
    "CLAIM [n]: [the claim]\n"
    "DEPENDS_ON: [comma-separated list of claim numbers it relies on, or NONE]\n"
    "RELATIONSHIP: [supports|requires|contradicts]\n\n"
    "Also identify any MISSING claims -- things that MUST be true for the "
    "conclusion to hold but are not stated:\n"
    "MISSING: [description of the unstated assumption or gap]"
)

_EDGE_VERIFY_PROMPT = (
    "Verify whether this logical connection is valid:\n\n"
    "Claim A: {claim_a}\n"
    "Claim B: {claim_b}\n"
    "Stated relationship: A {relationship} B\n\n"
    "Is this connection logically valid? Could Claim A be true while "
    "Claim B is false (or vice versa)? Are there hidden assumptions "
    "in this connection?\n\n"
    "Respond with:\n"
    "VALID: TRUE or FALSE\n"
    "REASON: [one line explanation]\n"
    "HIDDEN_ASSUMPTION: [any unstated assumption, or NONE]"
)


class CausalReasoningGraph:
    """Verifies the logical structure of an answer, not just individual facts.

    Three-layer verification:
        Layer 1: Node verification (are individual claims true?) -- handled by CoVe
        Layer 2: Edge verification (do the connections hold?)
        Layer 3: Completeness verification (are load-bearing claims missing?)

    The third layer is unique to Laevateinn. No other system checks whether
    the reasoning graph is COMPLETE -- whether there are missing nodes that,
    if false, would invalidate the entire conclusion.

    Args:
        llm_service: Daena's LLM service for model calls.
    """

    def __init__(self, llm_service: LLMService) -> None:
        self._llm = llm_service

    async def analyze(
        self,
        query: str,
        answer: str,
        compute: ComputeProfile,
        *,
        model_id: str = "",
    ) -> CausalGraphResult:
        """Build and verify a causal reasoning graph for an answer.

        Args:
            query: Original question.
            answer: The answer to verify structurally.
            compute: Compute profile for budget awareness.
            model_id: Model to use for graph construction.

        Returns:
            CausalGraphResult with nodes, edges, gaps, and validity.
        """
        start = time.perf_counter_ns()

        # Skip for trivial queries
        if compute.difficulty == Difficulty.TRIVIAL:
            return CausalGraphResult(
                composition_valid=True,
                confidence=0.7,
            )

        # Step 1: Decompose answer into claims and connections
        nodes, edges, missing = await self._decompose(query, answer, model_id)

        if not nodes:
            # Could not decompose -- fall back to heuristic
            nodes, edges, missing = self._heuristic_decompose(answer)

        # Step 2: Identify load-bearing nodes
        self._mark_load_bearing(nodes, edges)

        # Step 3: Verify edges (logical connections)
        invalid_edges: list[str] = []
        if compute.difficulty in (Difficulty.HARD, Difficulty.BRUTAL) and edges:
            invalid_edges = await self._verify_edges(
                nodes, edges, model_id
            )

        # Step 4: Check composition validity
        composition_valid = len(invalid_edges) == 0 and len(missing) <= 1

        # Calculate confidence
        confidence = self._calculate_confidence(
            nodes, edges, invalid_edges, missing
        )

        elapsed = int((time.perf_counter_ns() - start) / 1_000_000)

        logger.info(
            "causal_graph_complete",
            nodes=len(nodes),
            edges=len(edges),
            missing=len(missing),
            invalid=len(invalid_edges),
            valid=composition_valid,
            confidence=confidence,
            elapsed_ms=elapsed,
        )

        return CausalGraphResult(
            nodes=nodes,
            edges=edges,
            missing_nodes=missing,
            invalid_edges=invalid_edges,
            composition_valid=composition_valid,
            confidence=confidence,
            total_latency_ms=elapsed,
        )

    async def _decompose(
        self, query: str, answer: str, model_id: str,
    ) -> tuple[list[CausalNode], list[CausalEdge], list[str]]:
        """Decompose answer into claims, connections, and gaps using LLM."""
        from app.services.providers.base import GenerateRequest, LLMMessage

        prompt = _DECOMPOSE_PROMPT.format(query=query, answer=answer)
        messages = [LLMMessage(role="user", content=prompt)]

        request = GenerateRequest(
            messages=messages,
            model_id=model_id,
            temperature=0.2,
            max_tokens=1024,
        )

        try:
            result = await self._llm.generate_direct(request)
            return self._parse_decomposition(result.content)
        except Exception as e:
            logger.warning("causal_decompose_failed", error=str(e))
            return [], [], []

    def _heuristic_decompose(
        self, answer: str,
    ) -> tuple[list[CausalNode], list[CausalEdge], list[str]]:
        """Heuristic fallback: extract claims from sentences."""
        sentences = re.split(r"(?<=[.!?])\s+", answer.strip())
        nodes: list[CausalNode] = []
        edges: list[CausalEdge] = []
        missing: list[str] = []

        for i, s in enumerate(sentences):
            s = s.strip()
            if len(s.split()) < 4:
                continue
            nodes.append(CausalNode(
                claim=s, node_id=i, confidence=0.5,
            ))

        # Create sequential dependency chain
        for i in range(1, len(nodes)):
            edges.append(CausalEdge(
                from_id=nodes[i-1].node_id,
                to_id=nodes[i].node_id,
                relationship="supports",
            ))

        # Check for causal language that implies missing context
        answer_lower = answer.lower()
        if re.search(r"\btherefore\b|\bthus\b|\bhence\b", answer_lower):
            if not re.search(r"\bbecause\b|\bsince\b|\bgiven\b", answer_lower):
                missing.append(
                    "Conclusion drawn without explicit premises -- "
                    "causal chain may have unstated assumptions"
                )

        return nodes, edges, missing

    def _mark_load_bearing(
        self, nodes: list[CausalNode], edges: list[CausalEdge],
    ) -> None:
        """Mark nodes that are load-bearing (removing them changes conclusion).

        A node is load-bearing if:
            - It has outgoing edges (other claims depend on it)
            - It is the last node (the conclusion itself)
            - It appears in multiple edge connections
        """
        if not nodes:
            return

        # Count how many edges reference each node
        ref_count: dict[int, int] = {}
        for edge in edges:
            ref_count[edge.from_id] = ref_count.get(edge.from_id, 0) + 1
            ref_count[edge.to_id] = ref_count.get(edge.to_id, 0) + 1

        for node in nodes:
            # Load-bearing if referenced by 2+ edges or is terminal
            is_terminal = not any(e.from_id == node.node_id for e in edges)
            is_highly_referenced = ref_count.get(node.node_id, 0) >= 2
            node.load_bearing = is_terminal or is_highly_referenced

    async def _verify_edges(
        self,
        nodes: list[CausalNode],
        edges: list[CausalEdge],
        model_id: str,
    ) -> list[str]:
        """Verify logical connections between claims."""
        import asyncio
        from app.services.providers.base import GenerateRequest, LLMMessage

        invalid: list[str] = []
        node_map = {n.node_id: n for n in nodes}

        async def check_edge(edge: CausalEdge) -> str | None:
            from_node = node_map.get(edge.from_id)
            to_node = node_map.get(edge.to_id)
            if not from_node or not to_node:
                return None

            prompt = _EDGE_VERIFY_PROMPT.format(
                claim_a=from_node.claim,
                claim_b=to_node.claim,
                relationship=edge.relationship,
            )
            messages = [LLMMessage(role="user", content=prompt)]
            request = GenerateRequest(
                messages=messages,
                model_id=model_id,
                temperature=0.1,
                max_tokens=256,
            )

            try:
                result = await self._llm.generate_direct(request)
                if "FALSE" in result.content.upper():
                    edge.valid = False
                    return (
                        f"Invalid edge: '{from_node.claim[:50]}' "
                        f"-[{edge.relationship}]-> "
                        f"'{to_node.claim[:50]}'"
                    )
            except Exception as e:
                logger.warning("edge_verify_failed", error=str(e))
            return None

        # Verify edges in parallel (cap at 5 to control costs)
        tasks = [check_edge(e) for e in edges[:5]]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in results:
            if isinstance(r, str):
                invalid.append(r)

        return invalid

    def _parse_decomposition(
        self, text: str,
    ) -> tuple[list[CausalNode], list[CausalEdge], list[str]]:
        """Parse LLM decomposition output into nodes, edges, and gaps."""
        nodes: list[CausalNode] = []
        edges: list[CausalEdge] = []
        missing: list[str] = []

        # Parse CLAIM blocks
        claim_pattern = re.compile(
            r"CLAIM\s*\[?(\d+)\]?\s*:\s*(.+?)(?=\nCLAIM|\nMISSING|\nDEPENDS|\Z)",
            re.DOTALL | re.IGNORECASE,
        )

        for match in claim_pattern.finditer(text):
            node_id = int(match.group(1))
            claim = match.group(2).strip().split("\n")[0].strip()
            nodes.append(CausalNode(claim=claim, node_id=node_id, confidence=0.5))

        # Parse DEPENDS_ON lines
        depends_pattern = re.compile(
            r"CLAIM\s*\[?(\d+)\]?.*?DEPENDS_ON:\s*(.+?)(?:\n|$)",
            re.IGNORECASE,
        )
        rel_pattern = re.compile(
            r"RELATIONSHIP:\s*(\w+)", re.IGNORECASE,
        )

        for match in depends_pattern.finditer(text):
            to_id = int(match.group(1))
            deps = match.group(2).strip()

            if deps.upper() == "NONE":
                continue

            # Find relationship near this claim
            rel_text = text[match.start():match.start() + 200]
            rel_match = rel_pattern.search(rel_text)
            relationship = rel_match.group(1).lower() if rel_match else "supports"

            for dep in re.findall(r"\d+", deps):
                edges.append(CausalEdge(
                    from_id=int(dep),
                    to_id=to_id,
                    relationship=relationship,
                ))

        # Parse MISSING lines
        missing_pattern = re.compile(r"MISSING:\s*(.+?)(?:\n|$)", re.IGNORECASE)
        for match in missing_pattern.finditer(text):
            gap = match.group(1).strip()
            if gap and gap.upper() != "NONE" and len(gap) > 10:
                missing.append(gap)

        return nodes, edges, missing

    def _calculate_confidence(
        self,
        nodes: list[CausalNode],
        edges: list[CausalEdge],
        invalid_edges: list[str],
        missing: list[str],
    ) -> float:
        """Calculate structural confidence from graph analysis."""
        if not nodes:
            return 0.5

        base = 0.7

        # Penalty for invalid edges
        base -= len(invalid_edges) * 0.1

        # Penalty for missing load-bearing nodes
        base -= len(missing) * 0.08

        # Bonus for well-connected graph (more edges = more supported)
        if len(edges) >= len(nodes) - 1:
            base += 0.05

        # Bonus for all nodes verified
        verified_ratio = sum(1 for n in nodes if n.verified) / max(len(nodes), 1)
        base += verified_ratio * 0.1

        return max(0.15, min(base, 0.95))
