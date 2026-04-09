"""Live integration tests for Daena's Cognitive Engine.

Tests all reasoning modes against real Ollama models:
- Standard (single model)
- Council (multi-model synthesis) -- via CognitiveReasoner
- Quintessence (multi-model debate with expert lenses)
- With and without AGI mode
- Ollama timeout behavior for reasoning models

Requires: Ollama running on localhost:11434 with 2+ models.
"""

import asyncio
import time

import httpx
import pytest


def _ollama_available() -> bool:
    """Check if Ollama is reachable and has models."""
    try:
        resp = httpx.get("http://localhost:11434/api/tags", timeout=5.0)
        data = resp.json()
        models = [m["name"] for m in data.get("models", []) if "embed" not in m["name"]]
        return len(models) >= 2
    except Exception:
        return False


skip_no_ollama = pytest.mark.skipif(
    not _ollama_available(),
    reason="Ollama not running or fewer than 2 models available",
)


# ---- Ollama Timeout ----

class TestOllamaTimeout:
    """Verify model-aware timeout selection."""

    def test_reasoning_model_gets_long_timeout(self) -> None:
        from app.services.providers.ollama import OllamaProvider
        provider = OllamaProvider()
        timeout = provider._timeout_for_model("deepseek-r1:14b")
        assert timeout.read == 600.0  # 10 minutes

    def test_reasoning_model_variant(self) -> None:
        from app.services.providers.ollama import OllamaProvider
        provider = OllamaProvider()
        timeout = provider._timeout_for_model("deepseek-r1:8b")
        assert timeout.read == 600.0

    def test_standard_model_gets_default_timeout(self) -> None:
        from app.services.providers.ollama import OllamaProvider
        provider = OllamaProvider()
        timeout = provider._timeout_for_model("mistral:7b")
        assert timeout.read == 120.0

    def test_qwq_reasoning_model(self) -> None:
        from app.services.providers.ollama import OllamaProvider
        provider = OllamaProvider()
        timeout = provider._timeout_for_model("qwq:32b")
        assert timeout.read == 600.0

    def test_llama_standard_timeout(self) -> None:
        from app.services.providers.ollama import OllamaProvider
        provider = OllamaProvider()
        timeout = provider._timeout_for_model("llama3.1:8b")
        assert timeout.read == 120.0


# ---- Standard Mode (single model, no AGI) ----

@skip_no_ollama
class TestStandardMode:
    """Standard mode: single best model, no debate."""

    @pytest.mark.asyncio
    async def test_orient_with_ollama(self) -> None:
        """CognitiveReasoner.orient() works with a real Ollama model."""
        from app.services.cognition.cognitive_reasoner import CognitiveReasoner

        reasoner = CognitiveReasoner(agi_mode=False)
        await reasoner.initialize()

        assert reasoner.is_llm_available
        assert reasoner.reasoning_mode == "llm"  # Not quintessence (AGI off)

        result = await reasoner.orient(
            task="Analyze a web application for security issues",
            observation={
                "target": "example.com",
                "subdomains": 5,
                "waf_detected": "cloudflare",
                "technologies": ["nginx", "react"],
            },
        )

        assert result.reasoning_mode == "llm"
        assert result.model_used != ""
        assert len(result.analysis) > 50  # Should have real reasoning
        print(f"\n[STANDARD] Model: {result.model_used}")
        print(f"[STANDARD] Frameworks: {result.frameworks_used}")
        print(f"[STANDARD] Analysis length: {len(result.analysis)} chars")
        print(f"[STANDARD] First 200 chars: {result.analysis[:200]}")

    @pytest.mark.asyncio
    async def test_decide_with_ollama(self) -> None:
        """CognitiveReasoner.decide() generates a strategy."""
        from app.services.cognition.cognitive_reasoner import CognitiveReasoner

        reasoner = CognitiveReasoner(agi_mode=False)
        await reasoner.initialize()

        strategy = await reasoner.decide(
            analysis="Target is cloudflare-protected. Standard scans blocked.",
            available_tools=["subdomain_enum", "http_probe", "vuln_scan", "cve_search"],
        )

        assert strategy.name != ""
        assert strategy.reasoning != ""
        print(f"\n[DECIDE] Strategy: {strategy.name}")
        print(f"[DECIDE] Reasoning: {strategy.reasoning[:200]}")


# ---- AGI Mode (Quintessence debate) ----

@skip_no_ollama
class TestAGIMode:
    """AGI mode: Quintessence multi-model debate with expert lenses."""

    @pytest.mark.asyncio
    async def test_quintessence_detection(self) -> None:
        """With 2+ models, Quintessence should be detected as available."""
        from app.services.cognition.cognitive_reasoner import CognitiveReasoner

        reasoner = CognitiveReasoner(agi_mode=True)
        await reasoner.initialize()

        assert reasoner.is_llm_available
        assert reasoner._quintessence_available, (
            "Quintessence should be available with 2+ Ollama models. "
            "This was the bug -- registry.initialize() was missing."
        )
        assert reasoner.reasoning_mode == "quintessence"
        print(f"\n[AGI] Provider: {reasoner._provider}, Model: {reasoner._model_id}")
        print(f"[AGI] Quintessence available: {reasoner._quintessence_available}")

    @pytest.mark.asyncio
    async def test_quintessence_orient(self) -> None:
        """Full Quintessence debate: 3 models + expert lenses + synthesis."""
        from app.services.cognition.cognitive_reasoner import CognitiveReasoner

        reasoner = CognitiveReasoner(agi_mode=True)
        await reasoner.initialize()

        if not reasoner._quintessence_available:
            pytest.skip("Quintessence not available (need 2+ models)")

        start = time.monotonic()
        result = await reasoner.orient(
            task="Find vulnerabilities in a Google Cloud target for VRP",
            observation={
                "target": "cloud.google.com",
                "subdomains": 70,
                "all_404": True,
                "waf_detected": "google_frontend",
                "technologies": ["HTTP/3", "GFE"],
                "http_version": "HTTP/3",
            },
            previous_failures=[{
                "strategy": "nuclei_default",
                "reason": "All filtered by WAF",
                "lesson": "Standard templates are well-known and blocked",
            }],
        )
        elapsed = time.monotonic() - start

        # Quintessence should produce richer analysis than single model
        assert len(result.analysis) > 100
        assert result.model_used != ""
        print(f"\n[QUINTESSENCE] Model: {result.model_used}")
        print(f"[QUINTESSENCE] Frameworks: {result.frameworks_used}")
        print(f"[QUINTESSENCE] Analysis length: {len(result.analysis)} chars")
        print(f"[QUINTESSENCE] Time: {elapsed:.1f}s")
        print(f"[QUINTESSENCE] First 300 chars:\n{result.analysis[:300]}")


# ---- Reasoning Model Timeout ----

@skip_no_ollama
class TestReasoningModelTimeout:
    """Verify deepseek-r1 doesn't timeout prematurely."""

    @pytest.mark.asyncio
    async def test_deepseek_r1_completes(self) -> None:
        """deepseek-r1 should complete a reasoning task without timeout."""
        from app.services.providers.ollama import OllamaProvider
        from app.services.providers.base import GenerateRequest, LLMMessage

        provider = OllamaProvider()
        # Check if deepseek-r1 is available
        models = await provider.list_models()
        r1_models = [m for m in models if "deepseek-r1" in m.model_id]
        if not r1_models:
            pytest.skip("deepseek-r1 not installed")

        model_id = r1_models[0].model_id
        request = GenerateRequest(
            messages=[LLMMessage(
                role="user",
                content="What are 3 creative approaches to find security vulnerabilities "
                        "in a well-protected cloud application? Think step by step.",
            )],
            model_id=model_id,
            temperature=0.7,
            max_tokens=500,
        )

        start = time.monotonic()
        response = await provider.generate(request)
        elapsed = time.monotonic() - start

        assert response.content != ""
        assert response.model_id == model_id
        print(f"\n[DEEPSEEK-R1] Model: {model_id}")
        print(f"[DEEPSEEK-R1] Time: {elapsed:.1f}s")
        print(f"[DEEPSEEK-R1] Tokens in: {response.token_count_input}, out: {response.token_count_output}")
        print(f"[DEEPSEEK-R1] Response length: {len(response.content)} chars")
        print(f"[DEEPSEEK-R1] First 200 chars: {response.content[:200]}")


# ---- Model Count Verification ----

@skip_no_ollama
class TestModelCountVerification:
    """Verify the registry correctly counts reasoning models."""

    @pytest.mark.asyncio
    async def test_registry_counts_non_embed_models(self) -> None:
        """Registry should find all non-embedding Ollama models."""
        from app.services.model_registry import ModelRegistry

        registry = ModelRegistry()
        await registry.initialize()
        all_models = await registry.list_all_models()

        # Filter same way as CognitiveReasoner
        reasoning_models = [
            m for m in all_models
            if "embed" not in m.model_id.lower() and "nomic" not in m.model_id.lower()
        ]

        print(f"\n[REGISTRY] Total models: {len(all_models)}")
        print(f"[REGISTRY] Reasoning models: {len(reasoning_models)}")
        for m in reasoning_models:
            print(f"  {m.provider.value}: {m.model_id}")

        # We know Ollama has 12+ non-embed models
        assert len(reasoning_models) >= 2, (
            f"Expected 2+ reasoning models, got {len(reasoning_models)}. "
            f"This means the Quintessence check would fail."
        )
