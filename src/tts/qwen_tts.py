import os
import io
import time
import queue
import logging
import threading
import asyncio
import base64
import requests
import pathlib
import wave
from typing import Optional, AsyncGenerator

import dashscope
from dashscope.audio.qwen_tts_realtime import QwenTtsRealtime, QwenTtsRealtimeCallback, AudioFormat

from .base import BaseTTSProvider, create_wav_buffer
from .text_normalizer import normalize_for_tts, is_sentence_boundary
import core.config as config

class QwenTTSCallback(QwenTtsRealtimeCallback):
    def __init__(self, provider):
        # We hold a reference to the provider to access the queue and event
        self.provider = provider

    def on_open(self) -> None:
        logging.info('[QwenTTS] WebSocket session established.')
        self.provider.is_connected = True

    def on_close(self, close_status_code, close_msg) -> None:
        logging.info(f'[QwenTTS] WebSocket closed. Code={close_status_code}, Msg={close_msg}')
        self.provider.is_connected = False
        # Signal immediate end of stream when connection closes
        self.provider.audio_queue.put(('finished', None))

    def on_event(self, response: dict) -> None:
        try:
            event_type = response.get('type', '')
            if event_type == 'session.created':
                logging.info(f'[QwenTTS] Session created: {response["session"]["id"]}')
            
            elif event_type == 'response.audio.delta':
                audio_data = base64.b64decode(response['delta'])
                self.provider.audio_queue.put(('audio', audio_data))
            
            elif event_type == 'response.done':
                logging.info(f'[QwenTTS] Response done.')
                # Signal end of current turn
                self.provider.audio_queue.put(('done', None))
                
            elif event_type == 'session.finished':
                logging.info('[QwenTTS] Session finished.')
                self.provider.is_connected = False
                self.provider.audio_queue.put(('finished', None))
                
            elif event_type == 'error':
                 logging.error(f'[QwenTTS] Error event: {response}')
                 self.provider.audio_queue.put(('error', response.get('message', 'Unknown error')))

        except Exception as e:
            logging.error(f'[QwenTTS] Callback error: {e}')

class QwenTTSProvider(BaseTTSProvider):
    def __init__(self):
        self.api_key = config.QWEN_API_KEY
        if not self.api_key:
            logging.error("[QwenTTS] QWEN_API_KEY not found in config.")
        
        dashscope.api_key = self.api_key
        
        self.voice_file = getattr(config, "QWEN_TTS_VOICE_FILE", "voice.mp3")
        self.model = getattr(config, "QWEN_TTS_MODEL", "qwen3-tts-vc-realtime-2025-11-27")
        
        self.cached_voice_id = None
        self.voice_lock = asyncio.Lock()
        
        self.stream_client: Optional[QwenTtsRealtime] = None
        self.is_connected = False
        self.audio_queue = queue.Queue() 
        
        self.processing_lock = asyncio.Lock()

    def _create_voice(self, file_path_str: str) -> str:

        file_path = pathlib.Path(file_path_str)
        if not file_path.exists():
             project_root = os.getcwd() 
             file_path = pathlib.Path(project_root) / file_path_str
             
        if not file_path.exists():
             logging.error(f"[QwenTTS] Voice file not found at {file_path_str}")
             raise FileNotFoundError(f"Voice file not found: {file_path}")

        logging.info(f"[QwenTTS] Enrolling voice from {file_path}...")
        
        base64_str = base64.b64encode(file_path.read_bytes()).decode()
        data_uri = f"data:audio/mpeg;base64,{base64_str}"

        url = "https://dashscope-intl.aliyuncs.com/api/v1/services/audio/tts/customization"
        payload = {
            "model": "qwen-voice-enrollment",
            "input": {
                "action": "create",
                "target_model": self.model,
                "preferred_name": "cloned_voice",
                "audio": {"data": data_uri}
            }
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        resp = requests.post(url, json=payload, headers=headers)
        if resp.status_code != 200:
             logging.error(f"[QwenTTS] Enrollment failed: {resp.text}")
             if "voice" in resp.text and "already exists" in resp.text: 
                  pass
             raise RuntimeError(f"Failed to create voice: {resp.status_code}")

        voice_id = resp.json()["output"]["voice"]
        logging.info(f"[QwenTTS] Voice enrolled successfully. ID: {voice_id}")
        return voice_id

    async def get_voice_id(self):
        async with self.voice_lock:
            if self.cached_voice_id:
                return self.cached_voice_id
            
            loop = asyncio.get_event_loop()
            try:
                self.cached_voice_id = await loop.run_in_executor(None, self._create_voice, self.voice_file)
            except Exception as e:
                logging.error(f"[QwenTTS] Failed to create voice: {e}")
                # Fallback or retry logic could go here
                raise e
                
            return self.cached_voice_id
            
    async def initialize(self):

        try:
             logging.info("[QwenTTS] Initializing... Enrolling/Checking voice.")
             await self.get_voice_id()
             logging.info("[QwenTTS] Initialization complete.")
        except Exception as e:
             logging.error(f"[QwenTTS] Initialization failed: {e}")

    async def _ensure_connected(self):
        """Ensures the WebSocket connection is active."""
        if self.is_connected and self.stream_client:
            return

        logging.info("[QwenTTS] Connecting to DashScope...")
        
        # Reset queue
        while not self.audio_queue.empty():
            try: self.audio_queue.get_nowait()
            except queue.Empty: pass

        callback = QwenTTSCallback(self)
        self.stream_client = QwenTtsRealtime(
            model=self.model,
            callback=callback,
            url='wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime'
        )

        try:
            # Connect is blocking
            await asyncio.to_thread(self.stream_client.connect)
            
            voice_id = await self.get_voice_id()
             
            # Update session with voice
            self.stream_client.update_session(
                voice=voice_id,
                response_format=AudioFormat.PCM_24000HZ_MONO_16BIT,
                mode='server_commit',
            )
            self.is_connected = True
            
        except Exception as e:
            logging.error(f"[QwenTTS] Connection failed: {e}")
            self.is_connected = False
            self.stream_client = None
            raise e

    async def generate_audio_stream(self, text_stream: AsyncGenerator[str, None]) -> AsyncGenerator[bytes, None]:
        
        async with self.processing_lock:
            try:
                start_time = time.time()
                await self._ensure_connected()
                end_time = time.time()
                logging.info(f"[QwenTTS] Connected in {end_time - start_time} seconds.")
            except Exception as e:
                logging.error(f"[QwenTTS] Could not connect: {e}")
                return

            # Drain queue of any old events
            while not self.audio_queue.empty():
                try: self.audio_queue.get_nowait()
                except: pass

            # Background task to feed text with sentence buffering for normalization
            async def feed_text():
                try:
                    # Buffer to accumulate text until sentence boundary
                    text_buffer = ""
                    
                    async for text_chunk in text_stream:
                        if not text_chunk or not self.stream_client:
                            continue
                        
                        text_buffer += text_chunk
                        
                        last_boundary_idx = -1
                        for i in range(len(text_buffer)):
                            if is_sentence_boundary(text_buffer, i):
                                last_boundary_idx = i
                        
                        if last_boundary_idx >= 0:
                            complete_text = text_buffer[:last_boundary_idx + 1]
                            text_buffer = text_buffer[last_boundary_idx + 1:]
                
                            normalized = normalize_for_tts(complete_text)
                            if normalized:  # Only send if not empty after cleaning
                                logging.info(f"[QwenTTS] Sending to TTS: '{normalized[:80]}{'...' if len(normalized) > 80 else ''}'")
                                await asyncio.to_thread(self.stream_client.append_text, normalized)
                            else:
                                logging.debug(f"[QwenTTS] Skipped empty/short chunk: '{complete_text[:50]}'")
                    
                    if text_buffer and self.stream_client:
                        normalized = normalize_for_tts(text_buffer)
                        if normalized:
                            logging.info(f"[QwenTTS] Sending final to TTS: '{normalized[:80]}{'...' if len(normalized) > 80 else ''}'")
                            await asyncio.to_thread(self.stream_client.append_text, normalized)
                    
                    if self.stream_client:
                        await asyncio.to_thread(self.stream_client.finish)
                    
                except Exception as e:
                    logging.error(f"[QwenTTS] Error feeding text: {e}")

            feed_task = asyncio.create_task(feed_text())

            audio_chunk_buffer = []
            chunks_yielded = 0
            timeout_counter = 0
            max_empty_iterations = 300  # ~3 seconds with 0.01s sleep
            
            while True:
                try:
                    try:
                        item = self.audio_queue.get_nowait()
                        timeout_counter = 0  # Reset timeout on message received
                    except queue.Empty:
                        timeout_counter += 1
                        
                        # Break if connection is lost and no messages for extended period
                        if not self.is_connected and timeout_counter > max_empty_iterations:
                            logging.warning("[QwenTTS] WebSocket disconnected with no audio received. Breaking loop.")
                            break
                        
                        await asyncio.sleep(0.01)
                        continue

                    msg_type, data = item
                    
                    if msg_type == 'audio':
                        chunk = data
                        audio_chunk_buffer.append(chunk)

                        if sum(len(c) for c in audio_chunk_buffer) >= 32000:
                            full_audio = b''.join(audio_chunk_buffer)
                            audio_chunk_buffer = []
                            chunks_yielded += 1
                            
                            wav_bytes = create_wav_buffer(full_audio)
                            
                            yield wav_bytes
                            
                    elif msg_type == 'done':
                        logging.info("[QwenTTS] Turn complete signal received.")
                        break
                        
                    elif msg_type == 'finished':
                        logging.info("[QwenTTS] Session finished signal.")
                        self.is_connected = False
                        break
                        
                    elif msg_type == 'error':
                        logging.error(f"[QwenTTS] Stream error: {data}")
                        break

                except Exception as e:
                     logging.error(f"[QwenTTS] Loop error: {e}")
                     break

            # Yield remaining audio
            if audio_chunk_buffer:
                full_audio = b''.join(audio_chunk_buffer)
                wav_bytes = create_wav_buffer(full_audio)
                yield wav_bytes
                logging.info(f"[QwenTTS] Yielded final WAV.")

            await feed_task
            
            # Clean up session state
            self.stream_client = None
            self.is_connected = False
