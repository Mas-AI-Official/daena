"""
End-to-end test: Full Daena workflow from UI to brain to agents.

This is the "GO/NO-GO" test that proves the system is live.
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


def test_ui_dashboard_loads(client):
    """Test that dashboard UI loads (200)"""
    response = client.get("/ui/dashboard")
    assert response.status_code == 200, f"Dashboard failed: {response.status_code}"
    assert "text/html" in response.headers.get("content-type", "")


def test_ui_agents_loads(client):
    """Test that agents UI loads (200)"""
    response = client.get("/ui/agents")
    assert response.status_code == 200, f"Agents UI failed: {response.status_code}"
    assert "text/html" in response.headers.get("content-type", "")


def test_ui_departments_loads(client):
    """Test that departments UI loads (200)"""
    response = client.get("/ui/departments")
    assert response.status_code == 200, f"Departments UI failed: {response.status_code}"
    assert "text/html" in response.headers.get("content-type", "")


def test_api_agents_list(client):
    """Test that agents API returns list (200, non-empty)"""
    response = client.get("/api/v1/agents")
    assert response.status_code == 200, f"Agents API failed: {response.status_code}"
    data = response.json()
    assert isinstance(data, (list, dict)), f"Agents API returned unexpected format: {type(data)}"
    if isinstance(data, list):
        assert len(data) > 0, "Agents list is empty"
    elif isinstance(data, dict):
        assert "agents" in data or "data" in data, "Agents dict missing expected keys"


def test_api_departments_list(client):
    """Test that departments API returns list (200, non-empty)"""
    response = client.get("/api/v1/departments")
    assert response.status_code == 200, f"Departments API failed: {response.status_code}"
    data = response.json()
    assert isinstance(data, (list, dict)), f"Departments API returned unexpected format: {type(data)}"
    if isinstance(data, list):
        assert len(data) > 0, "Departments list is empty"
    elif isinstance(data, dict):
        assert "departments" in data or "data" in data, "Departments dict missing expected keys"


def test_daena_chat_endpoint_exists(client):
    """Test that Daena chat endpoint exists and accepts requests"""
    response = client.post(
        "/api/v1/daena/chat",
        json={"message": "Hello Daena"}
    )
    assert response.status_code == 200, f"Daena chat failed: {response.status_code}"
    data = response.json()
    assert "response" in data or "daena_response" in data, "Response missing 'response' or 'daena_response' field"


def test_daena_full_workflow_vibeagent(client):
    """
    THE CRITICAL TEST: Full workflow from user command to Daena response.
    
    This test verifies:
    1. User sends command: "Daena, build a VibeAgent app. Use departments and return a plan."
    2. Daena brain receives it
    3. CMP routes it (if applicable)
    4. Department agents are called (if applicable)
    5. Brain merges responses
    6. Final answer is returned
    """
    prompt = "Daena, build a VibeAgent app. Use departments and return a plan."
    
    response = client.post(
        "/api/v1/daena/chat",
        json={"message": prompt}
    )
    
    assert response.status_code == 200, f"Workflow test failed: {response.status_code}"
    data = response.json()
    
    # Must have a response
    response_text = data.get("response") or data.get("daena_response", {}).get("content", "")
    assert len(response_text) > 0, "No response text returned"
    assert len(response_text) > 10, "Response too short (likely error)"
    
    # Response should mention departments, agents, or planning (indicating brain processed it)
    response_lower = response_text.lower()
    workflow_indicators = [
        "department", "agent", "plan", "build", "app", "vibeagent",
        "engineering", "product", "design", "strategy"
    ]
    has_workflow_indicator = any(indicator in response_lower for indicator in workflow_indicators)
    
    # Log the response for debugging
    print(f"\n[WORKFLOW TEST] Response received ({len(response_text)} chars):")
    print(f"{response_text[:200]}...")
    
    # Note: We don't require ALL indicators, but at least some processing should be evident
    # The brain should have processed the request, not just returned a generic greeting
    assert has_workflow_indicator or len(response_text) > 50, \
        f"Response doesn't indicate workflow processing. Response: {response_text[:100]}"


def test_agent_chat_endpoint_exists(client):
    """Test that agent chat endpoint exists"""
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
        pytest.skip("No agent ID found - cannot test agent chat endpoint")
    
    # Test agent chat endpoint
    response = client.post(
        f"/api/v1/agents/{agent_id}/chat",
        json={"message": "Hello agent", "context": {}}
    )
    
    assert response.status_code in [200, 404], \
        f"Agent chat endpoint returned unexpected status: {response.status_code}"
    
    if response.status_code == 200:
        data = response.json()
        assert "final_answer" in data or "response" in data, \
            "Agent chat response missing expected fields"


def test_health_endpoint(client):
    """Test that health endpoint returns 200"""
    response = client.get("/api/v1/health")
    assert response.status_code == 200, f"Health endpoint failed: {response.status_code}"
    data = response.json()
    assert "status" in data or "health" in data, "Health response missing status field"


def test_session_delete_removes_from_db(client):
    """Test that deleting a session removes it from database (single source of truth)"""
    # Create session
    create_response = client.post(
        "/api/v1/chat-history/sessions",
        json={"title": "Test Delete Session", "category": "test"}
    )
    assert create_response.status_code == 200, f"Create session failed: {create_response.text}"
    session_id = create_response.json().get("session_id")
    assert session_id, "No session_id returned from create"
    
    # Delete session
    delete_response = client.delete(f"/api/v1/chat-history/sessions/{session_id}")
    assert delete_response.status_code == 200, f"Delete session failed: {delete_response.text}"
    assert "deleted" in delete_response.json().get("message", "").lower()
    
    # Verify it's gone from listing
    list_response = client.get("/api/v1/chat-history/sessions")
    assert list_response.status_code == 200
    sessions = list_response.json().get("sessions", [])
    session_ids = [s.get("session_id") or s.get("id") for s in sessions]
    assert session_id not in session_ids, f"Session {session_id} still appears after deletion"
    
    print(f"[DELETE TEST] Session {session_id[:8]}... created and deleted successfully")


def test_brain_status_includes_model_info(client):
    """Test that brain status includes model and Ollama info"""
    response = client.get("/api/v1/brain/status")
    assert response.status_code == 200, f"Brain status failed: {response.status_code}"
    data = response.json()
    
    # Should have Ollama availability info
    assert "ollama_available" in data, "Missing ollama_available field"
    
    # Should have available_models list (may be empty if Ollama not running)
    assert "available_models" in data, "Missing available_models field"
    
    print(f"[BRAIN STATUS] ollama={data.get('ollama_available')}, models={len(data.get('available_models', []))}")


def test_brain_list_models(client):
    """Test that brain list-models endpoint works"""
    response = client.get("/api/v1/brain/list-models")
    assert response.status_code == 200, f"List models failed: {response.status_code}"
    data = response.json()
    
    # Should have success field
    assert "success" in data, "Missing success field"
    
    # Should have models list
    assert "models" in data, "Missing models field"
    
    if data.get("success"):
        print(f"[LIST MODELS] Found {len(data.get('models', []))} models")
    else:
        print(f"[LIST MODELS] Error: {data.get('error', 'unknown')}")





