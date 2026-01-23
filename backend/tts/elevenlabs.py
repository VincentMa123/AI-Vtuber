import httpx
from typing import Optional
import core.config as config
from .base import BaseTTSProvider
import logging

class ElevenLabsProvider(BaseTTSProvider):
    """ElevenLabs API provider for text-to-speech."""
    
    async def generate_audio(self, text: str) -> Optional[bytes]:
        """Generate audio using ElevenLabs API."""
        if not config.ELEVENLABS_API_KEY:
            logging.error("ElevenLabs API key not set!")
            return None
            
        try:
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{config.ELEVENLABS_VOICE_ID}"
            headers = {
                "xi-api-key": config.ELEVENLABS_API_KEY,
                "Content-Type": "application/json"
            }
            data = {
                "text": text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.5
                }
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=data, headers=headers)
                if response.status_code == 200:
                    return response.content
                else:
                    logging.error(f"ElevenLabs error: {response.status_code} - {response.text}")
                    return None
        except httpx.TimeoutException:
            logging.error("ElevenLabs generation timed out!")
            return None
        except Exception as e:
            logging.error(f"ElevenLabs generation failed: {type(e).__name__}: {e}")
            return None
