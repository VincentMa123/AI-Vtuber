import json
import os
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
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
from chat.emotions import preload as preload_emotions
from chat.models import AggregationConfig
from chat.response_handler import handle_aggregated_response
from ws.manager import ws_manager
from ws.callbacks import broadcast_browser_update
from audio.pipe import AudioPipe
from audio.interceptor import install_tts_interceptor
from twitch.bot import start_twitch_bot, get_twitch_bot
from youtube.bot import start_youtube_bot, get_youtube_bot, stop_youtube_task
from rag.crawler import WebsiteCrawler
from rag.indexer import WebsiteIndexer
from rag import CRAWL_RESULT_PATH, WEBSITE_INDEX_PATH


AUDIO_PLAYBACK_COMPLETE_EVENT = "audio_playback_complete"

llm_providers = {
    "openrouter": OpenRouterProvider(),
    "deepseek": DeepSeekProvider(),
}

vllm_providers = {
    "remote": RemoteVLLMProvider(),
    "qwen": QwenProvider(),
}


async def _aggregation_callback(message: str, dominant_emotion: str = None, platform: str = "twitch"):
    if dominant_emotion:
        logging.info(f"[ChatAggregator] Emotion: {dominant_emotion}")
    await handle_aggregated_response(
        message=message,
        llm_providers=llm_providers,
        tts_manager=state.tts_manager,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.setup_logger()
    await check_models.check_models()
    preload_emotions()
    await _init_services()
    logging.info("[Startup] System fully initialized")

    yield

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
                except Exception:
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


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _init_services():

    # Crawl and index the website for RAG (search_website tool)
    try:
        logging.info(f"[Startup] Crawling website: {config.BROWSER_BASE_URL}")
        crawler = WebsiteCrawler(config.BROWSER_BASE_URL)
        result = await crawler.crawl(max_pages=10)
        
        os.makedirs(os.path.dirname(CRAWL_RESULT_PATH), exist_ok=True)
        with open(CRAWL_RESULT_PATH, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        logging.info(f"[Startup] Crawl complete: {len(result.get('sitemap', []))} nav links, {len(result.get('content', []))} pages indexed")

        indexer = WebsiteIndexer(index_path=WEBSITE_INDEX_PATH)
        indexer.build_index(CRAWL_RESULT_PATH)
        logging.info("[Startup] Website index built")
    except Exception as e:
        logging.error(f"[Startup] Crawl/index failed (search_website may not work): {e}")

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
            channel_handle=config.YOUTUBE_CHANNEL_HANDLE,
            aggregator=state.chat_aggregator,
        )
        target = config.YOUTUBE_CHANNEL_HANDLE or config.YOUTUBE_VIDEO_ID
        logging.info(f"[Startup] YouTube bot initialized for: {target}")
    else:
        logging.info("[Startup] YouTube integration disabled")

    # Audio Pipe (headless streaming)
    state.audio_pipe = AudioPipe()
    await state.audio_pipe.start()
    logging.info("[Startup] AudioPipe initialized")


    try:
        install_tts_interceptor(state.tts_manager, state.audio_pipe)
        logging.info("[Startup] TTS interceptor installed")
    except Exception as e:
        logging.error(f"[Startup] Failed to install TTS interceptor: {e}")

    state.chat_aggregator.response_callback = _aggregation_callback

    state.vision_heartbeat = VisionHeartbeat(
        llm_providers=vllm_providers,
        text_to_speech_stream_func=state.tts_manager.generate_audio_stream,
    )
    await state.vision_heartbeat.start_browser_loop(on_update=broadcast_browser_update)
    logging.info("[Startup] Vision heartbeat & browser loop started")

@app.get("/shell")
async def get_shell():
    overlay_url = config.VTUBER_FRONTEND_URL
    if '?' in overlay_url:
        overlay_url += '&autoplay=1'
    else:
        overlay_url += '?autoplay=1'

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>VTuber Shell</title>
        <style>
            body, html {{ margin: 0; padding: 0; width: 100vw; height: 100vh; overflow: hidden; background: #fff; cursor: none !important; }}
            iframe {{ border: none; position: absolute; top: 0; left: 0; width: 100%; height: 100%; }}
            #content-frame {{ z-index: 1; }}
            #vtuber-frame {{ z-index: 9999; pointer-events: none; }}
        </style>
    </head>
    <body>
        <iframe id="content-frame" name="content-frame" src="{config.BROWSER_BASE_URL}"
            sandbox="allow-forms allow-scripts allow-same-origin allow-popups allow-downloads allow-modals"
            allow="autoplay; microphone; camera; geolocation; payment">
        </iframe>
        <iframe id="vtuber-frame" name="vtuber-frame" src="{overlay_url}"
            allow="autoplay; microphone; camera" allowtransparency="true">
        </iframe>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            raw_data = await websocket.receive_text()
            try:
                data = json.loads(raw_data)
                if data.get("type") == AUDIO_PLAYBACK_COMPLETE_EVENT:
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