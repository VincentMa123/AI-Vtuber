import io
import base64
import httpx
import numpy as np
import soundfile as sf
from typing import Optional
import state
import config

async def generate_audio_elevenlabs(text: str) -> Optional[bytes]:
    """Generate audio using ElevenLabs API."""
    if not config.ELEVENLABS_API_KEY:
        print("ElevenLabs API key not set!")
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
                print(f"ElevenLabs error: {response.status_code} - {response.text}")
                return None
    except Exception as e:
        print(f"ElevenLabs generation failed: {e}")
        return None

def generate_audio_kokoro(text: str) -> Optional[str]:
    """Generate audio using Kokoro (Local) and return base64 string."""
    if not state.tts_pipeline:
        print("Kokoro pipeline not loaded!")
        return None

    try:
        generator = state.tts_pipeline(text, voice="jf_alpha", speed=1.1)
        audio_chunks = []
        for gs, ps, audio in generator:
            audio_chunks.append(audio)
        
        if audio_chunks:
            full_audio = np.concatenate(audio_chunks)
            buffer = io.BytesIO()
            sf.write(buffer, full_audio, samplerate=24000, format='WAV')
            buffer.seek(0)
            return base64.b64encode(buffer.read()).decode('utf-8')
    except Exception as e:
        print(f"Kokoro generation failed: {e}")
    
    return None
