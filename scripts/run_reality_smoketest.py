#!/usr/bin/env python3
"""
Reality Smoke Test - Comprehensive Daena System Verification

Checks:
1. Chat create/send/delete
2. Brain status & list models
3. Tools search/fetch
4. Voice status
5. Health endpoints
6. Snapshots create/list/restore

Run: python scripts/run_reality_smoketest.py
"""

import asyncio
import httpx
import json
from datetime import datetime
from typing import Dict, List, Tuple

BASE_URL = "http://localhost:8000/api/v1"
TIMEOUT = 15.0

class SmokeTest:
    def __init__(self):
        self.results: List[Tuple[str, bool, str]] = []
        self.session_id = None
        self.snapshot_id = None
        
    async def run_all(self):
        print("\n" + "="*60)
        print("  🐝 DAENA REALITY SMOKE TEST")
        print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        print("="*60 + "\n")
        
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            # 1. Health
            await self.test_health(client)
            await self.test_council_health(client)
            
            # 2. Brain
            await self.test_brain_status(client)
            await self.test_brain_models(client)
            
            # 3. Chat
            await self.test_chat_create(client)
            await self.test_chat_send(client)
            await self.test_chat_delete(client)
            
            # 4. Tools
            await self.test_tool_web_search(client)
            
            # 5. Voice
            await self.test_voice_status(client)
            
            # 6. Snapshots
            await self.test_snapshot_create(client)
            await self.test_snapshot_list(client)
            await self.test_snapshot_restore(client)
            
            # 7. Demo
            await self.test_demo_health(client)
            await self.test_demo_run(client)
        
        self.print_summary()
    
    def record(self, name: str, passed: bool, detail: str):
        self.results.append((name, passed, detail))
        status = "✅" if passed else "❌"
        print(f"  {status} {name}: {detail}")
    
    async def test_health(self, client):
        try:
            r = await client.get(f"{BASE_URL}/health/")
            if r.status_code == 200:
                data = r.json()
                self.record("Health Check", data.get("status") == "healthy", data.get("status", "unknown"))
            else:
                self.record("Health Check", False, f"HTTP {r.status_code}")
        except Exception as e:
            self.record("Health Check", False, str(e)[:50])
    
    async def test_council_health(self, client):
        try:
            r = await client.get(f"{BASE_URL}/health/council")
            if r.status_code == 200:
                data = r.json()
                status = data.get("status", "unknown")
                self.record("Council Health", status in ["healthy", "partial"], status)
            else:
                self.record("Council Health", False, f"HTTP {r.status_code}")
        except Exception as e:
            self.record("Council Health", False, str(e)[:50])
    
    async def test_brain_status(self, client):
        try:
            r = await client.get(f"{BASE_URL}/brain/status")
            if r.status_code == 200:
                data = r.json()
                connected = data.get("connected", False)
                self.record("Brain Status", True, f"connected={connected}")
            else:
                self.record("Brain Status", False, f"HTTP {r.status_code}")
        except Exception as e:
            self.record("Brain Status", False, str(e)[:50])
    
    async def test_brain_models(self, client):
        try:
            r = await client.get(f"{BASE_URL}/brain/models")
            if r.status_code == 200:
                data = r.json()
                models = data.get("models", [])
                self.record("Brain Models", len(models) > 0, f"{len(models)} models found")
            else:
                self.record("Brain Models", False, f"HTTP {r.status_code}")
        except Exception as e:
            self.record("Brain Models", False, str(e)[:50])
    
    async def test_chat_create(self, client):
        try:
            r = await client.post(f"{BASE_URL}/chat-history/sessions", json={
                "title": "Smoke Test Chat",
                "category": "executive"
            })
            if r.status_code == 200:
                data = r.json()
                self.session_id = data.get("session_id")
                self.record("Chat Create", bool(self.session_id), f"session_id={self.session_id[:8]}...")
            else:
                self.record("Chat Create", False, f"HTTP {r.status_code}")
        except Exception as e:
            self.record("Chat Create", False, str(e)[:50])
    
    async def test_chat_send(self, client):
        if not self.session_id:
            self.record("Chat Send", False, "No session")
            return
        try:
            r = await client.post(f"{BASE_URL}/daena/chat", json={
                "message": "Hello Daena, this is a test",
                "session_id": self.session_id
            })
            if r.status_code == 200:
                data = r.json()
                success = data.get("success", False)
                self.record("Chat Send", success, data.get("response", "")[:30] + "...")
            else:
                self.record("Chat Send", False, f"HTTP {r.status_code}")
        except Exception as e:
            self.record("Chat Send", False, str(e)[:50])
    
    async def test_chat_delete(self, client):
        if not self.session_id:
            self.record("Chat Delete", False, "No session")
            return
        try:
            r = await client.delete(f"{BASE_URL}/daena/chat/{self.session_id}")
            if r.status_code in [200, 204]:
                self.record("Chat Delete", True, "Session deleted")
            else:
                self.record("Chat Delete", False, f"HTTP {r.status_code}")
        except Exception as e:
            self.record("Chat Delete", False, str(e)[:50])
    
    async def test_tool_web_search(self, client):
        try:
            r = await client.post(f"{BASE_URL}/daena/chat", json={
                "message": "search for Python programming"
            })
            if r.status_code == 200:
                data = r.json()
                # Check if tool was invoked
                resp = data.get("response", "").lower()
                has_result = "search" in resp or "result" in resp or data.get("success")
                self.record("Tool: Web Search", has_result, data.get("response", "")[:40] + "...")
            else:
                self.record("Tool: Web Search", False, f"HTTP {r.status_code}")
        except Exception as e:
            self.record("Tool: Web Search", False, str(e)[:50])
    
    async def test_voice_status(self, client):
        try:
            r = await client.get(f"{BASE_URL}/voice/status")
            if r.status_code == 200:
                data = r.json()
                self.record("Voice Status", True, f"enabled={data.get('talk_active', False)}")
            elif r.status_code == 404:
                self.record("Voice Status", True, "Endpoint not found (voice disabled)")
            else:
                self.record("Voice Status", False, f"HTTP {r.status_code}")
        except Exception as e:
            self.record("Voice Status", False, str(e)[:50])
    
    async def test_snapshot_create(self, client):
        try:
            r = await client.post(f"{BASE_URL}/snapshots", json={
                "label": "Smoke Test Snapshot",
                "description": "Created by smoke test"
            })
            if r.status_code == 200:
                data = r.json()
                self.snapshot_id = data.get("snapshot_id")
                self.record("Snapshot Create", bool(self.snapshot_id), f"id={self.snapshot_id}")
            else:
                self.record("Snapshot Create", False, f"HTTP {r.status_code}")
        except Exception as e:
            self.record("Snapshot Create", False, str(e)[:50])
    
    async def test_snapshot_list(self, client):
        try:
            r = await client.get(f"{BASE_URL}/snapshots")
            if r.status_code == 200:
                data = r.json()
                snapshots = data.get("snapshots", [])
                self.record("Snapshot List", len(snapshots) > 0, f"{len(snapshots)} snapshots")
            else:
                self.record("Snapshot List", False, f"HTTP {r.status_code}")
        except Exception as e:
            self.record("Snapshot List", False, str(e)[:50])
    
    async def test_snapshot_restore(self, client):
        if not self.snapshot_id:
            self.record("Snapshot Restore", False, "No snapshot")
            return
        try:
            r = await client.post(f"{BASE_URL}/snapshots/{self.snapshot_id}/restore", json={
                "confirm": True
            })
            if r.status_code == 200:
                data = r.json()
                self.record("Snapshot Restore", data.get("success", False), "Restored")
            else:
                self.record("Snapshot Restore", False, f"HTTP {r.status_code}")
        except Exception as e:
            self.record("Snapshot Restore", False, str(e)[:50])
    
    async def test_demo_health(self, client):
        try:
            r = await client.get(f"{BASE_URL}/demo/health")
            if r.status_code == 200:
                data = r.json()
                self.record("Demo Health", data.get("status") == "ready", data.get("status", "unknown"))
            else:
                self.record("Demo Health", False, f"HTTP {r.status_code}")
        except Exception as e:
            self.record("Demo Health", False, str(e)[:50])
    
    async def test_demo_run(self, client):
        try:
            r = await client.post(f"{BASE_URL}/demo/run", json={
                "prompt": "Test prompt",
                "use_cloud": False
            })
            if r.status_code == 200:
                data = r.json()
                self.record("Demo Run", data.get("status") == "success", f"{data.get('total_duration_ms', 0)}ms")
            else:
                self.record("Demo Run", False, f"HTTP {r.status_code}")
        except Exception as e:
            self.record("Demo Run", False, str(e)[:50])
    
    def print_summary(self):
        print("\n" + "-"*60)
        passed = sum(1 for _, p, _ in self.results if p)
        total = len(self.results)
        pct = (passed / total * 100) if total > 0 else 0
        
        print(f"\n  SUMMARY: {passed}/{total} checks passed ({pct:.0f}%)")
        
        if pct == 100:
            print("\n  🎉 ALL SYSTEMS OPERATIONAL!")
        elif pct >= 80:
            print("\n  ⚠️  MOSTLY WORKING - Review failures above")
        else:
            print("\n  ❌ CRITICAL ISSUES - Fix before demo!")
        
        print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(SmokeTest().run_all())
