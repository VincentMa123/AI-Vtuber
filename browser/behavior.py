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
        
        steps = random.randint(8, 15)
        for i in range(steps):
            progress = i / steps
            # Ease in-out: slow start, fast middle, slow end
            eased = Behavior.ease_in_out(progress)
            # Calculate step size (more in the middle)
            base_step = total_amount / steps
            variation = random.uniform(0.7, 1.3)
            step = int(base_step * variation * (0.5 + eased))            
            await page.evaluate(f"window.scrollBy(0, {step * direction})")
            # Variable delay between scroll steps
            await asyncio.sleep(random.uniform(0.03, 0.12))
        
        # Occasional micro-pause (simulates reading)
        if random.random() < 0.3:
            await asyncio.sleep(random.uniform(0.2, 0.6))
