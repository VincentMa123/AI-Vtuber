import logging
import time
import asyncio
from typing import Dict, Optional, Tuple, Any
from pydantic import BaseModel

import config
import state
import utils
from chat.models import ChatResponse


# Request/Response Models
class HeartbeatRequest(BaseModel):
    image_base64: str
    timestamp: float = 0.0

class HeartbeatResponse(BaseModel):
    processed: bool
    action: str  # "ignore" or "react"
    reaction_text: Optional[str] = None
    audio_base64: Optional[str] = None
    category: Optional[str] = None
    debug_info: Optional[str] = None

class CooldownManager:
    def __init__(self):
        self.last_reaction_time = 0
        self.topic_locks: Dict[str, float] = {}
        
        self.GLOBAL_COOLDOWN = 60.0  # Seconds between ANY vision reaction
        self.TOPIC_LOCK_DURATION = 300.0  # 5 minutes lock on a specific category (e.g. "shopping")

    def can_react(self, category: str) -> bool:
        now = time.time()
        
        if now - self.last_reaction_time < self.GLOBAL_COOLDOWN:
            return False
            
        if category in self.topic_locks:
            lock_expiry = self.topic_locks[category]
            if now < lock_expiry:
                logging.debug(f"[Vision] Topic '{category}' locked until {lock_expiry}")
                return False
        
        return True

    def record_reaction(self, category: str):
        now = time.time()
        self.last_reaction_time = now
        self.topic_locks[category] = now + self.TOPIC_LOCK_DURATION
        logging.info(f"[Vision] Reaction recorded. global_cd=60s, topic_lock({category})=300s")


class VisionHeartbeat:
    def __init__(self, llm_providers: Dict, tts_providers: Dict, text_to_speech_func):
        self.llm_providers = llm_providers
        self.tts_providers = tts_providers
        self.text_to_speech_func = text_to_speech_func
        self.cooldown_manager = CooldownManager()
        
        logging.info("[VisionHeartbeat] Initialized with CooldownManager")

    async def _analyze_interestingness(self, image_base64: str) -> Tuple[bool, str]:
        """
        Ask the Fast Vision Model if the image is interesting.
        Returns: (is_interesting, category)
        """
        # Determine provider (Prefer Remote vLLM or Local for vision)
        provider_key = "remote" if config.REMOTE_VLLM_BASE_URL else "local"
        if provider_key == "local" and not state.local_model_available:
            logging.error("[Vision] No vision model available for heartbeat check.")
            return False, "none"
            
        provider = self.llm_providers.get(provider_key)
        if not provider:
             return False, "none"

        prompt = utils.load_prompt_file("vision_filter.md")

        try:
            # Short max_tokens for speed
            response = await provider.generate(prompt, [], image_base64, max_tokens=30)
            
            if not response:
                return False, "none"
            
            clean_response = response.strip().upper()
            logging.info(f"[Vision] Filter Response: {clean_response}")
            
            if clean_response.startswith("YES"):
                # Extract category
                parts = clean_response.split(" ", 1)
                category = parts[1] if len(parts) > 1 else "GENERAL"
                return True, category.strip()
            
            return False, "none"

        except Exception as e:
            logging.error(f"[Vision] Error in interestingness check: {e}")
            return False, "error"

    async def _generate_reaction(self, image_base64: str, category: str) -> str:
        """Generate the witty reaction text"""
        provider_key = state.llm_provider
        
        # If primary is DeepSeek (no vision), swap to Remote/Local for this call
        if provider_key == "deepseek":
            provider_key = "remote" if config.REMOTE_VLLM_BASE_URL else "local"
            
        provider = self.llm_providers.get(provider_key)
        if not provider:
            return "Wow, that looks interesting!"

        try:
            reaction = await provider.generate(
                message=f"I see {category}. React to this screenshot!",
                history=[], # No history needed for One-shot reaction
                image_base64=image_base64
            )
            return reaction or "Ooh, what's this?"
        except Exception as e:
            logging.error(f"[Vision] Error generating reaction: {e}")
            return "Ooh!"

    async def process_heartbeat(self, request: HeartbeatRequest) -> HeartbeatResponse:
        logging.info(f"[Vision] Processing heartbeat (img size: {len(request.image_base64)})")
        
        # 1. Fast Check
        is_interesting, category = await self._analyze_interestingness(request.image_base64)
        
        if not is_interesting:
            return HeartbeatResponse(processed=True, action="ignore", debug_info="Not interesting")

        # 2. Cooldown Check
        if not self.cooldown_manager.can_react(category):
             return HeartbeatResponse(processed=True, action="ignore", debug_info=f"Cooldown active for {category}")

        # 3. Generate Reaction
        reaction_text = await self._generate_reaction(request.image_base64, category)
        
        # 4. Generate Audio (using shared logic if possible, or direct call)
        # We need access to the TTS logic. For now, let's assume valid text.
        
        audio_base64 = None
        if self.text_to_speech_func:
            audio_base64 = await self.text_to_speech_func(reaction_text)

        # 5. Update Cooldowns
        self.cooldown_manager.record_reaction(category)

        return HeartbeatResponse(
            processed=True,
            action="react",
            reaction_text=reaction_text,
            audio_base64=audio_base64,
            category=category
        )
