"""
OpenAI Integration
Supports GPT-4o, DALL-E, Whisper, and TTS
"""
from typing import Dict, Any
from backend.services.integrations import BaseIntegration
import httpx
import logging

logger = logging.getLogger(__name__)

class Integration(BaseIntegration):
    """OpenAI Integration"""
    
    def __init__(self, integration_id: str, credentials: Dict[str, Any]):
        super().__init__(integration_id, credentials)
        self.api_key = credentials.get("api_key")
        self.base_url = "https://api.openai.com/v1"
        self.client = None
    
    async def connect(self) -> bool:
        """Connect to OpenAI API"""
        try:
            if not self.api_key:
                self.error = "API key is required"
                return False
            
            self.client = httpx.AsyncClient(
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                timeout=30.0
            )
            self.connected = True
            return True
        except Exception as e:
            self.error = str(e)
            logger.error(f"Error connecting to OpenAI: {e}")
            return False
    
    async def disconnect(self) -> bool:
        """Disconnect from OpenAI API"""
        try:
            if self.client:
                await self.client.aclose()
            self.connected = False
            return True
        except Exception as e:
            logger.error(f"Error disconnecting from OpenAI: {e}")
            return False
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test OpenAI connection by listing models"""
        try:
            if not self.connected:
                await self.connect()
            
            response = await self.client.get(f"{self.base_url}/models")
            
            if response.status_code == 200:
                models = response.json()
                return self.format_response(
                    success=True,
                    data={
                        "message": "✅ OpenAI connection successful",
                        "models_count": len(models.get("data", [])),
                        "sample_models": [m["id"] for m in models.get("data", [])[:5]]
                    }
                )
            else:
                return self.format_response(
                    success=False,
                    error=f"API returned status {response.status_code}"
                )
        except Exception as e:
            return self.format_response(success=False, error=str(e))
    
    async def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute OpenAI actions"""
        try:
            if not self.connected:
                await self.connect()
            
            if action == "chat":
                return await self._chat_completion(params)
            elif action == "generate_image":
                return await self._generate_image(params)
            elif action == "speech_to_text":
                return await self._speech_to_text(params)
            elif action == "text_to_speech":
                return await self._text_to_speech(params)
            else:
                return self.format_response(
                    success=False,
                    error=f"Unknown action: {action}"
                )
        except Exception as e:
            return self.format_response(success=False, error=str(e))
    
    async def _chat_completion(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Chat completion"""
        try:
            messages = params.get("messages", [])
            model = params.get("model", "gpt-4o")
            temperature = params.get("temperature", 0.7)
            
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature
            }
            
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                json=payload
            )
            
            if response.status_code == 200:
                data = response.json()
                return self.format_response(
                    success=True,
                    data={
                        "message": data["choices"][0]["message"]["content"],
                        "usage": data.get("usage"),
                        "model": data.get("model")
                    }
                )
            else:
                return self.format_response(
                    success=False,
                    error=f"API error: {response.text}"
                )
        except Exception as e:
            return self.format_response(success=False, error=str(e))
    
    async def _generate_image(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate image with DALL-E"""
        try:
            prompt = params.get("prompt")
            model = params.get("model", "dall-e-3")
            size = params.get("size", "1024x1024")
            
            if not prompt:
                return self.format_response(success=False, error="Prompt is required")
            
            payload = {
                "model": model,
                "prompt": prompt,
                "size": size,
                "n": 1
            }
            
            response = await self.client.post(
                f"{self.base_url}/images/generations",
                json=payload
            )
            
            if response.status_code == 200:
                data = response.json()
                return self.format_response(
                    success=True,
                    data={
                        "url": data["data"][0]["url"],
                        "revised_prompt": data["data"][0].get("revised_prompt")
                    }
                )
            else:
                return self.format_response(
                    success=False,
                    error=f"API error: {response.text}"
                )
        except Exception as e:
            return self.format_response(success=False, error=str(e))
    
    async def _speech_to_text(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Whisper speech-to-text"""
        try:
            audio_file = params.get("audio_file")
            model = params.get("model", "whisper-1")
            
            if not audio_file:
                return self.format_response(success=False, error="Audio file is required")
            
            # This would require multipart form data
            # For now return not implemented
            return self.format_response(
                success=False,
                error="Speech-to-text requires multipart upload - not yet implemented"
            )
        except Exception as e:
            return self.format_response(success=False, error=str(e))
    
    async def _text_to_speech(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Text-to-speech"""
        try:
            text = params.get("text")
            voice = params.get("voice", "alloy")
            model = params.get("model", "tts-1")
            
            if not text:
                return self.format_response(success=False, error="Text is required")
            
            payload = {
                "model": model,
                "input": text,
                "voice": voice
            }
            
            response = await self.client.post(
                f"{self.base_url}/audio/speech",
                json=payload
            )
            
            if response.status_code == 200:
                return self.format_response(
                    success=True,
                    data={
                        "message": "Audio generated successfully",
                        "audio_data": response.content  # Binary audio data
                    }
                )
            else:
                return self.format_response(
                    success=False,
                    error=f"API error: {response.text}"
                )
        except Exception as e:
            return self.format_response(success=False, error=str(e))
