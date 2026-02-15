"""
Efficient Single-Window Browser Controller
Just the content page - VTuber overlay handled by FFmpeg
"""

import logging
import asyncio
import random
import base64
import requests
from typing import Optional
from playwright.async_api import async_playwright, Browser, Page, Playwright
from .behavior import Behavior
import src.core.config as config

BROWSER_SELECTORS = {
    "load_more": [
        'button:has-text("Muat Lebih Banyak")',
        'button:has-text("Load More")',
    ],
    "product": [
        '.item',
        'div[class*="product"]',
        'a[href*="/product/"]',
    ],
    "popup_close": [
        'button[aria-label="Close"]',
        'button[aria-label="Tutup"]',
    ],
}

class BrowserController:
    """Single browser window - overlay handled externally by FFmpeg"""
    
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
            
            # 1. Get FlareSolverr solution
            flaresolverr_url = "http://localhost:8191/v1"
            cookies = []
            user_agent = None
            
            try:
                logging.info(f"[Browser] Requesting FlareSolverr solution...")
                response = requests.post(flaresolverr_url, json={
                    "cmd": "request.get",
                    "url": self.base_url,
                    "maxTimeout": 60000
                }, timeout=65)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "ok":
                        solution = data.get("solution", {})
                        user_agent = solution.get("userAgent")
                        cookies = solution.get("cookies", [])
                        logging.info(f"[Browser] ✓ FlareSolverr: Got {len(cookies)} cookies")
                    else:
                        logging.error(f"[Browser] FlareSolverr failed")
                        return False
            except Exception as e:
                logging.error(f"[Browser] FlareSolverr error: {e}")
                return False
            
            # 2. Launch single browser instance
            import os
            display = os.environ.get('DISPLAY', ':55')
            
            launch_args = [
                f'--display={display}',
                '--start-maximized',
                '--no-sandbox',
                '--no-first-run',
                '--no-default-browser-check',
                '--password-store=basic',
                '--disable-blink-features=AutomationControlled',
            ]
            
            try:
                self.browser = await self.playwright.chromium.launch(
                    channel="chrome",
                    headless=False,
                    args=launch_args,
                    env={'DISPLAY': display}
                )
                logging.info("[Browser] ✓ Chrome launched")
            except:
                self.browser = await self.playwright.chromium.launch(
                    headless=False,
                    args=launch_args,
                    env={'DISPLAY': display}
                )
                logging.info("[Browser] ✓ Chromium launched")
            
            # 3. Create context with FlareSolverr credentials
            context = await self.browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=user_agent,
                ignore_https_errors=True,
            )
            
            for cookie in cookies:
                if "sameSite" not in cookie:
                    cookie["sameSite"] = "Lax"
            await context.add_cookies(cookies)
            
            # 4. Create page and navigate to content
            self.page = await context.new_page()
            
            logging.info(f"[Browser] Loading {self.base_url}...")
            await self.page.goto(self.base_url, timeout=30000, wait_until='domcontentloaded')
            
            # Verify Cloudflare bypass
            title = await self.page.title()
            if "Verify you are human" in title or "Just a moment" in title:
                logging.error("[Browser] ✗ Cloudflare challenge detected!")
                return False
            
            logging.info(f"[Browser] ✓ Content loaded: {title}")
            
            # 5. Position window
            try:
                await self.page.evaluate("window.moveTo(0, 0); window.resizeTo(1920, 1080);")
                
                import subprocess
                result = subprocess.run(
                    ['xdotool', 'search', '--class', 'chrome'],
                    capture_output=True,
                    text=True,
                    env={'DISPLAY': display},
                    timeout=5
                )
                
                window_ids = [w.strip() for w in result.stdout.strip().split('\n') if w.strip()]
                if window_ids:
                    for wid in window_ids:
                        subprocess.run(['xdotool', 'windowmove', wid, '0', '0'], 
                                     env={'DISPLAY': display}, timeout=5)
                        subprocess.run(['xdotool', 'windowsize', wid, '1920', '1080'],
                                     env={'DISPLAY': display}, timeout=5)
                    logging.info("[Browser] ✓ Window positioned")
                
            except Exception as e:
                logging.warning(f"[Browser] Window positioning: {e}")
            
            self.is_running = True
            logging.info("[Browser] ✓ Single-window setup complete!")
            logging.info("[Browser] VTuber overlay will be added by FFmpeg")
            
            return True
            
        except Exception as e:
            logging.error(f"[Browser] Failed to start: {e}")
            import traceback
            traceback.print_exc()
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
            return base64.b64encode(screenshot_bytes).decode('utf-8')
        except Exception as e:
            logging.error(f"[Browser] Screenshot failed: {e}")
            return None
    
    async def get_current_url(self) -> str:
        return self.page.url if self.page else ""
    
    async def scroll_down(self, amount: Optional[int] = None):
        if not self.page:
            return
        if amount is None:
            amount = random.randint(config.BROWSER_SCROLL_AMOUNT_MIN, 
                                   config.BROWSER_SCROLL_AMOUNT_MAX)
        try:
            logging.info(f"[Browser] ◌ Smooth scrolling down {amount}px...")
            await Behavior.smooth_scroll(self.page, amount, direction=1)
        except Exception as e:
            logging.error(f"[Browser] Scroll failed: {e}")
    
    async def scroll_up(self, amount: Optional[int] = None):
        if not self.page:
            return
        if amount is None:
            amount = random.randint(config.BROWSER_SCROLL_AMOUNT_MIN,
                                   config.BROWSER_SCROLL_AMOUNT_MAX)
        try:
            logging.info(f"[Browser] ◌ Smooth scrolling up {amount}px...")
            await Behavior.smooth_scroll(self.page, amount, direction=-1)
        except Exception as e:
            logging.error(f"[Browser] Scroll failed: {e}")
    
    async def click_random_product(self) -> bool:
        if not self.page:
            return False
        try:
            for selector in BROWSER_SELECTORS.get("product", []):
                products = await self.page.query_selector_all(selector)
                if products:
                    product = random.choice(products[:10])
                    await product.click()
                    await asyncio.sleep(2)
                    logging.info("[Browser] Clicked product")
                    return True
            return False
        except Exception as e:
            logging.error(f"[Browser] Click failed: {e}")
            return False
    
    async def go_back(self):
        if self.page:
            await self.page.go_back()
            await asyncio.sleep(2)
    
    async def refresh(self, force_home: bool = False):
        if self.page:
            try:
                if force_home:
                    logging.info("[Browser] Forcing navigation to home for refresh...")
                    await self.page.goto(self.base_url, wait_until='domcontentloaded', timeout=30000)
                else:
                    logging.info("[Browser] Reloading page...")
                    await self.page.reload(wait_until='domcontentloaded', timeout=30000)
                await asyncio.sleep(3)
                logging.info("[Browser] ✓ Refresh complete")
            except Exception as e:
                logging.error(f"[Browser] Refresh failed: {e}")
                # Fallback to home if reload fails
                try:
                    await self.page.goto(self.base_url, wait_until='domcontentloaded', timeout=30000)
                except:
                    pass
    
    async def go_home(self):
        if self.page:
            await self.page.goto(self.base_url, wait_until='domcontentloaded')
            await asyncio.sleep(2)
    
    async def is_in_viewport(self, element) -> bool:
        if not self.page:
            return False
        try:
            box = await element.bounding_box()
            if not box:
                return False
            viewport = await self.page.evaluate("""() => ({
                width: window.innerWidth,
                height: window.innerHeight
            })""")
            return (box['x'] < viewport['width'] and 
                    box['x'] + box['width'] > 0 and 
                    box['y'] < viewport['height'] and 
                    box['y'] + box['height'] > 0)
        except:
            return False

    async def is_page_stuck(self) -> bool:
        """Detect if the page is stuck with placeholders/skeletons"""
        if not self.page:
            return False
        
        try:
            # Check for common skeleton/placeholder selectors on Klik Indomaret
            # Often they use 'shimmer', 'skeleton', 'placeholder' or just have many empty divs
            skeleton_selectors = [
                '.skeleton',
                '[class*="skeleton"]',
                '.shimmer',
                '.placeholder-item',
                'div[style*="background-color: rgb(238, 238, 238)"]' # Common grey placeholder
            ]
            
            for selector in skeleton_selectors:
                elements = await self.page.query_selector_all(selector)
                if len(elements) > 10: # If many skeletons, it's probably stuck
                    logging.warning(f"[Browser] ⚠ Stuck detection: Found {len(elements)} skeletons ({selector})")
                    return True
            
            # Check if any products ARE loaded
            for selector in BROWSER_SELECTORS.get("product", []):
                products = await self.page.query_selector_all(selector)
                if products:
                    # Found products, but do they have real content?
                    # Check first product's title/text
                    text = await products[0].inner_text()
                    if len(text.strip()) > 5:
                        return False # Real content found
            
            # If we are on the base URL but no products found after sleep, might be stuck
            return True
            
        except Exception as e:
            logging.error(f"[Browser] Stuck detection failed: {e}")
            return False
    
    async def click_load_more(self) -> bool:
        if not self.page:
            return False
        try:
            for selector in BROWSER_SELECTORS.get("load_more", []):
                button = await self.page.query_selector(selector)
                if button and await button.is_visible():
                    await button.click()
                    await asyncio.sleep(2)
                    return True
            return False
        except:
            return False
    
    async def check_and_close_popup(self) -> bool:
        """Detect and close random popups or modals using multiple layers, scanning all frames"""
        if not self.page:
            return False
            
        try:
            # Get all frames (main frame + any iframes)
            frames = self.page.frames
            for frame in frames:
                try:
                    # Layer 1: Specific Selectors
                    for selector in BROWSER_SELECTORS.get("popup_close", []):
                        try:
                            button = await frame.query_selector(selector)
                            if button and await button.is_visible():
                                box = await button.bounding_box()
                                if box:
                                    logging.info(f"[Browser] ◌ Popup detected in frame ({frame.name or 'main'}) via ({selector}) at ({box['x']}, {box['y']}), closing...")
                                    await button.click()
                                    await asyncio.sleep(1)
                                    return True
                        except:
                            continue
                    
                    # Layer 2: JS-based heuristic detection & click
                    did_click = await frame.evaluate("""() => {
                        const closeChars = ['×', 'x', 'X', 'Close', 'Tutup'];
                        const elements = document.querySelectorAll('button, span, i, div, a, img');
                        for (const el of elements) {
                            try {
                                const rect = el.getBoundingClientRect();
                                if (rect.width > 5 && rect.height > 5 && rect.width < 120 && rect.height < 120) {
                                    const text = (el.innerText || el.textContent || '').trim();
                                    const className = (el.className || '').toString().toLowerCase();
                                    const id = (el.id || '').toLowerCase();
                                    const src = (el.getAttribute('src') || '').toLowerCase();
                                    const alt = (el.getAttribute('alt') || '').toLowerCase();
                                    
                                    // Does it look like a close button?
                                    if (closeChars.includes(text) || 
                                        className.includes('close') || 
                                        className.includes('modal_button') ||
                                        id.includes('close') ||
                                        src.includes('close') ||
                                        alt.includes('close')) {
                                        
                                        // Visibility check
                                        const style = window.getComputedStyle(el);
                                        if (style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0') {
                                            el.click();
                                            return true;
                                        }
                                    }
                                }
                            } catch(e) {}
                        }
                        return false;
                    }""")
                    
                    if did_click:
                        logging.info(f"[Browser] ◌ Popup detected and clicked in frame ({frame.name or 'main'}) via JS Heuristics")
                        await asyncio.sleep(1)
                        return True
                        
                except Exception as e:
                    # Some frames might be cross-origin and inaccessible
                    continue
            
            return False
        except Exception as e:
            logging.error(f"[Browser] Popup check failed: {e}")
            return False
    
    async def get_scroll_position(self) -> dict:
        if not self.page:
            return {"scrollY": 0, "atBottom": False, "atTop": True}
        try:
            return await self.page.evaluate("""() => {
                const scrollY = window.scrollY;
                const scrollHeight = document.documentElement.scrollHeight;
                const viewportHeight = window.innerHeight;
                const maxScroll = scrollHeight - viewportHeight;
                const scrollPercent = maxScroll > 0 ? scrollY / maxScroll : 0;
                return {
                    scrollY,
                    scrollHeight,
                    viewportHeight,
                    scrollPercent,
                    atBottom: scrollPercent > 0.85,
                    atTop: scrollPercent < 0.15
                };
            }""")
        except:
            return {"scrollY": 0, "atBottom": False, "atTop": True}
    
    async def perform_random_action(self) -> str:
        if not self.page:
            return "no_page"
        
        await self.check_and_close_popup()
        
        current_url = await self.get_current_url()
        is_product_page = "/xpress/" in current_url or "/product/" in current_url
        
        scroll_pos = await self.get_scroll_position()
        at_bottom = scroll_pos.get("atBottom", False)
        at_top = scroll_pos.get("atTop", True)
        
        if is_product_page and random.random() < 0.7:
            await Behavior.sleep(0.5, 1.5)
            await self.go_back()
            return "go_back"
        
        # if await self.click_load_more():
        #     return "load_more"
        
        if at_bottom:
            actions = ['scroll_up'] * 3 + ['click_product', 'back']
        elif at_top:
            actions = ['scroll_down'] * 4 + ['click_product']
        else:
            actions = ['scroll_down'] * 2 + ['scroll_up', 'click_product'] * 2 + ['back']
        
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
            await Behavior.sleep(0.5, 1.5)
            await self.go_back()
            return "go_back"
        
        return action


browser_controller: Optional[BrowserController] = None

async def get_browser_controller() -> BrowserController:
    global browser_controller
    if browser_controller is None:
        browser_controller = BrowserController()
    return browser_controller