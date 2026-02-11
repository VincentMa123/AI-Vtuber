from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import core.check_models as check_models
from llm import OpenRouterProvider, DeepSeekProvider, RemoteVLLMProvider, QwenProvider
from tts import TTSManager
from rag import initialize_rag
from vision import HeartbeatRequest, VisionHeartbeat
import core.config as config
import uvicorn
import logging
import core.logger as logger
from core import state
from twitch.bot import start_twitch_bot, get_twitch_bot
from chat.aggregator import ChatAggregator
from chat.models import (
    ChatMessage, AggregationConfig,
    BatchChatRequest,
)
from chat.response_handler import handle_aggregated_response
from ws.manager import ws_manager
import json
import asyncio
import base64
import struct

app = FastAPI()

# Enable CORS - allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for dev/streaming
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

llm_providers = {
    "openrouter": OpenRouterProvider(),
    "deepseek": DeepSeekProvider(),
    "remote": RemoteVLLMProvider(),
    "qwen": QwenProvider()
}

@app.on_event("startup")
async def startup_event():
    """Application startup: Initialize all services."""
    logger.setup_logger()
    
    # 1. Initialize Models & RAG
    await check_models.check_models()
    try:
        initialize_rag()
    except Exception as e:
        logging.warning(f"[Startup] Warning: Could not initialize RAG: {e}")

    # 2. Initialize Services used by API
    await init_services()
    
    logging.info("[Startup] System fully initialized")

@app.on_event("shutdown")
async def shutdown_event():

    logging.info("[Shutdown] Stopping services...")
    
    if hasattr(state, 'vision_heartbeat') and state.vision_heartbeat:
        await state.vision_heartbeat.stop_browser()
        
    if hasattr(state, 'chat_aggregator') and state.chat_aggregator:
        await state.chat_aggregator.stop()
    
    twitch_bot = get_twitch_bot()
    if twitch_bot:
        try:
            await twitch_bot.close()
            logging.info("[Shutdown] Twitch bot closed")
        except Exception as e:
            logging.error(f"[Shutdown] Error closing Twitch bot: {e}")
        
    logging.info("[Shutdown] Services stopped")

async def init_services():

    
    # TTS Manager
    state.tts_manager = TTSManager()
    await state.tts_manager.initialize()
    logging.info(f"[Startup] TTS Manager initialized (Provider: {config.TTS_PROVIDER})")
    
    # Chat Aggregator
    aggregator_config = AggregationConfig(
        enabled=config.CHAT_AGGREGATION_ENABLED,
        window_seconds=config.AGGREGATION_WINDOW_SECONDS,
        min_response_interval=config.MIN_RESPONSE_INTERVAL_SECONDS,
        max_messages_per_user_per_window=config.MAX_MESSAGES_PER_USER_PER_WINDOW,
        min_message_length=config.MIN_MESSAGE_LENGTH,
        similarity_threshold=config.SIMILARITY_THRESHOLD,
        max_batch_size=config.MAX_BATCH_SIZE
    )
    state.chat_aggregator = ChatAggregator(aggregator_config)
    state.chat_aggregator.duplicate_expiry_seconds = config.DUPLICATE_EXPIRY_SECONDS
    await state.chat_aggregator.start()
    logging.info("[Startup] Chat aggregator initialized")    
    # Twitch Bot
    if config.TWITCH_ENABLED:
        await start_twitch_bot(
            token=config.TWITCH_BOT_TOKEN,
            channel=config.TWITCH_CHANNEL,
            prefix=config.TWITCH_BOT_PREFIX,
            aggregator=state.chat_aggregator,
            client_id=config.TWITCH_CLIENT_ID,
            client_secret=config.TWITCH_CLIENT_SECRET,
            bot_id=config.TWITCH_BOT_ID
        )
        logging.info(f"[Startup] Twitch bot initialized for channel: {config.TWITCH_CHANNEL}")
    else:
        logging.info("[Startup] Twitch integration disabled")
    


    # Audio Pipe (Headless Streaming)
    try:
        from audio.pipe import AudioPipe
        state.audio_pipe = AudioPipe()
        await state.audio_pipe.start()
        logging.info("[Startup] AudioPipe initialized for headless streaming")
        
        # Monkey-patch TTS Manager to intercept audio for the pipe
        original_generate = state.tts_manager.generate_audio_stream
        
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
                                pipe_task = asyncio.create_task(state.audio_pipe.stream_audio_flow(pipe_iterator(), input_rate=sample_rate))
                                
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
                logging.info(f"[AudioPipe Interceptor] Stream finished. Sent {chunk_count} chunks ({total_bytes} bytes PCM) to pipe.")
                # Signal end of stream to pipe
                await pipe_queue.put(None)
                pass

        state.tts_manager.generate_audio_stream = patched_generate_audio_stream
        logging.info("[Startup] TTS Manager patched for AudioPipe interception")

    except Exception as e:
        logging.error(f"[Startup] Failed to init AudioPipe: {e}")

    async def aggregation_callback(message: str, dominant_emotion: str = None):
        
        if dominant_emotion:
            logging.info(f"[ChatAggregator] Processed emotion: {dominant_emotion}")
        
        await handle_aggregated_response(
            message=message,
            llm_providers=llm_providers,
            tts_manager=state.tts_manager
        )
    state.chat_aggregator.response_callback = aggregation_callback

    state.vision_heartbeat = VisionHeartbeat(
        llm_providers=llm_providers,
        text_to_speech_stream_func=state.tts_manager.generate_audio_stream
    )
    
    # Browser Loop
    async def broadcast_browser_update(data):
        msg_type = data.get("type")
        if msg_type == "audio":

            await ws_manager.broadcast({
                "type": "audio_chunk",
                "audio_base64": data.get("data"),
                "complete": False
            })
        elif msg_type == "status":
            await ws_manager.broadcast({
                "type": "vision_status",
                "content": data.get("content")
            })
        elif msg_type == "stop":
            await ws_manager.broadcast({
                "type": "audio_chunk",
                "complete": True
            })
        elif msg_type == "text":
             await ws_manager.broadcast({
                "type": "text_chunk",
                "chunk": data.get("content"),
                "complete": True
             })
        else:
            await ws_manager.broadcast(data)
            
    await state.vision_heartbeat.start_browser_loop(on_update=broadcast_browser_update)
    logging.info("[Startup] Vision Heartbeat & Browser loop scheduled")


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):

    await ws_manager.connect(websocket)
    try:
        while True:
            raw_data = await websocket.receive_text()
            # Handle incoming messages from frontend
            try:
                data = json.loads(raw_data)
                msg_type = data.get("type")
                
                if msg_type == "audio_playback_complete":
                    # Frontend signals that audio playback has finished
                    state.signal_audio_complete()
                    
            except json.JSONDecodeError:
                pass 
    
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logging.error(f"[WebSocket] Error: {e}")
        ws_manager.disconnect(websocket)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)