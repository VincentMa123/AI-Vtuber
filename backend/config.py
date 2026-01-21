import os
from dotenv import load_dotenv

load_dotenv()

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openrouter")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "allenai/molmo-2-8b:free")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1/chat/completions"

TTS_PROVIDER = os.getenv("TTS_PROVIDER", "elevenlabs")  
REALTIMETTS_ENGINE = os.getenv("REALTIMETTS_ENGINE", "system")  
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "lhTvHflPVOqgSWyuWQry")  

LOCAL_MODEL_PATH = "./Qwen3-VL-2B-Instruct"

