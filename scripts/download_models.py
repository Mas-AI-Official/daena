# scripts/download_models.py
import os
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = ROOT / "models"
WHISPER_DIR = MODELS_DIR / "faster-whisper-medium"
XTTS_MARKER = MODELS_DIR / "xtts_v2" / ".download_ok"

def set_local_caches():
    # Force HF/Transformers/TTS caches into the project folder (no C:\Users\...\cache surprises)
    os.environ["HF_HOME"] = str(MODELS_DIR / "hf_home")
    os.environ["TRANSFORMERS_CACHE"] = str(MODELS_DIR / "hf_home")  # backward compat
    os.environ["XDG_CACHE_HOME"] = str(MODELS_DIR / "xdg_cache")
    os.environ["COQUI_TTS_HOME"] = str(MODELS_DIR / "coqui_tts")
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

def download_faster_whisper():
    try:
        from faster_whisper import WhisperModel
    except Exception as e:
        logging.error("faster-whisper import failed. Install it first: pip install faster-whisper")
        raise

    if WHISPER_DIR.exists() and any(WHISPER_DIR.iterdir()):
        logging.info("✅ Faster-Whisper (medium) already exists")
        return

    logging.info("⬇️ Downloading Faster-Whisper (medium)...")
    # This will download into HF_HOME; we keep a marker folder for your sanity.
    WhisperModel("medium", device="cpu", compute_type="int8")
    WHISPER_DIR.mkdir(parents=True, exist_ok=True)
    (WHISPER_DIR / ".download_ok").write_text("ok", encoding="utf-8")
    logging.info("✅ Faster-Whisper downloaded")

def download_xtts_v2():
    try:
        from TTS.api import TTS
    except Exception as e:
        logging.error("TTS import failed. Fix your versions. Error: %s", e)
        raise

    if XTTS_MARKER.exists():
        logging.info("✅ XTTS-v2 already marked as downloaded")
        return

    logging.info("⬇️ Downloading XTTS-v2 (this can take a while)...")
    # This triggers Coqui's download into COQUI_TTS_HOME
    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=False)
    target = MODELS_DIR / "xtts_v2"
    target.mkdir(parents=True, exist_ok=True)
    XTTS_MARKER.parent.mkdir(parents=True, exist_ok=True)
    XTTS_MARKER.write_text("ok", encoding="utf-8")
    logging.info("✅ XTTS-v2 download complete")

def main():
    set_local_caches()
    logging.info("Downloading models to: %s", MODELS_DIR)
    download_faster_whisper()
    download_xtts_v2()
    logging.info("✅ All model downloads done.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.error("❌ download_models failed: %s", e)
        sys.exit(1)
