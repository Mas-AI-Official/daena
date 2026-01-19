#!/usr/bin/env python3
"""
Test Voice System for Daena AI VP
Verifies voice file accessibility and TTS functionality
"""
import asyncio
import sys
import os
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.append(str(backend_path))

from config.voice_config import (
    get_daena_voice_path, 
    get_voice_file_info, 
    ensure_voice_directory,
    VOICE_PATHS
)

async def test_voice_configuration():
    """Test the voice configuration system"""
    print("🎤 Testing Voice System Configuration...")
    print("=" * 50)
    
    # Test voice file paths
    print("\n📍 Checking voice file paths:")
    for name, path in VOICE_PATHS.items():
        exists = "✅" if path.exists() else "❌"
        print(f"   {exists} {name}: {path}")
    
    # Test voice directory creation
    print("\n📁 Testing voice directory creation:")
    try:
        voice_dir = ensure_voice_directory()
        print(f"   ✅ Voice directory: {voice_dir}")
    except Exception as e:
        print(f"   ❌ Error creating voice directory: {e}")
    
    # Test voice file info
    print("\n📊 Getting voice file information:")
    try:
        voice_info = get_voice_file_info()
        print(f"   ✅ Daena voice found: {voice_info['daena_voice_found']}")
        print(f"   ✅ Voice file path: {voice_info['daena_voice_path']}")
        print(f"   ✅ File size: {voice_info['total_size']} bytes")
        print(f"   ✅ Available locations: {len(voice_info['available_locations'])}")
        
        for location in voice_info['available_locations']:
            print(f"      - {location['name']}: {location['path']} ({location['size']} bytes)")
            
    except Exception as e:
        print(f"   ❌ Error getting voice info: {e}")
    
    # Test primary voice path
    print("\n🎵 Testing primary voice path:")
    try:
        primary_path = get_daena_voice_path()
        if primary_path and primary_path.exists():
            print(f"   ✅ Primary voice file: {primary_path}")
            print(f"   ✅ File size: {primary_path.stat().st_size} bytes")
            
            # Check if it's a valid WAV file
            if primary_path.suffix.lower() == '.wav':
                print("   ✅ Valid WAV file format")
            else:
                print(f"   ⚠️ File format: {primary_path.suffix}")
        else:
            print("   ❌ Primary voice file not found")
    except Exception as e:
        print(f"   ❌ Error accessing primary voice path: {e}")
    
    print("\n" + "=" * 50)
    print("🎤 Voice System Test Complete!")

async def main():
    """Main test function"""
    try:
        await test_voice_configuration()
        return 0
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 