import io
import wave
import threading
from typing import Optional
import os
from .base import BaseTTSProvider
import core.config as config
from RealtimeTTS import TextToAudioStream, SystemEngine, ElevenlabsEngine
import logging

class RealtimeTTSProvider(BaseTTSProvider):
    """RealtimeTTS provider for text-to-speech with streaming support.
    
    Supports engines:
    - 'system': Uses system TTS (Windows SAPI, etc.)
    - 'elevenlabs': Uses ElevenLabs API with streaming for lower latency
    """
    
    def __init__(self, engine_name: str = "system"):
        if not TextToAudioStream:
            raise ImportError("RealtimeTTS library is not available")
            
        self.audio_buffer = []
        self.lock = threading.Lock()
        self.engine_name = engine_name
        
        logging.info(f"Initializing RealtimeTTS with {engine_name} engine...")
        
        if engine_name == "elevenlabs":
            if not ElevenlabsEngine:
                raise ImportError("ElevenlabsEngine not available. Install with: pip install RealtimeTTS[elevenlabs]")
            if not config.ELEVENLABS_API_KEY:
                raise ValueError("ELEVENLABS_API_KEY not set in config")
            
            self.engine = ElevenlabsEngine(
                api_key=config.ELEVENLABS_API_KEY,
                id = config.ELEVENLABS_VOICE_ID,
                model="eleven_multilingual_v2",
            )
            self.sample_rate = 44100 
        else:
            self.engine = SystemEngine()
            self.sample_rate = 22050  
        
        self.stream = TextToAudioStream(self.engine)
        logging.info(f"RealtimeTTS initialized with {engine_name} engine")
        
    def _on_audio_chunk(self, chunk):
        """Callback to receive audio chunks."""
        with self.lock:
            self.audio_buffer.append(chunk)

    async def generate_audio(self, text: str) -> Optional[bytes]:
        """
        Generates audio for the given text and returns WAV bytes.
        Uses streaming for lower latency with ElevenLabs.
        """
        try:
            logging.info(f"[RealtimeTTS] Starting audio generation for text: {text[:50]}...")
            
            with self.lock:
                self.audio_buffer = []
            
            logging.info(f"[RealtimeTTS] Feeding text to stream...")
            self.stream.feed(text)
            
            logging.info(f"[RealtimeTTS] Playing stream (muted mode)...")
            self.stream.play(
                muted=True, 
                on_audio_chunk=self._on_audio_chunk
            )
            
            with self.lock:
                chunk_count = len(self.audio_buffer)
                logging.info(f"[RealtimeTTS] Audio chunks received: {chunk_count}")
                
                if not self.audio_buffer:
                    logging.info("[RealtimeTTS] No audio chunks generated!")
                    return None
                
                full_audio_data = b''.join(self.audio_buffer)
            
            if self.engine_name == "elevenlabs":
                logging.info(f"[RealtimeTTS] Returning MP3 audio ({len(full_audio_data)} bytes)")
                return full_audio_data
            
            logging.info(f"[RealtimeTTS] Wrapping raw PCM in WAV format...")
            channel_count = 1
            sample_width = 2  
            sample_rate = self.sample_rate
            
            if hasattr(self.engine, 'get_stream_info'):
                info = self.engine.get_stream_info()
                if hasattr(info, 'rate'):
                    sample_rate = int(info.rate)

            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wf:
                wf.setnchannels(channel_count)
                wf.setsampwidth(sample_width)
                wf.setframerate(sample_rate)
                wf.writeframes(full_audio_data)
            
            return wav_buffer.getvalue()
            
        except Exception as e:
            logging.error(f"RealtimeTTS generation failed: {e}")
            import traceback
            traceback.print_exc()
            return None

