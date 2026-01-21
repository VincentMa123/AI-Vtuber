from abc import ABC, abstractmethod
from typing import Optional


class BaseTTSProvider(ABC):
    
    @abstractmethod
    async def generate_audio(self, text: str) -> Optional[bytes]:
        """
        Generate audio from text.
        
        Args:
            text: The text to convert to speech
            
        Returns:
            Audio bytes (WAV or MP3 format), or None if failed
        """
        pass
