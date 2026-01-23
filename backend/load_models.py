import os
import torch
from transformers import AutoModelForImageTextToText, AutoProcessor
import logging
import state as state
import config as config

async def load_all_models():
    """Load all necessary models into the state module."""

    try:
        logging.info("Loading Qwen3-VL model...")
        
        if os.path.exists(config.LOCAL_MODEL_PATH):
            state.model = AutoModelForImageTextToText.from_pretrained(
                config.LOCAL_MODEL_PATH,
                torch_dtype=torch.float16,
                device_map="cuda"
            )
            state.processor = AutoProcessor.from_pretrained(config.LOCAL_MODEL_PATH)
            state.model.eval()
            state.local_model_available = True
            logging.info("Local Qwen3-VL model loaded successfully!")
        else:
            logging.warning(f"Local model path '{config.LOCAL_MODEL_PATH}' not found. Will use OpenRouter only.")
    except Exception as e:
        logging.error(f"Failed to load local model: {e}")
        logging.info("Will use OpenRouter API only.")
    
    logging.info("Startup complete!")
    
    state.llm_provider = config.LLM_PROVIDER.lower()
    logging.info(f"LLM Provider: {state.llm_provider}")
    
    if config.OPENROUTER_API_KEY:
        logging.info(f"OpenRouter API configured with model: {config.OPENROUTER_MODEL}")
    if config.DEEPSEEK_API_KEY:
        logging.info(f"DeepSeek API configured with model: {config.DEEPSEEK_MODEL}")
    if config.REMOTE_VLLM_BASE_URL:
        model_info = config.REMOTE_VLLM_MODEL if config.REMOTE_VLLM_MODEL else "(auto-detect)"
        logging.info(f"Remote vLLM API configured: {config.REMOTE_VLLM_BASE_URL} (model: {model_info})")
        
    logging.info(f"TTS Provider: {config.TTS_PROVIDER}")
    if config.TTS_PROVIDER == "elevenlabs" and not config.ELEVENLABS_API_KEY:
        logging.warning("Warning: TTS_PROVIDER is elevenlabs but ELEVENLABS_API_KEY is missing!")

