"""
XTTS-v2 TTS Service
Provides text-to-speech with voice cloning using Coqui TTS XTTS-v2
"""
import logging
import os
from pathlib import Path
import functools

# Force torchaudio backend to soundfile to avoid TorchCodec issues in PyTorch 2.6+
os.environ["TORCHAUDIO_BACKEND"] = "soundfile"

import torch

# Apply XTTS Fix for PyTorch 2.6+ and torchaudio 2.9.1+ (must be before TTS import)
try:
    import torch
    import torchaudio
    import soundfile as sf
    import numpy as np
    import functools
    
    # 1. Monkeypatch torch.load to disable weights_only by default
    original_torch_load = torch.load
    @functools.wraps(original_torch_load)
    def patched_torch_load(*args, **kwargs):
        if 'weights_only' not in kwargs:
            kwargs['weights_only'] = False
        return original_torch_load(*args, **kwargs)
    
    torch.load = patched_torch_load
    print("PyTorch 2.6+ weights_only fix applied via monkeypatch")
    
    # 2. Monkeypatch torchaudio.load to use soundfile directly
    # This bypasses the broken torchcodec in torchaudio 2.9.1+
    original_torchaudio_load = torchaudio.load
    @functools.wraps(original_torchaudio_load)
    def patched_torchaudio_load(filepath, *args, **kwargs):
        try:
            data, samplerate = sf.read(filepath)
            # Convert to tensor (channels, samples)
            if len(data.shape) == 1:
                # Mono
                tensor = torch.from_numpy(data).float().unsqueeze(0)
            else:
                # Stereo or more
                tensor = torch.from_numpy(data).float().transpose(0, 1)
            return tensor, samplerate
        except Exception as e:
            # Fallback to original if soundfile fails
            return original_torchaudio_load(filepath, *args, **kwargs)

    torchaudio.load = patched_torchaudio_load
    print("torchaudio.load patched with soundfile")
    
    # Ensure FFmpeg is in PATH for Windows
    ffmpeg_paths = [
        r"C:\ProgramData\chocolatey\bin",
        r"C:\ffmpeg\bin",
        r"C:\Program Files\ffmpeg\bin"
    ]
    for path in ffmpeg_paths:
        if os.path.exists(path) and path not in os.environ["PATH"]:
            os.environ["PATH"] += os.pathsep + path
            print(f"Added {path} to PATH for FFmpeg")
            
except Exception as e:
    print(f"Note: PyTorch/Torchaudio fix failed: {e}")
    pass

from TTS.api import TTS

logger = logging.getLogger(__name__)


class TTSService:
    """Text-to-Speech service using XTTS-v2 with voice cloning"""
    
    def __init__(self, voice_sample_path=None, use_gpu=True):
        """
        Initialize XTTS-v2 model
        
        Args:
            voice_sample_path: Path to reference voice WAV file for cloning
            use_gpu: Whether to use GPU acceleration
        """
        logger.info("Initializing XTTS-v2 TTS service...")
        
        # Set default voice sample
        if voice_sample_path is None:
            # Look for daena_voice.wav in project root
            project_root = Path(__file__).parents[2]
            voice_sample_path = project_root / "daena_voice.wav"
        
        self.voice_sample = str(voice_sample_path)
        
        # Check if voice sample exists
        if not os.path.exists(self.voice_sample):
            logger.warning(f"Voice sample not found: {self.voice_sample}")
            logger.warning("TTS will work but without voice cloning")
        else:
            logger.info(f"Using voice sample: {self.voice_sample}")
        
        # Initialize XTTS-v2 model
        try:
            # Set TTS_HOME to local models directory
            project_root = Path(__file__).parents[2]
            models_dir = project_root / "models" / "tts"
            os.environ["TTS_HOME"] = str(models_dir)
            
            logger.info(f"Loading XTTS-v2 from: {models_dir}")
            
            # XTTS-v2 is multilingual and supports voice cloning
            self.tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=use_gpu)
            logger.info("✅ XTTS-v2 TTS initialized successfully")
            
            # Check GPU availability
            if use_gpu and torch.cuda.is_available():
                logger.info(f"GPU detected: {torch.cuda.get_device_name(0)}")
            elif use_gpu:
                logger.warning("GPU requested but not available, using CPU")
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize XTTS-v2: {e}", exc_info=True)
            raise
    
    def speak(
        self,
        text: str,
        output_path: str = "output.wav",
        language: str = "en",
        speaker_wav: str = None
    ) -> str:
        """
        Generate speech from text using voice cloning
        
        Args:
            text: Text to convert to speech
            output_path: Path to save output WAV file
            language: Language code (en, es, fr, de, it, pt, pl, tr, ru, nl, cs, ar, zh-cn, ja)
            speaker_wav: Optional override voice sample path
        
        Returns:
            Path to generated audio file
        """
        try:
            logger.info(f"Generating speech: '{text[:100]}...' (lang={language})")
            
            # Use provided speaker or default
            voice = speaker_wav or self.voice_sample
            
            # Check if voice cloning is possible
            if not os.path.exists(voice):
                logger.error(f"Voice sample not found: {voice}")
                raise FileNotFoundError(f"Voice sample missing: {voice}")
            
            # Generate speech with XTTS-v2
            self.tts.tts_to_file(
                text=text,
                speaker_wav=voice,
                language=language,
                file_path=output_path
            )
            
            logger.info(f"✅ Speech generated: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"❌ Speech generation failed: {e}", exc_info=True)
            raise
    
    def get_supported_languages(self) -> list:
        """Get list of supported languages"""
        return [
            "en",  # English
            "es",  # Spanish
            "fr",  # French
            "de",  # German
            "it",  # Italian
            "pt",  # Portuguese
            "pl",  # Polish
            "tr",  # Turkish
            "ru",  # Russian
            "nl",  # Dutch
            "cs",  # Czech
            "ar",  # Arabic
            "zh-cn",  # Chinese
            "ja",  # Japanese
        ]
