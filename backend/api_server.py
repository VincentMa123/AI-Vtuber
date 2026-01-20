from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import base64
import load_models
import model_calling
import tts_calling
import config
import utils
import state
import re

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str
    conversation_history: list = []
    image_base64: Optional[str] = None
    tts_enabled: bool = True  # New field to control TTS

class ChatResponse(BaseModel):
    text: str
    audio_base64: str
    component_call: Optional[str] = None
    source: Optional[str] = None  # 'openrouter', 'deepseek', or 'local'

@app.on_event("startup")
async def startup_event():
    await load_models.load_all_models()

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        output_text = None
        source = None
        
        print(f"Incoming Request Model Parsed: {request.dict()}")
        print(f"Incoming Request - TTS Enabled: {request.tts_enabled}")

        if request.image_base64:
            print(f"Received image data (length: {len(request.image_base64)})")
        
        # Use runtime LLM provider (can be changed via API)
        llm_provider = state.llm_provider
        
        # DeepSeek doesn't support images - auto-switch to OpenRouter for image requests
        if request.image_base64 and llm_provider == "deepseek":
            print("DeepSeek doesn't support vision - using OpenRouter for this image request")
            llm_provider = "openrouter"
        
        print(f"Using LLM provider: {llm_provider}")
        
        if llm_provider == "deepseek":
            print("Trying DeepSeek API...")
            output_text = await model_calling.call_deepseek(request.message, request.conversation_history, request.image_base64)
            if output_text:
                source = "deepseek"
                print("Got response from DeepSeek")
        elif llm_provider == "openrouter":
            print("Trying OpenRouter API...")
            output_text = await model_calling.call_openrouter(request.message, request.conversation_history, request.image_base64)
            if output_text:
                source = "openrouter"
                print("Got response from OpenRouter")
        elif llm_provider == "local":
            if state.local_model_available:
                print("Using local model...")
                output_text = model_calling.call_local_model(request.message, request.conversation_history, request.image_base64)
                source = "local"
                print("Got response from local model")
        
        # Fallback chain: if primary provider failed, try others
        if not output_text:
            print(f"Primary provider '{llm_provider}' failed, trying fallbacks...")
            
            # Try OpenRouter if not already tried
            if llm_provider != "openrouter" and config.OPENROUTER_API_KEY:
                print("Fallback: Trying OpenRouter...")
                output_text = await model_calling.call_openrouter(request.message, request.conversation_history, request.image_base64)
                if output_text:
                    source = "openrouter"
            
            # Try DeepSeek if still no response
            if not output_text and llm_provider != "deepseek" and config.DEEPSEEK_API_KEY:
                print("Fallback: Trying DeepSeek...")
                output_text = await model_calling.call_deepseek(request.message, request.conversation_history, request.image_base64)
                if output_text:
                    source = "deepseek"
            
            # Try local model as last resort
            if not output_text and state.local_model_available:
                print("Fallback: Using local model...")
                output_text = model_calling.call_local_model(request.message, request.conversation_history, request.image_base64)
                source = "local"
        
        if not output_text:
            raise HTTPException(
                status_code=503, 
                detail="All LLM providers failed"
            )
        
        # Debug: Print raw model output
        print(f"=== RAW MODEL OUTPUT ===\n{output_text}\n========================")
        
        # Extract component call if exists
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
                audio_bytes = await tts_calling.generate_audio_elevenlabs(clean_text)
                if audio_bytes:
                    audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
                else:
                    print("ElevenLabs failed. Falling back to Kokoro TTS...")
                    # Fall through to Kokoro
            
            elif config.TTS_PROVIDER == "edge":
                print("Generating audio with Edge TTS...")
                audio_b64_edge = await tts_calling.generate_audio_edge(clean_text)
                if audio_b64_edge:
                    audio_base64 = audio_b64_edge
                else:
                    print("Edge TTS failed. Falling back to Kokoro TTS...")
                    # Fall through to Kokoro
            
            # Use Kokoro (as default or fallback)
            if not audio_base64:
                print("Generating audio with Kokoro...")
                audio_b64_kokoro = tts_calling.generate_audio_kokoro(clean_text)
                if audio_b64_kokoro:
                    audio_base64 = audio_b64_kokoro
                else:
                    print("Kokoro generation failed or pipeline not loaded.")
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

class SetProviderRequest(BaseModel):
    provider: str

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)