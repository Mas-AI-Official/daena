"""
End-to-end GO/NO-GO test for Daena system.

This test verifies the system is "live" and ready for use.
All tests must pass for the system to be considered "go-live ready".
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_dashboard_pages_return_200():
    """Test that dashboard pages return 200"""
    pages = [
        "/ui/dashboard",
        "/ui/agents",
        "/ui/departments",
        "/ui/health",
    ]
    
    for page in pages:
        response = client.get(page)
        assert response.status_code == 200, f"Page {page} returned {response.status_code} instead of 200"


def test_agent_list_endpoint_returns_200():
    """Test that agent list endpoint returns 200"""
    response = client.get("/api/v1/agents")
    assert response.status_code == 200, f"Agent list returned {response.status_code}"
    
    data = response.json()
    # Should return agents (may be empty list, but should be valid JSON)
    assert isinstance(data, (dict, list)), "Agent list should return dict or list"


def test_department_list_endpoint_returns_200():
    """Test that department list endpoint returns 200"""
    response = client.get("/api/v1/departments")
    assert response.status_code == 200, f"Department list returned {response.status_code}"
    
    data = response.json()
    # Should return departments (may be empty list, but should be valid JSON)
    assert isinstance(data, (dict, list)), "Department list should return dict or list"


def test_daena_chat_returns_real_response():
    """Test that POST /api/v1/daena/chat returns a real response (not stub)"""
    response = client.post(
        "/api/v1/daena/chat",
        json={"message": "Hello Daena", "user_id": "test_user"}
    )
    
    assert response.status_code == 200, f"Daena chat returned {response.status_code}"
    data = response.json()
    
    # Must have a response field
    assert "response" in data or "content" in data, "Response missing 'response' or 'content' field"
    
    response_text = data.get("response") or data.get("content", "")
    assert len(response_text) > 0, "Response text is empty"
    assert len(response_text) > 10, "Response too short (likely stub/error)"


def test_assign_task_to_agent_works():
    """Test that assign task to agent endpoint works and returns real routed result"""
    # First, get an agent ID
    agents_response = client.get("/api/v1/agents")
    assert agents_response.status_code == 200
    
    agents_data = agents_response.json()
    
    # Extract agent ID (handle both list and dict formats)
    agent_id = None
    if isinstance(agents_data, list) and len(agents_data) > 0:
        agent_id = agents_data[0].get("id") or agents_data[0].get("agent_id")
    elif isinstance(agents_data, dict):
        agents_list = agents_data.get("agents") or agents_data.get("data", [])
        if isinstance(agents_list, list) and len(agents_list) > 0:
            agent_id = agents_list[0].get("id") or agents_list[0].get("agent_id")
    
    if not agent_id:
        pytest.skip("No agents available for testing")
    
    # Assign task to agent
    response = client.post(
        f"/api/v1/agents/{agent_id}/assign_task",
        json={
            "task": "Test task assignment",
            "priority": "medium",
            "context": {}
        }
    )
    
    assert response.status_code == 200, f"Task assignment returned {response.status_code}"
    data = response.json()
    
    # Must have status and some indication of routing
    assert "status" in data, "Response missing 'status' field"
    assert data.get("status") == "ok", f"Task assignment status is {data.get('status')}, expected 'ok'"
    
    # Should have final_answer or response indicating brain processing
    final_answer = data.get("final_answer") or data.get("response", "")
    assert len(final_answer) > 0, "No response from task assignment"


def test_brain_status_endpoint():
    """Test that brain status endpoint returns installed + active model"""
    response = client.get("/api/v1/brain/status")
    assert response.status_code == 200, f"Brain status returned {response.status_code}"
    
    data = response.json()
    assert "status" in data, "Brain status missing 'status' field"
    assert data.get("status") == "operational", "Brain status should be 'operational'"
    assert "shared_brain" in data, "Brain status missing 'shared_brain' field"
    assert "model" in data, "Brain status missing 'model' field"


def test_brain_query_endpoint():
    """Test that brain query endpoint works"""
    response = client.post(
        "/api/v1/brain/query",
        json={
            "query": "What is the company structure?",
            "context": {}
        }
    )
    
    assert response.status_code == 200, f"Brain query returned {response.status_code}"
    data = response.json()
    
    assert "response" in data, "Brain query missing 'response' field"
    assert len(data.get("response", "")) > 0, "Brain query response is empty"


def test_brain_propose_experience():
    """Test that agents can propose experiences"""
    response = client.post(
        "/api/v1/brain/propose_experience",
        json={
            "experience": {
                "type": "best_practice",
                "content": "Test experience for governance pipeline",
                "source": "test_agent"
            },
            "reason": "Testing governance pipeline",
            "source_agent_id": "test_agent_123",
            "department": "engineering"
        }
    )
    
    assert response.status_code == 200, f"Propose experience returned {response.status_code}"
    data = response.json()
    
    assert "status" in data, "Propose experience missing 'status' field"
    assert data.get("status") == "proposed", "Proposal status should be 'proposed'"
    assert "proposal_id" in data, "Proposal missing 'proposal_id' field"


def test_brain_queue_endpoint():
    """Test that governance queue endpoint works (requires VP access)"""
    response = client.get("/api/v1/brain/queue")
    assert response.status_code == 200, f"Brain queue returned {response.status_code}"
    
    data = response.json()
    assert "queue" in data, "Brain queue missing 'queue' field"
    assert "count" in data, "Brain queue missing 'count' field"
    assert isinstance(data.get("queue"), list), "Queue should be a list"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])









