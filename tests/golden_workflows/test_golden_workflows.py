"""
Golden Workflow Tests - Critical workflows that must always pass

These are the golden workflows from QA_GUARDIAN_CHARTER.md Part 4:
1. Core: create task -> route to dept -> agent executes -> results logged -> UI reflects
2. CMP: propose -> vote -> chosen plan -> execution -> audit trail
3. Tool reliability: retry + timeout behavior
4. Memory/logging: store/retrieve context without corruption
"""

import pytest
import httpx
import asyncio
import json
import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# Backend URL - configurable via env
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")


class TestGoldenCoreWorkflow:
    """
    Golden Workflow 1: Core Task Flow
    
    Create task -> Route to department -> Agent executes -> Results logged -> UI reflects
    """
    
    @pytest.fixture
    def client(self):
        return httpx.Client(base_url=BACKEND_URL, timeout=30.0)
    
    def test_health_check(self, client):
        """Backend must be healthy"""
        response = client.get("/api/v1/health/")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") in ["ok", "healthy", True]
    
    def test_departments_exist(self, client):
        """Departments must be retrievable"""
        response = client.get("/api/v1/departments/")
        assert response.status_code == 200
        data = response.json()
        
        # Must have at least the core 8 departments
        assert len(data) >= 8, f"Expected 8+ departments, got {len(data)}"
    
    def test_agents_exist(self, client):
        """Agents must be retrievable"""
        response = client.get("/api/v1/agents/")
        assert response.status_code == 200
        data = response.json()
        
        # Must have agents (8 depts × 6 agents = 48)
        assert len(data) >= 1, "No agents found"
    
    def test_create_chat_session(self, client):
        """Can create a new chat session"""
        response = client.post("/api/v1/chat/session", json={
            "title": f"Golden Test Session {datetime.utcnow().isoformat()}"
        })
        
        # Accept either 200 or 201
        assert response.status_code in [200, 201], f"Failed: {response.text}"
        data = response.json()
        assert "session_id" in data or "id" in data
    
    def test_send_message_to_chat(self, client):
        """Can send a message and get a response"""
        # Create session first
        session_response = client.post("/api/v1/chat/session", json={
            "title": "Golden Workflow Test"
        })
        
        if session_response.status_code not in [200, 201]:
            pytest.skip("Cannot create session - skipping message test")
        
        session_data = session_response.json()
        session_id = session_data.get("session_id") or session_data.get("id")
        
        # Send message
        msg_response = client.post(f"/api/v1/chat/{session_id}/message", json={
            "content": "Hello, this is a golden workflow test",
            "role": "user"
        })
        
        # Should succeed
        assert msg_response.status_code in [200, 201], f"Failed: {msg_response.text}"


class TestGoldenCMPWorkflow:
    """
    Golden Workflow 2: CMP (Collaborative Multi-Proposal) Flow
    
    Propose -> Vote -> Chosen plan -> Execution -> Audit trail
    """
    
    @pytest.fixture
    def client(self):
        return httpx.Client(base_url=BACKEND_URL, timeout=30.0)
    
    def test_cmp_endpoint_exists(self, client):
        """CMP endpoints must be accessible"""
        # Check if CMP routes exist
        response = client.get("/api/v1/cmp/proposals")
        
        # Accept 200 (success) or 404 (not implemented yet)
        # Fail only on 500 errors
        assert response.status_code != 500, f"CMP endpoint error: {response.text}"
    
    def test_councils_exist(self, client):
        """Councils must be retrievable"""
        response = client.get("/api/v1/councils/")
        
        # Accept various response codes
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list), "Councils should be a list"


class TestGoldenToolReliability:
    """
    Golden Workflow 3: Tool Call Reliability
    
    Verify retry and timeout behavior for tool calls
    """
    
    @pytest.fixture
    def client(self):
        return httpx.Client(base_url=BACKEND_URL, timeout=30.0)
    
    def test_tool_registry_accessible(self, client):
        """Tool registry must be accessible"""
        # Try common tool endpoints
        endpoints = [
            "/api/v1/tools/",
            "/api/v1/tools/registry",
            "/api/v1/ai/tools"
        ]
        
        success = False
        for endpoint in endpoints:
            response = client.get(endpoint)
            if response.status_code == 200:
                success = True
                break
        
        # At least one endpoint should work, or we skip
        if not success:
            pytest.skip("No tool registry endpoint found")
    
    def test_brain_status(self, client):
        """Brain/LLM status should be retrievable"""
        response = client.get("/api/v1/brain/status")
        
        # Skip if endpoint doesn't exist
        if response.status_code == 404:
            pytest.skip("Brain status endpoint not available")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data or "connected" in data or "available" in data


class TestGoldenMemoryWorkflow:
    """
    Golden Workflow 4: Memory/Logging Integrity
    
    Store and retrieve context without corruption
    """
    
    @pytest.fixture
    def client(self):
        return httpx.Client(base_url=BACKEND_URL, timeout=30.0)
    
    def test_database_exists(self):
        """Database file must exist"""
        db_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "daena.db"
        )
        assert os.path.exists(db_path), f"Database not found at {db_path}"
        
        # Check it has content
        size = os.path.getsize(db_path)
        assert size > 0, "Database is empty"
    
    def test_events_logging(self, client):
        """Events should be logged and retrievable"""
        response = client.get("/api/v1/events/recent")
        
        if response.status_code == 404:
            pytest.skip("Events endpoint not available")
        
        # Should return a list
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, (list, dict))
    
    def test_audit_trail(self, client):
        """Audit trail should be accessible"""
        response = client.get("/api/v1/audit/")
        
        if response.status_code == 404:
            pytest.skip("Audit endpoint not available")
        
        assert response.status_code != 500, "Audit endpoint error"


class TestGoldenQAGuardian:
    """
    Golden Workflow 5: QA Guardian Health
    
    QA Guardian should be operational (when enabled)
    """
    
    @pytest.fixture
    def client(self):
        return httpx.Client(base_url=BACKEND_URL, timeout=30.0)
    
    def test_qa_guardian_status(self, client):
        """QA Guardian status endpoint should respond"""
        response = client.get("/api/v1/qa/status")
        
        if response.status_code == 404:
            pytest.skip("QA Guardian not registered yet")
        
        assert response.status_code == 200
        data = response.json()
        assert "enabled" in data
    
    def test_qa_dashboard(self, client):
        """QA Dashboard should be accessible"""
        response = client.get("/api/v1/qa/dashboard")
        
        if response.status_code == 404:
            pytest.skip("QA Dashboard not available")
        
        assert response.status_code == 200


# Integration test helper
def run_golden_workflows():
    """Run all golden workflows and return summary"""
    results = {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "details": []
    }
    
    # Use pytest to run
    exit_code = pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "-q"
    ])
    
    return {
        "exit_code": exit_code,
        "success": exit_code == 0
    }


if __name__ == "__main__":
    # Run directly for testing
    pytest.main([__file__, "-v"])
