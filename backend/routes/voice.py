"""
Voice Interaction Routes
Handles voice commands and full voice interaction cycle
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Body
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.voice_command_parser import VoiceCommandParser
from backend.services.llm_service import llm_service
from backend.services.voice_service import voice_service
from backend.database import Project as ProjectDB

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/voice", tags=["voice"])

# Initialize parser
command_parser = VoiceCommandParser()


class VoiceInteractionResponse(BaseModel):
    transcription: str
    response_text: str
    audio_file: Optional[str] = None
    was_command: bool = False
    command: Optional[str] = None
    command_result: Optional[dict] = None

class VoiceSettings(BaseModel):
    volume: Optional[float] = None
    rate: Optional[int] = None
    pitch: Optional[int] = None

@router.get("/status")
async def voice_status():
    """Check voice service status"""
    try:
        status = await voice_service.get_voice_status()
        settings = voice_service.get_voice_settings()
        return {
            "status": "online",
            "service_status": status,
            "settings": settings,
            "talk_active": settings.get("talk_active", False),
            "command_parser": "ready"
        }
    except Exception as e:
        logger.error(f"Voice service check failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "talk_active": False
        }

@router.post("/settings")
async def update_voice_settings(settings: VoiceSettings):
    """Update voice settings (volume, rate, pitch)"""
    result = {}
    if settings.volume is not None:
        result["volume"] = voice_service.set_volume(settings.volume)
    if settings.rate is not None:
        result["rate"] = voice_service.set_rate(settings.rate)
    if settings.pitch is not None:
        result["pitch"] = voice_service.set_pitch(settings.pitch)
    
    return {
        "status": "success",
        "updated": result,
        "current_settings": voice_service.get_voice_settings()
    }

@router.get("/settings")
async def get_voice_settings():
    """Get current voice settings"""
    return voice_service.get_voice_settings()

class VoiceModeRequest(BaseModel):
    enabled: bool

class SpeakRequest(BaseModel):
    text: str

@router.post("/speak")
async def speak_text(request: SpeakRequest):
    """Speak text via TTS (e.g. after chat response when talk mode is on). Respects talk_active."""
    try:
        result = await voice_service.text_to_speech(
            request.text,
            voice_type="daena",
            auto_read=True
        )
        if result and result.get("error"):
            return {"success": False, "error": result["error"]}
        return {"success": True}
    except Exception as e:
        logger.error(f"Speak failed: {e}")
        return {"success": False, "error": str(e)}

@router.post("/talk-mode")
async def set_talk_mode(request: VoiceModeRequest):
    """Enable/disable continuous talk mode. Returns talk_active so frontend stays in sync."""
    result = await voice_service.set_talk_active(request.enabled)
    return { **result, "talk_active": request.enabled }

@router.post("/toggle")
async def toggle_voice(request: VoiceModeRequest = None):
    """Toggle voice on/off - returns structured status"""
    try:
        # Get current status first
        current_status = await voice_service.get_voice_status()
        
        if request and request.enabled is not None:
            new_enabled = request.enabled
        else:
            settings = voice_service.get_voice_settings()
            new_enabled = not settings.get("talk_active", False)
        
        result = await voice_service.set_talk_active(new_enabled)
        
        return {
            "success": True,
            "enabled": new_enabled,
            "mode": "listen" if new_enabled else "off",
            "detail": "Voice enabled" if new_enabled else "Voice disabled",
            "talk_active": new_enabled
        }
    except Exception as e:
        return {
            "success": False,
            "enabled": False,
            "mode": "error",
            "detail": str(e),
            "error": str(e)
        }

@router.get("/self-test")
async def voice_self_test():
    """Dry-run self-test of voice system"""
    results = {"success": True, "checks": [], "issues": []}
    
    # Check if voice service is available
    try:
        status = await voice_service.get_voice_status()
        results["checks"].append({"name": "Voice Service", "status": "ok", "detail": status})
    except Exception as e:
        results["checks"].append({"name": "Voice Service", "status": "error", "detail": str(e)})
        results["issues"].append(f"Voice service error: {e}")
        results["success"] = False
    
    # Check TTS availability
    try:
        # Just check if TTS function exists, don't actually generate audio
        if hasattr(voice_service, 'text_to_speech'):
            results["checks"].append({"name": "TTS Function", "status": "ok"})
        else:
            results["checks"].append({"name": "TTS Function", "status": "missing"})
            results["issues"].append("TTS function not available")
    except Exception as e:
        results["checks"].append({"name": "TTS Function", "status": "error", "detail": str(e)})
        results["issues"].append(f"TTS check error: {e}")
    
    # Check STT availability
    try:
        if hasattr(voice_service, 'speech_to_text'):
            results["checks"].append({"name": "STT Function", "status": "ok"})
        else:
            results["checks"].append({"name": "STT Function", "status": "missing"})
    except Exception as e:
        results["checks"].append({"name": "STT Function", "status": "error", "detail": str(e)})
    
    results["summary"] = f"{len([c for c in results['checks'] if c['status'] == 'ok'])}/{len(results['checks'])} checks passed"
    return results

@router.get("/test")
async def voice_test():
    """Test voice system with sample TTS"""
    try:
        result = await voice_service.text_to_speech(
            "Hello! I am Daena, your AI Vice President. Voice system is working correctly.",
            voice_type="daena",
            auto_read=True
        )
        
        if result and not result.get("error"):
            return {
                "status": "success",
                "message": "Voice test successful",
                "audio_data": result.get("audio_data") # Base64 encoded
            }
        else:
            raise HTTPException(status_code=500, detail=f"TTS test failed: {result.get('error') if result else 'Unknown error'}")
                
    except Exception as e:
        logger.error(f"Voice test failed: {e}")
        raise HTTPException(status_code=500, detail=f"Voice test failed: {str(e)}")


@router.post("/interact", response_model=VoiceInteractionResponse)
async def voice_interact(audio: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Full voice interaction cycle:
    1. Speech-to-text (transcribe user's voice)
    2. Parse command or generate chat response
    3. Execute command if applicable
    4. Text-to-speech (generate voice response)
    """
    try:
        logger.info(f"Voice interaction started: {audio.filename}")
        
        # Step 1: Speech-to-Text
        logger.info("Step 1: Transcribing audio...")
        content = await audio.read()
        user_text = await voice_service.speech_to_text(content)
        
        if not user_text:
            raise HTTPException(status_code=400, detail="No speech detected")
        
        logger.info(f"Transcription: '{user_text}'")
        
        # Step 2: Parse command
        logger.info("Step 2: Parsing command...")
        parsed = command_parser.parse(user_text)
        is_command = parsed["is_command"]
        command = parsed["command"]
        parameters = parsed["parameters"]
        
        # Step 3: Execute command or generate response
        response_text = ""
        command_result = None
        
        if is_command:
            logger.info(f"Executing command: {command} with params: {parameters}")
            command_result, response_text = await execute_voice_command(command, parameters, db)
        else:
            logger.info("No command detected, generating chat response...")
            # Use LLM for general chat
            if llm_service.is_ollama_available():
                response_text = await llm_service.generate_response(user_text, max_tokens=200)
            else:
                response_text = f"I heard you say: '{user_text}'. However, the brain is offline right now. How can I help you?"
        
        # Step 4: Text-to-Speech
        logger.info("Step 4: Generating speech response...")
        # Auto-read response
        tts_result = await voice_service.text_to_speech(response_text, voice_type="daena", auto_read=True)
        audio_file = tts_result.get("audio_data") if tts_result else None
        
        logger.info("Voice interaction complete!")
        
        return VoiceInteractionResponse(
            transcription=user_text,
            response_text=response_text,
            audio_file=audio_file, # Base64
            was_command=is_command,
            command=command if is_command else None,
            command_result=command_result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Voice interaction error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Voice interaction failed: {str(e)}")


async def execute_voice_command(command: str, parameters: dict, db: Session) -> tuple:
    """Execute a voice command and return (result, response_text)"""
    
    if command == "list_projects":
        projects = db.query(ProjectDB).all()
        result = {
            "projects": [{"id": p.id, "name": p.name, "status": p.status} for p in projects]
        }
        response_text = f"You have {len(projects)} projects. "
        if projects:
            response_text += "They are: " + ", ".join([p.name for p in projects[:5]])
        return result, response_text
    
    elif command == "create_project":
        name = parameters.get("name", "Untitled Project")
        project = ProjectDB(name=name, description="Created via voice command", status="active")
        db.add(project)
        db.commit()
        result = {"project_id": project.id, "name": project.name}
        response_text = f"I've created a new project called {name}."
        return result, response_text
    
    elif command == "system_status":
        # Get system health
        from backend.routes.brain import get_brain_status
        brain_status = await get_brain_status()
        result = brain_status
        response_text = f"System status: Brain is {'online' if brain_status.get('connected') else 'offline'}. "
        return result, response_text
    
    elif command == "open_dashboard":
        result = {"action": "navigate", "target": "/ui/dashboard"}
        response_text = "Opening the dashboard now."
        return result, response_text
    
    else:
        # Unknown command - treat as chat
        result = None
        response_text = f"I understood you want to {command}, but I don't know how to do that yet."
        return result, response_text


@router.get("/commands/help")
async def get_voice_commands_help():
    """Get list of available voice commands"""
    return {
        "help_text": command_parser.get_help_text(),
        "commands": list(command_parser.COMMAND_PATTERNS.keys())
    }
