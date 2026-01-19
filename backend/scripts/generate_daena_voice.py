#!/usr/bin/env python3
"""
Generate Daena Voice File
Creates a proper daena_voice.wav file using the TTS system
"""

import os
import sys
import asyncio
from pathlib import Path

# Add the backend directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.voice_service import VoiceService

async def generate_daena_voice():
    """Generate a proper daena_voice.wav file"""
    
    print("🎤 Generating Daena voice file...")
    
    # Initialize voice service
    voice_service = VoiceService()
    
    # Sample text for Daena voice
    sample_text = "Hello, I am Daena, your AI Vice President. I'm here to help manage your business operations and provide strategic insights."
    
    try:
        # Generate speech
        result = await voice_service.text_to_speech(sample_text, voice_type="daena")
        
        if result and result.get('success'):
            print("✅ Daena voice file generated successfully!")
            print(f"📁 File saved to: {result.get('file_path', 'daena_voice.wav')}")
            return True
        else:
            print("❌ Failed to generate voice file")
            return False
            
    except Exception as e:
        print(f"❌ Error generating voice file: {e}")
        return False

async def main():
    """Main function"""
    print("🧠 Daena Voice Generator")
    print("=" * 40)
    
    success = await generate_daena_voice()
    
    if success:
        print("\n✅ Voice generation completed successfully!")
        print("🎯 You can now use voice commands with Daena")
    else:
        print("\n❌ Voice generation failed")
        print("🔧 Please check your TTS configuration")

if __name__ == "__main__":
    asyncio.run(main()) 