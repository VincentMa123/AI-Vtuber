import logging
import asyncio
from typing import Dict, Tuple, Optional, Callable, Any
import core.config as config
import core.state as state
import core.utils as utils
from core.utils import compress_image_for_vlm, is_similar_to_last
from .models import HeartbeatRequest
from browser import BrowserController, get_browser_controller, Behavior
import random
import uuid

class VisionHeartbeat:
    def __init__(self, llm_providers: Dict, text_to_speech_stream_func=None):
        self.vllm_providers = llm_providers
        self.text_to_speech_stream_func = text_to_speech_stream_func
        
        # Browser automation
        self.browser_controller: Optional[BrowserController] = None
        self._browser_loop_task: Optional[asyncio.Task] = None
        self._browser_loop_running = False
        self._on_browser_update: Optional[Callable] = None  # Callback for WS updates
        self._last_analysis_time = 0
        self._last_auto_refresh_time = 0
        self.visited_urls = set()
        self.screenshot_buffer = []  # Buffer for multi-image vision
        
        logging.info("[VisionHeartbeat] Initialized with CooldownManager")


    async def _generate_reaction_stream(self, images_base64: Any):
        provider_key = config.VLLM_PROVIDER
        provider = self.vllm_providers.get(provider_key)
        
        # Determine current page context for the prompt
        scroll_status = "Middle of page"
        current_url = "Unknown"
        page_title = "Unknown"
        
        if self.browser_controller and self.browser_controller.page:
            try:
                current_url = self.browser_controller.page.url
                page_title = await self.browser_controller.page.title()
                pos = await self.browser_controller.get_scroll_position()
                if pos.get("atBottom"):
                    scroll_status = "At Bottom"
                elif pos.get("atTop"):
                    scroll_status = "At Top"
            except Exception as e:
                logging.warning(f"[Vision] Could not get page status: {e}")

        # Track current URL in history (normalize to avoid trailing slash issues)
        if current_url != "Unknown":
            norm_url = current_url.rstrip("/")
            self.visited_urls.add(norm_url)

        # Get the full persona prompt with dynamic context
        vision_task = utils.load_prompt_file("vision_reaction.md")
        system_prompt = utils.get_system_prompt(
            scroll_status=scroll_status,
            current_url=current_url,
            page_title=page_title,
            visited_urls=list(self.visited_urls)
        )
        
        # Merge specialized vision instructions into the system prompt
        full_system_prompt = f"{system_prompt}\n\nCURRENT VISION TASK:\n{vision_task}"

        try:
            # Use shared history for context
            history = state.get_history()
            
            message = "React to the currently visible content. You might see multiple screenshots representing a sequence as I scroll down the page. Use them to understand the page flow. If you are at the end of the page (At Bottom), transition to the next logical section using your navigation tool."
            
            async for token in provider.generate_stream(
                message=message, 
                history=history, 
                image_base64=images_base64,
                system_prompt=full_system_prompt,
                max_tokens=512
            ):
                yield token
        except Exception as e:
            logging.error(f"[Vision] Error generating reaction stream: {e}")
            yield "Ooh!"

    async def process_heartbeat_stream(self, request: HeartbeatRequest):

        images_base64 = request.image_base64
            
        if not images_base64:
             yield {"type": "status", "content": "Capture Failed"}
             yield {"type": "stop"}
             return
        
        # Create text generator
        text_stream = self._generate_reaction_stream(images_base64)
    
        full_text = ""

        async def tee_text_generator():
            nonlocal full_text
            async for token in text_stream:
                full_text += token
                yield token
                
        if self.text_to_speech_stream_func:
            try:
                async for audio_chunk in self.text_to_speech_stream_func(tee_text_generator()):
                    state.mark_audio_sent()
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

    async def _process_vision_cycle(self, images: Optional[Any] = None):

        try:
            # If no images provided, use the latest from browser
            if not images:
                screenshot = await self.browser_controller.get_screenshot()
                if not screenshot: return
                
                if self._on_browser_update:
                    await self._on_browser_update({
                        "type": "browser_screenshot",
                        "image_base64": screenshot
                    })
                
                images = compress_image_for_vlm(screenshot)

            async with state.acquire_speech_slot("vision"):
                request = HeartbeatRequest(
                    image_base64=images,
                    timestamp=asyncio.get_event_loop().time(),
                    use_native_capture=False
                )
                
                captured_text = ""
                async for chunk in self.process_heartbeat_stream(request):
                    if chunk.get("type") == "text":
                        captured_text = chunk.get("content", "")
                        
                    if self._on_browser_update:
                        await self._on_browser_update(chunk)
                
                # Wait for frontend to signal audio playback is complete
                await state.wait_for_audio_complete(timeout=20.0)
                
                logging.info(f"[Vision Cycle] Text length: {len(captured_text)} chars")
                        
        except Exception as e:
            logging.error(f"[Vision Cycle] Error: {e}")



    async def _action_loop(self):

        loop_id = str(uuid.uuid4())[:8]
        logging.info(f"[VisionHeartbeat] Sync Action Loop started. ID: {loop_id}")
        
        if not hasattr(self, '_last_analysis_time'):
            self._last_analysis_time = 0
            
        while self._browser_loop_running:
            try:
                # Check if browser connection is still alive
                if not self.browser_controller or not self.browser_controller.is_running:
                    logging.warning(f"[Action Loop {loop_id}] Browser connection lost, stopping loop")
                    self._browser_loop_running = False
                    break

                # 0. Check if page is stuck/placeholders only
                logging.debug(f"[Action Loop {loop_id}] Starting iteration...")
                action = await self.browser_controller.perform_random_action()
                logging.debug(f"[Action Loop] Performed: {action}")

                # Re-check after action in case connection died during it
                if not self.browser_controller.is_running:
                    logging.warning(f"[Action Loop {loop_id}] Browser died during action, stopping loop")
                    self._browser_loop_running = False
                    break
                
                if self._on_browser_update:
                    await self._on_browser_update({
                        "type": "browser_action",
                        "action": action,
                        "url": await self.browser_controller.get_current_url()
                    })
                
                # Send updated screenshot after each action for the frontend background
                screenshot = await self.browser_controller.get_screenshot()
                if screenshot and self._on_browser_update:
                    await self._on_browser_update({
                        "type": "browser_screenshot",
                        "image_base64": screenshot
                    })

                # 2. Check Triggers (Scroll-based or Click-based)
                pos = await self.browser_controller.get_scroll_position()
                at_bottom = pos.get("atBottom", False)
                
                is_scroll = (action == "scroll_down")
                is_click = (action == "click_product")
                
                # Capture current view for buffering or analysis
                current_screenshot_compressed = compress_image_for_vlm(screenshot)

                # Buffer logic: add to sequence if scrolling
                if is_scroll:
                    self.screenshot_buffer.append(current_screenshot_compressed)
                    logging.info(f"[Action Loop] Buffered screenshot ({len(self.screenshot_buffer)}/3)")

                # Analysis Trigger logic:
                # - Full buffer (3 scrolls)
                # - Explicit click (immediate reaction)
                # - Reached page bottom (essential for transition rules)
                should_analyze = (len(self.screenshot_buffer) >= 3) or is_click or at_bottom
                
                if should_analyze:
                    logging.info(f"[Action Loop] Triggering Vision (Buffer={len(self.screenshot_buffer)}, Click={is_click}, AtBottom={at_bottom})")
                    
                    # Construct analysis set
                    if is_click or at_bottom:
                        # For immediate events, ensure the current view is part of the set
                        # If buffer is empty, it becomes a single-image analysis
                        # If buffer has images, append current view as the 'final' state
                        if current_screenshot_compressed not in self.screenshot_buffer:
                            self.screenshot_buffer.append(current_screenshot_compressed)
                    
                    # Use whatever is in the buffer (1 to 4 images depending on timing)
                    analysis_images = self.screenshot_buffer if self.screenshot_buffer else current_screenshot_compressed
                    
                    await self._process_vision_cycle(images=analysis_images)
                    self.screenshot_buffer = [] # Reset buffer
                    self._last_analysis_time = asyncio.get_event_loop().time()
                    
                else:
                    # Natural variable delay between actions - use guarded sleep to prevent website JS jumps
                    await Behavior.guarded_sleep(self.browser_controller.page, 1, 3)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"[Action Loop] Error: {e}")
                # If browser connection is dead, don't retry - break the loop
                if self.browser_controller and not self.browser_controller.is_running:
                    logging.warning(f"[Action Loop {loop_id}] Browser not running after error, stopping loop")
                    self._browser_loop_running = False
                    break
                await Behavior.sleep(4, 7)
