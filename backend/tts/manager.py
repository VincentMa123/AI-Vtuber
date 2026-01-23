import logging
import base64
import config
import utils
from typing import Optional, Dict

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
