from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import base64
import load_models
from llm import OpenRouterProvider, DeepSeekProvider, LocalModelProvider
from tts import ElevenLabsProvider, RealtimeTTSProvider
from rag import initialize_rag
import config
import utils
import state
import re
from chat_aggregator import ChatAggregator, ChatMessage, AggregationConfig

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
    "local": LocalModelProvider()
}

tts_providers = {
    "elevenlabs": ElevenLabsProvider(),
    "realtimetts": None 
}

class ChatRequest(BaseModel):
    message: str
    conversation_history: list = []
    image_base64: Optional[str] = None
    tts_enabled: bool = True  
    use_aggregation: bool = False  # NEW: Toggle aggregation for this request

class BatchChatRequest(BaseModel):
    message: str
    user_id: str
    username: str = "Anonymous"
    image_base64: Optional[str] = None
    timestamp: Optional[float] = None

class ChatResponse(BaseModel):
    text: str
    audio_base64: str
    component_call: Optional[str] = None
    source: Optional[str] = None 

class SetProviderRequest(BaseModel):
    provider: str

class AggregationConfigRequest(BaseModel):
    enabled: Optional[bool] = None
    window_seconds: Optional[float] = None
    min_response_interval: Optional[float] = None
    max_messages_per_user_per_window: Optional[int] = None
    
chat_aggregator = None

@app.on_event("startup")
async def startup_event():
    global chat_aggregator
    
    await load_models.load_all_models()
    
    try:
        initialize_rag()
    except Exception as e:
        print(f"[Startup] Warning: Could not initialize RAG: {e}")
    
    aggregator_config = AggregationConfig(
        enabled=config.CHAT_AGGREGATION_ENABLED,
        window_seconds=config.AGGREGATION_WINDOW_SECONDS,
        min_response_interval=config.MIN_RESPONSE_INTERVAL_SECONDS,
        max_messages_per_user_per_window=config.MAX_MESSAGES_PER_USER_PER_WINDOW,
        min_message_length=config.MIN_MESSAGE_LENGTH,
        similarity_threshold=config.SIMILARITY_THRESHOLD
    )
    chat_aggregator = ChatAggregator(aggregator_config)
    chat_aggregator.duplicate_expiry_seconds = config.DUPLICATE_EXPIRY_SECONDS
    await chat_aggregator.start()
    print(f"[Startup] Chat aggregator initialized (enabled: {config.CHAT_AGGREGATION_ENABLED}, duplicate expiry: {config.DUPLICATE_EXPIRY_SECONDS}s)")

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        output_text = None
        source = None

        if request.image_base64:
            print(f"Received image data (length: {len(request.image_base64)})")
        
        llm_provider = state.llm_provider
        
        if request.image_base64 and llm_provider == "deepseek":
            print("DeepSeek doesn't support vision - using OpenRouter for this image request")
            llm_provider = "openrouter"
        
        print(f"Using LLM provider: {llm_provider}")
        
        # Get the provider instance
        provider = llm_providers.get(llm_provider)
        if not provider:
            raise HTTPException(status_code=500, detail=f"Invalid LLM provider: {llm_provider}")
        
        # Try primary provider
        output_text = await provider.generate(request.message, request.conversation_history, request.image_base64)
        if output_text:
            source = llm_provider
            print(f"Got response from {llm_provider}")
        
        # Fallback logic
        if not output_text:
            print(f"Primary provider '{llm_provider}' failed, trying fallbacks...")

            if not output_text and llm_provider != "openrouter" and config.OPENROUTER_API_KEY:
                print("Fallback: Trying OpenRouter...")
                output_text = await llm_providers["openrouter"].generate(request.message, request.conversation_history, request.image_base64)
                if output_text:
                    source = "openrouter"
            
            if not output_text and llm_provider != "deepseek" and config.DEEPSEEK_API_KEY:
                print("Fallback: Trying DeepSeek...")
                output_text = await llm_providers["deepseek"].generate(request.message, request.conversation_history, request.image_base64)
                if output_text:
                    source = "deepseek"
            
            if not output_text and state.local_model_available:
                print("Fallback: Using local model...")
                output_text = llm_providers["local"].generate(request.message, request.conversation_history, request.image_base64)
                source = "local"
        
        if not output_text:
            raise HTTPException(
                status_code=503, 
                detail="All LLM providers failed"
            )
        
        print(f"=== RAW MODEL OUTPUT ===\n{output_text}\n========================")
        
        component_call_data = utils.extract_component_call(output_text)
        
        display_text = re.sub(r'<component_call>.*?</component_call>', '', output_text, flags=re.DOTALL).strip()
        
        clean_text = utils.clean_text_for_tts(output_text)
        
        if not clean_text:
            clean_text = "Processing that for you now!"
        
        if not display_text:
            display_text = "*Processing action...*"
    
        audio_base64 = ""
        

        if request.tts_enabled:
            if config.TTS_PROVIDER == "elevenlabs":
                print("Generating audio with ElevenLabs...")
                audio_bytes = await tts_providers["elevenlabs"].generate_audio(clean_text)
                if audio_bytes:
                    audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
                else:
                    print("ElevenLabs failed to generate audio")
            
            elif config.TTS_PROVIDER == "realtimetts":
                print(f"Generating audio with RealtimeTTS (Engine: {config.REALTIMETTS_ENGINE})...")
                
                # Lazy initialization
                if tts_providers["realtimetts"] is None:
                    try:
                        tts_providers["realtimetts"] = RealtimeTTSProvider(config.REALTIMETTS_ENGINE)
                    except Exception as e:
                        print(f"Failed to initialize RealtimeTTS: {e}")
                
                if tts_providers["realtimetts"]:
                    audio_bytes = await tts_providers["realtimetts"].generate_audio(clean_text)
                    if audio_bytes:
                         audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
                    else:
                        print("RealtimeTTS generated no audio")
                else:
                    print("RealtimeTTS service not available")
        else:
            print("TTS disabled for this request.")


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
        "tts_provider": config.TTS_PROVIDER
    }

@app.get("/api/llm-provider")
async def get_llm_provider():
    """Get current LLM provider."""
    return {
        "provider": state.llm_provider,
        "available": ["openrouter", "deepseek", "local"]
    }


@app.post("/api/llm-provider")
async def set_llm_provider(request: SetProviderRequest):
    """Set the LLM provider at runtime."""
    provider = request.provider.lower()
    
    if provider not in ["openrouter", "deepseek", "local"]:
        raise HTTPException(status_code=400, detail="Invalid provider. Must be 'openrouter', 'deepseek', or 'local'")
    
    if provider == "local" and not state.local_model_available:
        raise HTTPException(status_code=400, detail="Local model is not available")
    
    state.llm_provider = provider
    print(f"LLM provider changed to: {provider}")
    
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)