import logging
import base64
import core.config as config

from typing import Optional, Dict, AsyncGenerator
from .realtimetts import RealtimeTTSProvider
from .qwen_tts import QwenTTSProvider

class TTSManager:
    def __init__(self):
        self.providers: Dict = {
            "realtimetts": None,
            "qwen": None
        }

        self._initialize_providers()
        
    def _initialize_providers(self):
        self.providers["realtimetts"] = RealtimeTTSProvider(config.REALTIMETTS_ENGINE)
        self.providers["qwen"] = QwenTTSProvider()

    async def initialize(self):
   
        if self.providers.get("qwen"):
            await self.providers["qwen"].initialize()

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
