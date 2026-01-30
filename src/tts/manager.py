import logging
import base64
import core.config as config
import core.utils as utils
from typing import Optional, Dict, AsyncGenerator
from .elevenlabs import ElevenLabsProvider
from .realtimetts import RealtimeTTSProvider
from .qwen_tts import QwenTTSProvider

class TTSManager:
    def __init__(self):
        self.providers: Dict = {
            "elevenlabs": None,
            "realtimetts": None,
            "qwen": None
        }

        self._initialize_providers()
        
    def _initialize_providers(self):
        self.providers["elevenlabs"] = ElevenLabsProvider()
        self.providers["realtimetts"] = RealtimeTTSProvider(config.REALTIMETTS_ENGINE)
        self.providers["qwen"] = QwenTTSProvider()

    async def initialize(self):
        """Initialize all providers"""
        if self.providers.get("qwen"):
            await self.providers["qwen"].initialize()
        
    async def generate_audio(self, text: str) -> Optional[str]:
    
        if not text:
            return None
    
        try:
            if config.TTS_PROVIDER == "elevenlabs":
                return await self._generate_elevenlabs(text)
            elif config.TTS_PROVIDER == "realtimetts":
                return await self._generate_realtimetts(text)
            elif config.TTS_PROVIDER == "qwen":
                return await self._generate_qwen(text)
            else:
                logging.warning(f"[TTSManager] Unknown provider: {config.TTS_PROVIDER}")
                return None
                
        except Exception as e:
            logging.error(f"[TTSManager] Error handling TTS generation: {e}")
            return None

    async def _generate_elevenlabs(self, text: str) -> Optional[str]:
        logging.info("Generating audio with ElevenLabs...")
        provider = self.providers["elevenlabs"]
        if not provider: return None
        audio_bytes = await provider.generate_audio(text)
        return base64.b64encode(audio_bytes).decode('utf-8') if audio_bytes else None

    async def _generate_realtimetts(self, text: str) -> Optional[str]:
        logging.info(f"Generating audio with RealtimeTTS...")
        provider = self.providers["realtimetts"]
        if not provider: return None
        audio_bytes = await provider.generate_audio(text)
        return base64.b64encode(audio_bytes).decode('utf-8') if audio_bytes else None

    async def _generate_qwen(self, text: str) -> Optional[str]:
        logging.info(f"Generating audio with Qwen TTS...")
        provider = self.providers["qwen"]
        if not provider: return None
        audio_bytes = await provider.generate_audio(text)
        return base64.b64encode(audio_bytes).decode('utf-8') if audio_bytes else None
    
    async def generate_audio_stream(
        self, 
        text_stream: AsyncGenerator[str, None],
    ) -> AsyncGenerator[str, None]:
 
        try:
            current_provider = config.TTS_PROVIDER
            provider = self.providers.get(current_provider)
            
            if provider:
                async for audio_chunk in provider.generate_audio_stream(text_stream):
                    if audio_chunk:
                        yield base64.b64encode(audio_chunk).decode('utf-8')
            else:
                logging.error(f"[TTSManager] Provider {current_provider} not available")

        except Exception as e:
            logging.error(f"[TTSManager] Streaming error: {e}")
