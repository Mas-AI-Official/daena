"""
Voice Configuration for Daena AI VP System
Centralized configuration for voice files, TTS settings, and voice recognition
"""

from pathlib import Path
from typing import List, Dict, Any
import os

# Project root detection
PROJECT_ROOT = Path(__file__).parent.parent.parent
BACKEND_DIR = Path(__file__).parent.parent

# MODELS_ROOT/xtts/voices (shared brain) - used when DAENA_VOICE_WAV not set
def _models_root_xtts_voices():
    try:
        from backend.config.settings import settings
        root = getattr(settings, "models_root", None)
        if root:
            return Path(root) / "xtts" / "voices" / "daena_voice.wav"
    except Exception:
        pass
    return None

# Voice file paths
# NOTE: We prefer MODELS_ROOT/xtts/voices/daena_voice.wav (shared), then repo-root, Voice/, etc.
MODELS_ROOT_VOICE = _models_root_xtts_voices()
VOICE_PATHS = {
    "models_root_xtts": MODELS_ROOT_VOICE,  # Shared brain: MODELS_ROOT/xtts/voices
    "daena_primary": PROJECT_ROOT / "daena_voice.wav",  # Repo root
    "voice_dir": PROJECT_ROOT / "Voice" / "daena_voice.wav",
    "daena_backup": BACKEND_DIR / "daena_voice.wav",
    "static_audio": PROJECT_ROOT / "frontend" / "static" / "audio" / "daena_voice.wav",
    "backend_static": BACKEND_DIR / "static" / "audio" / "daena_voice.wav"
}

# Voice activation phrases
WAKE_WORDS = [
    "Hey Daena",
    "Daena", 
    "Anna",
    "Wake up Daena",
    "Listen Daena"
]

# TTS Configuration
TTS_SETTINGS = {
    "default_rate": 150,      # Words per minute
    "default_volume": 0.8,    # Volume level (0.0 to 1.0)
    "default_pitch": 1.0,     # Pitch multiplier
    "voice_gender": "female",  # Preferred voice gender
    "language": "en-US",       # Language code
    "disable_system_tts": False,  # Enable system TTS as fallback since XTTS might fail
    "prefer_daena_voice": True   # Always prefer Daena's voice file over system TTS
}

# Voice Recognition Settings
SPEECH_RECOGNITION_SETTINGS = {
    "timeout": 1,              # Seconds to wait for speech
    "phrase_time_limit": 3,    # Maximum phrase length
    "ambient_duration": 0.5,   # Seconds to adjust for ambient noise
    "energy_threshold": 4000,  # Minimum audio energy to trigger
    "dynamic_energy_threshold": True
}

# Agent Voice Characteristics
AGENT_VOICES = {
    "engineering": {
        "style": "deep_technical",
        "rate": 140,
        "pitch": 0.9,
        "description": "Technical and analytical"
    },
    "marketing": {
        "style": "enthusiastic", 
        "rate": 160,
        "pitch": 1.1,
        "description": "Enthusiastic and engaging"
    },
    "sales": {
        "style": "confident",
        "rate": 145,
        "pitch": 1.0,
        "description": "Confident and persuasive"
    },
    "finance": {
        "style": "precise",
        "rate": 130,
        "pitch": 0.95,
        "description": "Precise and trustworthy"
    },
    "hr": {
        "style": "warm",
        "rate": 150,
        "pitch": 1.05,
        "description": "Warm and approachable"
    },
    "customer_success": {
        "style": "friendly",
        "rate": 155,
        "pitch": 1.0,
        "description": "Friendly and helpful"
    },
    "product": {
        "style": "innovative",
        "rate": 160,
        "pitch": 1.1,
        "description": "Innovative and creative"
    },
    "operations": {
        "style": "efficient",
        "rate": 140,
        "pitch": 0.95,
        "description": "Efficient and organized"
    }
}

def get_daena_voice_path() -> Path:
    """Get the primary Daena voice file path (prefer MODELS_ROOT/xtts/voices, then repo)."""
    # Explicit override (absolute or relative)
    override = os.getenv("DAENA_VOICE_WAV", "").strip()
    if override:
        p = Path(override)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        if p.exists():
            return p

    for name, path in VOICE_PATHS.items():
        if path is not None and path.exists():
            return path
    
    return VOICE_PATHS["daena_primary"]

def get_voice_file_info() -> Dict[str, Any]:
    """Get information about available voice files"""
    info = {
        "daena_voice_found": False,
        "daena_voice_path": None,
        "available_locations": [],
        "total_size": 0
    }
    
    # Include override location if set
    override = os.getenv("DAENA_VOICE_WAV", "").strip()
    if override:
        p = Path(override)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        if p.exists():
            info["available_locations"].append({
                "name": "DAENA_VOICE_WAV",
                "path": str(p),
                "size": p.stat().st_size,
                "exists": True
            })
            info["daena_voice_found"] = True
            info["daena_voice_path"] = str(p)
            info["total_size"] = p.stat().st_size

    for name, path in VOICE_PATHS.items():
        if path is not None and path.exists():
            info["available_locations"].append({
                "name": name,
                "path": str(path),
                "size": path.stat().st_size,
                "exists": True
            })
            if not info["daena_voice_found"] and name in ("models_root_xtts", "daena_primary"):
                info["daena_voice_found"] = True
                info["daena_voice_path"] = str(path)
                info["total_size"] = path.stat().st_size
    
    return info

def ensure_voice_directory() -> Path:
    """Ensure the voice directory exists and copy daena_voice.wav if needed"""
    voice_dir = PROJECT_ROOT / "Voice"
    voice_dir.mkdir(exist_ok=True)
    
    # If daena_voice.wav exists in root but not in Voice directory, copy it
    root_voice = VOICE_PATHS["daena_primary"]
    voice_dir_voice = voice_dir / "daena_voice.wav"
    
    if root_voice.exists() and not voice_dir_voice.exists():
        import shutil
        try:
            shutil.copy2(root_voice, voice_dir_voice)
            print(f"✅ Copied daena_voice.wav to Voice directory: {voice_dir_voice}")
        except Exception as e:
            print(f"⚠️ Could not copy voice file: {e}")
    
    return voice_dir 