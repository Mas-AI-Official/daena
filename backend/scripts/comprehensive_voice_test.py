#!/usr/bin/env python3
"""
Comprehensive Voice System Test for Daena AI VP
Tests TTS, speech recognition, voice file access, and voice controls
"""
import asyncio
import sys
import os
from pathlib import Path
import requests
import json

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.append(str(backend_path))

from config.voice_config import (
    get_daena_voice_path, 
    get_voice_file_info, 
    ensure_voice_directory,
    VOICE_PATHS,
    TTS_SETTINGS,
    SPEECH_RECOGNITION_SETTINGS
)

class VoiceSystemTester:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.test_results = []
    
    def log_test(self, test_name: str, success: bool, details: str = ""):
        """Log a test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        result = {
            "test": test_name,
            "status": status,
            "success": success,
            "details": details
        }
        self.test_results.append(result)
        print(f"{status} {test_name}")
        if details:
            print(f"   {details}")
    
    async def test_voice_configuration(self):
        """Test voice configuration system"""
        print("\n🎤 Testing Voice Configuration...")
        print("=" * 50)
        
        # Test voice file paths
        for name, path in VOICE_PATHS.items():
            exists = path.exists()
            self.log_test(
                f"Voice path: {name}",
                exists,
                f"Path: {path}"
            )
        
        # Test voice directory creation
        try:
            voice_dir = ensure_voice_directory()
            self.log_test(
                "Voice directory creation",
                True,
                f"Directory: {voice_dir}"
            )
        except Exception as e:
            self.log_test(
                "Voice directory creation",
                False,
                f"Error: {e}"
            )
        
        # Test voice file info
        try:
            voice_info = get_voice_file_info()
            self.log_test(
                "Voice file info retrieval",
                True,
                f"Found: {voice_info['daena_voice_found']}, Size: {voice_info['total_size']} bytes"
            )
        except Exception as e:
            self.log_test(
                "Voice file info retrieval",
                False,
                f"Error: {e}"
            )
        
        # Test primary voice path
        try:
            primary_path = get_daena_voice_path()
            if primary_path and primary_path.exists():
                self.log_test(
                    "Primary voice path access",
                    True,
                    f"Path: {primary_path}, Size: {primary_path.stat().st_size} bytes"
                )
            else:
                self.log_test(
                    "Primary voice path access",
                    False,
                    "Primary voice file not found"
                )
        except Exception as e:
            self.log_test(
                "Primary voice path access",
                False,
                f"Error: {e}"
            )
    
    async def test_voice_api_endpoints(self):
        """Test voice API endpoints"""
        print("\n🌐 Testing Voice API Endpoints...")
        print("=" * 50)
        
        endpoints = [
            ("/api/v1/voice/status", "GET"),
            ("/api/v1/voice/daena-voice", "GET"),
            ("/api/v1/voice/available-voices", "GET"),
            ("/api/v1/voice/test-voice", "GET")
        ]
        
        for endpoint, method in endpoints:
            try:
                url = f"{self.base_url}{endpoint}"
                if method == "GET":
                    response = requests.get(url, timeout=10)
                else:
                    response = requests.post(url, timeout=10)
                
                success = response.status_code == 200
                self.log_test(
                    f"API {method} {endpoint}",
                    success,
                    f"Status: {response.status_code}"
                )
                
                if success and endpoint == "/api/v1/voice/status":
                    try:
                        data = response.json()
                        voice_system = data.get("voice_system", {})
                        self.log_test(
                            "Voice status data structure",
                            "daena_voice_found" in voice_system,
                            f"Keys: {list(voice_system.keys())}"
                        )
                    except json.JSONDecodeError:
                        self.log_test(
                            "Voice status data structure",
                            False,
                            "Invalid JSON response"
                        )
                        
            except requests.exceptions.RequestException as e:
                self.log_test(
                    f"API {method} {endpoint}",
                    False,
                    f"Request error: {e}"
                )
    
    async def test_voice_controls(self):
        """Test voice control endpoints"""
        print("\n🎛️ Testing Voice Controls...")
        print("=" * 50)
        
        # Test voice activation
        try:
            response = requests.post(f"{self.base_url}/api/v1/voice/activate", timeout=10)
            success = response.status_code == 200
            self.log_test(
                "Voice activation",
                success,
                f"Status: {response.status_code}"
            )
            
            if success:
                try:
                    data = response.json()
                    self.log_test(
                        "Voice activation response",
                        data.get("status") == "success",
                        f"Response: {data.get('message', 'No message')}"
                    )
                except json.JSONDecodeError:
                    self.log_test(
                        "Voice activation response",
                        False,
                        "Invalid JSON response"
                    )
        except requests.exceptions.RequestException as e:
            self.log_test(
                "Voice activation",
                False,
                f"Request error: {e}"
            )
        
        # Test voice deactivation
        try:
            response = requests.post(f"{self.base_url}/api/v1/voice/deactivate", timeout=10)
            success = response.status_code == 200
            self.log_test(
                "Voice deactivation",
                success,
                f"Status: {response.status_code}"
            )
        except requests.exceptions.RequestException as e:
            self.log_test(
                "Voice deactivation",
                False,
                f"Request error: {e}"
            )
    
    async def test_voice_file_access(self):
        """Test voice file access and playback"""
        print("\n🎵 Testing Voice File Access...")
        print("=" * 50)
        
        # Test if voice file can be accessed via API
        try:
            response = requests.get(f"{self.base_url}/api/v1/voice/daena-voice", timeout=10)
            success = response.status_code == 200
            self.log_test(
                "Voice file API access",
                success,
                f"Status: {response.status_code}, Content-Type: {response.headers.get('content-type', 'Unknown')}"
            )
            
            if success:
                # Check if it's actually audio content
                content_type = response.headers.get('content-type', '')
                is_audio = 'audio' in content_type or 'wav' in content_type
                self.log_test(
                    "Voice file content type",
                    is_audio,
                    f"Content-Type: {content_type}"
                )
                
                # Check file size
                content_length = len(response.content)
                self.log_test(
                    "Voice file content size",
                    content_length > 0,
                    f"Size: {content_length} bytes"
                )
                
        except requests.exceptions.RequestException as e:
            self.log_test(
                "Voice file API access",
                False,
                f"Request error: {e}"
            )
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 50)
        print("📊 VOICE SYSTEM TEST SUMMARY")
        print("=" * 50)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["success"])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            print("\n❌ Failed Tests:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"   - {result['test']}: {result['details']}")
        
        print("\n🎤 Voice System Test Complete!")
        
        return passed_tests == total_tests

async def main():
    """Main test function"""
    print("🎤 Daena AI VP - Comprehensive Voice System Test")
    print("=" * 60)
    
    # Check if server is running
    try:
        response = requests.get("http://localhost:8000/api/v1/", timeout=5)
        if response.status_code != 200:
            print("⚠️  Warning: Backend server may not be running on localhost:8000")
            print("   Some tests may fail. Start the server with: python main.py")
    except:
        print("⚠️  Warning: Cannot connect to backend server on localhost:8000")
        print("   Some tests may fail. Start the server with: python main.py")
    
    tester = VoiceSystemTester()
    
    try:
        await tester.test_voice_configuration()
        await tester.test_voice_api_endpoints()
        await tester.test_voice_controls()
        await tester.test_voice_file_access()
        
        all_passed = tester.print_summary()
        return 0 if all_passed else 1
        
    except Exception as e:
        print(f"❌ Test suite failed with error: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 