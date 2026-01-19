import os
import torch
from transformers import AutoModelForImageTextToText, AutoProcessor
from kokoro import KPipeline
import state as state
import config as config

async def load_all_models():
    """Load all necessary models into the state module."""
    
    # Try to load local model
    try:
        print("Loading Qwen3-VL model...")
        
        if os.path.exists(config.LOCAL_MODEL_PATH):
            state.model = AutoModelForImageTextToText.from_pretrained(
                config.LOCAL_MODEL_PATH,
                torch_dtype=torch.float16,
                device_map="cuda"
            )
            state.processor = AutoProcessor.from_pretrained(config.LOCAL_MODEL_PATH)
            state.model.eval()
            state.local_model_available = True
            print("Local Qwen3-VL model loaded successfully!")
        else:
            print(f"Local model path '{config.LOCAL_MODEL_PATH}' not found. Will use OpenRouter only.")
    except Exception as e:
        print(f"Failed to load local model: {e}")
        print("Will use OpenRouter API only.")
    
    # Load Kokoro TTS
    # Only strictly necessary if using Kokoro, but we load it anyway for fallback/switching availability
    print("Loading Kokoro TTS...")
    try:
        state.tts_pipeline = KPipeline(lang_code="a", repo_id='hexgrad/Kokoro-82M')
        print("Kokoro TTS loaded.")
    except Exception as e:
        print(f"Failed to load Kokoro TTS: {e}")
    
    print("Startup complete!")
    if config.OPENROUTER_API_KEY:
        print(f"OpenRouter API configured with model: {config.OPENROUTER_MODEL}")
    else:
        print("Warning: OPENROUTER_API_KEY not set.")
        
    print(f"TTS Provider: {config.TTS_PROVIDER}")
    if config.TTS_PROVIDER == "elevenlabs" and not config.ELEVENLABS_API_KEY:
        print("Warning: TTS_PROVIDER is elevenlabs but ELEVENLABS_API_KEY is missing!")
