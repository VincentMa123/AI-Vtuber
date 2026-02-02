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
            min_chunk_size: Minimum characters before generating audio chunk
            
        Yields:
            Audio chunks (bytes) as they're ready
        """
        # Default implementation: collect all text then generate
        full_text = ""
        async for token in text_stream:
            full_text += token
        
        if full_text:
            audio = await self.generate_audio(full_text)
            if audio:
                yield audio
