"""
Ollama Scanner - Detects locally installed Ollama models
"""
import aiohttp
import os
from typing import List, Dict, Any

class OllamaScanner:
    def __init__(self):
        self.base_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')

    async def scan_models(self) -> List[Dict[str, Any]]:
        """Scan Ollama API for installed models"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/api/tags"
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return []

                    data = await resp.json()
                    models = data.get('models', [])

                    # Normalize model data
                    normalized = []
                    for model in models:
                        size_bytes = model.get('size', 0)
                        size_gb = round(size_bytes / (1024**3), 2)

                        normalized.append({
                            'id': model['name'],
                            'name': model['name'],
                            'size_gb': size_gb,
                            'parameter_size': self._extract_params(model['name']),
                            'provider': 'ollama',
                            'enabled': False,
                            'status': 'available'
                        })

                    return normalized

        except Exception as e:
            print(f"[OllamaScanner] Error scanning: {e}")
            return []

    def _extract_params(self, name: str) -> str:
        """Extract parameter size from model name (e.g., '7b' from 'llama2:7b')"""
        if ':' in name:
            parts = name.split(':')
            if len(parts) > 1:
                return parts[1]
        return 'unknown'

_scanner = None

def get_ollama_scanner() -> OllamaScanner:
    global _scanner
    if _scanner is None:
        _scanner = OllamaScanner()
    return _scanner
