"""
Voice Awakening Service for Daena AI VP System
Handles wake word detection and voice activation
"""

import logging
import asyncio
import threading
from typing import Optional, Callable
import os

logger = logging.getLogger(__name__)

# Try to import voice recognition libraries
try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False
    logger.warning("⚠️ SpeechRecognition not available. Install: pip install SpeechRecognition pyaudio")

try:
    import pvporcupine
    from pvporcupine import Porcupine
    PORCUPINE_AVAILABLE = True
except ImportError:
    PORCUPINE_AVAILABLE = False
    logger.warning("⚠️ Porcupine not available. Install: pip install pvporcupine")

class VoiceAwakening:
    """Service for wake word detection and voice activation"""
    
    def __init__(self):
        self.is_awake = False
        self.is_listening = False
        self.wake_word_detected = False
        self.activation_callback: Optional[Callable] = None
        
        # Initialize speech recognition
        if SPEECH_RECOGNITION_AVAILABLE:
            try:
                self.recognizer = sr.Recognizer()
                self.microphone = sr.Microphone()
                logger.info("✅ Speech recognition initialized for voice awakening")
            except Exception as e:
                logger.warning(f"⚠️ Speech recognition initialization failed: {e}")
                self.recognizer = None
                self.microphone = None
        else:
            self.recognizer = None
            self.microphone = None
        
        # Initialize Porcupine (if available)
        self.porcupine = None
        if PORCUPINE_AVAILABLE:
            try:
                porcupine_key = os.getenv("PORCUPINE_ACCESS_KEY", "")
                if porcupine_key:
                    self.porcupine = Porcupine(
                        access_key=porcupine_key,
                        keywords=["hey daena", "daena", "wake up daena"]
                    )
                    logger.info("✅ Porcupine wake word detection initialized")
                else:
                    logger.warning("⚠️ PORCUPINE_ACCESS_KEY not set. Using speech recognition fallback")
            except Exception as e:
                logger.warning(f"⚠️ Porcupine initialization failed: {e}")
    
    def set_activation_callback(self, callback: Callable):
        """Set callback function to call when wake word is detected"""
        self.activation_callback = callback
    
    async def start_listening(self):
        """Start listening for wake words"""
        if self.is_listening:
            logger.info("Already listening for wake words")
            return
        
        self.is_listening = True
        logger.info("🎤 Starting wake word detection...")
        
        # Start listening in background thread
        thread = threading.Thread(target=self._listen_loop, daemon=True)
        thread.start()
    
    def _listen_loop(self):
        """Main listening loop (runs in background thread)"""
        while self.is_listening:
            try:
                if self.porcupine:
                    # Use Porcupine for wake word detection
                    self._listen_with_porcupine()
                elif self.recognizer and self.microphone:
                    # Fallback to speech recognition
                    self._listen_with_speech_recognition()
                else:
                    logger.warning("⚠️ No wake word detection available")
                    break
            except Exception as e:
                logger.error(f"❌ Error in wake word detection: {e}")
                import time
                time.sleep(1)
    
    def _listen_with_porcupine(self):
        """Listen using Porcupine wake word detection"""
        import sounddevice as sd
        import numpy as np
        
        try:
            audio_data = sd.rec(
                int(self.porcupine.frame_length),
                samplerate=self.porcupine.sample_rate,
                channels=1,
                dtype=np.int16
            )
            sd.wait()
            
            keyword_index = self.porcupine.process(audio_data.flatten())
            
            if keyword_index >= 0:
                logger.info("🎤 Wake word detected via Porcupine!")
                self.wake_word_detected = True
                self.is_awake = True
                
                if self.activation_callback:
                    asyncio.run(self.activation_callback())
        except Exception as e:
            logger.error(f"❌ Porcupine detection error: {e}")
    
    def _listen_with_speech_recognition(self):
        """Listen using speech recognition (fallback)"""
        try:
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=3)
            
            text = self.recognizer.recognize_google(audio).lower()
            logger.debug(f"🎤 Heard: {text}")
            
            # Check for wake words
            wake_words = ["hey daena", "daena", "wake up daena", "listen daena", "anna"]
            for wake_word in wake_words:
                if wake_word in text:
                    logger.info(f"🎤 Wake word detected: {wake_word}")
                    self.wake_word_detected = True
                    self.is_awake = True
                    
                    if self.activation_callback:
                        asyncio.run(self.activation_callback())
                    break
                    
        except sr.WaitTimeoutError:
            pass  # No speech detected, continue listening
        except sr.UnknownValueError:
            pass  # Could not understand, continue listening
        except Exception as e:
            logger.error(f"❌ Speech recognition error: {e}")
    
    async def stop_listening(self):
        """Stop listening for wake words"""
        self.is_listening = False
        self.wake_word_detected = False
        logger.info("🎤 Wake word detection stopped")
    
    def reset_awake_state(self):
        """Reset awake state (after processing command)"""
        self.is_awake = False
        self.wake_word_detected = False
    
    def is_awake_state(self) -> bool:
        """Check if Daena is in awake state"""
        return self.is_awake

# Global instance
voice_awakening = VoiceAwakening()

