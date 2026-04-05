"""Tests for Laevateinn gap-filling modules.

Tests: CodeVerifier, DeepThinkEngine, EpisodicMemory,
       InteractionLogger, ToolAugmentedReasoner.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.laevateinn.code_verifier import CodeBlock, CodeVerifier
from app.services.laevateinn.deep_think import DeepThinkEngine, DeepThinkResult
from app.services.laevateinn.episodic_memory import EpisodicMemory, Episode
from app.services.laevateinn.interaction_logger import InteractionLogger, Interaction
from app.services.laevateinn.tool_augmented import ToolAugmentedReasoner, ToolCall


# ── Shared fixtures ──────────────────────────────────────────

@dataclass
class FakeLLMResponse:
    content: str
    model_id: str = "test-model"
    provider: str = "OLLAMA"
    token_count_input: int = 100
    token_count_output: int = 200
    cost_usd: float = 0.0
    latency_ms: int = 50
    finish_reason: str = "stop"
    raw: dict = field(default_factory=dict)


def make_mock_llm(responses: list[str] | None = None) -> MagicMock:
    llm = MagicMock()
    if responses is None:
        responses = ["Test answer."]
    call_count = 0

    async def fake_generate(request):
        nonlocal call_count
        idx = min(call_count, len(responses) - 1)
        call_count += 1
        return FakeLLMResponse(content=responses[idx], model_id=request.model_id or "test-model")

    llm.generate_direct = AsyncMock(side_effect=fake_generate)
    return llm


# ══════════════════════════════════════════════════════════════
# Gap 1: CodeVerifier
# ══════════════════════════════════════════════════════════════

class TestCodeVerifier:

    @pytest.fixture
    def verifier(self) -> CodeVerifier:
        return CodeVerifier()

    def test_extract_python_block(self, verifier: CodeVerifier):
        text = 'Here is code:\n```python\nprint("hello")\n```\nDone.'
        blocks = verifier.extract_code_blocks(text)
        assert len(blocks) == 1
        assert blocks[0].language == "python"
        assert 'print("hello")' in blocks[0].code

    def test_extract_bash_block(self, verifier: CodeVerifier):
        text = '```bash\necho hello\n```'
        blocks = verifier.extract_code_blocks(text)
        assert len(blocks) == 1
        assert blocks[0].language == "bash"

    def test_extract_no_blocks(self, verifier: CodeVerifier):
        blocks = verifier.extract_code_blocks("No code here.")
        assert len(blocks) == 0

    def test_extract_multiple_blocks(self, verifier: CodeVerifier):
        text = '```python\nx = 1\n```\nAnd:\n```python\ny = 2\n```'
        blocks = verifier.extract_code_blocks(text)
        assert len(blocks) == 2

    @pytest.mark.asyncio
    async def test_execute_python_success(self, verifier: CodeVerifier):
        block = CodeBlock(language="python", code='print("hello world")', line_start=0)
        result = await verifier.execute_code(block, timeout=5)
        assert result.success
        assert "hello world" in result.output
        assert result.exit_code == 0

    @pytest.mark.asyncio
    async def test_execute_python_error(self, verifier: CodeVerifier):
        block = CodeBlock(language="python", code='raise ValueError("bad")', line_start=0)
        result = await verifier.execute_code(block, timeout=5)
        assert not result.success
        assert result.exit_code != 0

    @pytest.mark.asyncio
    async def test_execute_timeout(self, verifier: CodeVerifier):
        block = CodeBlock(language="python", code='import time; time.sleep(30)', line_start=0)
        result = await verifier.execute_code(block, timeout=2)
        assert not result.success
        assert result.execution_time_ms >= 1000

    @pytest.mark.asyncio
    async def test_verify_answer_code(self, verifier: CodeVerifier):
        answer = 'Try this:\n```python\nprint(2 + 2)\n```'
        results = await verifier.verify_answer_code(answer)
        assert len(results) == 1
        assert results[0].success
        assert "4" in results[0].output


# ══════════════════════════════════════════════════════════════
# Gap 2: DeepThinkEngine
# ══════════════════════════════════════════════════════════════

class TestDeepThinkEngine:

    @pytest.mark.asyncio
    async def test_parse_think_tags(self):
        response_text = (
            "<think>\nApproach 1: use recursion.\n"
            "Wait, that might overflow.\n"
            "Approach 2: use iteration.\n"
            "Actually, iteration is better.\n"
            "</think>\n"
            "Use iteration for this problem."
        )
        llm = make_mock_llm([response_text])
        engine = DeepThinkEngine(llm)
        result = await engine.think("How to solve this?", model_id="deepseek-r1:14b")
        assert result.answer  # Has an answer
        assert result.thinking_trace  # Has thinking

    @pytest.mark.asyncio
    async def test_parse_answer_marker(self):
        response_text = (
            "Approach 1: use a hash map.\n"
            "Approach 2: use a sorted array.\n"
            "ANSWER: Use a hash map for O(1) lookups."
        )
        llm = make_mock_llm([response_text])
        engine = DeepThinkEngine(llm)
        result = await engine.think("Best data structure?", model_id="test-model")
        assert "hash map" in result.answer.lower()

    @pytest.mark.asyncio
    async def test_count_paths(self):
        engine = DeepThinkEngine(make_mock_llm())
        count = engine._count_paths(
            "Approach 1: try X.\nApproach 2: try Y.\nApproach 3: try Z."
        )
        assert count >= 3

    @pytest.mark.asyncio
    async def test_count_backtracks(self):
        engine = DeepThinkEngine(make_mock_llm())
        count = engine._count_backtracks(
            "Wait, that's wrong. Actually, we should do this instead. "
            "No, let me reconsider."
        )
        assert count >= 1

    @pytest.mark.asyncio
    async def test_confidence_estimation(self):
        response_text = (
            "Approach 1: X.\nApproach 2: Y.\n"
            "Wait, X is better because...\n"
            "ANSWER: Use X."
        )
        llm = make_mock_llm([response_text])
        engine = DeepThinkEngine(llm)
        result = await engine.think("Test", model_id="test-model")
        assert 0.0 <= result.confidence <= 1.0


# ══════════════════════════════════════════════════════════════
# Gap 3: EpisodicMemory
# ══════════════════════════════════════════════════════════════

class TestEpisodicMemory:

    @pytest.fixture
    async def memory(self, tmp_path) -> EpisodicMemory:
        db_path = str(tmp_path / "test_episodes.db")
        mem = EpisodicMemory(db_path=db_path)
        await mem.initialize()
        return mem

    @pytest.mark.asyncio
    async def test_record_and_recall(self, memory: EpisodicMemory):
        ep_id = await memory.record_episode(
            session_id="s1", topic="auth", query="How to fix auth?",
            answer="Check the middleware.", outcome="resolved",
        )
        assert ep_id

        episodes = await memory.recall_by_topic("auth")
        assert len(episodes) >= 1
        assert episodes[0].topic == "auth"

    @pytest.mark.asyncio
    async def test_recall_relevant(self, memory: EpisodicMemory):
        await memory.record_episode(
            session_id="s1", topic="database sql query",
            query="Fix the SQL database query",
            answer="Use JOIN instead of subquery for the database.", outcome="resolved",
            tags=["sql", "database", "query", "fix"],
        )
        await memory.record_episode(
            session_id="s1", topic="frontend css",
            query="Fix CSS layout",
            answer="Use flexbox.", outcome="resolved",
            tags=["css", "layout"],
        )

        results = await memory.recall_relevant("SQL database query", min_relevance=0.1)
        assert len(results) >= 1
        assert "database" in results[0].episode.topic

    @pytest.mark.asyncio
    async def test_recall_failures(self, memory: EpisodicMemory):
        await memory.record_episode(
            session_id="s1", topic="deploy", query="Deploy to prod",
            answer="Run docker push.", outcome="failed",
            failure_reason="Docker daemon not running",
        )
        failures = await memory.recall_failures()
        assert len(failures) == 1
        assert "Docker" in failures[0].failure_reason

    @pytest.mark.asyncio
    async def test_recall_preferences(self, memory: EpisodicMemory):
        await memory.record_episode(
            session_id="s1", topic="style", query="Format the code",
            answer="Used black formatter.", outcome="accepted",
            preference_learned="User prefers black over autopep8",
        )
        prefs = await memory.recall_preferences()
        assert len(prefs) == 1
        assert "black" in prefs[0].preference_learned

    @pytest.mark.asyncio
    async def test_recall_patterns(self, memory: EpisodicMemory):
        await memory.record_episode(
            session_id="s1", topic="routing", query="Fix route ordering",
            answer="Put specific routes before wildcard.",
            outcome="resolved",
            pattern_detected="Route ordering bug recurs monthly",
        )
        patterns = await memory.recall_patterns()
        assert len(patterns) == 1

    @pytest.mark.asyncio
    async def test_enrich_query(self, memory: EpisodicMemory):
        await memory.record_episode(
            session_id="s1", topic="auth", query="Fix auth bug",
            answer="Route ordering was the issue.", outcome="resolved",
            pattern_detected="Auth bugs often caused by route ordering",
        )
        enriched = await memory.enrich_query("Fix the auth middleware")
        assert "auth" in enriched.lower()

    @pytest.mark.asyncio
    async def test_get_session_episodes(self, memory: EpisodicMemory):
        await memory.record_episode(
            session_id="session-42", topic="test", query="q1",
            answer="a1", outcome="ok",
        )
        await memory.record_episode(
            session_id="session-42", topic="test", query="q2",
            answer="a2", outcome="ok",
        )
        await memory.record_episode(
            session_id="other", topic="test", query="q3",
            answer="a3", outcome="ok",
        )
        eps = await memory.get_session_episodes("session-42")
        assert len(eps) == 2


# ══════════════════════════════════════════════════════════════
# Gap 5: InteractionLogger
# ══════════════════════════════════════════════════════════════

class TestInteractionLogger:

    @pytest.fixture
    async def logger(self, tmp_path) -> InteractionLogger:
        db_path = str(tmp_path / "test_interactions.db")
        log = InteractionLogger(db_path=db_path)
        await log.initialize()
        return log

    @pytest.mark.asyncio
    async def test_log_interaction(self, logger: InteractionLogger):
        iid = await logger.log(
            session_id="s1", query="What is Python?",
            response="A programming language.", model_id="test-model",
            confidence=0.9, latency_ms=100,
        )
        assert iid  # Got an ID back

    @pytest.mark.asyncio
    async def test_record_feedback(self, logger: InteractionLogger):
        iid = await logger.log(
            session_id="s1", query="q", response="a", model_id="m",
        )
        await logger.record_feedback(iid, 1.0, "explicit")
        # Should not raise

    @pytest.mark.asyncio
    async def test_export_top_interactions(self, logger: InteractionLogger):
        # Log some interactions with varying feedback
        for i in range(5):
            iid = await logger.log(
                session_id="s1", query=f"query {i}",
                response=f"response {i}", model_id="m",
            )
            score = 0.9 if i % 2 == 0 else 0.3
            await logger.record_feedback(iid, score)

        top = await logger.export_top_interactions(min_score=0.7)
        assert len(top) >= 2  # The ones with 0.9 feedback

    @pytest.mark.asyncio
    async def test_get_stats(self, logger: InteractionLogger):
        await logger.log(
            session_id="s1", query="q1", response="a1",
            model_id="m", confidence=0.8, latency_ms=100,
        )
        await logger.log(
            session_id="s1", query="q2", response="a2",
            model_id="m", confidence=0.6, latency_ms=200,
        )
        stats = await logger.get_stats(days=7)
        assert stats.total == 2
        assert stats.avg_latency_ms > 0

    @pytest.mark.asyncio
    async def test_get_model_performance(self, logger: InteractionLogger):
        iid1 = await logger.log(
            session_id="s1", query="q", response="a", model_id="model-a",
        )
        await logger.record_feedback(iid1, 0.9)
        iid2 = await logger.log(
            session_id="s1", query="q", response="a", model_id="model-b",
        )
        await logger.record_feedback(iid2, 0.4)

        perf = await logger.get_model_performance()
        assert "model-a" in perf
        assert perf["model-a"] > perf["model-b"]


# ══════════════════════════════════════════════════════════════
# Gap 7: ToolAugmentedReasoner
# ══════════════════════════════════════════════════════════════

class TestToolAugmentedReasoner:

    @pytest.fixture
    def reasoner(self) -> ToolAugmentedReasoner:
        return ToolAugmentedReasoner()

    def test_extract_claims_numbers(self, reasoner: ToolAugmentedReasoner):
        text = "The response time is 200ms and memory usage is 512MB."
        claims = reasoner._extract_claims(text)
        assert len(claims) >= 1

    def test_extract_claims_code(self, reasoner: ToolAugmentedReasoner):
        text = "Use `sorted(items)` to sort the list."
        claims = reasoner._extract_claims(text)
        assert len(claims) >= 1

    def test_extract_claims_years(self, reasoner: ToolAugmentedReasoner):
        text = "Python was created in 1991 by Guido."
        claims = reasoner._extract_claims(text)
        assert len(claims) >= 1

    def test_classify_code_claim(self, reasoner: ToolAugmentedReasoner):
        result = reasoner._classify_claim("`print('hello')`")
        assert result == "code"

    def test_classify_numerical_claim(self, reasoner: ToolAugmentedReasoner):
        result = reasoner._classify_claim("The result is 42 times faster")
        assert result == "numerical"

    def test_classify_temporal_claim(self, reasoner: ToolAugmentedReasoner):
        result = reasoner._classify_claim("Released in 2024")
        assert result == "temporal"

    @pytest.mark.asyncio
    async def test_verify_numerical_claim(self, reasoner: ToolAugmentedReasoner):
        result = await reasoner._verify_numerical_claim("2 + 2 equals 4")
        # Should attempt to verify the math
        assert result.original_claim == "2 + 2 equals 4"

    @pytest.mark.asyncio
    async def test_verify_code_claim(self, reasoner: ToolAugmentedReasoner):
        result = await reasoner._verify_code_claim(
            "Running `print(2+2)` outputs 4"
        )
        assert result.original_claim

    @pytest.mark.asyncio
    async def test_verify_claims_full(self, reasoner: ToolAugmentedReasoner):
        verifications = await reasoner.verify_claims(
            "The result of 10 * 5 is 50 and Python was released in 1991.",
            "What are the facts?",
        )
        assert len(verifications) >= 1
