import logging
import asyncio
import random


class Behavior:
    
    @staticmethod
    async def sleep(min_sec: float, max_sec: float):
        await asyncio.sleep(random.uniform(min_sec, max_sec))
    
    @staticmethod
    async def guarded_sleep(page, min_sec: float, max_sec: float):

        if not page:
            await asyncio.sleep(random.uniform(min_sec, max_sec))
            return
            
        try:
            # Store initial scroll position
            initial_scroll = await page.evaluate("window.scrollY")
            total_duration = random.uniform(min_sec, max_sec)
            check_interval = 0.2  # Check every 200ms
            elapsed = 0
            
            while elapsed < total_duration:
                await asyncio.sleep(check_interval)
                elapsed += check_interval
                
                # Check if scroll position changed unexpectedly
                try:
                    current_scroll = await page.evaluate("window.scrollY")
                    if abs(current_scroll - initial_scroll) > 150:
                        # Restore scroll position smoothly
                        logging.info(f"[Behavior] Detected scroll jump during sleep ({initial_scroll} -> {current_scroll}), restoring...")
                        await page.evaluate(f"window.scrollTo(0, {initial_scroll})")
                except:
                    pass  # Page might have navigated, ignore
                    
        except Exception as e:
            logging.debug(f"[Behavior] Guarded sleep error: {e}")
            await asyncio.sleep(random.uniform(min_sec, max_sec))
    
    @staticmethod
    def ease_in_out(t: float) -> float:
        return t * t * (3 - 2 * t)  # Smoothstep
    
    @staticmethod
    async def smooth_scroll(page, total_amount: int, direction: int = 1):
        """Smooth scroll with jump detection and correction."""
        
        # Get starting position
        try:
            start_position = await page.evaluate("window.scrollY")
        except:
            return
        
        expected_position = start_position
        steps = random.randint(20, 30)
        current_scroll = 0
        
        for i in range(steps):
            progress = (i + 1) / steps
            eased_progress = Behavior.ease_in_out(progress)
            
            # Calculate absolute target position for this frame
            target_pos = int(total_amount * eased_progress)
            
            # Calculate delta to scroll
            step = target_pos - current_scroll
            
            if step != 0:
                try:
                    # Check if we're still at expected position before scrolling
                    actual_position = await page.evaluate("window.scrollY")
                    
                    # Now apply our scroll
                    await page.evaluate(f"window.scrollBy(0, {step * direction})")
                    current_scroll += step
                    expected_position = start_position + (current_scroll * direction)
                except:
                    pass
            
            # Consistent frame time
            await asyncio.sleep(0.016)
