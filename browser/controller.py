import logging
import asyncio
import random
import base64
from typing import Optional, List, Dict, Any
from playwright.async_api import async_playwright, Browser, Page, Playwright
from .behavior import Behavior
import src.core.config as config


class BrowserController:
    
    def __init__(self):
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.is_running = False
        self._loop_task: Optional[asyncio.Task] = None
        self.base_url = config.BROWSER_BASE_URL
        
    async def start(self) -> bool:
        
        try:
            self.playwright = await async_playwright().start()
            
            # Common launch args
            launch_args = [
                '--start-maximized',
                '--disable-blink-features=AutomationControlled',
                '--disable-gpu',
                '--disable-software-rasterizer',
                '--disable-accelerated-2d-canvas',
                '--disable-gpu-compositing',
                '--disable-d3d11'
            ]

            try:
                # Try launching real Chrome (better for OBS)
                self.browser = await self.playwright.chromium.launch(
                    channel="chrome",
                    headless=config.BROWSER_HEADLESS,
                    args=launch_args
                )
                logging.info("[Browser] Launched Google Chrome (channel='chrome') with GPU disabled")
            except Exception as e:
                logging.warning(f"[Browser] Failed to launch Chrome: {e}. Falling back to bundled Chromium.")
                self.browser = await self.playwright.chromium.launch(
                    headless=config.BROWSER_HEADLESS,
                    args=launch_args
                )
            
            # Create context with no_viewport=True to respect window size
            context = await self.browser.new_context(no_viewport=True)
            self.page = await context.new_page()

            await self.page.goto(self.base_url, wait_until='domcontentloaded', timeout=60000)
            
            self.is_running = True
            logging.info(f"[Browser] Started and navigated to {self.base_url}")
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
            screenshot_bytes = await self.page.screenshot(type='jpeg', quality=80)
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

    async def scroll_down(self, amount: Optional[int] = None):
        if not self.page:
            return
        
        if amount is None:
            amount = random.randint(config.BROWSER_SCROLL_AMOUNT_MIN, config.BROWSER_SCROLL_AMOUNT_MAX)

        try:
            await Behavior.smooth_scroll(self.page, amount, direction=1)
            logging.debug(f"[Browser] Scrolled down ~{amount}px (smooth)")
        except Exception as e:
            logging.error(f"[Browser] Scroll failed: {e}")
    
    async def scroll_up(self, amount: Optional[int] = None):
        if not self.page:
            return

        if amount is None:
            amount = random.randint(config.BROWSER_SCROLL_AMOUNT_MIN, config.BROWSER_SCROLL_AMOUNT_MAX)
            
        try:
            await Behavior.smooth_scroll(self.page, amount, direction=-1)
            logging.debug(f"[Browser] Scrolled up ~{amount}px (smooth)")
        except Exception as e:
            logging.error(f"[Browser] Scroll failed: {e}")
    
    async def is_in_viewport(self, element) -> bool:

        try:
            box = await element.bounding_box()
            if not box:
                return False
            
            viewport = await self.page.evaluate("""() => ({
                width: window.innerWidth,
                height: window.innerHeight,
                scrollY: window.scrollY
            })""")
            
            # Check if element is within visible viewport
            element_top = box['y']
            element_bottom = box['y'] + box['height']
            viewport_height = viewport['height']
            
            # Element is in viewport if it's between 0 and viewport height
            return element_top >= 0 and element_bottom <= viewport_height
        except:
            return False
    
    async def click_load_more(self) -> bool:

        if not self.page:
            return False
            
        try:
            selectors = config.BROWSER_SELECTORS.get("load_more", [])
            
            for selector in selectors:
                try:
                    button = await self.page.query_selector(selector)
                    if button and await button.is_visible():
                        await asyncio.sleep(0.3)
                        await button.click()
                        logging.info("[Browser] Clicked 'Load More' button")
                        await asyncio.sleep(2)  # Wait for content to load
                        return True
                except:
                    continue
            
            return False
        except Exception as e:
            logging.debug(f"[Browser] No load more button found: {e}")
            return False
    
    async def click_random_product(self) -> bool:
        
        if not self.page:
            return False
            
        try:
            product_selectors = config.BROWSER_SELECTORS.get("product", [])
            
            for attempt in range(3):
                products_in_viewport = []
                all_products = []
                
                for selector in product_selectors:
                    try:
                        found = await self.page.query_selector_all(selector)
                        if found:
                            for p in found:
                                if await p.is_visible():
                                    all_products.append(p)
                                    # Check if in viewport
                                    if await self.is_in_viewport(p):
                                        products_in_viewport.append(p)
                            if products_in_viewport:
                                break
                    except:
                        continue
                
                # Prefer products in viewport, fallback to all visible
                products = products_in_viewport if products_in_viewport else all_products[:10]
                
                if not products:
                    if attempt == 2: 
                        logging.warning("[Browser] No products found to click.")
                    await asyncio.sleep(1)
                    continue
                
                selection_pool = products[:8]  # Top 8 products
                
                if hasattr(self, '_last_clicked_index') and len(selection_pool) > 1:
                    available_indices = [i for i in range(len(selection_pool)) if i != self._last_clicked_index]
                    if available_indices:
                        chosen_index = random.choice(available_indices)
                    else:
                        chosen_index = random.randrange(len(selection_pool))
                else:
                    chosen_index = random.randrange(len(selection_pool))
                
                product = selection_pool[chosen_index]
                self._last_clicked_index = chosen_index
                
                try:
                    await product.click(timeout=3000)
                    logging.info(f"[Browser] Clicked product #{chosen_index} (from viewport: {len(products_in_viewport) > 0})")
                    await asyncio.sleep(random.uniform(1.5, 2.5))
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
        
        if not self.page:
            return
            
        try:
            await self.page.go_back()
            await asyncio.sleep(0.5)
            logging.debug("[Browser] Navigated back")
        except Exception as e:
            logging.error(f"[Browser] Go back failed: {e}")
    
    async def go_home(self):
        
        if not self.page:
            return
            
        try:
            await self.page.goto(self.base_url, wait_until='domcontentloaded')
            await asyncio.sleep(2)
            logging.info("[Browser] Navigated to homepage")
        except Exception as e:
            logging.error(f"[Browser] Go home failed: {e}")
    
    async def click_category(self, category_name: str):
        if not self.page:
            return
            
        try:
            # Note: This is an example selector pattern, can be moved to config too if needed
            selector_template = config.BROWSER_SELECTORS.get("category_link", 'a:has-text("{name}")')
            selector = selector_template.format(name=category_name)
            
            category_link = await self.page.query_selector(selector)
            if category_link:
                await category_link.click()
                await asyncio.sleep(2)
                logging.info(f"[Browser] Clicked category: {category_name}")
        except Exception as e:
            logging.error(f"[Browser] Click category failed: {e}")

    async def get_scroll_position(self) -> dict:
        """Get current scroll position and page dimensions."""
        if not self.page:
            return {"scrollY": 0, "scrollHeight": 1, "viewportHeight": 1, "atBottom": False, "atTop": True}
        
        try:
            pos = await self.page.evaluate("""() => {
                const scrollY = window.scrollY;
                const scrollHeight = document.documentElement.scrollHeight;
                const viewportHeight = window.innerHeight;
                const maxScroll = scrollHeight - viewportHeight;
                const scrollPercent = maxScroll > 0 ? scrollY / maxScroll : 0;
                return {
                    scrollY: scrollY,
                    scrollHeight: scrollHeight,
                    viewportHeight: viewportHeight,
                    scrollPercent: scrollPercent,
                    atBottom: scrollPercent > 0.85,
                    atTop: scrollPercent < 0.15
                };
            }""")
            return pos
        except:
            return {"scrollY": 0, "scrollHeight": 1, "viewportHeight": 1, "scrollPercent": 0, "atBottom": False, "atTop": True}
    
    async def is_load_more_visible(self) -> bool:
        """Check if load more button is visible in viewport."""
        if not self.page:
            return False
            
        try:
            selectors = config.BROWSER_SELECTORS.get("load_more", [])
            
            for selector in selectors:
                try:
                    button = await self.page.query_selector(selector)
                    if button and await button.is_visible():
                        # Check if in viewport
                        if await self.is_in_viewport(button):
                            return True
                except:
                    continue
            return False
        except:
            return False
    
    async def perform_random_action(self) -> str:
        if not self.page:
            return "no_page"
        
        current_url = await self.get_current_url()
        # klikindomaret specific check, relies on URL structure containing /xpress/ or /product/
        is_product_page = "/xpress/" in current_url or "/product/" in current_url
        is_homepage = current_url.rstrip('/') == self.base_url.rstrip('/')
        
        # Get current scroll position
        scroll_pos = await self.get_scroll_position()
        at_bottom = scroll_pos.get("atBottom", False)
        at_top = scroll_pos.get("atTop", True)
        
        # On product page: high chance to go back after viewing
        if is_product_page:
            if random.random() < 0.7:
                await Behavior.sleep(0.5, 1.5)
                await self.go_back()
                return "go_back"
            else:
                await self.scroll_down(random.randint(config.BROWSER_SCROLL_AMOUNT_MIN, config.BROWSER_SCROLL_AMOUNT_MAX))
                return "scroll_down"
        
        # Check if load more button is visible
        if await self.is_load_more_visible():
            success = await self.click_load_more()
            if success:
                return "load_more"
        
        # Weighted actions based on scroll position (for listing pages)
        if at_bottom:
            actions = ['scroll_up', 'scroll_up', 'scroll_up', 'click_product', 'back']
        elif at_top:
            actions = ['scroll_down', 'scroll_down', 'scroll_down', 'scroll_down', 'click_product']
        else:
            actions = ['scroll_down', 'scroll_down', 'scroll_up', 'click_product', 'click_product', 'back']
        
        action = random.choice(actions)

        if action == 'scroll_down':
            await self.scroll_down()
            return "scroll_down"
        
        elif action == 'scroll_up':
            await self.scroll_up()
            return "scroll_up"
            
        elif action == 'click_product':
            success = await self.click_random_product()
            return "click_product" if success else "click_failed"
            
        elif action == 'back':
            if not is_homepage:
                await Behavior.sleep(0.5, 1.5)
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
