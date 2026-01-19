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

class ChatResponse(BaseModel):
    text: str
    audio_base64: str
    component_call: Optional[str] = None
    source: Optional[str] = None  # 'openrouter' or 'local'

@app.on_event("startup")
async def startup_event():
    await load_models.load_all_models()

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        output_text = None
        source = None
        

        if request.image_base64:
            print(f"Received image data (length: {len(request.image_base64)})")
            
        print("Trying OpenRouter API...")
        output_text = await model_calling.call_openrouter(request.message, request.image_base64)
        
        if output_text:
            source = "openrouter"
            print("Got response from OpenRouter")
        else:
            # Fallback to local model
            if state.local_model_available:
                print("Falling back to local model...")
                output_text = model_calling.call_local_model(request.message, request.image_base64)
                source = "local"
                print("Got response from local model")
            else:
                raise HTTPException(
                    status_code=503, 
                    detail="OpenRouter API failed and local model is not available"
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
        

        if config.TTS_PROVIDER == "elevenlabs":
            print("Generating audio with ElevenLabs...")
            audio_bytes = await tts_calling.generate_audio_elevenlabs(clean_text)
            if audio_bytes:
                audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
            else:
                print("ElevenLabs failed. Falling back to Kokoro TTS...")
                # Fall through to Kokoro
        
        # Use Kokoro (as default or fallback)
        if not audio_base64:
            print("Generating audio with Kokoro...")
            audio_b64_kokoro = tts_calling.generate_audio_kokoro(clean_text)
            if audio_b64_kokoro:
                audio_base64 = audio_b64_kokoro
            else:
                print("Kokoro generation failed or pipeline not loaded.")

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
        "openrouter_configured": bool(config.OPENROUTER_API_KEY),
        "tts_provider": config.TTS_PROVIDER
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)