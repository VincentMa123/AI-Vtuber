from typing import Optional
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import base64
import core.load_models as load_models
from llm import OpenRouterProvider, DeepSeekProvider, LocalModelProvider, RemoteVLLMProvider
from tts import TTSManager
from rag import initialize_rag
from vision.heartbeat import HeartbeatRequest, HeartbeatResponse, VisionHeartbeat
import core.config as config
import core.utils as utils
import core.state as state
import re
import uvicorn
import logging
import core.logger as logger

from chat.aggregator import ChatAggregator
from chat.models import (
    ChatMessage, AggregationConfig,
    ChatRequest, BatchChatRequest, ChatResponse,
    SetProviderRequest, AggregationConfigRequest
)
from chat.response_handler import handle_aggregated_response
from websocket.manager import ws_manager

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
    "local": LocalModelProvider(),
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
    
    await load_models.load_all_models()
    
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
    
    # Set up aggregator response callback using the modular response handler
    async def aggregation_callback(message: str, top_messages: list):
        await handle_aggregated_response(
            message=message,
            top_messages=top_messages,
            llm_providers=llm_providers,
            tts_manager=tts_manager
        )
    
    chat_aggregator.response_callback = aggregation_callback
    logging.info("[Startup] Chat aggregator response callback configured")
    
    # Initialize Vision Heartbeat
    global vision_heartbeat
    
    vision_heartbeat = VisionHeartbeat(
        llm_providers=llm_providers,
        tts_providers={}, # Unused now
        text_to_speech_func=tts_manager.generate_audio
    )
    logging.info("[Startup] Vision Heartbeat system initialized")

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        output_text = None
        source = None

        if request.image_base64:
            logging.info(f"Received image data (length: {len(request.image_base64)})")
        
        llm_provider = state.llm_provider
        
        if request.image_base64 and llm_provider == "deepseek":
            logging.info("DeepSeek doesn't support vision - using remote vLLM for this image request")
            llm_provider = "remote"
        
        logging.info(f"Using LLM provider: {llm_provider}")
        
        # Get the provider instance
        provider = llm_providers.get(llm_provider)
        if not provider:
            raise HTTPException(status_code=500, detail=f"Invalid LLM provider: {llm_provider}")
        
        # Try primary provider
        output_text = await provider.generate(request.message, request.conversation_history, request.image_base64)
        if output_text:
            source = llm_provider
            logging.info(f"Got response from {llm_provider}")
        
        # Fallback logic
        if not output_text:
            logging.warning(f"Primary provider '{llm_provider}' failed, trying fallbacks...")

            if not output_text and llm_provider != "deepseek" and config.DEEPSEEK_API_KEY:
                logging.info("Fallback: Trying DeepSeek...")
                output_text = await llm_providers["deepseek"].generate(request.message, request.conversation_history, request.image_base64)
                if output_text:
                    source = "deepseek"
            
            if not output_text and llm_provider != "openrouter" and config.OPENROUTER_API_KEY:
                logging.info("Fallback: Trying OpenRouter...")
                output_text = await llm_providers["openrouter"].generate(request.message, request.conversation_history, request.image_base64)
                if output_text:
                    source = "openrouter"
            
            if not output_text and llm_provider != "remote" and config.REMOTE_VLLM_BASE_URL:
                logging.info("Fallback: Trying remote vLLM...")
                output_text = await llm_providers["remote"].generate(request.message, request.conversation_history, request.image_base64)


                if output_text:
                    source = "remote"
            
            if not output_text and state.local_model_available:
                logging.info("Fallback: Using local model...")
                output_text = llm_providers["local"].generate(request.message, request.conversation_history, request.image_base64)
                source = "local"
        
        if not output_text:
            raise HTTPException(
                status_code=503, 
                detail="All LLM providers failed"
            )
        
        logging.debug(f"=== RAW MODEL OUTPUT ===\n{output_text}\n========================")
        
        component_call_data = utils.extract_component_call(output_text)
        
        display_text = re.sub(r'<component_call>.*?</component_call>', '', output_text, flags=re.DOTALL).strip()
        
        clean_text = utils.clean_text_for_tts(output_text)
        
        if not clean_text:
            clean_text = "Processing that for you now!"
        
        if not display_text:
            display_text = "*Processing action...*"
    
        audio_base64 = ""
        

        if request.tts_enabled:
            audio_base64 = await tts_manager.generate_audio(clean_text)
        else:
            logging.info("TTS disabled for this request.")


        return ChatResponse(
            text=display_text,
            audio_base64=audio_base64,
            component_call=component_call_data,
            source=source
        )
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {
        "status": "ok", 
        "local_model_loaded": state.local_model_available,
        "llm_provider": state.llm_provider,
        "openrouter_configured": bool(config.OPENROUTER_API_KEY),
        "deepseek_configured": bool(config.DEEPSEEK_API_KEY),
        "remote_vllm_configured": bool(config.REMOTE_VLLM_BASE_URL),
        "tts_provider": config.TTS_PROVIDER
    }

@app.get("/api/llm-provider")
async def get_llm_provider():
    """Get current LLM provider."""
    return {
        "provider": state.llm_provider,
        "available": ["openrouter", "deepseek", "local", "remote"]
    }


@app.post("/api/llm-provider")
async def set_llm_provider(request: SetProviderRequest):
    """Set the LLM provider at runtime."""
    provider = request.provider.lower()
    
    if provider not in ["openrouter", "deepseek", "local", "remote"]:
        raise HTTPException(status_code=400, detail="Invalid provider. Must be 'openrouter', 'deepseek', 'local', or 'remote'")
    
    if provider == "local" and not state.local_model_available:
        raise HTTPException(status_code=400, detail="Local model is not available")
    
    state.llm_provider = provider
    logging.info(f"LLM provider changed to: {provider}")
    
    return {"provider": state.llm_provider, "message": f"Switched to {provider}"}

@app.post("/api/chat/batch")
async def batch_chat(request: BatchChatRequest):
    """Submit a message to the chat aggregation queue"""
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

@app.get("/api/chat/aggregation-status")
async def get_aggregation_status():
    """Get current chat aggregation status"""
    if not chat_aggregator:
        raise HTTPException(status_code=503, detail="Chat aggregator not initialized")
    
    return chat_aggregator.get_status()

@app.post("/api/chat/aggregation-config")
async def update_aggregation_config(request: AggregationConfigRequest):
    """Update chat aggregation configuration"""
    if not chat_aggregator:
        raise HTTPException(status_code=503, detail="Chat aggregator not initialized")
    
    # Update config with provided values
    updates = {k: v for k, v in request.dict().items() if v is not None}
    chat_aggregator.update_config(**updates)
    
    return {
        "message": "Configuration updated",
        "current_config": chat_aggregator.get_status()
    }

@app.post("/api/chat/aggregation-reset")
async def reset_aggregation():
    """Reset aggregation state (clear caches) - useful for testing"""
    if not chat_aggregator:
        raise HTTPException(status_code=503, detail="Chat aggregator not initialized")
    
    chat_aggregator.reset()
    
    return {
        "message": "Aggregation state reset",
        "status": chat_aggregator.get_status()
    }

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket endpoint for real-time chat updates"""
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
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