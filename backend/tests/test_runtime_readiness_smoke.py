"""Sprint-12A PR-5 smoke: runtime + QE + router readiness end-to-end.

Walks the full readiness ladder and asserts the operator-facing
guarantees the brief calls out:

    1. /system/runtime-readiness returns ALL expected provider IDs.
    2. No secret values in any response (regex sweep).
    3. Local vLLM / llama-server status is honest (callable iff probe
       succeeded; configured doesn't imply callable).
    4. Ollama status is honest.
    5. CLI runtimes (Claude / Codex / Gemini) are honest.
    6. Perplexity API key-present state matches settings.perplexity_api_key
       presence (boolean only).
    7. Router policy preference_order picks local-first for main_brain
       and Perplexity-only for web_grounding.
    8. QE mode is one of the three valid states; "full" requires >=2
       distinct ready runtimes filling >=3 slots.
    9. Phase-2 read-only flag still ON.
   10. /scrape, /research, /form-drafts, /governance/approvals/draft
       all still exist (Sprint-11 contracts intact).

This is the gate test: "is it safe to start Sprint-12 brain enrichment
on top of this readiness layer?"
"""

from __future__ import annotations

import json
import re
from unittest.mock import patch

import pytest

from app.core.config import get_settings
from app.services.runtime_readiness import (
    RUNTIME_CLASSIFICATION,
    QE_SLOTS,
    get_router_policy,
    get_runtime_readiness,
    get_qe_readiness,
)


EXPECTED_PROVIDER_IDS = {
    "cli_claude", "cli_codex", "cli_gemini", "cli_ollama",
    "ollama_backend", "ollama_windows", "vllm_configured",
    "provider_perplexity", "provider_anthropic",
    "provider_openai", "provider_gemini",
    "provider_groq", "provider_openrouter", "provider_together",
}


# ── 1-2. Inventory completeness + no secret leak ─────────────────────


CANNED_TRUTH = {
    "schema_version": 1,
    "updated_at": "2026-05-05T20:00:00Z",
    "items": [
        # vLLM ready
        {"id": "vllm_configured", "display_name": "vLLM",
         "type": "local_model", "detected": True, "configured": True,
         "callable": True, "reachable_from_backend": True,
         "authenticated": True,
         "endpoint": "http://127.0.0.1:8080",
         "models_tools_discovered": ["qwen3-8b"]},
        # Ollama detected but offline
        {"id": "ollama_backend", "display_name": "Ollama backend-local",
         "type": "local_model", "detected": True, "configured": True,
         "callable": False, "reachable_from_backend": False,
         "authenticated": "unknown",
         "last_failure_reason": "Endpoint not reachable.",
         "endpoint": "http://127.0.0.1:11434"},
        {"id": "ollama_windows", "display_name": "Ollama Windows host",
         "type": "local_model", "detected": True, "configured": True,
         "callable": False, "reachable_from_backend": False,
         "authenticated": "unknown",
         "endpoint": "http://host.docker.internal:11434"},
        {"id": "cli_ollama", "display_name": "Ollama CLI",
         "type": "cli", "detected": True, "configured": True,
         "callable": True, "reachable_from_backend": True,
         "authenticated": "unknown"},
        # Claude Code CLI detected
        {"id": "cli_claude", "display_name": "Claude Code CLI",
         "type": "cli", "detected": True, "configured": True,
         "callable": True, "reachable_from_backend": True,
         "authenticated": "unknown"},
        {"id": "cli_codex", "display_name": "Codex CLI",
         "type": "cli", "detected": False, "configured": False,
         "callable": False, "authenticated": "unknown"},
        {"id": "cli_gemini", "display_name": "Gemini CLI",
         "type": "cli", "detected": False, "configured": False,
         "callable": False, "authenticated": "unknown"},
        # API providers
        {"id": "provider_perplexity", "display_name": "Perplexity API",
         "type": "api", "detected": False, "configured": False,
         "callable": False, "authenticated": False},
        {"id": "provider_anthropic", "display_name": "Anthropic API",
         "type": "api", "detected": True, "configured": True,
         "callable": False, "authenticated": "unknown"},
        {"id": "provider_openai", "display_name": "OpenAI API",
         "type": "api", "detected": False, "configured": False,
         "callable": False, "authenticated": False},
        {"id": "provider_gemini", "display_name": "Google Gemini API",
         "type": "api", "detected": False, "configured": False,
         "callable": False, "authenticated": False},
        {"id": "provider_groq", "display_name": "Groq API",
         "type": "api", "detected": False, "configured": False,
         "callable": False, "authenticated": False},
        {"id": "provider_openrouter", "display_name": "OpenRouter API",
         "type": "api", "detected": False, "configured": False,
         "callable": False, "authenticated": False},
        {"id": "provider_together", "display_name": "Together API",
         "type": "api", "detected": False, "configured": False,
         "callable": False, "authenticated": False},
    ],
}


@pytest.fixture
def patched_truth():
    async def fake_get_truth(refresh: bool = False):  # noqa: ARG001
        return CANNED_TRUTH

    with patch(
        "app.services.runtime_readiness.runtime_truth_registry"
    ) as mock_reg:
        mock_reg.get_truth = fake_get_truth
        mock_reg.refresh = fake_get_truth
        yield mock_reg


class TestInventory:
    @pytest.mark.asyncio
    async def test_every_expected_provider_id_present(self, patched_truth):
        result = await get_runtime_readiness(refresh=False)
        ids = {item["id"] for item in result["items"]}
        missing = EXPECTED_PROVIDER_IDS - ids
        assert not missing, f"Missing provider rows: {missing}"

    @pytest.mark.asyncio
    async def test_no_secret_values_in_response(self, patched_truth):
        result = await get_runtime_readiness(refresh=False)
        blob = json.dumps(result)
        for pat in (
            r"sk-[A-Za-z0-9]{20,}",
            r"pplx-[A-Za-z0-9]{20,}",
            r"xai-[A-Za-z0-9]{20,}",
            r"gsk_[A-Za-z0-9]{20,}",
            r"AIzaSy[A-Za-z0-9]{20,}",  # google api key shape
        ):
            assert not re.search(pat, blob), (
                f"Readiness response leaks pattern {pat!r}"
            )


# ── 3-6. Honest status per cost class ────────────────────────────────


class TestHonestStatus:
    @pytest.mark.asyncio
    async def test_vllm_callable_means_ready(self, patched_truth):
        r = await get_runtime_readiness(refresh=False)
        vllm = next(i for i in r["items"] if i["id"] == "vllm_configured")
        assert vllm["readiness_state"] == "ready"
        assert vllm["recommended_role"] == "main_brain"
        assert vllm["cost_class"] == "free_local"

    @pytest.mark.asyncio
    async def test_ollama_offline_is_offline(self, patched_truth):
        r = await get_runtime_readiness(refresh=False)
        ollama = next(i for i in r["items"] if i["id"] == "ollama_backend")
        assert ollama["readiness_state"] == "detected_offline"
        # Offline means it's not picked for main_brain role
        assert ollama["recommended_role"] == "none"

    @pytest.mark.asyncio
    async def test_cli_claude_ready_when_on_path(self, patched_truth):
        r = await get_runtime_readiness(refresh=False)
        claude = next(i for i in r["items"] if i["id"] == "cli_claude")
        assert claude["readiness_state"] == "ready"
        assert claude["cost_class"] == "subscription"

    @pytest.mark.asyncio
    async def test_codex_undetected_is_not_configured(self, patched_truth):
        r = await get_runtime_readiness(refresh=False)
        codex = next(i for i in r["items"] if i["id"] == "cli_codex")
        assert codex["readiness_state"] == "not_configured"
        assert codex["recommended_role"] == "none"

    @pytest.mark.asyncio
    async def test_anthropic_configured_untested_when_only_key(self, patched_truth):
        r = await get_runtime_readiness(refresh=False)
        anthropic = next(i for i in r["items"] if i["id"] == "provider_anthropic")
        assert anthropic["readiness_state"] == "configured_untested"
        # Configured-untested means it's not surfaced as a router pick
        # because no zero-cost probe has run.
        assert anthropic["recommended_role"] == "none"

    @pytest.mark.asyncio
    async def test_perplexity_status_matches_settings(self):
        # No mock here -- this hits the real settings + truth registry.
        # The boolean only ever reflects api-key presence.
        from app.services.runtime_truth_registry import runtime_truth_registry
        truth = await runtime_truth_registry.get_truth()
        items = truth.get("items") or []
        pplx = next((i for i in items if i.get("id") == "provider_perplexity"), None)
        if pplx is not None:
            settings = get_settings()
            assert bool(pplx["configured"]) == bool(settings.perplexity_api_key)


# ── 7. Router policy preference_order ────────────────────────────────


class TestRouterPolicy:
    def test_main_brain_prefers_local_first(self):
        policy = get_router_policy()
        order = policy["roles"]["main_brain"]["preference_order"]
        # vllm_configured / ollama_backend must come before ANY metered_api
        local_indices = [order.index(x) for x in ("vllm_configured", "ollama_backend") if x in order]
        api_indices = [order.index(x) for x in order if x.startswith("provider_")]
        if local_indices and api_indices:
            assert max(local_indices) < min(api_indices), (
                "Router policy must prefer free_local over metered_api "
                "for main_brain."
            )

    def test_web_grounding_perplexity_only(self):
        policy = get_router_policy()
        order = policy["roles"]["web_grounding"]["preference_order"]
        assert order == ["provider_perplexity"], (
            f"web_grounding preference_order must be perplexity-only; "
            f"got {order}"
        )

    @pytest.mark.asyncio
    async def test_router_picks_local_main_brain_when_ready(self, patched_truth):
        result = await get_runtime_readiness(refresh=False)
        summary = result["router_summary"]
        assert summary["main_brain_id"] == "vllm_configured"
        assert summary["main_brain_cost_class"] == "free_local"


# ── 8. QE mode honesty ───────────────────────────────────────────────


class TestQeModeHonesty:
    @pytest.mark.asyncio
    async def test_qe_mode_with_two_distinct_ready_runtimes(self, patched_truth):
        # Canned truth has vllm_configured + cli_claude + cli_ollama
        # ready (3 distinct runtimes), so QE should be full.
        qe = await get_qe_readiness(refresh=False)
        assert qe["mode"] == "full", (
            f"QE should be full with 3+ distinct ready runtimes; got "
            f"{qe['mode']} -- {qe['mode_reason']}"
        )
        assert len(qe["distinct_runtime_ids"]) >= 2

    @pytest.mark.asyncio
    async def test_qe_mode_one_of_three_values(self, patched_truth):
        qe = await get_qe_readiness(refresh=False)
        assert qe["mode"] in ("full", "degraded", "unavailable")

    @pytest.mark.asyncio
    async def test_qe_slots_are_the_five_named_slots(self, patched_truth):
        qe = await get_qe_readiness(refresh=False)
        slots = {a["slot"] for a in qe["slot_assignments"]}
        assert slots == set(QE_SLOTS.keys())


# ── 9. Phase-2 still blocking writes ─────────────────────────────────


class TestPhase2StillOn:
    def test_flag_default_on(self):
        settings = get_settings()
        assert settings.integrations_phase2_readonly is True


# ── 10. Sprint-11 contracts intact ───────────────────────────────────


class TestSprint11ContractsIntact:
    @pytest.mark.asyncio
    async def test_supervised_work_routes_present(self, app):
        spec = app.openapi()
        paths = spec.get("paths", {})
        critical = [
            "/api/v1/scrape/extract",
            "/api/v1/research/career",
            "/api/v1/research/content",
            "/api/v1/research/drafts",
            "/api/v1/form-drafts/from-questions",
            "/api/v1/form-drafts/from-html",
            "/api/v1/form-drafts/from-url",
            "/api/v1/form-drafts",
            "/api/v1/governance/approvals/draft",
            # Sprint-12A new routes
            "/api/v1/system/runtime-readiness",
            "/api/v1/system/router-readiness",
            "/api/v1/system/router-policy",
            "/api/v1/system/qe-readiness",
        ]
        missing = [p for p in critical if p not in paths]
        assert not missing, (
            f"Sprint-11 + Sprint-12A surface broken; missing: {missing}"
        )

    @pytest.mark.asyncio
    async def test_no_banned_dispatch_routes(self, app):
        spec = app.openapi()
        paths = spec.get("paths", {})
        for offending in (
            "/api/v1/form-drafts/submit",
            "/api/v1/form-drafts/send",
            "/api/v1/form-drafts/apply",
            "/api/v1/form-drafts/post",
            "/api/v1/form-drafts/publish",
            "/api/v1/form-drafts/dispatch",
        ):
            assert offending not in paths


# ── Coverage assertion: every truth-registry id classified ────────────


class TestCoverageStillSync:
    def test_classification_covers_every_truth_id(self):
        missing = EXPECTED_PROVIDER_IDS - RUNTIME_CLASSIFICATION.keys()
        assert not missing, (
            f"Truth-registry IDs without a readiness classification: "
            f"{sorted(missing)}"
        )
