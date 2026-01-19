from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import torch
from transformers import AutoModelForImageTextToText, AutoProcessor
from kokoro import KPipeline
import soundfile as sf
import re
import base64
import io
import os
import httpx
import numpy as np

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables for models
model = None
processor = None
tts_pipeline = None
local_model_available = False

# OpenRouter configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "qwen/qwen3-2b:free")  # Free Qwen model
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

class ChatRequest(BaseModel):
    message: str
    conversation_history: list = []

class ChatResponse(BaseModel):
    text: str
    audio_base64: str
    component_call: Optional[str] = None
    source: Optional[str] = None  # 'openrouter' or 'local'

@app.on_event("startup")
async def load_models():
    global model, processor, tts_pipeline, local_model_available
    
    # Try to load local model
    try:
        print("Loading Qwen3-VL model...")
        model_path = "./Qwen3-VL-2B-Instruct"
        
        if os.path.exists(model_path):
            model = AutoModelForImageTextToText.from_pretrained(
                model_path,
                torch_dtype=torch.float16,
                device_map="cuda"
            )
            processor = AutoProcessor.from_pretrained(model_path)
            model.eval()
            local_model_available = True
            print("Local Qwen3-VL model loaded successfully!")
        else:
            print(f"Local model path '{model_path}' not found. Will use OpenRouter only.")
    except Exception as e:
        print(f"Failed to load local model: {e}")
        print("Will use OpenRouter API only.")
    
    print("Loading Kokoro TTS...")
    tts_pipeline = KPipeline(lang_code="a", repo_id='hexgrad/Kokoro-82M')
    
    print("Startup complete!")
    if OPENROUTER_API_KEY:
        print(f"OpenRouter API configured with model: {OPENROUTER_MODEL}")
    else:
        print("Warning: OPENROUTER_API_KEY not set. Set it via environment variable.")

def get_system_prompt():
    """Get the combined system prompt for the VTuber."""
    tech_rules = (
        "- For any programming code block, always specify the programming language\n"
        "- For any math equation, use LaTeX format\n"
    )
    
    character_persona = """
    You are 'Lumina', a high-tech AI VTuber.
    Personality: Cheerful, helpful, but gets confused by slang.
    Keep responses concise and friendly (2-3 sentences max).
    """
    
    capability_instructions = """
    You may call components like WeatherCard by adding at the end:
    <component_call>
      <component_name>WeatherCard</component_name>
      {"city": "New York"}
    </component_call>
    """
    
    return tech_rules + "\n" + character_persona + "\n" + capability_instructions

async def call_openrouter(message: str) -> Optional[str]:
    """Call OpenRouter API and return the response text, or None if failed."""
    if not OPENROUTER_API_KEY:
        return None
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                OPENROUTER_BASE_URL,
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost:3000",
                    "X-Title": "VTuber Chat"
                },
                json={
                    "model": OPENROUTER_MODEL,
                    "messages": [
                        {"role": "system", "content": get_system_prompt()},
                        {"role": "user", "content": message}
                    ],
                    "max_tokens": 256
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"]
            else:
                print(f"OpenRouter API error: {response.status_code} - {response.text}")
                return None
                
    except Exception as e:
        print(f"OpenRouter API call failed: {e}")
        return None

def call_local_model(message: str) -> str:
    """Call the local Qwen model and return the response text."""
    messages = [
        {"role": "system", "content": get_system_prompt()},
        {"role": "user", "content": [{"type": "text", "text": message}]}
    ]
    
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = processor(text=[text], padding=True, return_tensors="pt")
    inputs = inputs.to("cuda")
    
    generated_ids = model.generate(**inputs, max_new_tokens=256)
    generated_ids_trimmed = [
        out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
    ]
    
    output_text = processor.batch_decode(
        generated_ids_trimmed, 
        skip_special_tokens=True, 
        clean_up_tokenization_spaces=False
    )[0]
    
    return output_text

def clean_text_for_tts(text):
    clean = re.sub(r'<component_call>.*?</component_call>', '', text, flags=re.DOTALL)
    clean = clean.strip()
    return str(clean)

def extract_component_call(text):
    match = re.search(r'<component_call>(.*?)</component_call>', text, re.DOTALL)
    if match:
        return match.group(1)
    return None

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        output_text = None
        source = None
        
        # Try OpenRouter first
        print("Trying OpenRouter API...")
        output_text = await call_openrouter(request.message)
        
        if output_text:
            source = "openrouter"
            print("Got response from OpenRouter")
        else:
            # Fallback to local model
            if local_model_available:
                print("Falling back to local model...")
                output_text = call_local_model(request.message)
                source = "local"
                print("Got response from local model")
            else:
                raise HTTPException(
                    status_code=503, 
                    detail="OpenRouter API failed and local model is not available"
                )
        
        # Extract component call if exists
        component_call_data = extract_component_call(output_text)
        
        # Clean text for TTS
        clean_text = clean_text_for_tts(output_text)
        
        # Generate audio
        generator = tts_pipeline(clean_text, voice="jf_alpha", speed=1.1)
        
        # Collect audio chunks
        audio_chunks = []
        for gs, ps, audio in generator:
            audio_chunks.append(audio)
        
        # Concatenate audio
        full_audio = np.concatenate(audio_chunks)
        
        # Convert to base64
        buffer = io.BytesIO()
        sf.write(buffer, full_audio, samplerate=24000, format='WAV')
        buffer.seek(0)
        audio_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        
        return ChatResponse(
            text=clean_text,
            audio_base64=audio_base64,
            component_call=component_call_data,
            source=source
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {
        "status": "ok", 
        "local_model_loaded": local_model_available,
        "openrouter_configured": bool(OPENROUTER_API_KEY)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)