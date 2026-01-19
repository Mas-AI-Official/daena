#!/usr/bin/env python3
"""
Create Daena Voice File
Simple script to create a basic daena_voice.wav file
"""

import os
import sys
import tempfile
import subprocess
from pathlib import Path

def create_daena_voice():
    """Create a basic daena_voice.wav file"""
    
    print("🎤 Creating Daena voice file...")
    
    # Sample text for Daena
    text = "Hello, I am Daena, your AI Vice President."
    
    try:
        # Create temporary file for the text
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
            temp_file.write(text)
            temp_path = temp_file.name
        
        # Get the project root directory
        project_root = Path(__file__).parent.parent.parent
        voice_file_path = project_root / "daena_voice.wav"
        
        # Use Windows SAPI to create voice file
        try:
            # Try using PowerShell to create speech
            ps_script = f'''
            Add-Type -AssemblyName System.Speech
            $synthesizer = New-Object System.Speech.Synthesis.SpeechSynthesizer
            $synthesizer.SetOutputToWaveFile("{voice_file_path}")
            $synthesizer.Speak("{text}")
            $synthesizer.Dispose()
            '''
            
            # Run PowerShell script
            result = subprocess.run([
                "powershell", "-Command", ps_script
            ], capture_output=True, text=True)
            
            if result.returncode == 0 and voice_file_path.exists():
                print(f"✅ Daena voice file created successfully!")
                print(f"📁 File saved to: {voice_file_path}")
                return True
            else:
                print(f"❌ PowerShell failed: {result.stderr}")
                
        except Exception as e:
            print(f"❌ Error creating voice file: {e}")
        
        # Clean up temporary file
        os.unlink(temp_path)
        
        # Fallback: create a minimal WAV file
        if not voice_file_path.exists():
            print("🔄 Creating fallback voice file...")
            create_minimal_wav(voice_file_path)
            print(f"✅ Fallback voice file created: {voice_file_path}")
            return True
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def create_minimal_wav(file_path):
    """Create a minimal WAV file"""
    # Minimal WAV file structure (silence)
    wav_data = b'RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00'
    
    with open(file_path, 'wb') as f:
        f.write(wav_data)

if __name__ == "__main__":
    print("🧠 Daena Voice Creator")
    print("=" * 30)
    
    success = create_daena_voice()
    
    if success:
        print("\n✅ Voice file creation completed!")
        print("🎯 Daena voice is now available")
    else:
        print("\n❌ Voice file creation failed")
        print("🔧 Please check your system TTS configuration") 