import asyncio
import logging
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
