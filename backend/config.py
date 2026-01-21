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

CHAT_AGGREGATION_ENABLED = os.getenv("CHAT_AGGREGATION_ENABLED", "true").lower() == "true"
AGGREGATION_WINDOW_SECONDS = float(os.getenv("AGGREGATION_WINDOW_SECONDS", "5.0"))
MIN_RESPONSE_INTERVAL_SECONDS = float(os.getenv("MIN_RESPONSE_INTERVAL_SECONDS", "5.0"))
MAX_MESSAGES_PER_USER_PER_WINDOW = int(os.getenv("MAX_MESSAGES_PER_USER_PER_WINDOW", "3"))
MIN_MESSAGE_LENGTH = int(os.getenv("MIN_MESSAGE_LENGTH", "2"))
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.8"))
DUPLICATE_EXPIRY_SECONDS = float(os.getenv("DUPLICATE_EXPIRY_SECONDS", "60.0"))  # How long to remember messages for duplicate detection

# Twitch Integration
TWITCH_ENABLED = os.getenv("TWITCH_ENABLED", "false").lower() == "true"
TWITCH_BOT_TOKEN = os.getenv("TWITCH_BOT_TOKEN", "")
TWITCH_CHANNEL = os.getenv("TWITCH_CHANNEL", "")
TWITCH_BOT_PREFIX = os.getenv("TWITCH_BOT_PREFIX", "!")
