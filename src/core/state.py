import asyncio
import logging
from typing import List, Dict, Any
from contextlib import asynccontextmanager

model = None
processor = None
local_model_available = False
llm_provider = None

_response_processing_lock = asyncio.Lock()

@asynccontextmanager
async def acquire_speech_slot(source: str = "unknown"):

    logging.debug(f"[State] {source} waiting for speech slot...")
    async with _response_processing_lock:
        logging.info(f"[State] {source} acquired speech slot")
        try:
            yield
        finally:
            logging.info(f"[State] {source} released speech slot")


# ============ Chat History (Short-Term Memory) ============

MAX_HISTORY_MESSAGES = 20  # 10 exchanges (user + assistant pairs)
_chat_history: List[Dict[str, Any]] = []

def add_to_history(role: str, content: str):
    """Add a message to chat history."""
    global _chat_history
    _chat_history.append({"role": role, "content": content})
    logging.debug(f"[State] History now has {len(_chat_history)} messages")
    # Keep only last N messages
    if len(_chat_history) > MAX_HISTORY_MESSAGES:
        _chat_history = _chat_history[-MAX_HISTORY_MESSAGES:]
    logging.debug(f"[State] History now has {len(_chat_history)} messages")

def get_history() -> List[Dict[str, Any]]:
    """Get a copy of chat history."""
    return _chat_history.copy()

def clear_history():
    """Clear chat history."""
    global _chat_history
    _chat_history = []
    logging.info("[State] Chat history cleared")

