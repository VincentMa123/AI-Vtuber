import logging
import asyncio
import random
import base64
from typing import Optional
from playwright.async_api import async_playwright, Browser, Page, Playwright
from .behavior import Behavior

class BrowserController:
    
    BASE_URL = "https://www.klikindomaret.com/"
    
    def __init__(self):
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.is_running = False
        self._loop_task: Optional[asyncio.Task] = None
        
    async def start(self) -> bool:
        try:
            self.playwright = await async_playwright().start()
            
            try:
                # Try launching real Chrome (better for OBS)
                self.browser = await self.playwright.chromium.launch(
                    channel="chrome",
                    headless=False,
                    args=[
                        '--start-maximized',
                        '--disable-blink-features=AutomationControlled',
                        '--disable-gpu',
                        '--disable-software-rasterizer'
                    ]
                )
                logging.info("[Browser] Launched Google Chrome (channel='chrome')")
            except Exception as e:
                logging.warning(f"[Browser] Failed to launch Chrome: {e}. Falling back to bundled Chromium.")
                self.browser = await self.playwright.chromium.launch(
                    headless=False,
                    args=[
                        '--start-maximized',
                        '--disable-blink-features=AutomationControlled',
                        '--disable-gpu',
                        '--disable-software-rasterizer'
                    ]
                )
            
            # Create context with no_viewport=True to respect window size
            context = await self.browser.new_context(no_viewport=True)
            self.page = await context.new_page()

            await self.page.goto(self.BASE_URL, wait_until='domcontentloaded', timeout=60000) 
            
            self.is_running = True
            logging.info(f"[Browser] Started and navigated to {self.BASE_URL}")
            return True
            
        except Exception as e:
            logging.error(f"[Browser] Failed to start: {e}")
            return False
    
    async def stop(self):
        self.is_running = False
        
        if self._loop_task:
            self._loop_task.cancel()
            
        if self.browser:
            await self.browser.close()
            
        if self.playwright:
            await self.playwright.stop()
            
        logging.info("[Browser] Stopped")
    
    async def get_screenshot(self) -> Optional[str]:
        if not self.page:
            return None
            
        try:
            screenshot_bytes = await self.page.screenshot(type='jpeg', quality=70)
            encoded = base64.b64encode(screenshot_bytes).decode('utf-8')
            logging.debug(f"[Browser] Screenshot captured. Size: {len(encoded)}")
            return encoded
        except Exception as e:
            logging.error(f"[Browser] Screenshot failed: {e}")
            return None
    
    async def get_current_url(self) -> str:
        if self.page:
            return self.page.url
        return ""

    async def scroll_down(self, amount: int = 400):
        if not self.page:
            return
            
        try:
            await Behavior.smooth_scroll(self.page, amount, direction=1)
            logging.debug(f"[Browser] Scrolled down ~{amount}px (smooth)")
        except Exception as e:
            logging.error(f"[Browser] Scroll failed: {e}")
    
    async def scroll_up(self, amount: int = 400):
        if not self.page:
            return
            
        try:
            await Behavior.smooth_scroll(self.page, amount, direction=-1)
            logging.debug(f"[Browser] Scrolled up ~{amount}px (smooth)")
        except Exception as e:
            logging.error(f"[Browser] Scroll failed: {e}")
    
    async def click_random_product(self) -> bool:
        if not self.page:
            return False
            
        try:
            product_selectors = [
                '.item',                  
                'div[class*="product"]',  
                '.card',                
                'div:has-text("Rp")',   
                'a[href*="/product/"]',
                '.product-card',
                '.product-item a',
                '[data-testid="product-card"]'
            ]
            
            for attempt in range(3):
                products = []
                for selector in product_selectors:
                    try:
                        found = await self.page.query_selector_all(selector)
                        if found:
                            products.extend([p for p in found if await p.is_visible()])
                            if products: 
                                break
                    except:
                        continue
                
                if not products:
                    if attempt == 2: 
                        logging.warning("[Browser] No products found to click.")
                    await asyncio.sleep(1)
                    continue
                
                # Click random product
                product = random.choice(products[:10]) 
                try:
                    await product.click(timeout=3000)
                    logging.info("[Browser] Clicked on a product")
                    # Wait for page to load before screenshot
                    await asyncio.sleep(random.randint(2.0, 3.0))
                    return True
                except Exception as e:
                    if "attached" in str(e) or "target closed" in str(e):
                         logging.warning(f"[Browser] Click failed (stale element), retrying... {e}")
                         await asyncio.sleep(1)
                         continue
                    else:
                        logging.error(f"[Browser] Failed to click: {e}")
                        return False

            return False
            
        except Exception as e:
            logging.error(f"[Browser] Click product failed with error: {e}")
            return False
    
    async def go_back(self):
        """Navigate back to previous page"""
        if not self.page:
            return
            
        try:
            await self.page.go_back()
            await asyncio.sleep(1)
            logging.debug("[Browser] Navigated back")
        except Exception as e:
            logging.error(f"[Browser] Go back failed: {e}")
    
    async def go_home(self):
        """Navigate to homepage"""
        if not self.page:
            return
            
        try:
            await self.page.goto(self.BASE_URL, wait_until='domcontentloaded')
            await asyncio.sleep(2)
            logging.info("[Browser] Navigated to homepage")
        except Exception as e:
            logging.error(f"[Browser] Go home failed: {e}")
    
    async def click_category(self, category_name: str):
        if not self.page:
            return
            
        try:
            category_link = await self.page.query_selector(f'a:has-text("{category_name}")')
            if category_link:
                await category_link.click()
                await asyncio.sleep(2)
                logging.info(f"[Browser] Clicked category: {category_name}")
        except Exception as e:
            logging.error(f"[Browser] Click category failed: {e}")
    
    async def perform_random_action(self) -> str:
        # Weighted actions: more scrolling/reading, less clicking
        actions = ['scroll', 'scroll', 'scroll', 'scroll', 'scroll', 'click_product', 'back']
        action = random.choice(actions)
        
        if not self.page:
            actions = ['back', 'scroll']
            action = random.choice(actions)

        if action == 'scroll':
            direction = random.choice(['down', 'down', 'down', 'up'])
            if direction == 'down':
                await self.scroll_down(random.randint(150, 600))
            else:
                await self.scroll_up(random.randint(80, 400))
            return f"scroll_{direction}"
            
        elif action == 'click_product':
            success = await self.click_random_product()
            return "click_product" if success else "click_failed"
            
        elif action == 'back':
            current_url = await self.get_current_url()
            if current_url.rstrip('/') != self.BASE_URL.rstrip('/'):
                await Behavior.sleep(0.5, 1.5)  # Hesitation before going back
                await self.go_back()
                return "go_back"
            return "already_home"
        
        return action


# Global instance
browser_controller: Optional[BrowserController] = None


async def get_browser_controller() -> BrowserController:
    global browser_controller
    if browser_controller is None:
        browser_controller = BrowserController()
    return browser_controller
