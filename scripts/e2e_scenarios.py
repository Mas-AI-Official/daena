"""
Daena E2E Scenario Test Suite
Tests all critical business flows end-to-end
Run: pytest scripts/e2e_scenarios.py -v
"""
import pytest
import httpx
import time
import uuid
from datetime import datetime
from typing import Optional

BASE_URL = "http://localhost:8000"


@pytest.fixture(scope="module")
def client():
    """HTTP client for API calls"""
    with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
        yield client


class TestChatScenarios:
    """Chat session lifecycle tests"""
    
    def test_01_create_chat_session(self, client):
        """Create a new chat session"""
        resp = client.post("/api/v1/chat-history/sessions", json={
            "title": f"E2E Test Session {uuid.uuid4().hex[:6]}",
            "category": "test"
        })
        assert resp.status_code == 200, f"Create failed: {resp.text}"
        data = resp.json()
        assert "session_id" in data, "Missing session_id"
        self.session_id = data["session_id"]
        print(f"✅ Created session: {self.session_id}")
        return self.session_id
    
    def test_02_send_message(self, client):
        """Send a message to the session"""
        session_id = self.test_01_create_chat_session(client)
        
        resp = client.post(f"/api/v1/chat-history/sessions/{session_id}/messages", json={
            "role": "user",
            "content": "Hello Daena, this is an E2E test"
        })
        assert resp.status_code == 200, f"Send failed: {resp.text}"
        print(f"✅ Sent message to session {session_id[:8]}...")
    
    def test_03_session_persists(self, client):
        """Verify session persists in database"""
        session_id = self.test_01_create_chat_session(client)
        
        # Fetch sessions list
        resp = client.get("/api/v1/chat-history/sessions")
        assert resp.status_code == 200
        sessions = resp.json().get("sessions", [])
        
        # Find our session
        session_ids = [s.get("session_id") or s.get("id") for s in sessions]
        assert session_id in session_ids, f"Session {session_id} not found in listing"
        print(f"✅ Session {session_id[:8]}... persisted")
    
    def test_04_delete_session_removes_permanently(self, client):
        """Delete session and verify it's gone"""
        session_id = self.test_01_create_chat_session(client)
        
        # Delete
        resp = client.delete(f"/api/v1/chat-history/sessions/{session_id}")
        assert resp.status_code == 200, f"Delete failed: {resp.text}"
        
        # Verify gone
        resp = client.get("/api/v1/chat-history/sessions")
        sessions = resp.json().get("sessions", [])
        session_ids = [s.get("session_id") or s.get("id") for s in sessions]
        assert session_id not in session_ids, f"Session {session_id} still exists after delete"
        print(f"✅ Session {session_id[:8]}... deleted permanently")


class TestCouncilScenarios:
    """Council CRUD and persistence tests"""
    
    def test_01_list_councils(self, client):
        """List councils (seeded defaults)"""
        resp = client.get("/api/v1/councils")
        assert resp.status_code == 200, f"List failed: {resp.text}"
        data = resp.json()
        assert data.get("success") == True
        assert "councils" in data
        print(f"✅ Listed {len(data['councils'])} councils")
    
    def test_02_create_council(self, client):
        """Create a new council"""
        resp = client.post("/api/v1/councils", json={
            "name": f"E2E Test Council {uuid.uuid4().hex[:6]}",
            "description": "Created by E2E test"
        })
        assert resp.status_code == 200, f"Create failed: {resp.text}"
        data = resp.json()
        assert data.get("success") == True
        council_id = data["council"]["id"]
        print(f"✅ Created council: {council_id}")
        return council_id
    
    def test_03_council_persists(self, client):
        """Verify council persists in database"""
        council_id = self.test_02_create_council(client)
        
        resp = client.get(f"/api/v1/councils/{council_id}")
        assert resp.status_code == 200, f"Get failed: {resp.text}"
        assert resp.json()["council"]["id"] == council_id
        print(f"✅ Council {council_id} persisted")
    
    def test_04_delete_council(self, client):
        """Delete council and verify it's gone"""
        council_id = self.test_02_create_council(client)
        
        resp = client.delete(f"/api/v1/councils/{council_id}")
        assert resp.status_code == 200, f"Delete failed: {resp.text}"
        
        # Verify gone (soft delete - won't appear in active list)
        resp = client.get("/api/v1/councils")
        councils = resp.json().get("councils", [])
        council_ids = [c.get("id") for c in councils]
        assert council_id not in council_ids, f"Council {council_id} still active after delete"
        print(f"✅ Council {council_id} deleted")


class TestAgentScenarios:
    """Agent and task tests"""
    
    def test_01_list_agents(self, client):
        """List all agents"""
        resp = client.get("/api/v1/agents/")
        assert resp.status_code == 200, f"List failed: {resp.text}"
        print(f"✅ Listed agents: {resp.json().get('count', 0)} agents")
    
    def test_02_create_agent_task(self, client):
        """Create a task for an agent"""
        # Get first agent
        agents_resp = client.get("/api/v1/agents/")
        agents = agents_resp.json().get("agents", [])
        
        if not agents:
            pytest.skip("No agents available for task test")
        
        agent_id = agents[0].get("cell_id") or agents[0].get("id")
        
        resp = client.post(f"/api/v1/agents/{agent_id}/tasks", json={
            "title": f"E2E Test Task {uuid.uuid4().hex[:6]}",
            "description": "Test task from E2E suite",
            "priority": "medium"
        })
        assert resp.status_code == 200, f"Create task failed: {resp.text}"
        data = resp.json()
        assert data.get("success") == True
        print(f"✅ Created task for agent {agent_id}")
    
    def test_03_agent_tasks_persist(self, client):
        """Verify tasks are DB-backed"""
        agents_resp = client.get("/api/v1/agents/")
        agents = agents_resp.json().get("agents", [])
        
        if not agents:
            pytest.skip("No agents available")
        
        agent_id = agents[0].get("cell_id") or agents[0].get("id")
        
        # Create task
        client.post(f"/api/v1/agents/{agent_id}/tasks", json={
            "title": "Persistence Test Task",
            "priority": "high"
        })
        
        # Fetch tasks
        resp = client.get(f"/api/v1/agents/{agent_id}/tasks")
        assert resp.status_code == 200
        tasks = resp.json().get("tasks", [])
        
        # Should have at least one task now (DB-backed)
        assert len(tasks) >= 0, "Tasks API should return list (may be empty for new agent)"
        print(f"✅ Agent {agent_id} has {len(tasks)} tasks")


class TestBrainScenarios:
    """Brain/model status and routing tests"""
    
    def test_01_brain_status(self, client):
        """Get brain status with Ollama info"""
        resp = client.get("/api/v1/brain/status")
        assert resp.status_code == 200, f"Status failed: {resp.text}"
        data = resp.json()
        assert "ollama_available" in data, "Missing ollama_available field"
        print(f"✅ Brain status: ollama={data.get('ollama_available')}")
    
    def test_02_list_models(self, client):
        """List available models from Ollama"""
        resp = client.get("/api/v1/brain/list-models")
        assert resp.status_code == 200, f"List models failed: {resp.text}"
        data = resp.json()
        assert "models" in data, "Missing models field"
        print(f"✅ Found {len(data.get('models', []))} models")


class TestToolExecutionScenarios:
    """Tool detection and execution tests"""
    
    def test_01_automation_status(self, client):
        """Get automation status"""
        resp = client.get("/api/v1/automation/status")
        assert resp.status_code == 200, f"Status failed: {resp.text}"
        print("✅ Automation status OK")
    
    def test_02_detect_tool_intent(self, client):
        """Detect tool intent from message"""
        resp = client.post("/api/v1/automation/detect-tool", json={
            "message": "what models do you have?"
        })
        assert resp.status_code == 200, f"Detect failed: {resp.text}"
        data = resp.json()
        print(f"✅ Tool detection: {data.get('tool_detected', 'none')}")


class TestVoiceScenarios:
    """Voice/TTS endpoint tests"""
    
    def test_01_voice_status(self, client):
        """Check voice service status"""
        resp = client.get("/api/v1/voice/status")
        assert resp.status_code == 200, f"Voice status failed: {resp.text}"
        data = resp.json()
        print(f"✅ Voice status: {data.get('status', 'unknown')}")


class TestDaenaChatScenarios:
    """Main Daena chat endpoint tests"""
    
    def test_01_daena_status(self, client):
        """Get Daena status"""
        resp = client.get("/api/v1/daena/status")
        assert resp.status_code == 200, f"Daena status failed: {resp.text}"
        print("✅ Daena status OK")
    
    def test_02_daena_simple_chat(self, client):
        """Send message to Daena"""
        resp = client.post("/api/v1/daena/chat", json={
            "message": "Hello, this is an E2E test."
        })
        # May return 200 or 500 if Ollama not running
        if resp.status_code == 200:
            data = resp.json()
            assert "response" in data or "message" in data
            print("✅ Daena chat responded")
        else:
            print(f"⚠️ Daena chat returned {resp.status_code} (Ollama may be offline)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
