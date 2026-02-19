import logging
from . import config as config


async def check_models():
    """Log configured providers and API keys on startup."""
    
    logging.info(f"LLM Provider (Chat): {config.LLM_PROVIDER}")
    logging.info(f"VLM Provider (Vision): {config.VLLM_PROVIDER}")
    
    if config.OPENROUTER_API_KEY:
        logging.info(f"OpenRouter API configured with model: {config.OPENROUTER_MODEL}")
    if config.DEEPSEEK_API_KEY:
        logging.info(f"DeepSeek API configured with model: {config.DEEPSEEK_MODEL}")
    if config.QWEN_API_KEY:
        logging.info(f"Qwen API configured with model: {config.QWEN_MODEL}")
    if config.REMOTE_VLLM_BASE_URL:
        model_info = config.REMOTE_VLLM_MODEL if config.REMOTE_VLLM_MODEL else "(auto-detect)"
        logging.info(f"Remote vLLM API configured: {config.REMOTE_VLLM_BASE_URL} (model: {model_info})")
        
    logging.info(f"TTS Provider: {config.TTS_PROVIDER}")
    if config.TTS_PROVIDER == "elevenlabs" and not config.ELEVENLABS_API_KEY:
        logging.warning("Warning: TTS_PROVIDER is elevenlabs but ELEVENLABS_API_KEY is missing!")

    logging.info("Startup complete!")
