from __future__ import annotations

from app.core.constants import ModelProvider
from app.core.universal_cognitive_gateway import (
    attach_gateway_review,
    build_gateway_request,
    classify_risk,
    compress_mission,
    review_output,
    select_skills,
)
from app.services.providers.base import GenerateRequest, LLMMessage, LLMResponse


def test_gateway_wraps_request_once() -> None:
    request = GenerateRequest(messages=[LLMMessage(role="user", content="Build the gateway")])

    wrapped = build_gateway_request(request, model_id="test-model")
    wrapped_again = build_gateway_request(wrapped, model_id="test-model")

    assert wrapped.system_prompt
    assert "Daena Universal Cognitive Gateway is active" in wrapped.system_prompt
    assert wrapped_again.system_prompt == wrapped.system_prompt
    assert wrapped.metadata["universal_cognitive_gateway"]["wrapped"] is True
    assert "Cognitive stack:" in wrapped.system_prompt


def test_gateway_selects_skills_and_classifies_jailbreak_risk() -> None:
    mission = compress_mission("Study a jailbreak prompt but implement safe architecture")

    assert "architecture" in select_skills(mission)
    assert classify_risk(mission) == "unsafe-or-disallowed"


def test_gateway_review_metadata_attached_to_response() -> None:
    request = build_gateway_request(
        GenerateRequest(messages=[LLMMessage(role="user", content="Fix prompt injection defense")]),
        model_id="test-model",
    )
    response = LLMResponse(
        content="Done. Blocker: none. Next action: run tests. Confidence: high.",
        model_id="test-model",
        provider=ModelProvider.OLLAMA,
    )

    reviewed = attach_gateway_review(response, request)

    metadata = reviewed.raw["universal_cognitive_gateway"]
    assert metadata["risk"] in {"normal", "security-relevant"}
    assert metadata["review"]["no_dead_end"] is True


def test_gateway_repairs_dead_end_response() -> None:
    request = build_gateway_request(
        GenerateRequest(messages=[LLMMessage(role="user", content="Do the safe part")]),
        model_id="test-model",
        available_tools=["daenabot"],
    )
    response = LLMResponse(
        content="I can't help with that",
        model_id="test-model",
        provider=ModelProvider.OLLAMA,
    )

    reviewed = attach_gateway_review(response, request)

    assert "Daena gateway repair" in reviewed.content
    metadata = reviewed.raw["universal_cognitive_gateway"]
    assert metadata["review"]["repaired"] is True
    assert metadata["review"]["actionability_ok"] is True


def test_gateway_flags_inactionable_output() -> None:
    mission = compress_mission("Analyze this")
    review = review_output("Maybe.", mission, "normal")

    assert review.no_dead_end is True
    assert review.actionability_ok is False
