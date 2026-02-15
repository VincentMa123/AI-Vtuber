import os
from dotenv import load_dotenv

load_dotenv()

LLM_PROVIDER = "qwen"

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL ="allenai/molmo-2-8b:free"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = "deepseek-chat"
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1/chat/completions"

# Remote vLLM Configuration
REMOTE_VLLM_BASE_URL = "https://uncomparably-unconceding-dino.ngrok-free.dev/v1/chat/completions"
REMOTE_VLLM_MODEL = "Qwen3-VL-2B"  

# Qwen (DashScope) Configuration
QWEN_API_KEY = os.getenv("QWEN_API_KEY", os.getenv("DASHSCOPE_API_KEY", ""))
QWEN_MODEL = "qwen3-vl-plus" 
QWEN_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"  

TTS_PROVIDER = "qwen" #qwen, realtimetts
REALTIMETTS_ENGINE = "system" #system, elevenlabs

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = "jqPbtJasUGU5J3qH8a14"  

QWEN_TTS_MODEL = "qwen3-tts-vc-realtime-2025-11-27"
QWEN_TTS_VOICE_FILE = "voice.mp3"  


CHAT_AGGREGATION_ENABLED = True
AGGREGATION_WINDOW_SECONDS = 5.0
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
TWITCH_STREAM_KEY = os.getenv("TWITCH_STREAM_KEY", "")  # For server-side streaming
TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID", "")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET", "")
TWITCH_BOT_ID = os.getenv("TWITCH_BOT_ID", "")

# Browser Automation
BROWSER_BASE_URL = "https://www.klikindomaret.com/"
VTUBER_FRONTEND_URL = "http://localhost:3000"
BROWSER_HEADLESS = False
BROWSER_SCROLL_AMOUNT_MIN = 150
BROWSER_SCROLL_AMOUNT_MAX = 600

# FlareSolverr
FLARESOLVERR_URL = os.getenv("FLARESOLVERR_URL", "http://localhost:8191/v1")
