#!/usr/bin/env python3
"""
Test script for Daena's voice conversation system
Tests natural language responses and voice functionality
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.voice_service import VoiceService
from services.llm_service import LLMService

async def test_natural_conversation():
    """Test Daena's natural conversation responses"""
    print("🧪 Testing Daena's Natural Conversation...")
    print("=" * 50)
    
    # Test LLM service responses
    try:
        llm_service = LLMService()
        
        test_messages = [
            "hi",
            "hello",
            "hey boss",
            "how are you",
            "what's up",
            "thanks",
            "who are you"
        ]
        
        for message in test_messages:
            print(f"\n👤 User: {message}")
            
            # Test fallback responses
            fallback_response = await llm_service._fallback_generate(message)
            print(f"🤖 Daena (fallback): {fallback_response}")
            
            # Test LLM responses if available
            try:
                llm_response = await llm_service.generate_response(message)
                print(f"🤖 Daena (LLM): {llm_response}")
            except Exception as e:
                print(f"⚠️ LLM not available: {e}")
        
        print("\n✅ Natural conversation test completed!")
        
    except Exception as e:
        print(f"❌ Error testing conversation: {e}")

async def test_voice_system():
    """Test voice system functionality"""
    print("\n🎤 Testing Voice System...")
    print("=" * 50)
    
    try:
        # Create voice service without microphone initialization
        voice_service = VoiceService()
        
        # Test voice file detection
        print(f"🎵 Daena voice found: {voice_service.daena_voice_path}")
        print(f"🎵 Voice file exists: {voice_service.daena_voice_path.exists() if voice_service.daena_voice_path else False}")
        
        # Test TTS
        test_text = "Hey boss! How's it going?"
        print(f"\n🗣️ Testing TTS with: {test_text}")
        
        audio_data = await voice_service._generate_speech(test_text, "daena")
        if audio_data:
            print(f"✅ TTS generated {len(audio_data)} bytes of audio")
        else:
            print("❌ TTS failed to generate audio")
        
        print("\n✅ Voice system test completed!")
        
    except Exception as e:
        print(f"❌ Error testing voice system: {e}")
        print(f"⚠️ This might be due to missing microphone - that's okay for testing!")

async def main():
    """Main test function"""
    print("🚀 Daena Voice Conversation Test")
    print("=" * 50)
    
    await test_natural_conversation()
    await test_voice_system()
    
    print("\n🎯 All tests completed!")

if __name__ == "__main__":
    asyncio.run(main()) 