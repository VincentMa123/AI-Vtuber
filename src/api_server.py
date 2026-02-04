from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import core.check_models as check_models
from llm import OpenRouterProvider, DeepSeekProvider, RemoteVLLMProvider, QwenProvider
from tts import TTSManager
from rag import initialize_rag
from vision import HeartbeatRequest, HeartbeatResponse, VisionHeartbeat
import core.config as config
import uvicorn
import logging
import core.logger as logger
from twitch.bot import start_twitch_bot
from chat.aggregator import ChatAggregator
from chat.models import (
    ChatMessage, AggregationConfig,
    BatchChatRequest,
)
from chat.response_handler import handle_aggregated_response
from ws.manager import ws_manager
import json
global vision_heartbeat

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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


tts_manager = None 
chat_aggregator = None
vision_heartbeat = None

@app.on_event("startup")
async def startup_event():
    logger.setup_logger()
    global chat_aggregator
    global tts_manager
    
    await check_models.check_models()
    
    try:
        initialize_rag()
    except Exception as e:
        logging.warning(f"[Startup] Warning: Could not initialize RAG: {e}")

    # Initialize TTS Manager
    tts_manager = TTSManager()
    await tts_manager.initialize()
    logging.info(f"[Startup] TTS Manager initialized (Provider: {config.TTS_PROVIDER})")
    
    aggregator_config = AggregationConfig(
        enabled=config.CHAT_AGGREGATION_ENABLED,
        window_seconds=config.AGGREGATION_WINDOW_SECONDS,
        min_response_interval=config.MIN_RESPONSE_INTERVAL_SECONDS,
        max_messages_per_user_per_window=config.MAX_MESSAGES_PER_USER_PER_WINDOW,
        min_message_length=config.MIN_MESSAGE_LENGTH,
        similarity_threshold=config.SIMILARITY_THRESHOLD,
        max_batch_size=config.MAX_BATCH_SIZE
    )
    chat_aggregator = ChatAggregator(aggregator_config)
    chat_aggregator.duplicate_expiry_seconds = config.DUPLICATE_EXPIRY_SECONDS
    await chat_aggregator.start()
    logging.info(f"[Startup] Chat aggregator initialized (enabled: {config.CHAT_AGGREGATION_ENABLED}, duplicate expiry: {config.DUPLICATE_EXPIRY_SECONDS}s)")
    
    # Initialize Twitch bot if enabled
    if config.TWITCH_ENABLED:
        await start_twitch_bot(
            token=config.TWITCH_BOT_TOKEN,
            channel=config.TWITCH_CHANNEL,
            prefix=config.TWITCH_BOT_PREFIX,
            aggregator=chat_aggregator
        )
        logging.info(f"[Startup] Twitch bot initialized for channel: {config.TWITCH_CHANNEL}")
    else:
        logging.info("[Startup] Twitch integration disabled")
    
    async def aggregation_callback(message: str):
        await handle_aggregated_response(
            message=message,
            llm_providers=llm_providers,
            tts_manager=tts_manager
        )
    
    chat_aggregator.response_callback = aggregation_callback
    logging.info("[Startup] Chat aggregator response callback configured")
    
    # Initialize Vision Heartbeat
    
    vision_heartbeat = VisionHeartbeat(
        llm_providers=llm_providers,
        text_to_speech_stream_func=tts_manager.generate_audio_stream
    )
    
    logging.info("[Startup] Vision Heartbeat system initialized")
    
    async def broadcast_browser_update(data):
        # Map internal vision types to frontend types
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
            # Pass through other messages (browser_screenshot, etc.)
            await ws_manager.broadcast(data)
    await vision_heartbeat.start_browser_loop(on_update=broadcast_browser_update)
    logging.info("[Startup] Browser automation loop scheduled")

@app.post("/api/chat/batch")
async def batch_chat(request: BatchChatRequest):

    if not chat_aggregator:
        raise HTTPException(status_code=503, detail="Chat aggregator not initialized")
    
    if not chat_aggregator.config.enabled:
        raise HTTPException(status_code=400, detail="Chat aggregation is disabled")
    
    # Create chat message
    chat_msg = ChatMessage(
        message=request.message,
        user_id=request.user_id,
        username=request.username,
        timestamp=request.timestamp,
        image_base64=request.image_base64
    )
    
    # Submit to aggregator
    accepted = await chat_aggregator.submit_message(chat_msg)
    
    return {
        "accepted": accepted,
        "queue_size": chat_aggregator.message_queue.qsize(),
        "message": "Message queued for processing" if accepted else "Message filtered"
    }


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
                    from core import state
                    state.signal_audio_complete()
                    
            except json.JSONDecodeError:
                pass  # Non-JSON message, ignore
    
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logging.error(f"[WebSocket] Error: {e}")
        ws_manager.disconnect(websocket)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)