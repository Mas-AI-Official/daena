"""P1: Failure Memory -- learns from failures to reshape future strategies.

Mythos treats every failure as MORE valuable than success. It builds
a causal model of WHY it failed and uses that to reshape ALL future
strategies. The anti-fragility isn't just logging -- it's structural.

Laevateinn goes further: it persists failure patterns across sessions
(via NBMF tier integration) and uses accumulated patterns to adjust
the epistemic tracker and meta-strategy selector.

Integration: runs at pipeline start (before DCE), feeding failure
context into comprehension and strategy selection.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import TYPE_CHECKING

from app.core.logging import get_logger
from app.services.laevateinn.types import (
    FailureMemoryResult,
    FailureRecord,
    ReasoningStrategy,
)

if TYPE_CHECKING:
    from app.services.llm_service import LLMService

logger = get_logger(__name__)

# Default failure store path (inside var/ so it persists)
_DEFAULT_STORE_PATH = Path("var/laevateinn/failure_memory.jsonl")

_CAUSAL_ANALYSIS_PROMPT = (
    "A previous AI response was incorrect or low quality. "
    "Analyze WHY it failed. Identify the root cause, not just the symptom.\n\n"
    "Query: {query}\n"
    "Answer that failed: {answer}\n"
    "How it failed: {failure_description}\n\n"
    "Provide:\n"
    "ROOT_CAUSE: [the fundamental reason it failed]\n"
    "CAUSAL_CHAIN: [step by step: what led to what]\n"
    "PREVENTION: [a rule that would prevent this in future]\n"
    "FAILURE_TYPE: [factual|logical|structural|incomplete|hallucination]"
)


class FailureMemoryEngine:
    """Persistent failure memory with causal analysis.

    Unlike simple failure logging, this engine:
    1. Analyzes WHY each failure happened (causal chain)
    2. Generates prevention rules from failure patterns
    3. Reshapes strategy selection based on accumulated patterns
    4. Persists across sessions via JSONL storage

    The key insight: a system that fails the same way twice has learned nothing.
    A system that uses past failures to prevent future ones is anti-fragile.

    Args:
        llm_service: For causal analysis of complex failures.
        store_path: Path to JSONL failure store.
    """

    def __init__(
        self,
        llm_service: LLMService | None = None,
        store_path: Path | None = None,
    ) -> None:
        self._llm = llm_service
        self._store_path = store_path or _DEFAULT_STORE_PATH
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache: list[FailureRecord] | None = None

    def recall(
        self,
        query: str,
        *,
        strategy: ReasoningStrategy = ReasoningStrategy.STANDARD,
        max_relevant: int = 5,
    ) -> FailureMemoryResult:
        """Recall relevant past failures for a new query.

        Searches failure memory for patterns that match the current
        query or strategy, and returns adjustments.

        Args:
            query: Current query to check against failure patterns.
            strategy: Current reasoning strategy being considered.
            max_relevant: Max failures to return.

        Returns:
            FailureMemoryResult with relevant failures and adjustments.
        """
        records = self._load_records()

        if not records:
            return FailureMemoryResult(accumulated_patterns=0)

        # Find relevant failures
        query_lower = query.lower()
        relevant: list[FailureRecord] = []
        strategy_failures: dict[str, int] = {}

        for record in records:
            # Track strategy failure rates
            strategy_failures[record.strategy_used] = (
                strategy_failures.get(record.strategy_used, 0) + 1
            )

            # Check for keyword overlap with current query
            overlap = sum(
                1 for word in record.root_cause.lower().split()
                if len(word) > 4 and word in query_lower
            )
            if overlap >= 2:
                relevant.append(record)

        relevant = relevant[:max_relevant]

        # Generate strategy adjustments
        adjustments: list[str] = []
        risk_flags: list[str] = []

        # If current strategy has high failure rate, flag it
        current_strategy_fails = strategy_failures.get(strategy.value, 0)
        total_fails = sum(strategy_failures.values())
        if total_fails > 0 and current_strategy_fails / total_fails > 0.4:
            adjustments.append(
                f"Strategy {strategy.value} has failed {current_strategy_fails} "
                f"times ({current_strategy_fails/total_fails:.0%}). "
                f"Consider alternative approach."
            )

        # Collect prevention rules from relevant failures
        for r in relevant:
            if r.prevention_rule:
                risk_flags.append(r.prevention_rule)

        return FailureMemoryResult(
            relevant_failures=relevant,
            strategy_adjustments=adjustments,
            risk_flags=risk_flags,
            accumulated_patterns=len(records),
        )

    async def record_failure(
        self,
        query: str,
        answer: str,
        failure_description: str,
        strategy_used: ReasoningStrategy,
    ) -> FailureRecord:
        """Record a new failure with causal analysis.

        Args:
            query: The query that produced a bad answer.
            answer: The answer that failed.
            failure_description: How/why it failed.
            strategy_used: Which strategy was active.

        Returns:
            FailureRecord with causal analysis.
        """
        query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]

        # Attempt LLM causal analysis
        root_cause = failure_description
        causal_chain: list[str] = []
        prevention_rule = ""
        failure_type = "unknown"

        if self._llm:
            analysis = await self._llm_causal_analysis(
                query, answer, failure_description
            )
            if analysis:
                root_cause = analysis.get("root_cause", root_cause)
                causal_chain = analysis.get("causal_chain", [])
                prevention_rule = analysis.get("prevention", "")
                failure_type = analysis.get("failure_type", "unknown")

        record = FailureRecord(
            query_hash=query_hash,
            failure_type=failure_type,
            root_cause=root_cause,
            strategy_used=strategy_used.value,
            causal_chain=causal_chain,
            prevention_rule=prevention_rule,
        )

        # Persist
        self._append_record(record)

        logger.info(
            "failure_recorded",
            failure_type=failure_type,
            root_cause=root_cause[:80],
            strategy=strategy_used.value,
            total_patterns=len(self._load_records()),
        )

        return record

    def get_strategy_stats(self) -> dict[str, dict[str, int]]:
        """Get failure statistics per strategy for meta-strategy tuning."""
        records = self._load_records()
        stats: dict[str, dict[str, int]] = {}

        for r in records:
            if r.strategy_used not in stats:
                stats[r.strategy_used] = {"total": 0, "types": {}}
            stats[r.strategy_used]["total"] += 1
            ft = r.failure_type
            stats[r.strategy_used]["types"] = stats[r.strategy_used].get("types", {})
            stats[r.strategy_used]["types"][ft] = (
                stats[r.strategy_used]["types"].get(ft, 0) + 1
            )

        return stats

    async def _llm_causal_analysis(
        self, query: str, answer: str, failure_description: str,
    ) -> dict[str, Any] | None:
        """Use LLM to perform causal analysis of a failure."""
        from app.services.providers.base import GenerateRequest, LLMMessage

        prompt = _CAUSAL_ANALYSIS_PROMPT.format(
            query=query[:300],
            answer=answer[:500],
            failure_description=failure_description,
        )
        messages = [LLMMessage(role="user", content=prompt)]
        request = GenerateRequest(
            messages=messages,
            model_id="",
            temperature=0.2,
            max_tokens=512,
        )

        try:
            result = await self._llm.generate_direct(request)
            return self._parse_causal_analysis(result.content)
        except Exception as e:
            logger.warning("failure_analysis_failed", error=str(e))
            return None

    def _parse_causal_analysis(self, text: str) -> dict[str, Any]:
        """Parse LLM causal analysis output."""
        import re
        result: dict[str, Any] = {}

        root = re.search(r"ROOT_CAUSE:\s*(.+?)(?:\n|$)", text, re.IGNORECASE)
        if root:
            result["root_cause"] = root.group(1).strip()

        chain = re.search(r"CAUSAL_CHAIN:\s*(.+?)(?:\n(?:PREVENTION|FAILURE)|$)", text, re.IGNORECASE | re.DOTALL)
        if chain:
            steps = [s.strip() for s in chain.group(1).split("->")]
            if len(steps) == 1:
                steps = [s.strip() for s in chain.group(1).split("\n") if s.strip()]
            result["causal_chain"] = steps

        prev = re.search(r"PREVENTION:\s*(.+?)(?:\n|$)", text, re.IGNORECASE)
        if prev:
            result["prevention"] = prev.group(1).strip()

        ft = re.search(r"FAILURE_TYPE:\s*(\w+)", text, re.IGNORECASE)
        if ft:
            result["failure_type"] = ft.group(1).strip().lower()

        return result

    def _load_records(self) -> list[FailureRecord]:
        """Load failure records from JSONL store."""
        if self._cache is not None:
            return self._cache

        records: list[FailureRecord] = []
        if not self._store_path.exists():
            self._cache = records
            return records

        try:
            with open(self._store_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    records.append(FailureRecord(**data))
        except Exception as e:
            logger.warning("failure_memory_load_error", error=str(e))

        self._cache = records
        return records

    def _append_record(self, record: FailureRecord) -> None:
        """Append a record to the JSONL store."""
        try:
            with open(self._store_path, "a") as f:
                data = {
                    "query_hash": record.query_hash,
                    "failure_type": record.failure_type,
                    "root_cause": record.root_cause,
                    "strategy_used": record.strategy_used,
                    "causal_chain": record.causal_chain,
                    "prevention_rule": record.prevention_rule,
                    "timestamp": record.timestamp,
                }
                f.write(json.dumps(data) + "\n")

            # Invalidate cache
            self._cache = None
        except Exception as e:
            logger.warning("failure_memory_write_error", error=str(e))
