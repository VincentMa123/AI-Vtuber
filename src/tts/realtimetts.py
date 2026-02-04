import io
import wave
import threading
import asyncio
from typing import Optional, AsyncGenerator
from .base import BaseTTSProvider, create_wav_buffer
import core.config as config
from RealtimeTTS import TextToAudioStream, SystemEngine, ElevenlabsEngine
from queue import Queue as ThreadQueue
import logging

class RealtimeTTSProvider(BaseTTSProvider):
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
        
        self.stream = TextToAudioStream(self.engine, language="id")
        logging.info(f"RealtimeTTS initialized with {engine_name} engine")
        
    def _on_audio_chunk(self, chunk):

        with self.lock:
            self.audio_buffer.append(chunk)
    
    async def generate_audio_stream(
        self, 
        text_stream: AsyncGenerator[str, None],
    ) -> AsyncGenerator[bytes, None]:

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

                while True:
                    try:
                        token = text_queue.get(timeout=0.05)
                        if token is None:
                            break
                        yield token
                    except Exception:
                        if feed_complete:
                            break
                        continue            
            # Start feeding tokens in background
            feed_task = asyncio.create_task(feed_tokens_to_queue())
            
            logging.info("[RealtimeTTS] Feeding text generator to stream...")
            self.stream.feed(sync_text_generator_from_queue())
            
            def run_play():
                nonlocal play_complete, play_error
                try:
                    logging.info("[RealtimeTTS] Using play_async()...")
                    self.stream.play_async(
                        muted=True,
                        on_audio_chunk=on_audio_chunk
                    )
    
                    while self.stream.is_playing():
                        import time
                        time.sleep(0.05)
        
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
                    try:
                        chunk = audio_queue.get_nowait()
                    except Empty:
                        # Queue is empty, wait briefly to let other tasks run
                        chunk = None
                        await asyncio.sleep(0.01)
                    
                    if chunk is None:
                        timeout_count += 1
                        
                        # Check if everything is done
                        # We need to make sure we don't exit if the thread is just starting up
                        if feed_complete and play_complete and audio_queue.empty():
                             break

                        if timeout_count > max_timeouts * 10: # Adjust for faster loop
                            logging.warning("[RealtimeTTS] Stream timeout waiting for audio")
                            break
                        continue
                    
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
                        
                        # Calculate total size to avoid sending tiny WAVs
                        current_buffer_size = sum(len(c) for c in audio_chunk_buffer)
                        
                        # Buffer ~32KB (approx 1.5s of audio) to ensure smooth playback segments
                        # This avoids the "machine gun" effect of playing many small WAV files
                        if current_buffer_size >= 32000:
                            full_audio = b''.join(audio_chunk_buffer)
                            audio_chunk_buffer = []
                            chunks_yielded += 1
                            
                            wav_bytes = create_wav_buffer(full_audio, self.sample_rate)
                            
                            logging.debug(f"[RealtimeTTS] Yielding large WAV chunk #{chunks_yielded} ({len(full_audio)} bytes)")
                            yield wav_bytes
                
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
                wav_bytes = create_wav_buffer(full_audio, self.sample_rate)
                chunks_yielded += 1
                logging.debug(f"[RealtimeTTS] Yielding final WAV chunk #{chunks_yielded} ({len(full_audio)} bytes)")
                yield wav_bytes
            
            if play_error:
                logging.error(f"[RealtimeTTS] Play error: {play_error}")
            
            logging.info(f"[RealtimeTTS] Complete. Yielded {chunks_yielded} chunks")
            
        except Exception as e:
            logging.error(f"[RealtimeTTS] Streaming failed: {e}")
            import traceback
            traceback.print_exc()

