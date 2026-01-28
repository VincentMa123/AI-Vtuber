from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import core.check_models as check_models
from llm import OpenRouterProvider, DeepSeekProvider, RemoteVLLMProvider
from tts import TTSManager
from rag import initialize_rag
from vision import HeartbeatRequest, HeartbeatResponse, VisionHeartbeat
import core.config as config
import uvicorn
import logging
import core.logger as logger

from chat.aggregator import ChatAggregator
from chat.models import (
    ChatMessage, AggregationConfig,
    BatchChatRequest,
)
from chat.response_handler import handle_aggregated_response
from websocket.manager import ws_manager
import json

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
    "remote": RemoteVLLMProvider()
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
        from twitch.bot import start_twitch_bot
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
    global vision_heartbeat
    
    vision_heartbeat = VisionHeartbeat(
        llm_providers=llm_providers,
        text_to_speech_func=tts_manager.generate_audio,
        text_to_speech_stream_func=tts_manager.generate_audio_stream
    )
    
    logging.info("[Startup] Vision Heartbeat system initialized")

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
            
            try:
                data = json.loads(raw_data)
                
                # Handle Vision Frames
                if data.get("type") == "vision_frame":
                    if not vision_heartbeat:
                        continue
                        
                    request = HeartbeatRequest(
                        image_base64=data.get("image_base64"),
                        timestamp=data.get("timestamp", 0),
                        use_native_capture=data.get("use_native_capture", False)
                    )
                    
                    async for chunk in vision_heartbeat.process_heartbeat_stream(request):
                        # Map Vision types to Frontend types
                        msg_type = chunk.get("type")
                        
                        if msg_type == "audio":
                            await websocket.send_json({
                                "type": "audio_chunk",
                                "audio_base64": chunk.get("data"),
                                "complete": False
                            })
                        elif msg_type == "status":
                             # We can send status updates to debug UI
                             await websocket.send_json({
                                "type": "vision_status",
                                "content": chunk.get("content")
                             })
                        elif msg_type == "stop":
                            await websocket.send_json({
                                "type": "audio_chunk",
                                "complete": True
                            })
                            
            except json.JSONDecodeError:
                pass
            except Exception as e:
                logging.error(f"[WebSocket] processing error: {e}")
                
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logging.error(f"[WebSocket] Error: {e}")
        ws_manager.disconnect(websocket)


@app.post("/api/vision/heartbeat", response_model=HeartbeatResponse)
async def vision_heartbeat_endpoint(request: HeartbeatRequest):
    if not vision_heartbeat:
        raise HTTPException(status_code=503, detail="Vision system not initialized")
    
    return await vision_heartbeat.process_heartbeat(request)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)