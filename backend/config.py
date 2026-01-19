import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# OpenRouter configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "allenai/molmo-2-8b:free")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

# TTS Configuration
TTS_PROVIDER = os.getenv("TTS_PROVIDER", "kokoro")  # 'kokoro' or 'elevenlabs'
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY_hicwo", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "lhTvHflPVOqgSWyuWQry")  

# Local Model Path
LOCAL_MODEL_PATH = "./Qwen3-VL-2B-Instruct"
