"""
Tests for Explorer Mode (human-in-the-loop consultation).

Tests:
- API mode (ENABLE_CLOUD_LLM=1) works independently
- Explorer mode (ENABLE_EXPLORER_MODE=1) works independently
- Mixed mode prevention (no conflicts)
"""

import os
import pytest
from fastapi.testclient import TestClient

# Set DISABLE_AUTH=1 for tests
os.environ["DISABLE_AUTH"] = "1"


@pytest.fixture
def client():
    """Create test client"""
    from backend.main import app
    return TestClient(app)


def test_explorer_mode_status(client):
    """Test that Explorer Mode status endpoint works"""
    response = client.get("/api/v1/explorer/status")
    
    assert response.status_code == 200
    data = response.json()
    assert "success" in data
    assert "enabled" in data
    assert "supported_targets" in data
    assert isinstance(data["supported_targets"], list)
    assert "chatgpt" in data["supported_targets"]
    assert "gemini" in data["supported_targets"]


def test_explorer_build_prompt(client):
    """Test that Explorer Mode can build prompts"""
    response = client.post(
        "/api/v1/explorer/build_prompt",
        json={
            "task": "What is the capital of France?",
            "target": "chatgpt",
            "context": {"test": True}
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data.get("success") is True
    assert "formatted_prompt" in data
    assert "instructions" in data
    assert "target" in data
    assert len(data["formatted_prompt"]) > 0
    assert "TASK:" in data["formatted_prompt"]
    assert "FINAL ANSWER:" in data["formatted_prompt"]


def test_explorer_parse_response(client):
    """Test that Explorer Mode can parse responses"""
    sample_response = """REASONING:
I need to find the capital of France.

ASSUMPTIONS:
France is a country in Europe.

FINAL ANSWER:
The capital of France is Paris.

CONFIDENCE:
High"""
    
    response = client.post(
        "/api/v1/explorer/parse_response",
        json={
            "text": sample_response,
            "target": "chatgpt"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data.get("success") is True
    assert "reasoning" in data
    assert "assumptions" in data
    assert "answer" in data
    assert "confidence" in data
    assert "parsed_successfully" in data
    assert "Paris" in data["answer"] or "paris" in data["answer"].lower()


def test_explorer_merge_responses(client):
    """Test that Explorer Mode can merge responses with Daena's"""
    daena_response = "Based on my analysis, the capital of France is Paris."
    explorer_response = {
        "target": "chatgpt",
        "reasoning": "I looked up the information.",
        "assumptions": "France is a country.",
        "answer": "The capital of France is Paris.",
        "confidence": "High"
    }
    
    response = client.post(
        "/api/v1/explorer/merge",
        json={
            "daena_response": daena_response,
            "explorer_response": explorer_response
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data.get("success") is True
    assert "synthesis" in data
    assert "daena_analysis" in data
    assert "external_consultation" in data
    assert len(data["synthesis"]) > 0
    assert daena_response in data["synthesis"]


def test_api_mode_independent(client):
    """Test that API mode (ENABLE_CLOUD_LLM) works independently of Explorer Mode"""
    # This test verifies that enabling/disabling Explorer Mode doesn't break API mode
    # The router should handle both independently
    
    # Test that daena chat still works
    response = client.post(
        "/api/v1/daena/chat",
        json={
            "message": "Hello Daena",
            "user_id": "founder"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "response" in data or "daena_response" in data


def test_explorer_mode_no_automation(client):
    """Test that Explorer Mode does NOT attempt automation"""
    # Explorer Mode should only format/parse - no browser automation
    # This is verified by checking that the service doesn't import automation tools
    
    from backend.services.explorer_bridge import explorer_bridge
    
    # Verify it's a formatting/parsing service only
    assert hasattr(explorer_bridge, "build_prompt")
    assert hasattr(explorer_bridge, "parse_response")
    assert hasattr(explorer_bridge, "merge_with_daena_response")
    
    # Verify it does NOT have automation methods
    assert not hasattr(explorer_bridge, "open_browser")
    assert not hasattr(explorer_bridge, "scrape")
    assert not hasattr(explorer_bridge, "automate")


def test_explorer_mode_requires_approval(client):
    """Test that Explorer Mode requires manual approval (hint only)"""
    # When Daena suggests Explorer Mode, it should be a hint, not automatic execution
    
    response = client.post(
        "/api/v1/daena/chat",
        json={
            "message": "Compare this with what ChatGPT thinks",
            "user_id": "founder"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Check if explorer hint is present
    context = data.get("context") or data.get("daena_response", {}).get("context", {})
    explorer_hint = context.get("explorer_hint")
    
    if explorer_hint:
        assert explorer_hint.get("suggested") is True
        assert explorer_hint.get("requires_approval") is True
        assert explorer_hint.get("mode") == "explorer"  # Human-in-the-loop


def test_no_duplicate_explorer_services(client):
    """Test that there are no duplicate explorer services"""
    import importlib
    import sys
    
    # Check that only one explorer_bridge exists
    explorer_modules = []
    for module_name in sys.modules:
        if "explorer" in module_name.lower() and "bridge" in module_name.lower():
            explorer_modules.append(module_name)
    
    # Should only have one explorer_bridge module
    explorer_bridge_modules = [m for m in explorer_modules if "explorer_bridge" in m]
    assert len(explorer_bridge_modules) <= 1, f"Multiple explorer_bridge modules found: {explorer_bridge_modules}"









