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
    print("TTSService initialized successfully!")
    
    print("Testing speak()...")
    output_path = "test_output.wav"
    if os.path.exists(output_path):
        os.remove(output_path)
        
    tts.speak(
        text="This is a test of the voice system.",
        output_path=output_path,
        language="en"
    )
    
    if os.path.exists(output_path):
        print(f"speak() successful! Output: {os.path.abspath(output_path)}")
    else:
        print("speak() failed! Output file not created.")
    
except Exception as e:
    print(f"Error: {str(e)}")
    import traceback
    traceback.print_exc()
