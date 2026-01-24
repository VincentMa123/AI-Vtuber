import logging
import base64
import core.config as config
import core.utils as utils
from typing import Optional, Dict, AsyncGenerator

# Import providers
from .elevenlabs import ElevenLabsProvider
from .realtimetts import RealtimeTTSProvider

class TTSManager:
    """
    Manages Text-to-Speech generation, handling provider selection and lazy initialization.
    """
    def __init__(self):
        self.providers: Dict = {
            "elevenlabs": None,
            "realtimetts": None
        }
        self.realtime_tts_cls = RealtimeTTSProvider
        self._initialize_providers()
        
    def _initialize_providers(self):
        """Initialize strict providers (ElevenLabs) but lazy-load RealtimeTTS."""
        # ElevenLabs is lightweight to init
        self.providers["elevenlabs"] = ElevenLabsProvider()
        
        # RealtimeTTS is heavy, we'll init it on first use if selected
        self.providers["realtimetts"] = None
        
    async def generate_audio(self, text: str) -> Optional[str]:
        """
        Generate TTS audio using the configured provider.
        Returns: Base64 encoded audio string or None.
        """
        clean_text = utils.clean_text_for_tts(text)
        if not clean_text:
            return None
            
        try:
            if config.TTS_PROVIDER == "elevenlabs":
                return await self._generate_elevenlabs(clean_text)
            
            elif config.TTS_PROVIDER == "realtimetts":
                return await self._generate_realtimetts(clean_text)
                
            else:
                logging.warning(f"[TTSManager] Unknown provider: {config.TTS_PROVIDER}")
                return None
                
        except Exception as e:
            logging.error(f"[TTSManager] Error handling TTS generation: {e}")
            return None

    async def _generate_elevenlabs(self, text: str) -> Optional[str]:
        logging.info("Generating audio with ElevenLabs...")
        provider = self.providers["elevenlabs"]
        
        audio_bytes = await provider.generate_audio(text)
        if audio_bytes:
            return base64.b64encode(audio_bytes).decode('utf-8')
        else:
            logging.error("[TTSManager] ElevenLabs failed to generate audio")
            return None

    async def _generate_realtimetts(self, text: str) -> Optional[str]:
        logging.info(f"Generating audio with RealtimeTTS (Engine: {config.REALTIMETTS_ENGINE})...")
        
        # Lazy initialization
        if self.providers["realtimetts"] is None:
            try:
                logging.info("[TTSManager] Initializing RealtimeTTS engine...")
                self.providers["realtimetts"] = self.realtime_tts_cls(config.REALTIMETTS_ENGINE)
            except Exception as e:
                logging.error(f"[TTSManager] Failed to initialize RealtimeTTS: {e}")
                return None
        
        provider = self.providers["realtimetts"]
        if provider:
            audio_bytes = await provider.generate_audio(text)
            if audio_bytes:
                return base64.b64encode(audio_bytes).decode('utf-8')
            else:
                logging.error("[TTSManager] RealtimeTTS generated no audio")
                return None
        else:
            logging.error("[TTSManager] RealtimeTTS service not available")
            return None
    
    async def generate_audio_stream(
        self, 
        text_stream: AsyncGenerator[str, None],
        min_chunk_size: int = 10
    ) -> AsyncGenerator[str, None]:
        """
        Generate TTS audio chunks as text tokens arrive.
        Yields base64-encoded audio chunks.
        """
        try:
            if config.TTS_PROVIDER == "realtimetts":
                # Lazy initialization
                if self.providers["realtimetts"] is None:
                    try:
                        logging.info("[TTSManager] Initializing RealtimeTTS engine for streaming...")
                        self.providers["realtimetts"] = self.realtime_tts_cls(config.REALTIMETTS_ENGINE)
                    except Exception as e:
                        logging.error(f"[TTSManager] Failed to initialize RealtimeTTS: {e}")
                        return
                
                provider = self.providers["realtimetts"]
                if provider:
                    async for audio_chunk in provider.generate_audio_stream(text_stream, min_chunk_size):
                        if audio_chunk:
                            yield base64.b64encode(audio_chunk).decode('utf-8')
                else:
                    logging.error("[TTSManager] RealtimeTTS service not available")
            else:
                # For non-streaming providers, collect text then generate
                full_text = ""
                async for token in text_stream:
                    full_text += token
                
                if full_text:
                    clean_text = utils.clean_text_for_tts(full_text)
                    if clean_text:
                        audio_base64 = await self.generate_audio(clean_text)
                        if audio_base64:
                            yield audio_base64
        except Exception as e:
            logging.error(f"[TTSManager] Streaming error: {e}")
