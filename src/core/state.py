# Shared state for models and resources
# these will be initialized by load_models.py
import time
import asyncio

model = None
processor = None
local_model_available = False
llm_provider = None

# Speaking cooldown state
_last_speech_end_time = 0
_speech_lock = asyncio.Lock()
MIN_SPEECH_GAP_SECONDS = 2.5  # Minimum gap between speeches

async def can_speak() -> bool:
    """Check if enough time has passed since last speech ended."""
    global _last_speech_end_time
    current_time = time.time()
    time_since_last = current_time - _last_speech_end_time
    return time_since_last >= MIN_SPEECH_GAP_SECONDS

async def wait_for_speech_cooldown() -> float:
    """Wait until cooldown is over. Returns time waited."""
    global _last_speech_end_time
    async with _speech_lock:
        current_time = time.time()
        time_since_last = current_time - _last_speech_end_time
        
        if time_since_last < MIN_SPEECH_GAP_SECONDS:
            wait_time = MIN_SPEECH_GAP_SECONDS - time_since_last
            await asyncio.sleep(wait_time)
            return wait_time
        return 0

def mark_speech_started():
    """Mark that speech has started (optional, for tracking)."""
    pass

def mark_speech_ended():
    """Mark that speech has ended - resets cooldown timer."""
    global _last_speech_end_time
    _last_speech_end_time = time.time()
