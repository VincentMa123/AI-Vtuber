import os
import asyncio
import logging
import subprocess
import time

class AudioPipe:

    def __init__(self, pipe_path="/tmp/tts_audio.fifo", sample_rate=48000):
        self.pipe_path = pipe_path
        self.sample_rate = sample_rate
        self.running = False
        self.queue = asyncio.Queue() 
        self._pipe_fd = None
        self._worker_task = None
        self.active_streams = 0 # Track concurrent streams to handle silence logic
        
        # Audio format constants (s16le, 1 channel, 48000Hz)
        self.bytes_per_sample = 2 # 16-bit
        self.channels = 1
        self.bytes_per_second = self.sample_rate * self.bytes_per_sample * self.channels
        
    async def start(self):

        if self.running:
            return
            
        if not hasattr(os, "mkfifo"):
            logging.warning("[AudioPipe] os.mkfifo not available (Windows detected). Audio pipe disabled.")
            return

        # Ensure FIFO exists
        if not os.path.exists(self.pipe_path):
            try:
                os.mkfifo(self.pipe_path)
                logging.info(f"[AudioPipe] Created FIFO at {self.pipe_path}")
            except FileExistsError:
                pass
            except Exception as e:
                logging.error(f"[AudioPipe] Failed to create FIFO: {e}")
                return

        self.running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        logging.info("[AudioPipe] Started audio pipe worker")

    async def stop(self):

        self.running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        
        if self._pipe_fd:
            try:
                os.close(self._pipe_fd)
            except:
                pass
        logging.info("[AudioPipe] Stopped")

    async def stream_audio_flow(self, audio_chunk_iterator, input_rate=24000):
     
        if not self.running:
            # Consume iterator to avoid unawaited warnings or logic issues
            async for _ in audio_chunk_iterator:
                pass
            return

        self.active_streams += 1
        try:
            args = [
                "ffmpeg", 
                "-hide_banner", "-loglevel", "error",
                "-f", "s16le", "-ar", str(input_rate), "-ac", "1", "-i", "pipe:0",  
                "-f", "s16le", "-ar", str(self.sample_rate), "-ac", str(self.channels), 
                "pipe:1" 
            ]
            
            p = await asyncio.create_subprocess_exec(
                *args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            async def write_stdin():
                try:
                    async for chunk in audio_chunk_iterator:
                        if chunk:
                            p.stdin.write(chunk)
                            await p.stdin.drain()
                    p.stdin.close()
                except Exception as e:
                    logging.error(f"[AudioPipe] Error writing to FFmpeg: {e}")

            async def read_stdout():
                try:
                    chunks_read = 0
                    while True:
                        # Read PCM chunks (e.g. 4KB)
                        data = await p.stdout.read(4096)
                        if not data:
                            break
                        await self.queue.put(data)
                        chunks_read += 1
                        if chunks_read % 50 == 0:
                            logging.debug(f"[AudioPipe] Converter produced {chunks_read} PCM chunks so far...")
                    logging.info(f"[AudioPipe] Converter finished. Total PCM chunks: {chunks_read}")
                except Exception as e:
                    logging.error(f"[AudioPipe] Error reading from FFmpeg output: {e}")

            async def read_stderr():
                try:
                    while True:
                        line = await p.stderr.readline()
                        if not line:
                            break
                        # Log FFmpeg errors/warnings
                        line_str = line.decode().strip()
                        if "Error" in line_str or "Warning" in line_str:
                             logging.warning(f"[FFmpeg Internal] {line_str}")
                except Exception as e:
                    logging.error(f"[AudioPipe] Error reading stderr: {e}")

            # Run read/write concurrently
            logging.info("[AudioPipe] Starting streaming conversion...")
            await asyncio.gather(write_stdin(), read_stdout(), read_stderr())
            await p.wait()
            
            if p.returncode != 0:
                 logging.error(f"[AudioPipe] Streaming converter exited with code {p.returncode}")
            else:
                 logging.info("[AudioPipe] Streaming conversion finished successfully")
            
        except Exception as e:
            logging.error(f"[AudioPipe] Stream conversion error: {e}")
        finally:
            self.active_streams -= 1


    async def _worker_loop(self):

        loop = asyncio.get_running_loop()
        silence_count = 0
        
        def write_sync(fd, data):
            try:
                os.write(fd, data)
                return True
            except BrokenPipeError:
                return False
            except Exception as e:
                logging.error(f"[AudioPipe] Write error: {e}")
                return False

        while self.running:
            # 1. Ensure Pipe is Open
            if not self._pipe_fd:
                logging.info(f"[AudioPipe] Opening pipe {self.pipe_path}...")
                try:
                    self._pipe_fd = await loop.run_in_executor(None, os.open, self.pipe_path, os.O_WRONLY)
                    logging.info("[AudioPipe] Pipe connected!")
                    silence_count = 0 
                    
                    # Reset Timing for Realtime Pacing
                    # We want to align the "Audio Stream Time" with "Wall Clock Time"
                    self.start_time = time.time()
                    self.bytes_written_total = 0
                    
                except Exception as e:
                    logging.error(f"[AudioPipe] Failed to open pipe: {e}. Retrying in 1s...")
                    await asyncio.sleep(1)
                    continue

            # Silence chunk (100ms)
            silence_bytes = int(self.bytes_per_second * 0.1)
            silence_data = b'\x00' * silence_bytes
            
            # --- Realtime Pacing Logic ---
            # Calculate how much audio we have sent so far (in seconds)
            audio_time_sent = self.bytes_written_total / self.bytes_per_second
            
            # Calculate how much real time has passed since we started streaming
            wall_time_elapsed = time.time() - self.start_time
            
            # If we have sent MORE audio than time has passed, we are "ahead of schedule".
            # We must wait for reality to catch up.
            drift = audio_time_sent - wall_time_elapsed
            
            if drift > 0.01: # 10ms tolerance
                await asyncio.sleep(drift)

            try:
                data_to_write = None
                try:
                    data_to_write = await asyncio.wait_for(self.queue.get(), timeout=0.01) # Short timeout
                except asyncio.TimeoutError:
                    data_to_write = silence_data
                    silence_count += 1
                
                if data_to_write:
                     success = await loop.run_in_executor(None, write_sync, self._pipe_fd, data_to_write)
                     if not success:
                         logging.warning("[AudioPipe] Broken pipe writing data. Reconnecting...")
                         try: os.close(self._pipe_fd)
                         except: pass
                         self._pipe_fd = None
                         continue
                     
                     self.bytes_written_total += len(data_to_write)
                     
                     if data_to_write is not silence_data:
                         silence_count = 0 # Reset silence counter if we got real data
                     


            except Exception as e:
                logging.error(f"[AudioPipe] Worker loop unexpected error: {e}")
                await asyncio.sleep(1)
                
        logging.info("[AudioPipe] Worker loop finished (Running=False)")
