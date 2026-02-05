import asyncio
import logging
from typing import List, Dict, Any
from contextlib import asynccontextmanager

model = None
processor = None
local_model_available = False
llm_provider = None

_response_processing_lock = asyncio.Lock()


SPEECH_GAP_SECONDS = 1.0

MAX_HISTORY_MESSAGES = 20
_chat_history: List[Dict[str, Any]] = []

# Audio playback signaling
_audio_complete_event = asyncio.Event()
_waiting_for_audio = False

def signal_audio_complete():

    global _waiting_for_audio
    if _waiting_for_audio:
        logging.info("[State] Received audio_playback_complete signal from frontend")
        _audio_complete_event.set()

async def wait_for_audio_complete(timeout: float = 30.0) -> bool:

    global _waiting_for_audio
    _audio_complete_event.clear()
    _waiting_for_audio = True
    try:
        await asyncio.wait_for(_audio_complete_event.wait(), timeout=timeout)
        logging.debug("[State] Audio complete signal received")
        return True
    except asyncio.TimeoutError:
        logging.warning(f"[State] Audio complete wait timed out after {timeout}s")
        return False
    finally:
        _waiting_for_audio = False


@asynccontextmanager
async def acquire_speech_slot(source: str = "unknown"):

    logging.debug(f"[State] {source} waiting for speech slot...")
    async with _response_processing_lock:
        logging.info(f"[State] {source} acquired speech slot")
        try:
            yield
        finally:
            if SPEECH_GAP_SECONDS > 0:
                logging.debug(f"[State] Adding {SPEECH_GAP_SECONDS}s gap after speech")
                await asyncio.sleep(SPEECH_GAP_SECONDS)
            logging.info(f"[State] {source} released speech slot")

def add_to_history(role: str, content: str):

    global _chat_history
    _chat_history.append({"role": role, "content": content})
    # Keep only last N messages
    if len(_chat_history) > MAX_HISTORY_MESSAGES:
        _chat_history = _chat_history[-MAX_HISTORY_MESSAGES:]
    logging.debug(f"[State] History now has {len(_chat_history)} messages")

def get_history() -> List[Dict[str, Any]]:

    return _chat_history.copy()

def clear_history():

    global _chat_history
    _chat_history = []
    logging.info("[State] Chat history cleared")

