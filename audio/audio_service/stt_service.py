"""
Faster-Whisper STT Service
Provides speech-to-text using faster-whisper (4x faster than OpenAI Whisper)
"""
from faster_whisper import WhisperModel
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class STTService:
    """Speech-to-Text service using faster-whisper"""
    
    def __init__(self, model_size="medium", device="cuda", compute_type="float16"):
        """
        Initialize faster-whisper model
        
        Args:
            model_size: tiny, base, small, medium, large-v2, large-v3
            device: cuda or cpu
            compute_type: float16 (GPU) or int8 (CPU)
        """
        logger.info(f"Initializing faster-whisper STT: model={model_size}, device={device}")
        
        try:
            # Look for local model first
            project_root = Path(__file__).parents[2]
            local_model_path = project_root / "models" / "stt" / model_size
            
            model_to_load = str(local_model_path) if local_model_path.exists() else model_size
            if local_model_path.exists():
                logger.info(f"Loading local STT model from: {local_model_path}")
            
            self.model = WhisperModel(model_to_load, device=device, compute_type=compute_type)
            logger.info("✅ faster-whisper STT initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize faster-whisper: {e}")
            # Fallback to CPU
            logger.warning("Falling back to CPU mode...")
            self.model = WhisperModel(model_size, device="cpu", compute_type="int8")
    
    def transcribe(self, audio_path: str, language: str = None) -> dict:
        """
        Transcribe audio file to text
        
        Args:
            audio_path: Path to audio file (wav, mp3, etc.)
            language: Optional language code (e.g., 'en', 'es')
        
        Returns:
            dict with 'text', 'language', 'duration', 'segments'
        """
        try:
            logger.info(f"Transcribing audio: {audio_path}")
            
            # Transcribe with faster-whisper
            segments, info = self.model.transcribe(
                audio_path,
                beam_size=5,
                language=language,
                vad_filter=True,  # Voice Activity Detection
                vad_parameters=dict(min_silence_duration_ms=500)
            )
            
            # Collect all segments
            segment_list = []
            full_text = []
            
            for segment in segments:
                segment_list.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip()
                })
                full_text.append(segment.text.strip())
            
            result = {
                "text": " ".join(full_text),
                "language": info.language,
                "language_probability": info.language_probability,
                "duration": info.duration,
                "segments": segment_list
            }
            
            logger.info(f"✅ Transcription complete: {len(full_text)} segments, language={info.language}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Transcription failed: {e}", exc_info=True)
            return {
                "text": "",
                "language": "unknown",
                "error": str(e)
            }
    
    def transcribe_stream(self, audio_stream):
        """Real-time transcription from audio stream (future implementation)"""
        # TODO: Implement streaming transcription
        raise NotImplementedError("Streaming transcription not yet implemented")
