import io
import wave
from abc import ABC, abstractmethod
from typing import Optional, AsyncGenerator


class BaseTTSProvider(ABC):
    
    @abstractmethod
    async def generate_audio_stream(
        self, 
        text_stream: AsyncGenerator[str, None]
    ) -> AsyncGenerator[bytes, None]:
        """
        Generate audio chunks as text tokens arrive.
        
        Args:
            text_stream: Async generator yielding text tokens
            
        Yields:
            Audio chunks (bytes) as they're ready
        """
        pass


def create_wav_buffer(audio_data: bytes, sample_rate: int = 24000) -> bytes:
    """Create a WAV buffer from raw PCM audio data."""
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_data)
    return wav_buffer.getvalue()
