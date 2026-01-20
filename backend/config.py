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
TTS_PROVIDER = os.getenv("TTS_PROVIDER", "kokoro")  # 'kokoro', 'elevenlabs', or 'edge'
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "lhTvHflPVOqgSWyuWQry")  

# Edge TTS Configuration (free, no API key needed)
# Popular voices: en-US-AvaMultilingualNeural, en-US-AriaNeural, en-US-GuyNeural, id-ID-ArdiNeural (Indonesian)
EDGE_TTS_VOICE = os.getenv("EDGE_TTS_VOICE", "en-US-AvaMultilingualNeural")  

# Local Model Path
LOCAL_MODEL_PATH = "./Qwen3-VL-2B-Instruct"

