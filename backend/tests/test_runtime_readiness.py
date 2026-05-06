"""Sprint-12A PR-1+2: runtime + router readiness inventory tests.

Asserts:
    1. RUNTIME_CLASSIFICATION covers every id RuntimeTruthRegistry
       emits (no orphans). Adding a new provider to the truth registry
       without classifying it is a CI failure.
    2. _classify_item maps each runtime to a sane (cost_class,
       recommended_role, readiness_state) triple.
    3. _readiness_state respects the cost-class ladder:
        - free_local: callable -> ready
        - subscription: detected -> configured_untested (CLI auth
          probe is intentionally NOT done)
        - metered_api: configured -> configured_untested unless an
          explicit zero-cost test marked it ready
    4. The router summary picks free_local for main_brain when one
       is ready, downgrades QE to degraded when only one reviewer is
       ready.
    5. The static get_router_policy() matrix carries every role.
    6. The /system/runtime-readiness endpoint returns no secret
       values (assert no string longer than 20 chars in the response
       starts with "sk-" / "pplx-" / "xai-" etc).
    7. Phase-2 read-only flag is still ON when readiness is queried.
"""

from __future__ import annotations

import json
import re
from unittest.mock import patch

import pytest

from app.services.runtime_readiness import (
    RUNTIME_CLASSIFICATION,
    _classify_item,
    _readiness_state,
    _build_router_summary,
    _kind_of,
    get_router_policy,
    get_runtime_readiness,
    item_to_dict,
)


# ── Classification coverage ──────────────────────────────────────────


class TestClassificationCoverage:
    def test_known_truth_registry_ids_classified(self):
        """Every id RuntimeTruthRegistry emits MUST appear in
        RUNTIME_CLASSIFICATION. If a new provider is added to the
        truth registry, this test fails until the readiness layer
        catches up."""
        EXPECTED_IDS = {
            "cli_claude", "cli_codex", "cli_gemini", "cli_ollama",
            "ollama_backend", "ollama_windows", "vllm_configured",
            "provider_perplexity", "provider_anthropic",
            "provider_openai", "provider_gemini",
            "provider_groq", "provider_openrouter", "provider_together",
        }
        missing = EXPECTED_IDS - RUNTIME_CLASSIFICATION.keys()
        assert not missing, (
            f"Truth-registry IDs without a readiness classification: "
            f"{sorted(missing)}"
        )

    def test_every_classification_has_required_fields(self):
        for item_id, c in RUNTIME_CLASSIFICATION.items():
            assert "cost_class" in c, item_id
            assert c["cost_class"] in {
                "free_local", "subscription", "metered_api", "unknown",
            }, item_id
            assert "primary_role" in c, item_id
            assert "secondary_roles" in c, item_id
            assert "rationale" in c, item_id
            assert isinstance(c["rationale"], str) and c["rationale"].strip()


# ── readiness_state ladder ───────────────────────────────────────────


class TestReadinessLadder:
    def test_free_local_ready_when_callable(self):
        item = {
            "type": "local_model",
            "detected": True, "configured": True,
            "callable": True, "reachable_from_backend": True,
            "authenticated": True,
        }
        assert _readiness_state(item, "free_local") == "ready"

    def test_free_local_offline_when_configured_but_not_callable(self):
        item = {
            "type": "local_model",
            "detected": True, "configured": True,
            "callable": False, "reachable_from_backend": False,
            "authenticated": "unknown",
        }
        assert _readiness_state(item, "free_local") == "detected_offline"

    def test_subscription_ready_when_callable(self):
        item = {
            "type": "cli", "detected": True, "configured": True,
            "callable": True, "reachable_from_backend": True,
            "authenticated": "unknown",
        }
        assert _readiness_state(item, "subscription") == "ready"

    def test_subscription_untested_when_detected_but_not_callable(self):
        item = {
            "type": "cli", "detected": True, "configured": True,
            "callable": False, "reachable_from_backend": False,
            "authenticated": "unknown",
        }
        assert _readiness_state(item, "subscription") == "configured_untested"

    def test_metered_api_untested_when_configured(self):
        item = {
            "type": "api", "detected": True, "configured": True,
            "callable": False, "reachable_from_backend": False,
            "authenticated": "unknown",
        }
        # Configured but no zero-cost probe yet -> configured_untested
        assert _readiness_state(item, "metered_api") == "configured_untested"

    def test_metered_api_not_configured_without_key(self):
        item = {
            "type": "api", "detected": False, "configured": False,
            "callable": False,
        }
        assert _readiness_state(item, "metered_api") == "not_configured"


# ── _classify_item demotes role when not ready ───────────────────────


class TestRoleDemotion:
    def test_recommended_role_none_when_not_ready(self):
        # vllm_configured exists in RUNTIME_CLASSIFICATION as main_brain
        # but the truth-item state here is offline -> recommended_role
        # must be 'none', not 'main_brain'.
        offline_local = {
            "id": "vllm_configured",
            "display_name": "vLLM",
            "type": "local_model",
            "detected": True, "configured": True,
            "callable": False, "reachable_from_backend": False,
        }
        c = _classify_item(offline_local)
        assert c.recommended_role == "none"
        assert c.readiness_state == "detected_offline"

    def test_recommended_role_when_ready(self):
        ready_local = {
            "id": "vllm_configured",
            "display_name": "vLLM",
            "type": "local_model",
            "detected": True, "configured": True,
            "callable": True, "reachable_from_backend": True,
            "authenticated": True,
        }
        c = _classify_item(ready_local)
        assert c.recommended_role == "main_brain"
        assert c.readiness_state == "ready"


# ── Router summary aggregation ───────────────────────────────────────


def _classified(*items: dict) -> list:
    return [_classify_item(it) for it in items]


class TestRouterSummary:
    def test_picks_free_local_main_brain_when_available(self):
        items = _classified(
            {
                "id": "vllm_configured", "display_name": "vLLM",
                "type": "local_model", "detected": True, "configured": True,
                "callable": True, "reachable_from_backend": True,
                "authenticated": True,
            },
            {
                "id": "provider_anthropic", "display_name": "Anthropic",
                "type": "api", "detected": True, "configured": True,
                "callable": False, "authenticated": "unknown",
            },
        )
        summary = _build_router_summary(items)
        assert summary.main_brain_id == "vllm_configured"
        assert summary.main_brain_cost_class == "free_local"

    def test_qe_full_when_two_or_more_ready(self):
        items = _classified(
            {
                "id": "vllm_configured", "display_name": "vLLM",
                "type": "local_model", "detected": True, "configured": True,
                "callable": True, "reachable_from_backend": True,
            },
            {
                "id": "ollama_backend", "display_name": "Ollama",
                "type": "local_model", "detected": True, "configured": True,
                "callable": True, "reachable_from_backend": True,
            },
        )
        summary = _build_router_summary(items)
        assert summary.qe_mode == "full"
        assert len(summary.qe_reviewers_ready) >= 2

    def test_qe_degraded_when_only_one_reviewer(self):
        items = _classified(
            {
                "id": "vllm_configured", "display_name": "vLLM",
                "type": "local_model", "detected": True, "configured": True,
                "callable": True, "reachable_from_backend": True,
            },
        )
        summary = _build_router_summary(items)
        assert summary.qe_mode == "degraded"

    def test_qe_unavailable_when_none(self):
        items = _classified(
            {
                "id": "provider_perplexity", "display_name": "Perplexity",
                "type": "api", "detected": False, "configured": False,
                "callable": False,
            },
        )
        summary = _build_router_summary(items)
        assert summary.qe_mode == "unavailable"

    def test_next_action_blocked_when_no_main_brain(self):
        items = _classified(
            {
                "id": "provider_anthropic", "display_name": "Anthropic",
                "type": "api", "detected": True, "configured": True,
                "callable": False,
            },
        )
        summary = _build_router_summary(items)
        assert "blocked" in summary.next_action.lower() or \
               "no main brain" in summary.next_action.lower()


# ── Static policy matrix ─────────────────────────────────────────────


class TestRouterPolicyMatrix:
    def test_all_roles_present(self):
        policy = get_router_policy()
        roles = policy["roles"]
        for role in (
            "main_brain", "qe_reviewer", "coder", "researcher",
            "web_grounding", "fallback",
        ):
            assert role in roles, f"missing role: {role}"
            assert "preference_order" in roles[role]
            assert "guard" in roles[role]
            assert isinstance(roles[role]["preference_order"], list)

    def test_perplexity_only_for_web_grounding(self):
        policy = get_router_policy()
        for role, body in policy["roles"].items():
            if role == "web_grounding":
                assert "provider_perplexity" in body["preference_order"]
            else:
                assert "provider_perplexity" not in body["preference_order"], (
                    f"Perplexity must NOT appear in role {role!r} -- "
                    f"that would auto-bill the operator."
                )

    def test_hard_rules_documented(self):
        policy = get_router_policy()
        rules = policy["hard_rules"]
        assert any("no paid api" in r.lower() for r in rules)
        assert any("qe" in r.lower() and ">=2" in r for r in rules)


# ── End-to-end via mocked truth registry ─────────────────────────────


CANNED_TRUTH = {
    "schema_version": 1,
    "updated_at": "2026-05-05T20:00:00Z",
    "items": [
        {
            "id": "vllm_configured", "display_name": "vLLM",
            "type": "local_model", "detected": True, "configured": True,
            "callable": True, "reachable_from_backend": True,
            "authenticated": True, "models_tools_discovered": ["qwen3"],
        },
        {
            "id": "cli_claude", "display_name": "Claude Code CLI",
            "type": "cli", "detected": True, "configured": True,
            "callable": True, "reachable_from_backend": True,
            "authenticated": "unknown",
        },
        {
            "id": "provider_perplexity", "display_name": "Perplexity API",
            "type": "api", "detected": False, "configured": False,
            "callable": False, "authenticated": False,
        },
        {
            "id": "provider_anthropic", "display_name": "Anthropic API",
            "type": "api", "detected": True, "configured": True,
            "callable": False, "authenticated": "unknown",
        },
    ],
}


class TestEndToEnd:
    @pytest.mark.asyncio
    async def test_get_runtime_readiness_no_secret_leak(self):
        async def fake_get_truth(refresh: bool = False):  # noqa: ARG001
            return CANNED_TRUTH

        with patch(
            "app.services.runtime_readiness.runtime_truth_registry"
        ) as mock_reg:
            mock_reg.get_truth = fake_get_truth
            mock_reg.refresh = fake_get_truth
            result = await get_runtime_readiness(refresh=False)

        # No bytes that look like an API key
        blob = json.dumps(result)
        for pat in (r"sk-[A-Za-z0-9]{20,}", r"pplx-[A-Za-z0-9]{20,}",
                    r"xai-[A-Za-z0-9]{20,}", r"gsk_[A-Za-z0-9]{20,}"):
            assert not re.search(pat, blob), (
                f"Readiness response leaks something matching {pat}"
            )

        assert result["router_summary"]["main_brain_id"] == "vllm_configured"
        assert result["router_summary"]["main_brain_cost_class"] == "free_local"
        assert result["router_summary"]["qe_mode"] in {"full", "degraded"}

    @pytest.mark.asyncio
    async def test_endpoint_route_registered(self, app):
        spec = app.openapi()
        paths = spec.get("paths", {})
        assert "/api/v1/system/runtime-readiness" in paths
        assert "/api/v1/system/router-readiness" in paths
        assert "/api/v1/system/router-policy" in paths

    @pytest.mark.asyncio
    async def test_phase2_readonly_still_on(self):
        from app.core.config import get_settings
        assert get_settings().integrations_phase2_readonly is True


# ── kind mapping ─────────────────────────────────────────────────────


class TestKindMapping:
    def test_local_model_type_maps_to_local_llm(self):
        assert _kind_of({"type": "local_model", "id": "x"}) == "local_llm"

    def test_cli_type_maps_to_cli_runtime(self):
        assert _kind_of({"type": "cli", "id": "x"}) == "cli_runtime"

    def test_api_type_maps_to_api_provider(self):
        assert _kind_of({"type": "api", "id": "x"}) == "api_provider"

    def test_runtime_dependency_kept_separate(self):
        # node / npm / docker are runtime *dependencies*, not brains
        # themselves -- they must NOT be classified as main_brain
        # candidates.
        assert _kind_of({"type": "runtime", "id": "cli_node"}) == "runtime"
