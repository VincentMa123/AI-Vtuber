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
from audio.pipe import AudioPipe
from audio.interceptor import install_tts_interceptor
from ws.callbacks import broadcast_browser_update
import json
import asyncio


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
        state.audio_pipe = AudioPipe()
        await state.audio_pipe.start()
        logging.info("[Startup] AudioPipe initialized for headless streaming")
    except Exception as e:
        logging.error(f"[Startup] Failed to init AudioPipe: {e}")
        return

    # Install Interceptor
    try:
        install_tts_interceptor(state.tts_manager, state.audio_pipe)
        logging.info("[Startup] TTS interceptor installed")
    except Exception as e:
        logging.error(f"[Startup] Failed to install TTS interceptor: {e}")

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