"""
Daena Audio Service - FastAPI Entry Point
Provides TTS and STT services for Daena VP system
"""
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel
import logging
import shutil
import os
from pathlib import Path
import uuid

# Import services
from .stt_service import STTService
from .tts_service import TTSService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Daena Audio Service", version="1.0.0")

# Initialize services (lazy loading)
stt_service = None
tts_service = None


def get_stt_service():
    """Lazy load STT service"""
    global stt_service
    if stt_service is None:
        try:
            stt_service = STTService(model_size="medium", device="cuda", compute_type="float16")
        except Exception as e:
            logger.error(f"Failed to initialize STT service: {e}")
            # Try CPU fallback
            try:
                stt_service = STTService(model_size="medium", device="cpu", compute_type="int8")
            except Exception as e2:
                logger.error(f"CPU fallback also failed: {e2}")
                raise HTTPException(status_code=500, detail="STT service initialization failed")
    return stt_service


def get_tts_service():
    """Lazy load TTS service"""
    global tts_service
    if tts_service is None:
        try:
            tts_service = TTSService(use_gpu=True)
        except Exception as e:
            logger.error(f"Failed to initialize TTS service: {e}")
            raise HTTPException(status_code=500, detail="TTS service initialization failed")
    return tts_service


# Request/Response models
class TTSRequest(BaseModel):
    text: str
    language: str = "en"
    speaker_wav: str = None


class TTSResponse(BaseModel):
    audio_file: str
    message: str = "Speech generated successfully"


class STTResponse(BaseModel):
    text: str
    language: str
    duration: float
    confidence: float = 0.0


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "daena_audio",
        "version": "1.0.0",
        "stt_loaded": stt_service is not None,
        "tts_loaded": tts_service is not None
    }


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Daena Audio Service",
        "endpoints": {
            "health": "/health",
            "stt": "/api/stt/transcribe",
            "tts": "/api/tts/speak",
            "docs": "/docs"
        }
    }


@app.post("/api/stt/transcribe", response_model=STTResponse)
async def transcribe_audio(audio: UploadFile = File(...), language: str = None):
    """
    Speech-to-text endpoint
    
    Accepts audio file upload and returns transcription
    """
    try:
        # Get STT service
        stt = get_stt_service()
        
        # Save uploaded file temporarily
        temp_dir = Path("temp")
        temp_dir.mkdir(exist_ok=True)
        
        temp_path = temp_dir / f"{uuid.uuid4()}_{audio.filename}"
        
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(audio.file, buffer)
        
        logger.info(f"Transcribing audio: {audio.filename}")
        
        # Transcribe
        result = stt.transcribe(str(temp_path), language=language)
        
        # Clean up temp file
        try:
            os.remove(temp_path)
        except:
            pass
        
        return STTResponse(
            text=result.get("text", ""),
            language=result.get("language", "unknown"),
            duration=result.get("duration", 0.0),
            confidence=result.get("language_probability", 0.0)
        )
        
    except Exception as e:
        logger.error(f"Transcription error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")


@app.post("/api/tts/speak", response_model=TTSResponse)
async def generate_speech(request: TTSRequest):
    """
    Text-to-speech endpoint
    
    Accepts text and returns audio file path
    """
    try:
        # Get TTS service
        tts = get_tts_service()
        
        # Generate output filename
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        
        output_filename = f"speech_{uuid.uuid4()}.wav"
        output_path = output_dir / output_filename
        
        logger.info(f"Generating speech: '{request.text[:100]}...'")
        
        # Generate speech
        tts.speak(
            text=request.text,
            output_path=str(output_path),
            language=request.language,
            speaker_wav=request.speaker_wav
        )
        
        return TTSResponse(
            audio_file=str(output_path),
            message="Speech generated successfully"
        )
        
    except Exception as e:
        logger.error(f"TTS error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Speech generation failed: {str(e)}")


@app.get("/api/tts/audio/{filename}")
async def get_audio_file(filename: str):
    """Serve generated audio file"""
    try:
        output_path = Path("output") / filename
        
        if not output_path.exists():
            raise HTTPException(status_code=404, detail="Audio file not found")
        
        return FileResponse(
            path=str(output_path),
            media_type="audio/wav",
            filename=filename
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving audio: {e}")
        raise HTTPException(status_code=500, detail="Failed to serve audio file")


@app.get("/api/tts/languages")
async def get_supported_languages():
    """Get list of supported TTS languages"""
    try:
        tts = get_tts_service()
        return {"languages": tts.get_supported_languages()}
    except Exception as e:
        logger.error(f"Error getting languages: {e}")
        raise HTTPException(status_code=500, detail="Failed to get languages")


if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Daena Audio Service on http://0.0.0.0:5001")
    uvicorn.run(app, host="0.0.0.0", port=5001)
