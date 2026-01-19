"""
Test script for voice cloning functionality
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.voice_cloning import voice_cloning_service
from backend.config.voice_config import get_daena_voice_path

async def test_voice_cloning():
    """Test voice cloning functionality"""
    print("🎤 Testing Voice Cloning Service...")
    print()
    
    # Check API key
    if not voice_cloning_service.api_key:
        print("⚠️ ELEVENLABS_API_KEY not set")
        print("💡 Set ELEVENLABS_API_KEY environment variable")
        return
    
    print(f"✅ API Key found: {voice_cloning_service.api_key[:20]}...")
    
    # Check voice file
    voice_path = get_daena_voice_path()
    if voice_path.exists():
        print(f"✅ Voice file found: {voice_path}")
        print(f"   Size: {voice_path.stat().st_size / 1024 / 1024:.2f} MB")
    else:
        print(f"⚠️ Voice file not found: {voice_path}")
        return
    
    # Initialize voices
    print()
    print("🔄 Initializing voice cloning...")
    await voice_cloning_service.initialize_voices()
    
    if voice_cloning_service.voice_id:
        print(f"✅ Daena voice cloned: {voice_cloning_service.voice_id}")
    else:
        print("⚠️ Voice cloning failed")
        return
    
    # Test TTS
    print()
    print("🗣️ Testing TTS generation...")
    test_text = "Hello, I am Daena. This is a test of my voice cloning system."
    
    audio_data = await voice_cloning_service.text_to_speech(
        text=test_text,
        voice_type="daena"
    )
    
    if audio_data:
        print(f"✅ TTS generated successfully ({len(audio_data)} bytes)")
        
        # Save to file for testing
        output_file = Path("test_daena_voice.wav")
        with open(output_file, 'wb') as f:
            f.write(audio_data)
        print(f"✅ Audio saved to: {output_file}")
    else:
        print("⚠️ TTS generation failed")
    
    # Test agent voices
    print()
    print("👥 Testing agent voices...")
    for agent_name in ["engineering", "product", "marketing"]:
        audio_data = await voice_cloning_service.text_to_speech(
            text=f"Hello, I am the {agent_name} agent.",
            voice_type="agent",
            agent_name=agent_name
        )
        if audio_data:
            print(f"✅ {agent_name} voice generated ({len(audio_data)} bytes)")
        else:
            print(f"⚠️ {agent_name} voice generation failed")
    
    print()
    print("✅ Voice cloning test complete!")

if __name__ == "__main__":
    asyncio.run(test_voice_cloning())

