import io
import wave
import threading
import asyncio
from typing import Optional, AsyncGenerator
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
    
    async def generate_audio_stream(
        self, 
        text_stream: AsyncGenerator[str, None],
        min_chunk_size: int = 10
    ) -> AsyncGenerator[bytes, None]:
        """
        Generate audio chunks as text tokens arrive using RealtimeTTS streaming.
        Uses RealtimeTTS pattern: feed a generator directly, then call play_async() or play().
        """
        try:
            logging.info("[RealtimeTTS] Starting streaming audio generation...")
            
            # Use a queue to pass audio chunks from the callback
            from queue import Queue, Empty
            audio_queue = Queue()
            play_complete = False
            play_error = None
            
            def on_audio_chunk(chunk):
                """Callback to receive audio chunks from RealtimeTTS"""
                if chunk:
                    audio_queue.put(chunk)
                    logging.debug(f"[RealtimeTTS] Audio chunk received: {len(chunk)} bytes")
            
            # Convert async generator to sync generator for RealtimeTTS
            # RealtimeTTS expects a sync generator/iterator
            def sync_text_generator():
                """Convert async generator to sync generator"""
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    async def collect_tokens():
                        tokens = []
                        async for token in text_stream:
                            tokens.append(token)
                        return tokens
                    
                    # Run async collection in the loop
                    tokens = loop.run_until_complete(collect_tokens())
                    for token in tokens:
                        yield token
                finally:
                    loop.close()
            
            # Alternative: Use a bridge that feeds tokens as they arrive
            # This allows true streaming instead of collecting all tokens first
            from queue import Queue as ThreadQueue
            text_queue = ThreadQueue()
            feed_complete = False
            
            async def feed_tokens_to_queue():
                """Feed tokens from async generator to sync queue"""
                nonlocal feed_complete
                try:
                    async for token in text_stream:
                        text_queue.put(token)
                    text_queue.put(None)  # Signal end
                    feed_complete = True
                except Exception as e:
                    logging.error(f"[RealtimeTTS] Error feeding tokens: {e}")
                    text_queue.put(None)
                    feed_complete = True
            
            def sync_text_generator_from_queue():
                """Sync generator that reads from queue (allows true streaming)"""
                while True:
                    try:
                        token = text_queue.get(timeout=0.1)
                        if token is None:
                            break
                        yield token
                    except:
                        if feed_complete:
                            break
                        continue
            
            # Start feeding tokens in background
            feed_task = asyncio.create_task(feed_tokens_to_queue())
            
            # Feed the generator to RealtimeTTS (it will consume tokens as they arrive)
            logging.info("[RealtimeTTS] Feeding text generator to stream...")
            self.stream.feed(sync_text_generator_from_queue())
            
            # Use play_async() if available, otherwise use play() in a thread
            def run_play():
                nonlocal play_complete, play_error
                try:
                    # Check if play_async() is available
                    if hasattr(self.stream, 'play_async'):
                        logging.info("[RealtimeTTS] Using play_async()...")
                        # play_async() is non-blocking, but we need to wait for completion
                        self.stream.play_async(
                            muted=True,
                            on_audio_chunk=on_audio_chunk
                        )
                        # Wait for playback to complete
                        while self.stream.is_playing():
                            import time
                            time.sleep(0.1)
                    else:
                        logging.info("[RealtimeTTS] Using play() (blocking)...")
                        self.stream.play(
                            muted=True,
                            on_audio_chunk=on_audio_chunk
                        )
                    
                    logging.info("[RealtimeTTS] Playback completed")
                    play_complete = True
                    audio_queue.put(None)  # Signal completion
                except Exception as e:
                    logging.error(f"[RealtimeTTS] Play error: {e}")
                    import traceback
                    traceback.print_exc()
                    play_error = e
                    play_complete = True
                    audio_queue.put(None)
            
            # Start playback in a thread
            import threading
            play_thread = threading.Thread(target=run_play, daemon=True)
            play_thread.start()
            
            # Yield audio chunks as they arrive
            chunks_yielded = 0
            audio_chunk_buffer = []
            timeout_count = 0
            max_timeouts = 200
            
            while True:
                try:
                    # Get chunk from queue with timeout
                    # Helper function that catches Empty exception
                    def get_chunk_with_timeout():
                        try:
                            return audio_queue.get(timeout=0.1)
                        except Empty:
                            # Queue timeout - return None to signal empty
                            return None
                    
                    try:
                        chunk_result = await asyncio.wait_for(
                            asyncio.to_thread(get_chunk_with_timeout),
                            timeout=0.2
                        )
                    except asyncio.TimeoutError:
                        # Outer timeout
                        chunk_result = None
                    
                    if chunk_result is None:
                        # Queue was empty (timeout)
                        timeout_count += 1
                        
                        # Check if everything is done
                        if feed_task.done() and play_complete:
                            if timeout_count < 10:
                                await asyncio.sleep(0.2)
                                continue
                            else:
                                break
                        
                        if timeout_count > max_timeouts:
                            logging.warning("[RealtimeTTS] Too many timeouts")
                            break
                        continue
                    
                    chunk = chunk_result
                    
                    timeout_count = 0
                    
                    if chunk is None:
                        # Play completed, get any remaining chunks
                        try:
                            while True:
                                remaining = audio_queue.get_nowait()
                                if remaining and remaining is not None:
                                    if self.engine_name == "elevenlabs":
                                        yield remaining
                                        chunks_yielded += 1
                                    else:
                                        audio_chunk_buffer.append(remaining)
                        except Empty:
                            pass
                        break
                    
                    # Yield audio chunk
                    if self.engine_name == "elevenlabs":
                        chunks_yielded += 1
                        logging.debug(f"[RealtimeTTS] Yielding chunk #{chunks_yielded}: {len(chunk)} bytes")
                        yield chunk
                    else:
                        # System engine: accumulate and yield as WAV
                        audio_chunk_buffer.append(chunk)
                        if len(audio_chunk_buffer) >= 5:
                            full_audio = b''.join(audio_chunk_buffer)
                            audio_chunk_buffer = []
                            chunks_yielded += 1
                            
                            wav_buffer = io.BytesIO()
                            with wave.open(wav_buffer, 'wb') as wf:
                                wf.setnchannels(1)
                                wf.setsampwidth(2)
                                wf.setframerate(self.sample_rate)
                                wf.writeframes(full_audio)
                            
                            logging.debug(f"[RealtimeTTS] Yielding WAV chunk #{chunks_yielded}")
                            yield wav_buffer.getvalue()
                
                except Exception as e:
                    logging.error(f"[RealtimeTTS] Error: {e}")
                    import traceback
                    traceback.print_exc()
                    break
            
            # Wait for tasks
            await feed_task
            if play_thread.is_alive():
                play_thread.join(timeout=5.0)
            
            # Yield remaining audio
            if audio_chunk_buffer:
                full_audio = b''.join(audio_chunk_buffer)
                wav_buffer = io.BytesIO()
                with wave.open(wav_buffer, 'wb') as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(self.sample_rate)
                    wf.writeframes(full_audio)
                chunks_yielded += 1
                logging.info(f"[RealtimeTTS] Yielding final chunk")
                yield wav_buffer.getvalue()
            
            if play_error:
                logging.error(f"[RealtimeTTS] Play error: {play_error}")
            
            logging.info(f"[RealtimeTTS] Complete. Yielded {chunks_yielded} chunks")
            
        except Exception as e:
            logging.error(f"[RealtimeTTS] Streaming failed: {e}")
            import traceback
            traceback.print_exc()

