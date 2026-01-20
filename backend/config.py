import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# LLM Provider: 'openrouter', 'deepseek', or 'local'
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openrouter")

# OpenRouter configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "allenai/molmo-2-8b:free")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

# DeepSeek configuration
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1/chat/completions"

# TTS Configuration
TTS_PROVIDER = os.getenv("TTS_PROVIDER", "elevenlabs")  # 'elevenlabs' or 'realtimetts'
REALTIMETTS_ENGINE = os.getenv("REALTIMETTS_ENGINE", "system")  # 'system', 'coqui', 'openai', etc.
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "lhTvHflPVOqgSWyuWQry")  

# Local Model Path
LOCAL_MODEL_PATH = "./Qwen3-VL-2B-Instruct"

