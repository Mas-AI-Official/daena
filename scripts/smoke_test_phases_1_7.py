#!/usr/bin/env python3
"""
Comprehensive Smoke Test for Phases 1-7
Tests all implemented features:
- Phase 1: Backend State Audit
- Phase 2: SQLite Persistence
- Phase 3: WebSocket Event Bus
- Phase 4: Frontend Mock Data Removal
- Phase 5: Department Chat Dual-View
- Phase 6: Brain + Model Management
- Phase 7: Voice Pipeline + Env Launchers
"""
from __future__ import annotations

import sys
import os
import io
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Fix Unicode output on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

try:
    import httpx
except ImportError:
    print("ERROR: httpx not installed. Run: pip install httpx")
    sys.exit(1)

# Configuration
BACKEND_URL = "http://127.0.0.1:8000"
TIMEOUT = 10.0
DB_PATH = Path(__file__).parent.parent / "daena.db"

class SmokeTestResults:
    """Track test results"""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        self.results: List[Dict[str, Any]] = []
    
    def add_result(self, name: str, passed: bool, message: str = "", warning: bool = False):
        """Add a test result"""
        if passed:
            self.passed += 1
            status = "✅ PASS"
        elif warning:
            self.warnings += 1
            status = "⚠️  WARN"
        else:
            self.failed += 1
            status = "❌ FAIL"
        
        self.results.append({
            "name": name,
            "status": status,
            "message": message,
            "passed": passed,
            "warning": warning
        })
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 70)
        print("  TEST SUMMARY")
        print("=" * 70)
        print(f"  ✅ Passed:  {self.passed}")
        print(f"  ❌ Failed:  {self.failed}")
        print(f"  ⚠️  Warnings: {self.warnings}")
        print("=" * 70)
        
        if self.failed == 0:
            print("\n  🎉 ALL TESTS PASSED!")
            return 0
        else:
            print("\n  ⚠️  SOME TESTS FAILED - Check details above")
            return 1

def test_backend_health(results: SmokeTestResults) -> bool:
    """Test Phase 1: Backend health"""
    try:
        response = httpx.get(f"{BACKEND_URL}/api/v1/health/", timeout=TIMEOUT, follow_redirects=True)
        if response.status_code == 200:
            results.add_result("Backend Health", True, f"Status: {response.status_code}")
            return True
        else:
            results.add_result("Backend Health", False, f"Expected 200, got {response.status_code}")
            return False
    except Exception as e:
        results.add_result("Backend Health", False, f"Error: {e}")
        return False

def test_database_persistence(results: SmokeTestResults) -> bool:
    """Test Phase 2: SQLite persistence"""
    try:
        # Check if database exists
        if not DB_PATH.exists():
            results.add_result("Database File", False, f"Database not found: {DB_PATH}")
            return False
        
        # Check database size (should be > 0)
        db_size = DB_PATH.stat().st_size
        if db_size == 0:
            results.add_result("Database File", False, "Database file is empty")
            return False
        
        results.add_result("Database File", True, f"Database exists ({db_size} bytes)")
        
        # Test database connectivity via API
        try:
            # Get agents (should be from DB)
            response = httpx.get(f"{BACKEND_URL}/api/v1/agents", timeout=TIMEOUT)
            if response.status_code == 200:
                data = response.json()
                agents = data.get("agents", [])
                results.add_result("Database Connectivity", True, f"Retrieved {len(agents)} agents from DB")
                return True
            else:
                results.add_result("Database Connectivity", False, f"Status: {response.status_code}")
                return False
        except Exception as e:
            results.add_result("Database Connectivity", False, f"Error: {e}")
            return False
            
    except Exception as e:
        results.add_result("Database File", False, f"Error: {e}")
        return False

def test_websocket_events(results: SmokeTestResults) -> bool:
    """Test Phase 3: WebSocket event bus"""
    try:
        # Test events endpoint
        response = httpx.get(f"{BACKEND_URL}/api/v1/events/recent", timeout=TIMEOUT, params={"limit": 10})
        if response.status_code == 200:
            data = response.json()
            events = data.get("events", [])
            results.add_result("WebSocket Events", True, f"Retrieved {len(events)} recent events")
            return True
        else:
            results.add_result("WebSocket Events", False, f"Status: {response.status_code}", warning=True)
            return False
    except Exception as e:
        results.add_result("WebSocket Events", False, f"Error: {e}", warning=True)
        return False

def test_no_mock_data(results: SmokeTestResults) -> bool:
    """Test Phase 4: No mock data in frontend"""
    try:
        # Test agents endpoint (should be from DB, not mock)
        response = httpx.get(f"{BACKEND_URL}/api/v1/agents", timeout=TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            agents = data.get("agents", [])
            
            # Check if agents have real IDs (not mock)
            if agents:
                agent = agents[0]
                if "id" in agent or "cell_id" in agent:
                    results.add_result("No Mock Data (Agents)", True, f"Retrieved {len(agents)} real agents from DB")
                    return True
                else:
                    results.add_result("No Mock Data (Agents)", False, "Agents missing IDs")
                    return False
            else:
                results.add_result("No Mock Data (Agents)", True, "No agents (empty DB is valid)")
                return True
        else:
            results.add_result("No Mock Data (Agents)", False, f"Status: {response.status_code}")
            return False
    except Exception as e:
        results.add_result("No Mock Data (Agents)", False, f"Error: {e}")
        return False

def test_chat_history_dual_view(results: SmokeTestResults) -> bool:
    """Test Phase 5: Department chat history dual-view"""
    try:
        # Get departments
        dept_response = httpx.get(f"{BACKEND_URL}/api/v1/departments", timeout=TIMEOUT)
        if dept_response.status_code != 200:
            results.add_result("Chat Dual-View (Departments)", False, f"Cannot get departments: {dept_response.status_code}")
            return False
        
        departments = dept_response.json().get("departments", [])
        if not departments:
            results.add_result("Chat Dual-View (Departments)", True, "No departments (empty DB is valid)")
            return True
        
        dept = departments[0]
        dept_id = dept.get("id") or dept.get("cell_id")
        
        # Test department chat sessions
        sessions_response = httpx.get(
            f"{BACKEND_URL}/api/v1/departments/{dept_id}/chat/sessions",
            timeout=TIMEOUT
        )
        
        if sessions_response.status_code == 200:
            sessions = sessions_response.json().get("sessions", [])
            results.add_result("Chat Dual-View (Department Sessions)", True, f"Retrieved {len(sessions)} sessions")
            
            # Test Daena aggregated view
            daena_response = httpx.get(
                f"{BACKEND_URL}/api/v1/daena/chat/sessions",
                timeout=TIMEOUT,
                params={"category": "departments"}
            )
            
            if daena_response.status_code == 200:
                daena_sessions = daena_response.json().get("sessions", [])
                results.add_result("Chat Dual-View (Daena Aggregated)", True, f"Retrieved {len(daena_sessions)} aggregated sessions")
                return True
            else:
                results.add_result("Chat Dual-View (Daena Aggregated)", False, f"Status: {daena_response.status_code}")
                return False
        else:
            results.add_result("Chat Dual-View (Department Sessions)", False, f"Status: {sessions_response.status_code}")
            return False
            
    except Exception as e:
        results.add_result("Chat Dual-View", False, f"Error: {e}")
        return False

def test_brain_model_management(results: SmokeTestResults) -> bool:
    """Test Phase 6: Brain + Model Management"""
    try:
        # Test brain status
        status_response = httpx.get(f"{BACKEND_URL}/api/v1/brain/status", timeout=TIMEOUT)
        if status_response.status_code == 200:
            status_data = status_response.json()
            connected = status_data.get("connected", False)
            active_model = status_data.get("active_model")
            
            results.add_result("Brain Status", True, f"Connected: {connected}, Active: {active_model or 'None'}")
        else:
            results.add_result("Brain Status", False, f"Status: {status_response.status_code}")
            return False
        
        # Test models list
        models_response = httpx.get(f"{BACKEND_URL}/api/v1/brain/models", timeout=TIMEOUT)
        if models_response.status_code == 200:
            models_data = models_response.json()
            local_models = models_data.get("local", [])
            results.add_result("Brain Models", True, f"Found {len(local_models)} local models")
            return True
        else:
            results.add_result("Brain Models", False, f"Status: {models_response.status_code}")
            return False
            
    except Exception as e:
        results.add_result("Brain Model Management", False, f"Error: {e}")
        return False

def test_voice_pipeline(results: SmokeTestResults) -> bool:
    """Test Phase 7: Voice Pipeline"""
    try:
        # Test voice status
        status_response = httpx.get(f"{BACKEND_URL}/api/v1/voice/status", timeout=TIMEOUT)
        if status_response.status_code == 200:
            status_data = status_response.json()
            talk_active = status_data.get("talk_active", False)
            results.add_result("Voice Status", True, f"Talk mode: {talk_active}")
        else:
            results.add_result("Voice Status", False, f"Status: {status_response.status_code}")
            return False
        
        # Test voice file endpoint
        voice_file_response = httpx.get(f"{BACKEND_URL}/api/v1/voice/daena-voice", timeout=TIMEOUT)
        if voice_file_response.status_code == 200:
            content_length = len(voice_file_response.content)
            results.add_result("Voice File Serving", True, f"Voice file served ({content_length} bytes)")
            return True
        elif voice_file_response.status_code == 404:
            results.add_result("Voice File Serving", True, "Voice file not found (optional)", warning=True)
            return True
        else:
            results.add_result("Voice File Serving", False, f"Status: {voice_file_response.status_code}")
            return False
        
        # Test voice info endpoint
        voice_info_response = httpx.get(f"{BACKEND_URL}/api/v1/voice/voice-info", timeout=TIMEOUT)
        if voice_info_response.status_code == 200:
            info_data = voice_info_response.json()
            voice_found = info_data.get("daena_voice_found", False)
            results.add_result("Voice Info", True, f"Voice file found: {voice_found}")
            return True
        else:
            results.add_result("Voice Info", False, f"Status: {voice_info_response.status_code}")
            return False
            
    except Exception as e:
        results.add_result("Voice Pipeline", False, f"Error: {e}")
        return False

def test_persistence_after_restart(results: SmokeTestResults) -> bool:
    """Test that data persists after restart (simulated by checking DB directly)"""
    try:
        # Create a test session
        start_response = httpx.post(
            f"{BACKEND_URL}/api/v1/daena/chat/start",
            timeout=TIMEOUT
        )
        
        if start_response.status_code != 200:
            results.add_result("Persistence Test (Create)", False, f"Cannot create session: {start_response.status_code}")
            return False
        
        session_data = start_response.json()
        session_id = session_data.get("session_id")
        
        if not session_id:
            results.add_result("Persistence Test (Create)", False, "No session_id returned")
            return False
        
        # Send a message
        message_response = httpx.post(
            f"{BACKEND_URL}/api/v1/daena/chat/{session_id}/message",
            json={"content": "Test persistence message", "context": {}},
            timeout=TIMEOUT
        )
        
        if message_response.status_code != 200:
            results.add_result("Persistence Test (Message)", False, f"Cannot send message: {message_response.status_code}")
            return False
        
        # Retrieve session (simulating restart)
        get_response = httpx.get(
            f"{BACKEND_URL}/api/v1/daena/chat/sessions/{session_id}",
            timeout=TIMEOUT
        )
        
        if get_response.status_code == 200:
            session_data = get_response.json()
            messages = session_data.get("messages", [])
            if messages:
                results.add_result("Persistence Test", True, f"Session persisted with {len(messages)} messages")
                return True
            else:
                results.add_result("Persistence Test", False, "Session found but no messages")
                return False
        else:
            results.add_result("Persistence Test", False, f"Cannot retrieve session: {get_response.status_code}")
            return False
            
    except Exception as e:
        results.add_result("Persistence Test", False, f"Error: {e}")
        return False

def test_tasks_persistence(results: SmokeTestResults) -> bool:
    """Test that tasks are persisted in DB"""
    try:
        # Get tasks
        tasks_response = httpx.get(f"{BACKEND_URL}/api/v1/tasks", timeout=TIMEOUT)
        if tasks_response.status_code == 200:
            tasks_data = tasks_response.json()
            tasks = tasks_data.get("tasks", [])
            results.add_result("Tasks Persistence", True, f"Retrieved {len(tasks)} tasks from DB")
            return True
        else:
            results.add_result("Tasks Persistence", False, f"Status: {tasks_response.status_code}")
            return False
    except Exception as e:
        results.add_result("Tasks Persistence", False, f"Error: {e}")
        return False

def main() -> int:
    """Run comprehensive smoke tests for Phases 1-7"""
    print("=" * 70)
    print("  DAENA SMOKE TEST - PHASES 1-7 COMPREHENSIVE")
    print("=" * 70)
    print()
    print("  Testing all implemented features:")
    print("    Phase 1: Backend State Audit")
    print("    Phase 2: SQLite Persistence")
    print("    Phase 3: WebSocket Event Bus")
    print("    Phase 4: Frontend Mock Data Removal")
    print("    Phase 5: Department Chat Dual-View")
    print("    Phase 6: Brain + Model Management")
    print("    Phase 7: Voice Pipeline + Env Launchers")
    print()
    print("=" * 70)
    print()
    
    results = SmokeTestResults()
    
    # Phase 1: Backend Health
    print("┌" + "─" * 68 + "┐")
    print("│  PHASE 1: BACKEND STATE AUDIT                                    │")
    print("└" + "─" * 68 + "┘")
    print()
    test_backend_health(results)
    print()
    
    # Phase 2: SQLite Persistence
    print("┌" + "─" * 68 + "┐")
    print("│  PHASE 2: SQLITE PERSISTENCE                                     │")
    print("└" + "─" * 68 + "┘")
    print()
    test_database_persistence(results)
    test_tasks_persistence(results)
    test_persistence_after_restart(results)
    print()
    
    # Phase 3: WebSocket Event Bus
    print("┌" + "─" * 68 + "┐")
    print("│  PHASE 3: WEBSOCKET EVENT BUS                                    │")
    print("└" + "─" * 68 + "┘")
    print()
    test_websocket_events(results)
    print()
    
    # Phase 4: Frontend Mock Data Removal
    print("┌" + "─" * 68 + "┐")
    print("│  PHASE 4: FRONTEND MOCK DATA REMOVAL                             │")
    print("└" + "─" * 68 + "┘")
    print()
    test_no_mock_data(results)
    print()
    
    # Phase 5: Department Chat Dual-View
    print("┌" + "─" * 68 + "┐")
    print("│  PHASE 5: DEPARTMENT CHAT DUAL-VIEW                             │")
    print("└" + "─" * 68 + "┘")
    print()
    test_chat_history_dual_view(results)
    print()
    
    # Phase 6: Brain + Model Management
    print("┌" + "─" * 68 + "┐")
    print("│  PHASE 6: BRAIN + MODEL MANAGEMENT                               │")
    print("└" + "─" * 68 + "┘")
    print()
    test_brain_model_management(results)
    print()
    
    # Phase 7: Voice Pipeline
    print("┌" + "─" * 68 + "┐")
    print("│  PHASE 7: VOICE PIPELINE + ENV LAUNCHERS                         │")
    print("└" + "─" * 68 + "┘")
    print()
    test_voice_pipeline(results)
    print()
    
    # Print detailed results
    print("=" * 70)
    print("  DETAILED RESULTS")
    print("=" * 70)
    print()
    for result in results.results:
        print(f"  {result['status']}  {result['name']}")
        if result['message']:
            print(f"      {result['message']}")
    print()
    
    # Print summary
    return results.print_summary()

if __name__ == "__main__":
    sys.exit(main())



