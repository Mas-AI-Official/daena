#!/usr/bin/env python3
"""
Voice System Demonstration for Daena AI VP
Shows how to use voice features and test voice functionality
"""
import asyncio
import sys
import os
from pathlib import Path
import requests
import json
import time

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.append(str(backend_path))

from config.voice_config import (
    get_daena_voice_path, 
    get_voice_file_info, 
    ensure_voice_directory,
    WAKE_WORDS,
    TTS_SETTINGS
)

class VoiceDemo:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
    
    def print_header(self, title: str):
        """Print a formatted header"""
        print(f"\n{'='*60}")
        print(f"🎤 {title}")
        print(f"{'='*60}")
    
    def print_section(self, title: str):
        """Print a formatted section header"""
        print(f"\n📋 {title}")
        print("-" * 40)
    
    def demo_voice_configuration(self):
        """Demonstrate voice configuration"""
        self.print_section("Voice Configuration")
        
        print("🔧 Voice Settings:")
        print(f"   • Default Rate: {TTS_SETTINGS['default_rate']} WPM")
        print(f"   • Default Volume: {TTS_SETTINGS['default_volume']}")
        print(f"   • Default Pitch: {TTS_SETTINGS['default_pitch']}")
        print(f"   • Voice Gender: {TTS_SETTINGS['voice_gender']}")
        print(f"   • Language: {TTS_SETTINGS['language']}")
        
        print("\n🎯 Wake Words:")
        for word in WAKE_WORDS:
            print(f"   • '{word}'")
        
        print("\n📁 Voice File Information:")
        voice_info = get_voice_file_info()
        print(f"   • Daena Voice Found: {voice_info['daena_voice_found']}")
        print(f"   • Voice File Path: {voice_info['daena_voice_path']}")
        print(f"   • File Size: {voice_info['total_size']:,} bytes")
        print(f"   • Available Locations: {len(voice_info['available_locations'])}")
    
    def demo_voice_api_endpoints(self):
        """Demonstrate voice API endpoints"""
        self.print_section("Voice API Endpoints")
        
        endpoints = [
            ("/api/v1/voice/status", "GET", "Get voice system status"),
            ("/api/v1/voice/daena-voice", "GET", "Access Daena's voice file"),
            ("/api/v1/voice/available-voices", "GET", "List available voices"),
            ("/api/v1/voice/test-voice", "GET", "Test voice system"),
            ("/api/v1/voice/activate", "POST", "Activate voice listening"),
            ("/api/v1/voice/deactivate", "POST", "Deactivate voice listening")
        ]
        
        print("🌐 Available Voice Endpoints:")
        for endpoint, method, description in endpoints:
            print(f"   • {method} {endpoint}")
            print(f"     {description}")
        
        # Test voice status endpoint
        print("\n🔍 Testing Voice Status Endpoint:")
        try:
            response = requests.get(f"{self.base_url}/api/v1/voice/status", timeout=10)
            if response.status_code == 200:
                data = response.json()
                print("   ✅ Voice status endpoint working")
                print(f"   📊 Voice System: {data.get('voice_system', {}).get('daena_voice_found', 'Unknown')}")
                print(f"   🎤 Voice Service: {data.get('voice_service', {}).get('enabled', 'Unknown')}")
            else:
                print(f"   ❌ Voice status endpoint failed: {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error testing voice status: {e}")
    
    def demo_voice_controls(self):
        """Demonstrate voice control features"""
        self.print_section("Voice Controls")
        
        print("🎛️ Voice Control Features:")
        print("   • Wake Word Detection: Listen for activation phrases")
        print("   • Voice Activation: Enable/disable voice listening")
        print("   • Talk Mode: Enable/disable Daena's speech output")
        print("   • Agent Voices: Different voice characteristics per department")
        
        # Test voice activation
        print("\n🔊 Testing Voice Activation:")
        try:
            response = requests.post(f"{self.base_url}/api/v1/voice/activate", timeout=10)
            if response.status_code == 200:
                data = response.json()
                print("   ✅ Voice activation successful")
                print(f"   📢 Message: {data.get('message', 'No message')}")
            else:
                print(f"   ❌ Voice activation failed: {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error testing voice activation: {e}")
        
        # Test voice deactivation
        print("\n🔇 Testing Voice Deactivation:")
        try:
            response = requests.post(f"{self.base_url}/api/v1/voice/deactivate", timeout=10)
            if response.status_code == 200:
                data = response.json()
                print("   ✅ Voice deactivation successful")
                print(f"   📢 Message: {data.get('message', 'No message')}")
            else:
                print(f"   ❌ Voice deactivation failed: {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error testing voice deactivation: {e}")
    
    def demo_voice_file_access(self):
        """Demonstrate voice file access"""
        self.print_section("Voice File Access")
        
        print("🎵 Voice File Access:")
        print("   • Primary Location: Project root (daena_voice.wav)")
        print("   • Backup Location: Voice directory")
        print("   • API Access: /api/v1/voice/daena-voice")
        print("   • File Format: WAV audio")
        
        # Test voice file access
        print("\n📁 Testing Voice File Access:")
        try:
            response = requests.get(f"{self.base_url}/api/v1/voice/daena-voice", timeout=10)
            if response.status_code == 200:
                print("   ✅ Voice file accessible via API")
                print(f"   📊 Content-Type: {response.headers.get('content-type', 'Unknown')}")
                print(f"   📏 File Size: {len(response.content):,} bytes")
                
                # Check if it's actually audio
                content_type = response.headers.get('content-type', '')
                if 'audio' in content_type or 'wav' in content_type:
                    print("   🎵 Valid audio content detected")
                else:
                    print("   ⚠️ Content type may not be audio")
            else:
                print(f"   ❌ Voice file access failed: {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error testing voice file access: {e}")
    
    def demo_usage_examples(self):
        """Show usage examples"""
        self.print_section("Usage Examples")
        
        print("💡 How to Use Daena's Voice System:")
        print("\n1. 🎤 Activate Voice Listening:")
        print("   curl -X POST http://localhost:8000/api/v1/voice/activate")
        
        print("\n2. 🎵 Access Daena's Voice:")
        print("   curl http://localhost:8000/api/v1/voice/daena-voice")
        
        print("\n3. 📊 Check Voice Status:")
        print("   curl http://localhost:8000/api/v1/voice/status")
        
        print("\n4. 🔇 Deactivate Voice:")
        print("   curl -X POST http://localhost:8000/api/v1/voice/deactivate")
        
        print("\n5. 🧪 Test Voice System:")
        print("   curl http://localhost:8000/api/v1/voice/test-voice")
        
        print("\n🎯 Frontend Integration:")
        print("   • Use the voice toggle button in Daena Office")
        print("   • Say 'Hey Daena' to activate voice recognition")
        print("   • Voice responses will play automatically")
    
    def run_demo(self):
        """Run the complete voice demonstration"""
        self.print_header("Daena AI VP Voice System Demonstration")
        
        print("🎤 Welcome to Daena's Voice System Demo!")
        print("This demonstration shows all the voice features available in the system.")
        
        # Run all demo sections
        self.demo_voice_configuration()
        self.demo_voice_api_endpoints()
        self.demo_voice_controls()
        self.demo_voice_file_access()
        self.demo_usage_examples()
        
        self.print_header("Demo Complete!")
        print("🎉 Voice system demonstration completed successfully!")
        print("\n🚀 Next Steps:")
        print("   • Test voice features in the Daena Office frontend")
        print("   • Use voice commands to interact with Daena")
        print("   • Customize voice settings in voice_config.py")
        print("   • Run comprehensive tests with: python scripts/comprehensive_voice_test.py")

async def main():
    """Main demo function"""
    try:
        demo = VoiceDemo()
        demo.run_demo()
        return 0
    except Exception as e:
        print(f"❌ Demo failed with error: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 