import json
import asyncio
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

import core.config as config
import core.logger as logger
import core.check_models as check_models
from core import state

from llm import OpenRouterProvider, DeepSeekProvider, RemoteVLLMProvider, QwenProvider
from tts import TTSManager
from vision import VisionHeartbeat
from chat.aggregator import ChatAggregator
from chat.models import AggregationConfig
from chat.response_handler import handle_aggregated_response
from ws.manager import ws_manager
from ws.callbacks import broadcast_browser_update
from audio.pipe import AudioPipe
from audio.interceptor import install_tts_interceptor
from twitch.bot import start_twitch_bot, get_twitch_bot
from youtube.bot import start_youtube_bot, get_youtube_bot, stop_youtube_task

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


llm_providers = {
    "openrouter": OpenRouterProvider(),
    "deepseek": DeepSeekProvider(),
}

vllm_providers = {
    "remote": RemoteVLLMProvider(),
    "qwen": QwenProvider(),
}


@app.on_event("startup")
async def startup_event():

    logger.setup_logger()
    await check_models.check_models()
    
    # Preload emotion model to avoid cold-start latency on first query
    from chat.emotions import preload as preload_emotions
    preload_emotions()
    
    await _init_services()
    logging.info("[Startup] System fully initialized")


@app.on_event("shutdown")
async def shutdown_event():
    logging.info("[Shutdown] Initiating graceful shutdown...")
    
    try:
        # 1. Stop vision heartbeat FIRST (stops all broadcasting)
        logging.info("[Shutdown] Stopping vision heartbeat...")
        if state.vision_heartbeat:
            try:
                await asyncio.wait_for(state.vision_heartbeat.stop_browser(), timeout=2.0)
            except asyncio.TimeoutError:
                logging.warning("[Shutdown] Vision heartbeat timeout")
            except Exception as e:
                logging.warning(f"[Shutdown] Error stopping vision: {e}")
    except Exception as e:
        logging.warning(f"[Shutdown] Error in vision stop: {e}")

    try:
        # 2. Stop bots to prevent them from broadcasting
        logging.info("[Shutdown] Stopping bots...")
        twitch_bot = get_twitch_bot()
        if twitch_bot:
            try:
                await asyncio.wait_for(twitch_bot.close(), timeout=2.0)
                logging.info("[Shutdown] Twitch bot stopped")
            except asyncio.TimeoutError:
                logging.warning("[Shutdown] Twitch bot timeout")
            except Exception as e:
                logging.warning(f"[Shutdown] Error stopping Twitch bot: {e}")
        
        yt_bot = get_youtube_bot()
        if yt_bot:
            try:
                yt_bot.shutting_down = True  # Signal bot to stop immediately
                yt_bot.running = False  # Force running flag off
                await asyncio.wait_for(yt_bot.close(), timeout=2.0)
                logging.info("[Shutdown] YouTube bot stopped")
            except asyncio.TimeoutError:
                logging.warning("[Shutdown] YouTube bot timeout, forcing cancellation")
                try:
                    await stop_youtube_task()
                except:
                    pass
            except Exception as e:
                logging.warning(f"[Shutdown] Error stopping YouTube bot: {e}")
        
    except Exception as e:
        logging.warning(f"[Shutdown] Error in bot stop: {e}")

    try:
        # 3. Close all WebSocket connections (now that nothing is broadcasting)
        logging.info("[Shutdown] Closing WebSocket connections...")
        await ws_manager.close_all()
        logging.info("[Shutdown] WebSockets closed")
    except Exception as e:
        logging.warning(f"[Shutdown] Error closing WebSockets: {e}")

    try:
        # 4. Stop remaining services
        if state.chat_aggregator:
            logging.info("[Shutdown] Stopping chat aggregator...")
            await asyncio.wait_for(state.chat_aggregator.stop(), timeout=1.0)
    except asyncio.TimeoutError:
        logging.warning("[Shutdown] Chat aggregator timeout")
    except Exception as e:
        logging.warning(f"[Shutdown] Error stopping aggregator: {e}")

    try:
        # 5. Wait for YouTube task to finish with aggressive timeout
        logging.info("[Shutdown] Cancelling YouTube task...")
        await asyncio.wait_for(stop_youtube_task(), timeout=1.0)
    except asyncio.TimeoutError:
        logging.warning("[Shutdown] YouTube task timeout")
    except Exception as e:
        logging.warning(f"[Shutdown] Error stopping YouTube task: {e}")

    logging.info("[Shutdown] Shutdown complete")


async def _init_services():

    state.tts_manager = TTSManager()
    await state.tts_manager.initialize()
    logging.info(f"[Startup] TTS initialized (provider: {config.TTS_PROVIDER})")

    aggregator_config = AggregationConfig(
        enabled=config.CHAT_AGGREGATION_ENABLED,
        window_seconds=config.AGGREGATION_WINDOW_SECONDS,
        min_response_interval=config.MIN_RESPONSE_INTERVAL_SECONDS,
        max_messages_per_user_per_window=config.MAX_MESSAGES_PER_USER_PER_WINDOW,
        min_message_length=config.MIN_MESSAGE_LENGTH,
        similarity_threshold=config.SIMILARITY_THRESHOLD,
        max_batch_size=config.MAX_BATCH_SIZE,
    )
    state.chat_aggregator = ChatAggregator(aggregator_config)
    state.chat_aggregator.duplicate_expiry_seconds = config.DUPLICATE_EXPIRY_SECONDS
    await state.chat_aggregator.start()
    logging.info("[Startup] Chat aggregator initialized")

    if config.TWITCH_ENABLED:
        await start_twitch_bot(
            token=config.TWITCH_BOT_TOKEN,
            channel=config.TWITCH_CHANNEL,
            prefix=config.TWITCH_BOT_PREFIX,
            aggregator=state.chat_aggregator,
            client_id=config.TWITCH_CLIENT_ID,
            client_secret=config.TWITCH_CLIENT_SECRET,
            bot_id=config.TWITCH_BOT_ID,
        )
        logging.info(f"[Startup] Twitch bot initialized for channel: {config.TWITCH_CHANNEL}")
    else:
        logging.info("[Startup] Twitch integration disabled")

    if config.YOUTUBE_ENABLED:
        await start_youtube_bot(
            video_id=config.YOUTUBE_VIDEO_ID,
            aggregator=state.chat_aggregator,
        )
        logging.info(f"[Startup] YouTube bot initialized for video: {config.YOUTUBE_VIDEO_ID}")
    else:
        logging.info("[Startup] YouTube integration disabled")

    # 4. Audio Pipe (headless streaming)

    state.audio_pipe = AudioPipe()
    await state.audio_pipe.start()
    logging.info("[Startup] AudioPipe initialized")


    try:
        install_tts_interceptor(state.tts_manager, state.audio_pipe)
        logging.info("[Startup] TTS interceptor installed")
    except Exception as e:
        logging.error(f"[Startup] Failed to install TTS interceptor: {e}")

    async def aggregation_callback(message: str, dominant_emotion: str = None, platform: str = "twitch"):
        if dominant_emotion:
            logging.info(f"[ChatAggregator] Emotion: {dominant_emotion}")
        await handle_aggregated_response(
            message=message,
            llm_providers=llm_providers,
            tts_manager=state.tts_manager,
        )

    state.chat_aggregator.response_callback = aggregation_callback

    state.vision_heartbeat = VisionHeartbeat(
        llm_providers=vllm_providers,
        text_to_speech_stream_func=state.tts_manager.generate_audio_stream,
    )
    await state.vision_heartbeat.start_browser_loop(on_update=broadcast_browser_update)
    logging.info("[Startup] Vision heartbeat & browser loop started")

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            raw_data = await websocket.receive_text()
            try:
                data = json.loads(raw_data)
                if data.get("type") == "audio_playback_complete":
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