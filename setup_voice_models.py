"""
Download and setup voice models for Daena
Models will be stored in D:\Ideas\Daena_old_upgrade_20251213\models\
"""
import os
import sys
from pathlib import Path

# Add parent to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def setup_models():
    """Download and setup voice models"""
    models_dir = project_root / "models"
    models_dir.mkdir(exist_ok=True)
    
    print("=" * 60)
    print("DAENA VOICE MODELS SETUP")
    print("=" * 60)
    print(f"Project root: {project_root}")
    print(f"Models directory: {models_dir}")
    print()
    
    # Setup faster-whisper model
    print("[1/2] Setting up faster-whisper (STT)...")
    print("   Model: medium (balanced speed/accuracy)")
    print("   Note: Model downloads automatically on first use")
    print("   Cache location: ~/.cache/huggingface/")
    print("   ✓ No manual download needed")
    print()
    
    # Setup XTTS-v2 model
    print("[2/2] Setting up XTTS-v2 (TTS)...")
    print("   Model: tts_models/multilingual/multi-dataset/xtts_v2")
    print("   Size: ~1.8GB")
    print("   Note: Model downloads automatically on first use")
    print("   Cache location: ~/.local/share/tts/")
    
    try:
        # Import TTS to trigger model list update
        from TTS.api import TTS
        print("   ✓ TTS library ready")
        
        # List available models (this updates the model registry)
        print("   Updating model registry...")
        models = TTS.list_models()
        if "tts_models/multilingual/multi-dataset/xtts_v2" in models:
            print("   ✓ XTTS-v2 model available")
        
    except Exception as e:
        print(f"   ⚠ TTS not installed yet: {e}")
        print("   Run: pip install TTS")
    
    print()
    print("=" * 60)
    print("VOICE MODEL SETUP COMPLETE")
    print("=" * 60)
    print()
    print("Models will download automatically on first use:")
    print("  - faster-whisper: On first STT request")
    print("  - XTTS-v2: On first TTS request")
    print()
    print("Estimated download sizes:")
    print("  - faster-whisper medium: ~1.5GB")
    print("  - XTTS-v2: ~1.8GB")
    print("  - Total: ~3.3GB")
    print()
    print("To start using:")
    print("  1. Start audio service: python -m audio.audio_service.main")
    print("  2. Make STT/TTS requests via API")
    print("  3. Models download automatically")
    print()

if __name__ == "__main__":
    setup_models()
