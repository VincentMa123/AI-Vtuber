import logging
import asyncio
from typing import Dict, Tuple, Optional, Callable, Any
import core.config as config
import core.state as state
import core.utils as utils
from .models import HeartbeatRequest, HeartbeatResponse
from .browser import BrowserController, get_browser_controller
import mss
import io
import base64
from PIL import Image
import random
import uuid

class VisionHeartbeat:
    def __init__(self, llm_providers: Dict, text_to_speech_func, text_to_speech_stream_func=None):
        self.llm_providers = llm_providers
        self.text_to_speech_func = text_to_speech_func
        self.text_to_speech_stream_func = text_to_speech_stream_func
        
        # Browser automation
        self.browser_controller: Optional[BrowserController] = None
        self._browser_loop_task: Optional[asyncio.Task] = None
        self._browser_loop_running = False
        self._on_browser_update: Optional[Callable] = None  # Callback for WS updates
        self._last_analysis_time = 0
        
        logging.info("[VisionHeartbeat] Initialized with CooldownManager")

    async def _generate_reaction(self, image_base64: str) -> str:
        provider_key = state.llm_provider
            

        provider = self.llm_providers.get(provider_key)
        try:
            # Load specialized vision persona
            system_prompt = utils.load_prompt_file("vision_reaction.md")
            if not system_prompt:
                system_prompt = utils.get_system_prompt() # Fallback
                
            reaction = await provider.generate(
                message="React to this image.", # Short trigger
                history=[], 
                image_base64=image_base64,
                system_prompt=system_prompt, # Override default system prompt
                max_tokens=128 # Force brevity
            )
            return reaction
        except Exception as e:
            logging.error(f"[Vision] Error generating reaction: {e}")

    async def _generate_reaction_stream(self, image_base64: str):
        provider_key = state.llm_provider
        provider = self.llm_providers.get(provider_key)
        
        # Load specialized vision persona
        system_prompt = utils.load_prompt_file("vision_reaction.md")
        if not system_prompt:
             system_prompt = utils.get_system_prompt() # Fallback
             logging.warning("Failed to load vision_reaction.md, using default system prompt")

        try:
            async for token in provider.generate_stream(
                message="React to this image.", 
                history=[], 
                image_base64=image_base64,
                system_prompt=system_prompt, # Override default system prompt
                max_tokens=128 # Adjusted to prevent cut-offs
            ):
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

        # 3. Generate Reaction
        reaction_text = await self._generate_reaction(image_base64)
        
        # 4. Generate Audio (using shared logic if possible, or direct call)
        audio_base64 = None
        if self.text_to_speech_func:
            try:
                audio_base64 = await self.text_to_speech_func(reaction_text)
            except Exception as e:
                logging.error(f"[Vision] TTS Generation failed: {e}")

        return HeartbeatResponse(
            processed=True,
            action="react",
            reaction_text=reaction_text,
            audio_base64=audio_base64,
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
        
        # Create text generator
        text_stream = self._generate_reaction_stream(image_base64)
    
        full_text = ""

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
        
        logging.info(f"[Vision Response] {full_text}")
        yield {"type": "text", "content": full_text}
        yield {"type": "stop"}

    
    async def start_browser(self) -> bool:

        self.browser_controller = await get_browser_controller()
        success = await self.browser_controller.start()
        if success:
            logging.info("[VisionHeartbeat] Browser started successfully")
        return success
    
    async def stop_browser(self):

        self._browser_loop_running = False
        if self._browser_loop_task:
            self._browser_loop_task.cancel()
        if self.browser_controller:
            await self.browser_controller.stop()
        logging.info("[VisionHeartbeat] Browser stopped")
    
    async def start_browser_loop(self, on_update: Callable = None):

        if self._browser_loop_task and not self._browser_loop_task.done():
            logging.warning("[VisionHeartbeat] Cancelling existing browser loop before starting new one.")
            self._browser_loop_task.cancel()
            try:
                await self._browser_loop_task
            except asyncio.CancelledError:
                pass
            
        self._on_browser_update = on_update
        self._browser_loop_running = True
        self._browser_loop_task = asyncio.create_task(self._orchestrate_browser_loops())

    async def _orchestrate_browser_loops(self):
        
        # 1. Initialize browser
        if not self.browser_controller or not self.browser_controller.is_running:
            logging.info("[VisionHeartbeat] Orchestrator: Initializing browser...")
            success = await self.start_browser()
            if not success:
                logging.error("[VisionHeartbeat] Failed to start browser. Stopping.")
                self._browser_loop_running = False
                return

        logging.info("[VisionHeartbeat] Browser initialized. Starting concurrent Action and Vision loops...")

        # Task: Synchronous Action/Vision Loop
        action_task = asyncio.create_task(self._action_loop())

        try:
            # Wait for action loop (or cancellation)
            await action_task
        except asyncio.CancelledError:
            logging.info("[VisionHeartbeat] Orchestrator cancelled. Stopping sub-tasks...")
            action_task.cancel()
            await action_task
        except Exception as e:
            logging.error(f"[VisionHeartbeat] Orchestrator error: {e}")
            action_task.cancel()

    async def _process_vision_cycle(self):

        try:
            # 1. Capture screenshot
            screenshot = await self.browser_controller.get_screenshot()
            if not screenshot:
                return

            # 2. Send screenshot to frontend immediately
            if self._on_browser_update:
                await self._on_browser_update({
                    "type": "browser_screenshot",
                    "image_base64": screenshot
                })

            # 3. Process through vision pipeline (AI Analysis)
            request = HeartbeatRequest(
                image_base64=screenshot,
                timestamp=asyncio.get_event_loop().time(),
                use_native_capture=False
            )

            # Use streaming for audio/response
            captured_text = ""
            async for chunk in self.process_heartbeat_stream(request):
                if chunk.get("type") == "text":
                    captured_text = chunk.get("content", "")
                    
                if self._on_browser_update:
                    await self._on_browser_update(chunk)
            
            duration = max(0, len(captured_text) * 0.05)
            logging.info(f"[Vision Cycle] Text length: {len(captured_text)}, Calculated wait: {duration:.1f}s")
            return duration
                    
        except Exception as e:
            logging.error(f"[Vision Cycle] Error: {e}")
            return 5.0 # Fallback duration



    async def _action_loop(self):

        loop_id = str(uuid.uuid4())[:8]
        logging.info(f"[VisionHeartbeat] Sync Action Loop started. ID: {loop_id}")
        
        # Initialize timestamp if not already set
        if not hasattr(self, '_last_analysis_time'):
            self._last_analysis_time = 0
            
        while self._browser_loop_running:
            try:
                logging.debug(f"[Action Loop {loop_id}] Starting iteration...")
                # 1. Perform random action
                action = await self.browser_controller.perform_random_action()
                logging.debug(f"[Action Loop] Performed: {action}")
                
                # Send action update
                if self._on_browser_update:
                    await self._on_browser_update({
                        "type": "browser_action",
                        "action": action,
                        "url": await self.browser_controller.get_current_url()
                    })

                # 2. Check Triggers
                current_time = asyncio.get_event_loop().time()
                is_click = (action == "click_product")

                is_overdue = (current_time - self._last_analysis_time) >= random.uniform(15, 25)
                
                should_analyze = is_click or is_overdue
                
                if should_analyze:
                    logging.info(f"[Action Loop] Triggering Vision (Click={is_click}, Overdue={is_overdue})")
                    
                    if is_click:
                        await asyncio.sleep(3.0) # Wait for page load
                    
                    # 3. Process Vision & Get Duration
                    wait_duration = await self._process_vision_cycle()
                    self._last_analysis_time = asyncio.get_event_loop().time()
                    
                    # 4. Wait for Speech (Dynamic)
                    logging.info(f"[Action Loop] Waiting {wait_duration:.1f}s for speech to finish...")
                    await asyncio.sleep(wait_duration)
                else:
                    # 5. Standard Action Cooldown (2-5s)
                    delay = random.uniform(1.0, 3.0)
                    await asyncio.sleep(delay)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"[Action Loop] Error: {e}")
                await asyncio.sleep(5)
