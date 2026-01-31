import logging
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(os.getcwd())

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from audio.audio_service.tts_service import TTSService
    print("Import successful")
    
    print("Initializing TTSService(use_gpu=False)...")
    tts = TTSService(use_gpu=False)
    print("✅ TTSService initialized successfully!")
    
except Exception as e:
    print(f"❌ Failed to initialize TTSService: {e}")
    import traceback
    traceback.print_exc()
