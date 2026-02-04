import logging
import asyncio
import random


class Behavior:
    
    @staticmethod
    async def sleep(min_sec: float, max_sec: float):
        await asyncio.sleep(random.uniform(min_sec, max_sec))
    
    @staticmethod
    def ease_in_out(t: float) -> float:
        return t * t * (3 - 2 * t)  # Smoothstep
    
    @staticmethod
    async def smooth_scroll(page, total_amount: int, direction: int = 1):
        
        # Higher steps for smoother animation
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
                await page.evaluate(f"window.scrollBy(0, {step * direction})")
                current_scroll += step
            
            # Consistent frame time (approx 60fps)
            await asyncio.sleep(0.016)
