import os
from dotenv import load_dotenv

load_dotenv()

LLM_PROVIDER = "deepseek"

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL ="allenai/molmo-2-8b:free"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = "deepseek-chat"
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1/chat/completions"

# Remote vLLM Configuration
REMOTE_VLLM_BASE_URL = os.getenv("REMOTE_VLLM_BASE_URL", "http://localhost:8001/v1/chat/completions")
REMOTE_VLLM_MODEL = os.getenv("REMOTE_VLLM_MODEL", "./Qwen3-VL-8B-Instruct")  

TTS_PROVIDER = "realtimetts"
REALTIMETTS_ENGINE = "system" # Options: "system", "elevenlabs"

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = "cgSgspJ2msm6clMCkdW9"  


CHAT_AGGREGATION_ENABLED = True
AGGREGATION_WINDOW_SECONDS = 0.5
MIN_RESPONSE_INTERVAL_SECONDS = 5.0
MAX_MESSAGES_PER_USER_PER_WINDOW = 3
MIN_MESSAGE_LENGTH = 2
SIMILARITY_THRESHOLD = 0.8
DUPLICATE_EXPIRY_SECONDS = 60.0
MAX_BATCH_SIZE = 10

# Twitch Integration
TWITCH_ENABLED = True
TWITCH_BOT_TOKEN = os.getenv("TWITCH_BOT_TOKEN", "")
TWITCH_CHANNEL = os.getenv("TWITCH_CHANNEL", "")
TWITCH_BOT_PREFIX = "!"
