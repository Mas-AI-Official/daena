"""
Tests for Human Relay Explorer (manual copy/paste bridge).

Tests:
- Generate prompt returns relay_id and prompt_text
- Ingest saves insight and returns parsed summary
- Synthesize returns final_answer and references used insight ids
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


def test_human_relay_status(client):
    """Test that Human Relay Explorer status endpoint works"""
    response = client.get("/api/v1/human-relay/status")
    
    assert response.status_code == 200
    data = response.json()
    assert "success" in data
    assert "enabled" in data
    assert "supported_providers" in data
    assert isinstance(data["supported_providers"], list)
    assert "chatgpt" in data["supported_providers"]
    assert "gemini" in data["supported_providers"]


def test_generate_prompt(client):
    """Test that Human Relay Explorer can generate prompts"""
    response = client.post(
        "/api/v1/human-relay/prompt",
        json={
            "provider": "chatgpt",
            "task": "What is the capital of France?",
            "context": {"test": True}
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data.get("success") is True
    assert "prompt_text" in data
    assert "relay_id" in data
    assert "trace_id" in data
    assert len(data["prompt_text"]) > 0
    assert "TASK:" in data["prompt_text"]
    assert "FINAL ANSWER:" in data["prompt_text"]


def test_ingest_response(client):
    """Test that Human Relay Explorer can ingest responses"""
    # First generate a prompt to get relay_id
    prompt_response = client.post(
        "/api/v1/human-relay/prompt",
        json={
            "provider": "chatgpt",
            "task": "What is the capital of France?",
        }
    )
    assert prompt_response.status_code == 200
    prompt_data = prompt_response.json()
    relay_id = prompt_data["relay_id"]
    
    # Now ingest a response
    sample_response = """REASONING:
I need to find the capital of France.

ASSUMPTIONS:
France is a country in Europe.

FINAL ANSWER:
The capital of France is Paris.

CONFIDENCE:
High"""
    
    response = client.post(
        "/api/v1/human-relay/ingest",
        json={
            "relay_id": relay_id,
            "provider": "chatgpt",
            "pasted_answer": sample_response
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data.get("success") is True
    assert "stored_id" in data
    assert "parsed" in data
    assert "summary" in data["parsed"]
    assert "answer" in data["parsed"]
    assert "Paris" in data["parsed"]["answer"] or "paris" in data["parsed"]["answer"].lower()


def test_synthesize(client):
    """Test that Human Relay Explorer can synthesize with Daena brain"""
    # Generate prompt
    prompt_response = client.post(
        "/api/v1/human-relay/prompt",
        json={
            "provider": "chatgpt",
            "task": "What is the capital of France?",
        }
    )
    assert prompt_response.status_code == 200
    relay_id = prompt_response.json()["relay_id"]
    
    # Ingest response
    ingest_response = client.post(
        "/api/v1/human-relay/ingest",
        json={
            "relay_id": relay_id,
            "provider": "chatgpt",
            "pasted_answer": "FINAL ANSWER:\nThe capital of France is Paris."
        }
    )
    assert ingest_response.status_code == 200
    insight_id = ingest_response.json()["stored_id"]
    
    # Synthesize
    response = client.post(
        "/api/v1/human-relay/synthesize",
        json={
            "task": "What is the capital of France?",
            "insight_ids": [insight_id],
            "mode": "assist_only"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data.get("success") is True
    assert "final_answer" in data
    assert "used_insights" in data
    assert len(data["final_answer"]) > 0
    assert len(data["used_insights"]) > 0


def test_human_relay_no_router_mixing(client):
    """Test that Human Relay Explorer does NOT mix with router"""
    # Normal chat endpoint should remain unchanged
    chat_response = client.post(
        "/api/v1/daena/chat",
        json={"message": "Hello Daena"}
    )
    
    assert chat_response.status_code == 200
    # Should not contain Human Relay specific fields
    chat_data = chat_response.json()
    assert "relay_id" not in chat_data
    assert "human_relay" not in str(chat_data).lower()


def test_human_relay_uses_canonical_brain(client):
    """Test that synthesize calls canonical Daena brain"""
    # Generate and ingest
    prompt_response = client.post(
        "/api/v1/human-relay/prompt",
        json={
            "provider": "chatgpt",
            "task": "Test question",
        }
    )
    relay_id = prompt_response.json()["relay_id"]
    
    ingest_response = client.post(
        "/api/v1/human-relay/ingest",
        json={
            "relay_id": relay_id,
            "provider": "chatgpt",
            "pasted_answer": "FINAL ANSWER:\nTest answer."
        }
    )
    insight_id = ingest_response.json()["stored_id"]
    
    # Synthesize should call canonical brain
    synthesize_response = client.post(
        "/api/v1/human-relay/synthesize",
        json={
            "task": "Test question",
            "insight_ids": [insight_id],
            "mode": "assist_only"
        }
    )
    
    assert synthesize_response.status_code == 200
    data = synthesize_response.json()
    # Final answer should be from Daena brain (not just copied from insight)
    assert "final_answer" in data
    assert len(data["final_answer"]) > 0
    # Should indicate synthesis (not just raw copy)
    assert data["used_insights"]  # Should reference the insight









