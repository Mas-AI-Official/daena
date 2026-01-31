import os
import torch
import sounddevice as sd
import numpy as np
from pathlib import Path

def _xtts_model_root():
    """Use MODELS_ROOT/xtts from settings when available."""
    try:
        from backend.config.settings import settings
        root = getattr(settings, "xtts_model_path", None) or (Path(getattr(settings, "models_root", "D:/Ideas/MODELS_ROOT")) / "xtts")
        return Path(root)
    except Exception:
        return Path("D:/Ideas/MODELS_ROOT/xtts")

_root = _xtts_model_root()
MODEL_PATH = str(_root / "model.pth")
CONFIG_PATH = str(_root / "config.json")
VOCAB_PATH = str(_root / "vocab.json")
MEL_STATS_PATH = str(_root / "mel_stats.pth")

try:
    from TTS.utils.synthesizer import Synthesizer
    synthesizer = Synthesizer(
        tts_checkpoint=MODEL_PATH,
        tts_config_path=CONFIG_PATH,
        speakers_file_path=VOCAB_PATH,
        use_cuda=torch.cuda.is_available(),
        stats_path=MEL_STATS_PATH
    )
except Exception:
    synthesizer = None

def speak(text):
    if synthesizer is None:
        print("[Daena Voice] TTS not loaded (MODELS_ROOT/xtts or TTS not available)")
        return
    print(f"[Daena Voice]  Speaking: {text}")
    wav = synthesizer.tts(text)
    wav = np.array(wav)
    sd.play(wav, samplerate=22050)
    sd.wait()
