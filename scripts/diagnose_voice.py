import sys
import os
import logging
import asyncio
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def check_dependencies():
    logger.info("🔍 Checking Voice Dependencies...")
    
    # Check Torch
    try:
        import torch
        logger.info(f"✅ Torch available: {torch.__version__}")
        logger.info(f"   CUDA available: {torch.cuda.is_available()}")
    except ImportError as e:
        logger.error(f"❌ Torch not found: {e}")
    except Exception as e:
        logger.error(f"❌ Torch error: {e}")

    # Check pyttsx3
    try:
        import pyttsx3
        logger.info("✅ pyttsx3 available")
        try:
            engine = pyttsx3.init()
            logger.info("   pyttsx3 engine initialized successfully")
        except Exception as e:
            logger.error(f"   ❌ pyttsx3 init failed: {e}")
    except ImportError:
        logger.warning("⚠️ pyttsx3 not installed")

    # Check TTS (Coqui)
    try:
        import TTS
        logger.info(f"✅ TTS (Coqui) available: {TTS.__version__}")
    except ImportError:
        logger.error("❌ TTS not installed")
    except Exception as e:
        logger.error(f"❌ TTS import error: {e}")

async def test_voice_service():
    logger.info("\n🎤 Testing Voice Service Initialization...")
    
    # Add project root to path so we can import backend modules
    project_root = Path(__file__).parent.parent
    sys.path.append(str(project_root))
    
    try:
        from backend.services.voice_service import VoiceService
        logger.info("   Imported VoiceService class")
        
        service = VoiceService()
        logger.info("   VoiceService instantiated")
        
        # Check initialization status
        if service.tts_engine:
            logger.info("✅ System TTS (pyttsx3) is READY")
        else:
            logger.warning("⚠️ System TTS (pyttsx3) is NOT ready")
            
        # Check XTTS availability (logic from service)
        try:
            import torch
            from TTS.api import TTS
            logger.info("   Attempting to load XTTS model (this might take a moment)...")
            
            # Apply the fix we added
            try:
                from TTS.tts.configs.xtts_config import XttsConfig
                torch.serialization.add_safe_globals([XttsConfig])
                logger.info("   ✅ Applied torch safe globals fix")
            except Exception as e:
                logger.warning(f"   ⚠️ Could not apply fix: {e}")

            # Try loading model
            tts = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2", gpu=False)
            logger.info("✅ XTTS Model loaded successfully")
        except Exception as e:
            logger.error(f"❌ XTTS Model load failed: {e}")

    except ImportError as e:
        logger.error(f"❌ Could not import backend services: {e}")
    except Exception as e:
        logger.error(f"❌ VoiceService test failed: {e}")

if __name__ == "__main__":
    check_dependencies()
    asyncio.run(test_voice_service())
