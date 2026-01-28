import logging
import asyncio
from typing import Dict, Tuple

import core.config as config
import core.state as state
import core.utils as utils

from .models import HeartbeatRequest, HeartbeatResponse
from .cooldown import CooldownManager
import mss
import io
import base64
from PIL import Image

class VisionHeartbeat:
    def __init__(self, llm_providers: Dict, text_to_speech_func, text_to_speech_stream_func=None):
        self.llm_providers = llm_providers
        self.text_to_speech_func = text_to_speech_func
        self.text_to_speech_stream_func = text_to_speech_stream_func
        self.cooldown_manager = CooldownManager()
        
        logging.info("[VisionHeartbeat] Initialized with CooldownManager")

    async def _analyze_interestingness(self, image_base64: str) -> Tuple[bool, str]:
            
        provider = self.llm_providers.get(config.LLM_PROVIDER)
        if not provider:
             return False, "none"

        prompt = utils.load_prompt_file("vision_filter.md")
        try:
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
        provider_key = state.llm_provider
            

        provider = self.llm_providers.get(provider_key)
        try:

            reaction = await provider.generate(
                message=full_prompt,
                history=[], # No history needed for One-shot reaction
                image_base64=image_base64
            )
            return reaction
        except Exception as e:
            logging.error(f"[Vision] Error generating reaction: {e}")

    async def _generate_reaction_stream(self, image_base64: str, category: str):
        provider_key = state.llm_provider
        provider = self.llm_providers.get(provider_key)
        
        system_prompt = utils.get_system_prompt()
        prompt = f"{system_prompt}\n\nI see {category}. React to this screenshot!"
        
        try:
            async for token in provider.generate_stream(message=prompt, history=[], image_base64=image_base64):
                yield token
        except Exception as e:
            logging.error(f"[Vision] Error generating reaction stream: {e}")
            yield "Ooh!"

    async def _capture_native(self) -> str:
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._capture_sync)
        except Exception as e:
            logging.error(f"[Vision] Native capture error: {e}")
            return None

    def _capture_sync(self) -> str:
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            sct_img = sct.grab(monitor)
            
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            
            img.thumbnail((1024, 1024))
            
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG", quality=60)
            return base64.b64encode(buffered.getvalue()).decode("utf-8")

    async def process_heartbeat(self, request: HeartbeatRequest) -> HeartbeatResponse:
        image_base64 = request.image_base64
        
        if request.use_native_capture:
            logging.info("[Vision] Attempting native screen capture...")
            image_base64 = await self._capture_native()
            
        if not image_base64:
             return HeartbeatResponse(
                 processed=True, 
                 action="ignore", 
                 debug_info="No image provided and capture failed"
             )

        logging.info(f"[Vision] Processing heartbeat (img size: {len(image_base64)})")
        
        # 1. Fast Check
        logging.info("[Vision] Analyzing image for interestingness...")
        is_interesting, category = await self._analyze_interestingness(image_base64)
        
        logging.info(f"[Vision] Check Result: Interesting={is_interesting}, Category={category}")

        if not is_interesting:
            return HeartbeatResponse(processed=True, action="ignore", debug_info="Not interesting")

        # 2. Cooldown Check
        if not self.cooldown_manager.can_react(category):
             return HeartbeatResponse(processed=True, action="ignore", debug_info=f"Cooldown active for {category}")

        # 3. Generate Reaction
        reaction_text = await self._generate_reaction(image_base64, category)
        
        # 4. Generate Audio (using shared logic if possible, or direct call)
        audio_base64 = None
        if self.text_to_speech_func:
            try:
                audio_base64 = await self.text_to_speech_func(reaction_text)
            except Exception as e:
                logging.error(f"[Vision] TTS Generation failed: {e}")

        self.cooldown_manager.record_reaction(category)

        return HeartbeatResponse(
            processed=True,
            action="react",
            reaction_text=reaction_text,
            audio_base64=audio_base64,
            category=category
        )

    async def process_heartbeat_stream(self, request: HeartbeatRequest):

        image_base64 = request.image_base64
        
        if request.use_native_capture:
            yield {"type": "status", "content": "Capturing..."}
            image_base64 = await self._capture_native()
            
        if not image_base64:
             yield {"type": "status", "content": "Capture Failed"}
             yield {"type": "stop"}
             return

        # 1. Fast Check
        yield {"type": "status", "content": "Analyzing..."}
        is_interesting, category = await self._analyze_interestingness(image_base64)
        
        if not is_interesting:
             yield {"type": "status", "content": "Idle"}
             yield {"type": "stop"}
             return

        # 2. Cooldown Check
        if not self.cooldown_manager.can_react(category):
             yield {"type": "status", "content": f"Cooldown ({category})"}
             yield {"type": "stop"}
             return

        # 3. Generate Reaction & Audio
        yield {"type": "status", "content": f"Reacting ({category})"}
        self.cooldown_manager.record_reaction(category)
        
        # Create text generator
        text_stream = self._generate_reaction_stream(image_base64, category)
    
        full_text = ""
        
        async def tracking_text_stream():
            nonlocal full_text
            async for token in text_stream:
                full_text += token
                # Send text chunk to client for subtitles
                yield token
        
        async def text_stream_wrapper():
             async for token in text_stream:
                 yield token 

        async def tee_text_generator():
            nonlocal full_text
            async for token in text_stream:
                full_text += token
                yield token
                
        if self.text_to_speech_stream_func:
            try:
                async for audio_chunk in self.text_to_speech_stream_func(tee_text_generator()):
                    yield {"type": "audio", "data": audio_chunk}
            except Exception as e:
                logging.error(f"[Vision] Streaming TTS error: {e}")
        
        yield {"type": "text", "content": full_text}
        yield {"type": "stop"}
