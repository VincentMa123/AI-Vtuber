import asyncio
import logging
import base64
import struct
from core import state

def install_tts_interceptor(tts_manager, audio_pipe):

    original_generate = tts_manager.generate_audio_stream
    
    async def patched_generate_audio_stream(text_stream):
        # 1. Create a queue to bridge to AudioPipe
        pipe_queue = asyncio.Queue()
        
        # 2. Define the consumer iterator for AudioPipe
        async def pipe_iterator():
            while True:
                chunk = await pipe_queue.get()
                if chunk is None:
                    break
                yield chunk
        
        pipe_started = False
        chunk_count = 0
        total_bytes = 0
        logging.info("[AudioPipe Interceptor] Starting to intercept TTS stream...")
        
        try:
            # We need to manually iterate to get the first chunk
            gen = original_generate(text_stream)
            
            async for b64_chunk in gen:
                try:
                    if b64_chunk:
                        chunk_bytes = base64.b64decode(b64_chunk)
                        
                        # Inspect first chunk for WAV header
                        if not pipe_started:
                            sample_rate = 24000 # Default (Qwen)
                            
                            # Check for RIFF header
                            if len(chunk_bytes) > 44 and chunk_bytes[0:4] == b'RIFF' and chunk_bytes[8:12] == b'WAVE':
                                try:
                                    sample_rate = struct.unpack('<I', chunk_bytes[24:28])[0]
                                    logging.info(f"[AudioPipe Interceptor] Detected WAV sample rate: {sample_rate}")
                                except:
                                    logging.warning("[AudioPipe Interceptor] Failed to parse WAV header, defaulting to 24000")
                            
                            # Start the pipe with detected rate
                            logging.info(f"[AudioPipe Interceptor] Starting pipe with input_rate={sample_rate}")
                            pipe_task = asyncio.create_task(audio_pipe.stream_audio_flow(pipe_iterator(), input_rate=sample_rate))
                            
                            # Keep a strong reference
                            if not hasattr(state, "background_tasks"):
                                state.background_tasks = set()
                            state.background_tasks.add(pipe_task)
                            pipe_task.add_done_callback(state.background_tasks.discard)
                            pipe_started = True

                        pcm_data = chunk_bytes[44:]
                        await pipe_queue.put(pcm_data)
                        chunk_count += 1
                        total_bytes += len(pcm_data)
                        
                except Exception as e:
                    logging.error(f"[AudioPipe Interceptor] Error processing chunk: {e}")
                
                # Yield original (base64 WAV) to Frontend
                yield b64_chunk
                
        finally:
            duration_seconds = 0
            if 'sample_rate' in locals():
                duration_seconds = total_bytes / (sample_rate * 2) 
            logging.info(f"[AudioPipe Interceptor] Stream finished. Sent {chunk_count} chunks ({total_bytes} bytes PCM) to pipe. Duration: {duration_seconds:.2f}s")
            
            # Simulate frontend audio_playback_complete event after the calculated duration
            if duration_seconds > 0:
                asyncio.get_running_loop().call_later(duration_seconds, state.signal_audio_complete)
                
            # Signal end of stream to pipe
            await pipe_queue.put(None)

    tts_manager.generate_audio_stream = patched_generate_audio_stream
    logging.info("[Startup] TTS Manager patched for AudioPipe interception")
