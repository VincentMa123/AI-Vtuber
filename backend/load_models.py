import os
import torch
from transformers import AutoModelForImageTextToText, AutoProcessor
import state as state
import config as config

async def load_all_models():
    """Load all necessary models into the state module."""

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
    
    print("Startup complete!")
    
    state.llm_provider = config.LLM_PROVIDER.lower()
    print(f"LLM Provider: {state.llm_provider}")
    
    if config.OPENROUTER_API_KEY:
        print(f"OpenRouter API configured with model: {config.OPENROUTER_MODEL}")
    if config.DEEPSEEK_API_KEY:
        print(f"DeepSeek API configured with model: {config.DEEPSEEK_MODEL}")
        
    print(f"TTS Provider: {config.TTS_PROVIDER}")
    if config.TTS_PROVIDER == "elevenlabs" and not config.ELEVENLABS_API_KEY:
        print("Warning: TTS_PROVIDER is elevenlabs but ELEVENLABS_API_KEY is missing!")

