"""
Voice Service for Daena AI VP System
Handles text-to-speech, speech recognition, and voice activation
"""

import asyncio
import json
import logging
import base64
import io
from typing import Dict, List, Optional, Union, BinaryIO, Any
from enum import Enum
import aiofiles
import tempfile
import os
from pathlib import Path
import threading
import time

logger = logging.getLogger(__name__)

# Try to import voice libraries
try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from backend.config.settings import settings
from backend.config.voice_config import (
    WAKE_WORDS, 
    TTS_SETTINGS, 
    SPEECH_RECOGNITION_SETTINGS,
    AGENT_VOICES,
    get_daena_voice_path,
    get_voice_file_info,
    ensure_voice_directory
)

# Import voice cloning and awakening services
try:
    from backend.services.voice_cloning import voice_cloning_service
    VOICE_CLONING_AVAILABLE = True
except Exception as e:
    VOICE_CLONING_AVAILABLE = False
    voice_cloning_service = None
    logger.warning(f"⚠️ Voice cloning service not available: {e}")

try:
    from backend.services.voice_awakening import voice_awakening
    VOICE_AWAKENING_AVAILABLE = True
except Exception as e:
    VOICE_AWAKENING_AVAILABLE = False
    voice_awakening = None
    logger.warning(f"⚠️ Voice awakening service not available: {e}")

class VoiceProvider(str, Enum):
    ELEVENLABS = "elevenlabs"
    GOOGLE_TTS = "google_tts"
    SYSTEM_TTS = "system_tts"

class VoiceService:
    def __init__(self):
        self.enabled = settings.voice_enabled if hasattr(settings, 'voice_enabled') else True
        self.activation_phrases = WAKE_WORDS
        
        # Global voice control states
        self.voice_active = False  # Wake word listening
        self.talk_active = False   # Daena speaks responses
        self.agents_talk_active = False  # Agents speak responses
        self._speech_stopped = False  # Flag for interruption
        
        # Wake word detection
        self.wake_word_listener = None
        self.is_listening = False
        self.wake_word_thread = None
        
        # Initialize speech recognition
        if SPEECH_RECOGNITION_AVAILABLE:
            try:
                self.recognizer = sr.Recognizer()
                self.microphone = sr.Microphone()
                logger.info("✅ Speech recognition initialized")
            except Exception as e:
                logger.warning(f"⚠️ Speech recognition initialization failed: {e}")
                self.recognizer = None
                self.microphone = None
        else:
            logger.warning("⚠️ Speech recognition not available. Install: pip install SpeechRecognition pyaudio")
            self.recognizer = None
            self.microphone = None
        
        # Initialize TTS engine (disabled by default to prevent computer voice conflicts)
        if PYTTSX3_AVAILABLE and not TTS_SETTINGS.get("disable_system_tts", True):
            try:
                self.tts_engine = pyttsx3.init()
                self.tts_engine.setProperty('rate', TTS_SETTINGS["default_rate"])
                self.tts_engine.setProperty('volume', TTS_SETTINGS["default_volume"])
                self.tts_engine.setProperty('pitch', TTS_SETTINGS["default_pitch"])
                voices = self.tts_engine.getProperty('voices')
                if voices and len(voices) > 1:
                    # Try to use a female voice if available
                    self.tts_engine.setProperty('voice', voices[1].id)
                logger.info("✅ System TTS initialized")
            except Exception as e:
                logger.error(f"❌ System TTS initialization failed: {e}")
                self.tts_engine = None
        else:
            if TTS_SETTINGS.get("disable_system_tts", True):
                logger.info("🔇 System TTS disabled to prevent computer voice conflicts")
            else:
                logger.warning("⚠️ System TTS not available. Install: pip install pyttsx3")
            if TTS_SETTINGS.get("disable_system_tts", True):
                logger.info("🔇 System TTS disabled to prevent computer voice conflicts")
            else:
                logger.warning("⚠️ System TTS not available. Install: pip install pyttsx3")
            self.tts_engine = None
        
        # Default settings
        self.volume = TTS_SETTINGS.get("default_volume", 1.0)
        self.rate = TTS_SETTINGS.get("default_rate", 150)
        self.pitch = TTS_SETTINGS.get("default_pitch", 100)
        
        self.available = self._check_availability()
        self.daena_voice_path = self._find_daena_voice()
        
        # Initialize voice cloning and awakening
        if VOICE_CLONING_AVAILABLE:
            logger.info("✅ Voice cloning service available")
        if VOICE_AWAKENING_AVAILABLE:
            logger.info("✅ Voice awakening service available")
            # Set up wake word callback
            voice_awakening.set_activation_callback(self.on_wake_word_detected)
    
    def _check_availability(self) -> bool:
        """Check if voice services are available"""
        try:
            # Check for basic voice capabilities
            return True
        except Exception as e:
            logger.warning(f"Voice service not available: {e}")
            return False
    
    def _find_daena_voice(self) -> Optional[Path]:
        """Find Daena's voice file using centralized configuration"""
        try:
            # Ensure voice directory exists and copy file if needed
            ensure_voice_directory()
            
            # Get the primary voice file path
            voice_path = get_daena_voice_path()
            
            if voice_path.exists():
                logger.info(f"✅ Found Daena voice file: {voice_path}")
                return voice_path
            else:
                logger.warning("⚠️ Daena voice file not found")
                return None
                
        except Exception as e:
            logger.error(f"Error finding Daena voice file: {e}")
            return None

    # Global Voice Control Methods
    async def set_voice_active(self, active: bool) -> Dict[str, Any]:
        """Enable/disable wake word detection"""
        self.voice_active = active
        
        if active:
            await self.start_wake_word_detection()
            logger.info("🎤 Wake word detection activated")
            return {"status": "activated", "message": "Voice listening activated. Say 'Hey Daena' to activate me."}
        else:
            await self.stop_wake_word_detection()
            logger.info("🎤 Wake word detection deactivated")
            return {"status": "deactivated", "message": "Voice listening deactivated."}
    
    async def set_talk_active(self, active: bool) -> Dict[str, Any]:
        """Enable/disable Daena's speech output"""
        self.talk_active = active
        
        if active:
            logger.info("🗣️ Daena talk mode activated")
            return {"status": "activated", "message": "Talk mode activated. I will speak my responses."}
        else:
            logger.info("🗣️ Daena talk mode deactivated")
            return {"status": "deactivated", "message": "Talk mode deactivated. I will only type responses."}
    
    async def set_agents_talk_active(self, active: bool) -> Dict[str, Any]:
        """Enable/disable agents' speech output"""
        self.agents_talk_active = active
        
        if active:
            logger.info("👥 Agents talk mode activated")
            return {"status": "activated", "message": "Agents talk mode activated. All agents will speak their responses."}
        else:
            logger.info("👥 Agents talk mode deactivated")
            return {"status": "deactivated", "message": "Agents talk mode deactivated. Agents will only type responses."}
    
    async def start_wake_word_detection(self):
        """Start listening for wake words"""
        if not SPEECH_RECOGNITION_AVAILABLE:
            logger.error("Speech recognition not available")
            return
        
        if self.is_listening:
            return
        
        self.is_listening = True
        
        def wake_word_loop():
            while self.is_listening and self.voice_active:
                try:
                    with self.microphone as source:
                        self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                        audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=3)
                    
                    text = self.recognizer.recognize_google(audio).lower()
                    logger.info(f"🎤 Heard: {text}")
                    
                    # Check for wake words
                    for phrase in self.activation_phrases:
                        if phrase.lower() in text:
                            logger.info(f"🎤 Wake word detected: {phrase}")
                            asyncio.run(self.on_wake_word_detected())
                            break
                            
                except sr.WaitTimeoutError:
                    continue
                except sr.UnknownValueError:
                    continue
                except Exception as e:
                    logger.error(f"Wake word detection error: {e}")
                    time.sleep(0.1)
        
        self.wake_word_thread = threading.Thread(target=wake_word_loop, daemon=True)
        self.wake_word_thread.start()
    
    async def stop_wake_word_detection(self):
        """Stop listening for wake words"""
        self.is_listening = False
        if self.wake_word_thread:
            self.wake_word_thread.join(timeout=1)
    
    async def on_wake_word_detected(self):
        """Handle wake word detection"""
        logger.info("🎤 Wake word detected - starting active listening")
        
        # Speak confirmation if talk is active
        if self.talk_active:
            await self.text_to_speech("Yes?", "daena", auto_read=True)
        
        # Start active listening for command
        command = await self.start_active_listening()
        
        # Process the command if we got one
        if command:
            await self.process_voice_command_text(command)
    
    def stop_current_speech(self):
        """Stop any current speech output (for interrupt mode)"""
        try:
            if hasattr(self, '_current_audio_thread') and self._current_audio_thread:
                self._current_audio_thread.stop()
                self._current_audio_thread = None
            logger.info("🔇 Speech interrupted")
        except Exception as e:
            logger.error(f"Error stopping speech: {e}")
    
    def is_speaking(self) -> bool:
        """Check if Daena is currently speaking"""
        return hasattr(self, '_current_audio_thread') and self._current_audio_thread and self._current_audio_thread.is_alive()
    
    async def start_active_listening(self, timeout: int = 10) -> Optional[str]:
        """Listen for voice command after wake word"""
        if not SPEECH_RECOGNITION_AVAILABLE or not self.microphone or not self.recognizer:
            logger.warning("🎤 Speech recognition not available for active listening")
            return None
        
        try:
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=15)
            
            text = self.recognizer.recognize_google(audio)
            logger.info(f"🎤 Command received: {text}")
            return text
            
        except sr.WaitTimeoutError:
            logger.info("🎤 No command received within timeout")
            return None
        except sr.UnknownValueError:
            logger.info("🎤 Could not understand command")
            return None
        except Exception as e:
            logger.error(f"Active listening error: {e}")
            return None

    # Enhanced TTS with voice control
    async def text_to_speech(self, text: str, voice_type: str = "daena", agent_name: Optional[str] = None, auto_read: bool = False) -> Optional[Dict[str, Any]]:
        """
        Convert text to speech with voice control
        
        Args:
            text: Text to convert to speech
            voice_type: Type of voice to use (daena, agent, etc.)
            auto_read: Whether to automatically play the audio
            
        Returns:
            Dict containing audio data and metadata
        """
        if not text.strip():
            return None
        
        try:
            # Check if speech is enabled based on voice type
            if voice_type == "daena" and not self.talk_active:
                logger.info("🗣️ Daena talk mode disabled - skipping speech")
                return {"text": text, "speech_enabled": False}
            
            if voice_type == "agent" and not self.agents_talk_active:
                logger.info("👥 Agents talk mode disabled - skipping speech")
                return {"text": text, "speech_enabled": False}
            
            # Generate speech with agent name if provided
            audio_data = await self._generate_speech(text, voice_type=voice_type, agent_name=agent_name)
            
            if audio_data:
                result = {
                    "text": text,
                    "audio_data": base64.b64encode(audio_data).decode('utf-8'),
                    "voice_type": voice_type,
                    "speech_enabled": True,
                    "timestamp": time.time()
                }
                
                # Auto-play if requested
                if auto_read:
                    # Stop any current speech if interrupt mode is enabled
                    if self.is_speaking():
                        self.stop_current_speech()
                    
                    # Play audio in background thread
                    self._current_audio_thread = threading.Thread(
                        target=self._play_audio_sync, 
                        args=(audio_data,)
                    )
                    self._current_audio_thread.start()
                
                return result
            else:
                return {"text": text, "speech_enabled": False, "error": "Failed to generate speech"}
                
        except Exception as e:
            logger.error(f"TTS error: {e}")
            return {"text": text, "speech_enabled": False, "error": str(e)}

    async def _generate_speech(self, text: str, voice_type: str = "daena", agent_name: Optional[str] = None) -> Optional[bytes]:
        """Generate speech using available TTS engines with voice cloning"""
        try:
            # Priority 1: Use ElevenLabs voice cloning (best quality, natural sound)
            if REQUESTS_AVAILABLE:
                elevenlabs_audio = await self._elevenlabs_tts(text, voice_type=voice_type, agent_name=agent_name)
                if elevenlabs_audio:
                    logger.info(f"✅ Using ElevenLabs voice cloning for {voice_type}")
                    return elevenlabs_audio
            
            # Priority 2: Use XTTSv2 or TTS library with daena_voice.wav (proper TTS with voice cloning)
            if self.daena_voice_path and self.daena_voice_path.exists():
                xtts_audio = await self._xtts_tts(text, voice_file=self.daena_voice_path)
                if xtts_audio:
                    logger.info(f"✅ Using XTTSv2 with Daena's voice file for {voice_type}")
                    return xtts_audio
            
            # Priority 3: Try Google TTS as fallback
            if REQUESTS_AVAILABLE:
                google_audio = await self._google_tts(text)
                if google_audio:
                    logger.info("✅ Using Google TTS")
                    return google_audio
            
            # Priority 4: System TTS disabled to prevent computer voice conflicts
            # This was causing the computer voice to turn off
            if PYTTSX3_AVAILABLE and self.tts_engine:
                logger.info("🔊 System TTS disabled to prevent computer voice conflicts")
                return None
            
            logger.warning("⚠️ No TTS provider available")
            return None
            
        except Exception as e:
            logger.error(f"❌ Speech generation error: {e}")
            return None
    
    async def _xtts_tts(self, text: str, voice_file: Path) -> Optional[bytes]:
        """Generate speech using XTTSv2 or TTS library with voice file"""
        try:
            # Try to use TTS library with XTTS model
            try:
                from TTS.api import TTS
                import numpy as np
                import wave
                import io
                
                # Initialize XTTS model
                # FIX: Allow XttsConfig for torch 2.6+
                try:
                    import torch
                    from TTS.tts.configs.xtts_config import XttsConfig
                    torch.serialization.add_safe_globals([XttsConfig])
                except Exception as e:
                    logger.warning(f"Could not apply torch safe globals fix: {e}")

                tts_model = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2", gpu=False)
                
                # Generate speech using daena_voice.wav as reference
                wav = tts_model.tts(
                    text=text,
                    speaker_wav=str(voice_file),
                    language="en"
                )
                
                # Convert to bytes
                wav_np = np.array(wav)
                wav_int16 = (wav_np * 32767).astype(np.int16)
                
                # Create WAV file in memory
                wav_buffer = io.BytesIO()
                with wave.open(wav_buffer, 'wb') as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(22050)
                    wf.writeframes(wav_int16.tobytes())
                
                wav_buffer.seek(0)
                return wav_buffer.read()
                
            except ImportError:
                logger.warning("⚠️ TTS library not available. Install: pip install TTS")
                return None
            except Exception as e:
                logger.warning(f"⚠️ XTTS generation failed: {e}")
                return None
                
        except Exception as e:
            logger.error(f"❌ XTTS TTS error: {e}")
            return None
    
    async def _system_tts(self, text: str) -> Optional[bytes]:
        """Generate speech using system TTS engine"""
        try:
            if not self.tts_engine:
                return None
            
            # Create temporary file for TTS output
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_path = temp_file.name
            
            # Generate speech
            self.tts_engine.save_to_file(text, temp_path)
            self.tts_engine.runAndWait()
            
            # Read the generated audio
            with open(temp_path, 'rb') as f:
                audio_data = f.read()
            
            # Clean up temporary file
            os.unlink(temp_path)
            
            return audio_data
            
        except Exception as e:
            logger.error(f"System TTS error: {e}")
            return None

    async def _elevenlabs_tts(self, text: str, voice_type: str = "daena", agent_name: Optional[str] = None) -> Optional[bytes]:
        """Generate speech using ElevenLabs TTS with voice cloning"""
        try:
            # Import voice cloning service
            from backend.services.voice_cloning import voice_cloning_service
            
            # Initialize if not already done
            if not voice_cloning_service._initialized:
                logger.info("🎤 Initializing voice cloning service...")
                await voice_cloning_service.initialize_voices()
            
            if not voice_cloning_service.is_available():
                logger.warning("⚠️ Voice cloning service not available (check API key and voice file)")
                return None
            
            # Generate speech using cloned voice
            audio_data = await voice_cloning_service.text_to_speech(
                text=text,
                voice_type=voice_type,
                agent_name=agent_name
            )
            
            if audio_data:
                logger.info(f"✅ ElevenLabs TTS generated successfully ({len(audio_data)} bytes)")
                return audio_data
            else:
                logger.warning("⚠️ ElevenLabs TTS generation failed (no audio data returned)")
                return None
                
        except ImportError:
            logger.warning("⚠️ Voice cloning service not available (import error)")
            return None
        except Exception as e:
            logger.error(f"❌ ElevenLabs TTS error: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
    
    async def _google_tts(self, text: str) -> Optional[bytes]:
        """Generate speech using Google TTS"""
        try:
            # This is a placeholder - would need Google TTS API integration
            logger.info("Google TTS not configured")
            return None
        except Exception as e:
            logger.error(f"Google TTS error: {e}")
            return None

    def _play_audio_sync(self, audio_data: bytes):
        """Play audio synchronously with interruption support"""
        try:
            # Reset stop flag
            self._speech_stopped = False
            
            # Save to temporary file and play
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_path = temp_file.name
            
            # Use sounddevice for better interruption control
            try:
                import sounddevice as sd
                import soundfile as sf
                import numpy as np
                
                # Load audio file
                data, samplerate = sf.read(temp_path)
                
                # Play with interruption check
                sd.play(data, samplerate)
                
                # Wait for playback to finish or interruption
                while sd.get_stream().active and not self._speech_stopped:
                    import time
                    time.sleep(0.1)
                
                # Stop if interrupted
                if self._speech_stopped:
                    sd.stop()
                    logger.info("🔇 Audio playback interrupted")
                
                # Clean up
                sd.wait()
                os.unlink(temp_path)
                return
                
            except ImportError:
                # Fallback to system command
                import subprocess
                import platform
                
                if platform.system() == "Windows":
                    subprocess.run(["start", temp_path], shell=True)
                elif platform.system() == "Darwin":  # macOS
                    subprocess.run(["afplay", temp_path])
                else:  # Linux
                    subprocess.run(["aplay", temp_path])
                
                # Clean up after a delay (can't interrupt system commands easily)
                import time
                time.sleep(1)  # Give it time to start
                try:
                    os.unlink(temp_path)
                except:
                    pass
                
        except Exception as e:
            logger.error(f"Audio playback error: {e}")
    
    async def speech_to_text(self, audio_data: bytes) -> Optional[str]:
        """Convert speech audio to text"""
        if not self.enabled or not SPEECH_RECOGNITION_AVAILABLE:
            return None
        
        try:
            # Create temporary file for audio data
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_path = temp_file.name
            
            # Convert audio to text
            loop = asyncio.get_event_loop()
            text = await loop.run_in_executor(
                None,
                lambda: self._recognize_speech(temp_path)
            )
            
            # Clean up temporary file
            os.unlink(temp_path)
            return text
            
        except Exception as e:
            logger.error(f"Speech recognition error: {e}")
            return None
    
    def _recognize_speech(self, audio_path: str) -> Optional[str]:
        """Recognize speech from audio file (blocking operation)"""
        try:
            with sr.AudioFile(audio_path) as source:
                audio = self.recognizer.record(source)
            
            # Use Google Speech Recognition (free)
            text = self.recognizer.recognize_google(audio)
            return text
            
        except sr.UnknownValueError:
            logger.warning("Could not understand audio")
            return None
        except sr.RequestError as e:
            logger.error(f"Speech recognition service error: {e}")
            return None
        except Exception as e:
            logger.error(f"Speech recognition error: {e}")
            return None
    
    async def listen_for_activation(self, timeout: int = 5) -> Optional[str]:
        """Listen for voice activation phrases"""
        if not self.enabled or not SPEECH_RECOGNITION_AVAILABLE:
            return None
        
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                lambda: self._listen_for_activation_blocking(timeout)
            )
        except Exception as e:
            logger.error(f"Voice activation listening error: {e}")
            return None
    
    def _listen_for_activation_blocking(self, timeout: int) -> Optional[str]:
        """Listen for activation phrases (blocking operation)"""
        try:
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source)
            
            logger.info("Listening for voice activation...")
            
            with self.microphone as source:
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=3)
            
            text = self.recognizer.recognize_google(audio).lower()
            
            # Check for activation phrases
            for phrase in self.activation_phrases:
                if phrase.lower() in text:
                    logger.info(f"Voice activation detected: {phrase}")
                    return phrase
            
            return None
            
        except sr.WaitTimeoutError:
            return None
        except sr.UnknownValueError:
            return None
        except sr.RequestError as e:
            logger.error(f"Voice activation service error: {e}")
            return None
        except Exception as e:
            logger.error(f"Voice activation error: {e}")
            return None
    
    async def process_voice_command(self, audio_data: bytes) -> Optional[str]:
        """Process complete voice command after activation"""
        text = await self.speech_to_text(audio_data)
        if text:
            logger.info(f"Voice command recognized: {text}")
            return text
        return None
    
    async def process_voice_command_text(self, command: str):
        """Process voice command by sending it to the main chat system"""
        try:
            logger.info(f"🎤 Processing voice command: {command}")
            
            # Import here to avoid circular imports
            from main import daena
            
            # Process the command through the main chat system
            response = await daena.process_message(command, {"user_id": "founder", "voice": True})
            
            # The response will automatically be spoken if talk_active is True
            logger.info(f"🗣️ Voice command processed: {response[:50]}...")
            
        except Exception as e:
            logger.error(f"Error processing voice command: {e}")
            if self.talk_active:
                await self.text_to_speech("Sorry, I didn't catch that. Could you try again?", "daena", auto_read=True)

    def is_voice_enabled(self) -> bool:
        """Check if voice features are enabled"""
        return self.enabled and (SPEECH_RECOGNITION_AVAILABLE or self.tts_engine is not None)
    
    def get_activation_phrases(self) -> List[str]:
        """Get list of voice activation phrases"""
        return self.activation_phrases
    
    def get_available_providers(self) -> List[str]:
        """Get list of available TTS providers"""
        providers = []
        
        if settings.elevenlabs_api_key:
            providers.append(VoiceProvider.ELEVENLABS.value)
        if settings.google_tts_api_key:
            providers.append(VoiceProvider.GOOGLE_TTS.value)
        if self.tts_engine:
            providers.append(VoiceProvider.SYSTEM_TTS.value)
            
        return providers
    
    async def get_voice_status(self) -> Dict:
        """Get voice service status"""
        return {
            "enabled": self.enabled,
            "talk_active": self.talk_active,
            "speech_recognition_available": SPEECH_RECOGNITION_AVAILABLE,
            "tts_available": self.tts_engine is not None,
            "providers_available": self.get_available_providers(),
            "activation_phrases": self.activation_phrases,
            "elevenlabs_configured": bool(getattr(settings, 'elevenlabs_api_key', None)),
            "google_tts_configured": bool(getattr(settings, 'google_tts_api_key', None))
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get voice service status"""
        return {
            "available": self.available,
            "daena_voice_file": self.daena_voice_path is not None,
            "daena_voice_path": str(self.daena_voice_path) if self.daena_voice_path else None,
            "status": "Ready" if self.available else "Not available"
        }

    def handle_typing_start(self):
        """Stop speech when user starts typing (interrupt mode)"""
        if self.is_speaking():
            self.stop_current_speech()
            logger.info("🔇 Speech stopped - user started typing")
    
    def handle_voice_interrupt(self):
        """Stop speech when interrupted by voice or other input"""
        if self.is_speaking():
            self.stop_current_speech()
            logger.info("🔇 Speech interrupted by user")
    
    async def restore_computer_voice(self):
        """Restore computer's default voice settings if they were changed"""
        try:
            if PYTTSX3_AVAILABLE and self.tts_engine:
                # Reset TTS engine properties to default values
                self.tts_engine.setProperty('rate', 150)
                self.tts_engine.setProperty('volume', 1.0)
                self.tts_engine.setProperty('voice', '')
                logger.info("🔊 Computer voice settings restored to defaults")
                return {"status": "restored", "message": "Computer voice settings restored"}
            else:
                logger.info("🔊 No system TTS engine to restore")
                return {"status": "no_engine", "message": "No system TTS engine to restore"}
        except Exception as e:
            logger.error(f"Error restoring computer voice: {e}")
            return {"status": "error", "message": f"Error restoring computer voice: {e}"}

    # Voice Control Methods
    def set_volume(self, volume: float) -> Dict[str, Any]:
        """Set TTS volume (0.0 to 1.0)"""
        try:
            self.volume = max(0.0, min(1.0, volume))
            if self.tts_engine:
                self.tts_engine.setProperty('volume', self.volume)
            return {"status": "success", "volume": self.volume}
        except Exception as e:
            logger.error(f"Error setting volume: {e}")
            return {"status": "error", "message": str(e)}

    def set_rate(self, rate: int) -> Dict[str, Any]:
        """Set TTS rate (words per minute)"""
        try:
            self.rate = max(50, min(400, rate))
            if self.tts_engine:
                self.tts_engine.setProperty('rate', self.rate)
            return {"status": "success", "rate": self.rate}
        except Exception as e:
            logger.error(f"Error setting rate: {e}")
            return {"status": "error", "message": str(e)}

    def set_pitch(self, pitch: int) -> Dict[str, Any]:
        """Set TTS pitch (engine dependent)"""
        try:
            self.pitch = pitch
            if self.tts_engine:
                # pyttsx3 doesn't standardly support pitch on all engines, but we try
                try:
                    self.tts_engine.setProperty('pitch', self.pitch)
                except:
                    pass
            return {"status": "success", "pitch": self.pitch}
        except Exception as e:
            logger.error(f"Error setting pitch: {e}")
            return {"status": "error", "message": str(e)}

    def get_voice_settings(self) -> Dict[str, Any]:
        """Get current voice settings"""
        return {
            "volume": self.volume,
            "rate": self.rate,
            "pitch": self.pitch,
            "voice_active": self.voice_active,
            "talk_active": self.talk_active,
            "agents_talk_active": self.agents_talk_active
        }

# Global voice service instance
voice_service = VoiceService() 