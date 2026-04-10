"""Beyond Mythos: Consensus Gradient -- per-section confidence mapping.

Nobody does this. Not Mythos, not any other system.

Instead of ONE confidence score for the entire answer, Laevateinn maps
confidence at the section/paragraph level. Some parts of an answer might
be 95% confident (well-established facts) while other parts are 40%
(speculation or contested claims).

This gives users a heat map of trustworthiness across the answer,
so they know exactly which parts to verify themselves.

Integration: runs at Delivery stage, using data from AMD debate,
CRG causal graph, and Adversarial Gate.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from app.core.logging import get_logger
from app.services.laevateinn.types import (
    AdversarialGateResult,
    CausalGraphResult,
    ConsensusGradient,
    ConsensusSection,
    DebateResult,
    DepthResult,
    ValidationResult,
)

logger = get_logger(__name__)


class ConsensusGradientEngine:
    """Maps per-section confidence across an answer.

    Uses signals from the entire pipeline to determine which PARTS
    of the answer are strong and which are weak:

    Signals used:
    - Debate disagreements: sections models disagreed on get lower confidence
    - Causal graph: claims with invalid edges get lower confidence
    - Verification: claims that failed CoVe get lower confidence
    - Adversarial gate: sections matching counter-evidence get lower confidence

    The output is a list of (section, confidence) pairs that can be
    rendered as a confidence heat map in the frontend.
    """

    def analyze(
        self,
        answer: str,
        *,
        debate: DebateResult | None = None,
        depth: DepthResult | None = None,
        causal_graph: CausalGraphResult | None = None,
        validation: ValidationResult | None = None,
        adversarial_gate: AdversarialGateResult | None = None,
    ) -> ConsensusGradient:
        """Build a per-section confidence gradient.

        Args:
            answer: The final answer text.
            debate: AMD output with disagreement data.
            depth: RDE output with verification data.
            causal_graph: CRG output with structural validity.
            validation: Gauntlet output with test results.
            adversarial_gate: Gate output with counter-evidence.

        Returns:
            ConsensusGradient with per-section confidence.
        """
        # Split answer into sections
        sections = self._split_into_sections(answer)

        if not sections:
            return ConsensusGradient(overall_confidence=0.5)

        # Build confidence for each section
        consensus_sections: list[ConsensusSection] = []

        for section_text in sections:
            confidence = 0.7  # Base confidence
            contested = False
            source = "pipeline"

            # Check if this section was contested in debate
            if debate and debate.disagreement_points:
                for dp in debate.disagreement_points:
                    if self._text_overlap(section_text, dp.topic):
                        confidence -= 0.15
                        contested = True
                        source = "debated"

            # Check against causal graph invalid edges
            if causal_graph and causal_graph.invalid_edges:
                for inv in causal_graph.invalid_edges:
                    if self._text_overlap(section_text, inv):
                        confidence -= 0.2
                        source = "structural_issue"

            # Check against verification inconsistencies
            if depth and depth.inconsistencies_found:
                for inc in depth.inconsistencies_found:
                    if self._text_overlap(section_text, inc):
                        confidence -= 0.15
                        source = "verification_issue"

            # Check against counter-evidence
            if adversarial_gate and adversarial_gate.counter_evidence_found:
                for ce in adversarial_gate.counter_evidence_found:
                    if self._text_overlap(section_text, ce):
                        confidence -= 0.25
                        source = "counter_evidence"

            # Boost from validation passing
            if validation and validation.passed:
                confidence += 0.05

            if validation and validation.cove_verified:
                confidence += 0.1

            confidence = max(0.1, min(confidence, 0.99))

            consensus_sections.append(ConsensusSection(
                content=section_text,
                confidence=round(confidence, 2),
                source=source,
                contested=contested,
            ))

        # Overall confidence = weighted average (longer sections count more)
        total_chars = sum(len(s.content) for s in consensus_sections)
        if total_chars > 0:
            overall = sum(
                s.confidence * len(s.content) / total_chars
                for s in consensus_sections
            )
        else:
            overall = 0.5

        # Find extremes
        weakest = min(consensus_sections, key=lambda s: s.confidence)
        strongest = max(consensus_sections, key=lambda s: s.confidence)

        result = ConsensusGradient(
            sections=consensus_sections,
            overall_confidence=round(overall, 3),
            weakest_section=weakest.content[:80],
            strongest_section=strongest.content[:80],
        )

        logger.info(
            "consensus_gradient_complete",
            sections=len(consensus_sections),
            overall=result.overall_confidence,
            weakest=weakest.confidence,
            strongest=strongest.confidence,
        )

        return result

    def _split_into_sections(self, text: str) -> list[str]:
        """Split answer into meaningful sections.

        Splits on: double newlines, markdown headers, numbered lists.
        Merges very short sections with the next one.
        """
        # Split on paragraph boundaries
        raw_sections = re.split(r"\n\n+|\n(?=#{1,3}\s)|\n(?=\d+\.\s)", text)

        sections: list[str] = []
        buffer = ""

        for s in raw_sections:
            s = s.strip()
            if not s:
                continue

            buffer += (" " if buffer else "") + s

            # Flush buffer if it's substantial enough
            if len(buffer.split()) >= 10:
                sections.append(buffer)
                buffer = ""

        # Flush remaining buffer
        if buffer:
            if sections:
                sections[-1] += " " + buffer
            else:
                sections.append(buffer)

        return sections

    def _text_overlap(self, section: str, reference: str) -> bool:
        """Check if a section overlaps with a reference text.

        Uses keyword overlap: if 3+ significant words match, consider
        it a match.
        """
        section_words = set(
            w.lower() for w in section.split() if len(w) > 4
        )
        ref_words = set(
            w.lower() for w in reference.split() if len(w) > 4
        )

        overlap = section_words & ref_words
        return len(overlap) >= 3
