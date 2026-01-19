import torch
import sys
import os

def apply_xtts_fix():
    """
    Allowlist XTTS config for PyTorch 2.6+ weights_only=True default.
    """
    try:
        from torch.serialization import add_safe_globals
    except ImportError:
        # PyTorch < 2.6 doesn't have this, so we don't need the fix
        print("PyTorch version < 2.6, skipping safe globals allowlist.")
        return

    try:
        from TTS.tts.configs.xtts_config import XttsConfig
        add_safe_globals([XttsConfig])
        print("✅ XTTS-v2 config allowlisted for PyTorch 2.6+")
    except ImportError:
        print("❌ Could not import XttsConfig. Is TTS installed?")
    except Exception as e:
        print(f"❌ Error applying XTTS fix: {e}")

def main():
    print("Applying XTTS Fix for PyTorch 2.6...")
    apply_xtts_fix()
    
    # Test loading if run as script
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        try:
            from TTS.api import TTS
            print("Testing TTS load...")
            # Assuming models are downloaded in standard location or handled by env vars
            # This is just a smoke test if the user runs it manually
            tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=torch.cuda.is_available())
            print("✅ XTTS-v2 loaded successfully!")
        except Exception as e:
            print(f"❌ XTTS load failed: {e}")

if __name__ == "__main__":
    main()
