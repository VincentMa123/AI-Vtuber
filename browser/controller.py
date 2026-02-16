import logging
import asyncio
import random
import base64
from typing import Optional
from playwright.async_api import async_playwright, Browser, Page, Playwright
from .behavior import Behavior
import src.core.config as config
from src.core.utils import get_flaresolverr_cookies

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
        '.modal-close',
        'button.close',
        '[class*="close"]',
    ],
}

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
            
            # 1. Get FlareSolverr solution
            cookies, user_agent = get_flaresolverr_cookies(self.base_url)
            
            if not cookies:
                logging.error(f"[Browser] FlareSolverr failed to get cookies")
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
                '--test-type',
                '--disable-infobars',
            ]
            
            try:
                self.browser = await self.playwright.chromium.launch(
                    channel="chrome",
                    headless=False,
                    args=launch_args,
                    env={'DISPLAY': display},
                    ignore_default_args=["--enable-automation"]
                )
                logging.info("[Browser] ✓ Chrome launched")
            except:
                self.browser = await self.playwright.chromium.launch(
                    headless=False,
                    args=launch_args,
                    env={'DISPLAY': display},
                    ignore_default_args=["--enable-automation"]
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
            await self.page.goto(self.base_url, timeout=3000, wait_until='domcontentloaded')
            
            # Hide cursor on all pages (including navigations)
            await self.page.add_style_tag(content="* { cursor: none !important; }")
            self.page.on("framenavigated", lambda frame: asyncio.create_task(frame.add_style_tag(content="* { cursor: none !important; }")) if frame == self.page.main_frame else None)
            
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
                    logging.info(f"[Browser] Clicked product via selector: {selector}")
                    return True
            logging.warning("[Browser] No products found with any selector")
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
    
    async def check_and_close_popup(self) -> bool:

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
                                    logging.info(f"[Browser] ◌ Popup detected in frame ({frame.name or 'main'}) via selector ({selector}) at ({box['x']}, {box['y']}), closing...")
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
        
        # 1. Recovery: If we are on about:blank, go home
        current_url = await self.get_current_url()
        if "about:blank" in current_url:
            logging.warning("[Browser] ⚠ Detected about:blank! Navigating home...")
            await self.go_home()
            return "recovered_from_blank"

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
        
        if at_bottom:
            actions = ['scroll_up'] * 3 + ['click_product', 'back']
        elif at_top:
            actions = ['scroll_down'] * 4 + ['click_product']
        else:
            actions = ['scroll_down'] * 3 + ['scroll_up', 'click_product'] + ['back']
        
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