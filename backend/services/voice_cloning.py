"""
Voice Cloning Service for Daena AI VP System
Uses ElevenLabs API for voice cloning and TTS generation
"""

import os
import logging
import asyncio
import aiofiles
from pathlib import Path
from typing import Optional, Dict, Any, List
import base64

logger = logging.getLogger(__name__)

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    aiohttp = None
    AIOHTTP_AVAILABLE = False

class VoiceCloningService:
    """Service for voice cloning using ElevenLabs API"""
    
    def __init__(self):
        # Get API key from environment or settings
        self.api_key = os.getenv("ELEVENLABS_API_KEY", "")
        if not self.api_key:
            # Try to get from settings
            try:
                from backend.config.settings import settings
                self.api_key = getattr(settings, 'elevenlabs_api_key', '') or ''
            except:
                pass
        
        # Also try reading from config file directly
        if not self.api_key:
            try:
                config_file = Path("config/production.env")
                if config_file.exists():
                    with open(config_file, 'r') as f:
                        for line in f:
                            if line.startswith("ELEVENLABS_API_KEY="):
                                self.api_key = line.split("=", 1)[1].strip()
                                break
            except:
                pass
        
        self.api_url = "https://api.elevenlabs.io/v1"
        self.voice_id = None
        self.agent_voices: Dict[str, str] = {}  # agent_name -> voice_id
        self.agent_voice_configs: Dict[str, Dict[str, Any]] = {}
        # Find daena_voice.wav in multiple locations
        from backend.config.voice_config import get_daena_voice_path
        self.daena_voice_path = get_daena_voice_path()
        
        # Initialize voice cloning (async will be called separately)
        self._initialized = False
        self._available = AIOHTTP_AVAILABLE
        if not self._available:
            logger.info("🔇 Voice cloning disabled (missing dependency: aiohttp). Install the audio environment to enable.")
    
    async def initialize_voices(self):
        """Initialize voice cloning for Daena and agents (async)"""
        if not self._available:
            self._initialized = True
            return
        if self._initialized:
            logger.debug("Voice cloning already initialized")
            return
        
        # Re-check API key
        if not self.api_key:
            # Try to get from environment again
            self.api_key = os.getenv("ELEVENLABS_API_KEY", "")
            if not self.api_key:
                try:
                    from backend.config.settings import settings
                    self.api_key = getattr(settings, 'elevenlabs_api_key', '') or ''
                except:
                    pass
        
        
        # Check if API key is valid (not placeholder)
        if not self.api_key or self.api_key == "your_elevenlabs_api_key_here":
            logger.info("🔇 ElevenLabs voice cloning disabled (no API key configured)")
            logger.info("💡 Using local XTTS-v2 audio service instead (http://127.0.0.1:5001)")
            logger.info("💡 To enable ElevenLabs cloud TTS, set ELEVENLABS_API_KEY in .env")
            self._initialized = True
            return
        
        try:
            # Re-check voice file path
            if not self.daena_voice_path or not self.daena_voice_path.exists():
                from backend.config.voice_config import get_daena_voice_path
                self.daena_voice_path = get_daena_voice_path()
            
            # Clone Daena's voice from daena_voice.wav
            if self.daena_voice_path and self.daena_voice_path.exists():
                logger.info(f"🎤 Found Daena voice file: {self.daena_voice_path}")
                logger.info(f"📁 File size: {self.daena_voice_path.stat().st_size} bytes")
                
                self.voice_id = await self._clone_voice(
                    name="Daena AI VP",
                    description="Daena AI VP - Main voice cloned from daena_voice.wav",
                    voice_file=self.daena_voice_path
                )
                if self.voice_id:
                    logger.info(f"✅ Daena voice cloned successfully: {self.voice_id}")
                else:
                    logger.warning("⚠️ Voice cloning failed - will use fallback")
                    # Try to get existing voice if clone failed
                    existing_voices = await self.get_voices()
                    daena_voice = next((v for v in existing_voices if "Daena" in v.get("name", "")), None)
                    if daena_voice:
                        self.voice_id = daena_voice.get("voice_id")
                        logger.info(f"✅ Using existing Daena voice: {self.voice_id}")
            else:
                logger.warning(f"⚠️ Daena voice file not found: {self.daena_voice_path}")
                logger.info("💡 Place daena_voice.wav in Voice/ directory for voice cloning")
                # Try to get existing voice if file not found
                existing_voices = await self.get_voices()
                daena_voice = next((v for v in existing_voices if "Daena" in v.get("name", "")), None)
                if daena_voice:
                    self.voice_id = daena_voice.get("voice_id")
                    logger.info(f"✅ Using existing Daena voice: {self.voice_id}")
            
            # Create agent voices (different variations)
            self._create_agent_voices()
            self._initialized = True
            logger.info("✅ Voice cloning initialization complete")
            
        except Exception as e:
            logger.error(f"❌ Error initializing voice cloning: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            logger.info("💡 Voice cloning will use fallback methods")
            self._initialized = True
    
    async def _clone_voice(self, name: str, description: str, voice_file: Path) -> Optional[str]:
        """Clone a voice from a WAV file using ElevenLabs API"""
        if not self._available:
            return None
        if not self.api_key:
            return None
        
        try:
            # Read the voice file
            async with aiofiles.open(voice_file, 'rb') as f:
                voice_data = await f.read()
            
            # Create voice clone
            url = f"{self.api_url}/voices/add"
            headers = {
                "xi-api-key": self.api_key
            }
            
            data = aiohttp.FormData()
            data.add_field('name', name)
            data.add_field('description', description)
            data.add_field('files', voice_data, filename=voice_file.name, content_type='audio/wav')
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, data=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        voice_id = result.get("voice_id")
                        logger.info(f"✅ Voice cloned: {name} -> {voice_id}")
                        return voice_id
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Voice cloning failed: {response.status} - {error_text}")
                        return None
                        
        except Exception as e:
            logger.error(f"❌ Error cloning voice: {e}")
            return None
    
    def _create_agent_voices(self):
        """Create different voices for different agents"""
        # Use Daena's voice as base but with different settings for each agent
        # In production, you could clone different voice samples for each agent
        
        agent_voice_configs = {
            "engineering": {
                "name": "Engineering Agent",
                "description": "Technical, precise voice for engineering department",
                "stability": 0.5,
                "similarity_boost": 0.75
            },
            "product": {
                "name": "Product Agent",
                "description": "Friendly, customer-focused voice for product department",
                "stability": 0.6,
                "similarity_boost": 0.8
            },
            "marketing": {
                "name": "Marketing Agent",
                "description": "Energetic, persuasive voice for marketing department",
                "stability": 0.7,
                "similarity_boost": 0.75
            },
            "sales": {
                "name": "Sales Agent",
                "description": "Confident, professional voice for sales department",
                "stability": 0.6,
                "similarity_boost": 0.8
            },
            "finance": {
                "name": "Finance Agent",
                "description": "Calm, analytical voice for finance department",
                "stability": 0.5,
                "similarity_boost": 0.7
            },
            "hr": {
                "name": "HR Agent",
                "description": "Warm, empathetic voice for HR department",
                "stability": 0.65,
                "similarity_boost": 0.8
            },
            "legal": {
                "name": "Legal Agent",
                "description": "Formal, authoritative voice for legal department",
                "stability": 0.5,
                "similarity_boost": 0.7
            },
            "operations": {
                "name": "Operations Agent",
                "description": "Efficient, clear voice for operations department",
                "stability": 0.6,
                "similarity_boost": 0.75
            }
        }
        
        # Store agent voice configs (will use same voice_id but different settings)
        self.agent_voice_configs = agent_voice_configs
        
        # For now, use Daena's voice for all agents but with different settings
        # In production, you could clone separate voices for each agent
        for agent_name in agent_voice_configs.keys():
            self.agent_voices[agent_name] = self.voice_id  # Use Daena's voice ID
    
    async def text_to_speech(
        self,
        text: str,
        voice_type: str = "daena",
        agent_name: Optional[str] = None,
        stability: Optional[float] = None,
        similarity_boost: Optional[float] = None,
        style: float = 0.0,
        use_speaker_boost: bool = True
    ) -> Optional[bytes]:
        """
        Generate speech using cloned voice
        
        Args:
            text: Text to convert to speech
            voice_type: Type of voice (daena, agent)
            agent_name: Name of agent (for agent-specific voice)
            stability: Voice stability (0.0-1.0)
            similarity_boost: Similarity boost (0.0-1.0)
            style: Style setting (0.0-1.0)
            use_speaker_boost: Use speaker boost for clarity
            
        Returns:
            Audio data as bytes
        """
        if not self._available:
            return None
        if not self.api_key:
            logger.warning("⚠️ ElevenLabs API key not configured")
            return None
        
        # Initialize if not already done
        if not self._initialized:
            await self.initialize_voices()
        
        # Select voice ID
        if voice_type == "daena":
            voice_id = self.voice_id
            # Use optimal settings for Daena
            if stability is None:
                stability = 0.5
            if similarity_boost is None:
                similarity_boost = 0.75
        elif voice_type == "agent" and agent_name:
            voice_id = self.agent_voices.get(agent_name, self.voice_id)
            # Get agent-specific settings
            if agent_name in self.agent_voice_configs:
                config = self.agent_voice_configs[agent_name]
                if stability is None:
                    stability = config.get("stability", 0.5)
                if similarity_boost is None:
                    similarity_boost = config.get("similarity_boost", 0.75)
            else:
                if stability is None:
                    stability = 0.5
                if similarity_boost is None:
                    similarity_boost = 0.75
        else:
            voice_id = self.voice_id  # Default to Daena's voice
            if stability is None:
                stability = 0.5
            if similarity_boost is None:
                similarity_boost = 0.75
        
        if not voice_id:
            logger.warning("⚠️ Voice ID not available")
            return None
        
        try:
            url = f"{self.api_url}/text-to-speech/{voice_id}"
            headers = {
                "xi-api-key": self.api_key,
                "Content-Type": "application/json"
            }
            
            # Optimize settings for natural sound
            data = {
                "text": text,
                "model_id": "eleven_multilingual_v2",  # Best quality model
                "voice_settings": {
                    "stability": stability,
                    "similarity_boost": similarity_boost,
                    "style": style,
                    "use_speaker_boost": use_speaker_boost
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=data) as response:
                    if response.status == 200:
                        audio_data = await response.read()
                        logger.info(f"✅ TTS generated successfully ({len(audio_data)} bytes)")
                        return audio_data
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ TTS generation failed: {response.status} - {error_text}")
                        return None
                        
        except Exception as e:
            logger.error(f"❌ Error generating TTS: {e}")
            return None
    
    async def get_voices(self) -> List[Dict[str, Any]]:
        """Get list of all cloned voices"""
        if not self._available:
            return []
        if not self.api_key:
            return []
        
        try:
            url = f"{self.api_url}/voices"
            headers = {
                "xi-api-key": self.api_key
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get("voices", [])
                    else:
                        logger.error(f"❌ Failed to get voices: {response.status}")
                        return []
                        
        except Exception as e:
            logger.error(f"❌ Error getting voices: {e}")
            return []
    
    def get_voice_id(self, voice_type: str = "daena", agent_name: Optional[str] = None) -> Optional[str]:
        """Get voice ID for a specific voice type or agent"""
        if voice_type == "daena":
            return self.voice_id
        elif voice_type == "agent" and agent_name:
            return self.agent_voices.get(agent_name, self.voice_id)
        return self.voice_id
    
    def is_available(self) -> bool:
        """Check if voice cloning is available"""
        return bool(self._available and self.api_key and self.voice_id)

# Global instance
voice_cloning_service = VoiceCloningService()

