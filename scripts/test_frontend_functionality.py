"""
Frontend Functionality Test Script
Tests all clickable elements, backend sync, and page content
"""

import asyncio
import httpx
import json
from pathlib import Path
from typing import List, Dict, Any

BASE_URL = "http://localhost:8000"
TIMEOUT = 10.0

class FrontendTester:
    def __init__(self):
        self.results = {
            "pages": {},
            "endpoints": {},
            "errors": [],
            "warnings": []
        }
        self.client = httpx.AsyncClient(timeout=TIMEOUT, base_url=BASE_URL)
    
    async def test_endpoint(self, method: str, path: str, expected_status: int = 200) -> Dict[str, Any]:
        """Test a single endpoint"""
        try:
            if method.upper() == "GET":
                response = await self.client.get(path)
            elif method.upper() == "POST":
                response = await self.client.post(path, json={})
            else:
                return {"error": f"Unsupported method: {method}"}
            
            return {
                "status": response.status_code,
                "expected": expected_status,
                "success": response.status_code == expected_status,
                "content_type": response.headers.get("content-type", ""),
                "has_content": len(response.content) > 0
            }
        except Exception as e:
            return {"error": str(e), "success": False}
    
    async def test_ui_pages(self):
        """Test all UI pages"""
        pages = [
            "/ui/daena-office",
            "/ui/dashboard",
            "/ui/departments",
            "/ui/agents",
            "/ui/workspace",
            "/ui/council-dashboard",
            "/ui/analytics",
            "/ui/system-monitor",
            "/ui/founder-panel",
            "/ui/memory"
        ]
        
        print("\n=== Testing UI Pages ===")
        for page in pages:
            result = await self.test_endpoint("GET", page)
            self.results["pages"][page] = result
            status = "✅" if result.get("success") else "❌"
            print(f"{status} {page}: {result.get('status', 'ERROR')}")
    
    async def test_api_endpoints(self):
        """Test critical API endpoints"""
        endpoints = [
            ("GET", "/api/v1/health/system"),
            ("GET", "/api/v1/brain/status"),
            ("GET", "/api/v1/llm/providers"),
            ("GET", "/api/v1/voice/status"),
            ("GET", "/api/v1/departments"),
            ("GET", "/api/v1/agents"),
            ("GET", "/api/v1/chat-history/sessions"),
            ("GET", "/api/v1/analytics/summary"),
            ("GET", "/api/v1/monitoring/memory/stats"),
            ("GET", "/api/v1/founder-panel/dashboard"),
        ]
        
        print("\n=== Testing API Endpoints ===")
        for method, endpoint in endpoints:
            result = await self.test_endpoint(method, endpoint)
            self.results["endpoints"][endpoint] = result
            status = "✅" if result.get("success") else "❌"
            print(f"{status} {method} {endpoint}: {result.get('status', 'ERROR')}")
    
    async def test_voice_endpoints(self):
        """Test voice-specific endpoints"""
        voice_endpoints = [
            ("GET", "/api/v1/voice/status"),
            ("POST", "/api/v1/voice/enable"),
            ("POST", "/api/v1/voice/disable"),
        ]
        
        print("\n=== Testing Voice Endpoints ===")
        for method, endpoint in voice_endpoints:
            result = await self.test_endpoint(method, endpoint)
            status = "✅" if result.get("success") else "❌"
            print(f"{status} {method} {endpoint}: {result.get('status', 'ERROR')}")
    
    async def check_backend_frontend_sync(self):
        """Check if backend endpoints match frontend expectations"""
        print("\n=== Checking Backend-Frontend Sync ===")
        
        # Check if frontend API client methods match backend endpoints
        api_client_path = Path("frontend/static/js/api-client.js")
        if api_client_path.exists():
            content = api_client_path.read_text(encoding='utf-8')
            
            # Check for common endpoint patterns
            checks = {
                "getChatSessions": "/api/v1/chat-history/sessions",
                "getDepartments": "/api/v1/departments",
                "getAgents": "/api/v1/agents",
                "getBrainStatus": "/api/v1/brain/status",
                "getLLMStatus": "/api/v1/llm/providers",
                "getVoiceStatus": "/api/v1/voice/status",
            }
            
            for method_name, expected_endpoint in checks.items():
                if method_name in content and expected_endpoint in content:
                    print(f"✅ {method_name} -> {expected_endpoint}")
                else:
                    print(f"⚠️  {method_name} may not match {expected_endpoint}")
                    self.results["warnings"].append(f"{method_name} endpoint mismatch")
    
    async def check_voice_cloning(self):
        """Check voice cloning setup"""
        print("\n=== Checking Voice Cloning Setup ===")
        
        # Check if voice cloning service exists
        voice_cloning_path = Path("backend/services/voice_cloning_service.py")
        if voice_cloning_path.exists():
            print("✅ Voice cloning service file exists")
            content = voice_cloning_path.read_text(encoding='utf-8')
            
            if "elevenlabs" in content.lower() or "aiohttp" in content.lower():
                print("✅ Voice cloning dependencies referenced")
            else:
                print("⚠️  Voice cloning dependencies not found in service")
                self.results["warnings"].append("Voice cloning dependencies may be missing")
        else:
            print("❌ Voice cloning service file not found")
            self.results["errors"].append("Voice cloning service missing")
        
        # Check requirements
        req_audio_path = Path("requirements-audio.txt")
        if req_audio_path.exists():
            content = req_audio_path.read_text(encoding='utf-8')
            if "aiohttp" in content:
                print("✅ aiohttp in requirements-audio.txt")
            else:
                print("⚠️  aiohttp not in requirements-audio.txt")
                self.results["warnings"].append("aiohttp missing from audio requirements")
    
    async def check_environments(self):
        """Check environment setup"""
        print("\n=== Checking Environment Setup ===")
        
        venv_main = Path("venv_daena_main_py310")
        venv_audio = Path("venv_daena_audio_py310")
        
        if venv_main.exists():
            print("✅ Main virtual environment exists")
        else:
            print("⚠️  Main virtual environment not found")
            self.results["warnings"].append("Main venv not found")
        
        if venv_audio.exists():
            print("✅ Audio virtual environment exists")
        else:
            print("⚠️  Audio virtual environment not found")
            self.results["warnings"].append("Audio venv not found")
    
    async def generate_report(self):
        """Generate test report"""
        print("\n=== Test Summary ===")
        
        total_pages = len(self.results["pages"])
        successful_pages = sum(1 for r in self.results["pages"].values() if r.get("success"))
        
        total_endpoints = len(self.results["endpoints"])
        successful_endpoints = sum(1 for r in self.results["endpoints"].values() if r.get("success"))
        
        print(f"Pages: {successful_pages}/{total_pages} successful")
        print(f"Endpoints: {successful_endpoints}/{total_endpoints} successful")
        print(f"Errors: {len(self.results['errors'])}")
        print(f"Warnings: {len(self.results['warnings'])}")
        
        if self.results["errors"]:
            print("\n=== Errors ===")
            for error in self.results["errors"]:
                print(f"❌ {error}")
        
        if self.results["warnings"]:
            print("\n=== Warnings ===")
            for warning in self.results["warnings"]:
                print(f"⚠️  {warning}")
        
        # Save report
        report_path = Path("docs/2025-12-20/FRONTEND_TEST_REPORT.md")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        
        report_content = f"""# Frontend Functionality Test Report

**Date**: {Path(__file__).stat().st_mtime}
**Status**: {'✅ PASS' if len(self.results['errors']) == 0 else '❌ FAIL'}

## Summary

- **Pages Tested**: {total_pages}
- **Pages Successful**: {successful_pages}
- **Endpoints Tested**: {total_endpoints}
- **Endpoints Successful**: {successful_endpoints}
- **Errors**: {len(self.results['errors'])}
- **Warnings**: {len(self.results['warnings'])}

## Page Results

"""
        for page, result in self.results["pages"].items():
            status = "✅" if result.get("success") else "❌"
            report_content += f"- {status} {page}: Status {result.get('status', 'ERROR')}\n"
        
        report_content += "\n## Endpoint Results\n\n"
        for endpoint, result in self.results["endpoints"].items():
            status = "✅" if result.get("success") else "❌"
            report_content += f"- {status} {endpoint}: Status {result.get('status', 'ERROR')}\n"
        
        if self.results["errors"]:
            report_content += "\n## Errors\n\n"
            for error in self.results["errors"]:
                report_content += f"- ❌ {error}\n"
        
        if self.results["warnings"]:
            report_content += "\n## Warnings\n\n"
            for warning in self.results["warnings"]:
                report_content += f"- ⚠️  {warning}\n"
        
        report_path.write_text(report_content, encoding='utf-8')
        print(f"\n✅ Report saved to {report_path}")
    
    async def run_all_tests(self):
        """Run all tests"""
        print("=" * 60)
        print("FRONTEND FUNCTIONALITY TEST SUITE")
        print("=" * 60)
        
        try:
            await self.test_ui_pages()
            await self.test_api_endpoints()
            await self.test_voice_endpoints()
            await self.check_backend_frontend_sync()
            await self.check_voice_cloning()
            await self.check_environments()
            await self.generate_report()
        finally:
            await self.client.aclose()

async def main():
    tester = FrontendTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())




