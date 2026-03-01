import os
import subprocess
import traceback
import logging
import asyncio
import random
import base64
from typing import Optional
from playwright.async_api import async_playwright, Browser, Page, Playwright, Frame
from .behavior import Behavior
import core.config as config
from core.utils import get_flaresolverr_cookies
from rag.klikindomaret_service import get_waf_token, set_waf_token

BROWSER_SELECTORS = {
    "load_more": [
        'button:has-text("Muat Lebih Banyak")',
        'button:has-text("Load More")',
    ],
    "product": [
        'a[href*="/xpress/"]',
        'a[href*="/p/"]',
        'a[href*="/product/"]',
        '.item[data-cs-item]',
        '.item .product-collection',
        'div[class*="product-collection"] .item',
        '.item',
        'div[class*="product"]',
        '.card',
        '.product-card',
        '.product-item a',
        '[data-testid="product-card"]'
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
        self.shell_url = "http://localhost:8000/shell"

    def _get_content_frame(self) -> Optional[Frame]:
        """Get the content iframe from the shell page."""
        if not self.page:
            return None
        if config.SHELL_ENABLED:
            frame = self.page.frame(name="content-frame")
            return frame if frame else self.page
        return self.page

    async def start(self) -> bool:
        try:
            self.playwright = await async_playwright().start()

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
                '--disable-features=CrossOriginOpenerPolicy,CrossOriginEmbedderPolicy',
                # WebGL via software rendering (needed for Live2D on headless/Xvfb)
                '--enable-webgl',
                '--use-gl=angle',
                '--use-angle=swiftshader-webgl',
                '--enable-unsafe-swiftshader',
                '--ignore-gpu-blocklist',
            ]

            try:
                self.browser = await self.playwright.chromium.launch(
                    channel="chrome",
                    headless=False,
                    args=launch_args,
                    env={'DISPLAY': display},
                    ignore_default_args=["--enable-automation"]
                )
                logging.info("[Browser] Chrome launched")
            except:
                self.browser = await self.playwright.chromium.launch(
                    headless=False,
                    args=launch_args,
                    env={'DISPLAY': display},
                    ignore_default_args=["--enable-automation"]
                )
                logging.info("[Browser] Chromium launched")

            context = await self.browser.new_context(
                viewport={"width": 1920, "height": 1080},
                no_viewport=True,
                ignore_https_errors=True,
                bypass_csp=True,
            )

            self.page = await context.new_page()

            # Forward browser console logs to Python logging (for debugging VTuber iframe)
            self.page.on("console", lambda msg: logging.info(f"[Browser Console] [{msg.type}] {msg.text}"))
            self.page.on("pageerror", lambda err: logging.error(f"[Browser PageError] {err}"))

            # Capture WAF tokens from network requests (fires for all frame requests)
            def _on_request(request):
                try:
                    waf_token = request.headers.get('x-aws-waf-token')
                    if waf_token:
                        set_waf_token(waf_token)
                except Exception as e:
                    logging.warning(f"[Browser] Error in request interceptor: {e}")

            self.page.on("request", _on_request)

            # Strip X-Frame-Options and CSP headers so content sites load in the shell iframe
            if config.SHELL_ENABLED:
                async def _strip_frame_headers(route):
                    if route.request.resource_type != "document":
                        await route.continue_()
                        return
                    try:
                        response = await route.fetch()
                        headers = dict(response.headers)
                        headers.pop('x-frame-options', None)
                        headers.pop('content-security-policy', None)
                        headers.pop('content-security-policy-report-only', None)
                        await route.fulfill(response=response, headers=headers)
                    except Exception:
                        await route.continue_()
                await self.page.route("**/*", _strip_frame_headers)

            # Navigate to shell page or directly to content
            if config.SHELL_ENABLED:
                target_url = self.shell_url
                logging.info(f"[Browser] Loading shell at {target_url}...")
            else:
                target_url = self.base_url
                logging.info(f"[Browser] Loading {target_url}...")

            await self.page.goto(target_url, timeout=30000, wait_until='domcontentloaded')

            # Hide cursor on shell page
            await self.page.add_style_tag(content="* { cursor: none !important; }")

            if config.SHELL_ENABLED:
                # Wait for content iframe to load
                logging.info("[Browser] Waiting for content frame...")
                content_frame = None
                for _ in range(30):
                    content_frame = self.page.frame(name="content-frame")
                    if content_frame:
                        break
                    await asyncio.sleep(1)

                if not content_frame:
                    logging.error("[Browser] Content frame not found!")
                    return False

                try:
                    await content_frame.wait_for_load_state('domcontentloaded', timeout=30000)
                except Exception as e:
                    logging.warning(f"[Browser] Content frame load timeout: {e}")

                # Hide cursor in content frame
                try:
                    await content_frame.add_style_tag(content="* { cursor: none !important; }")
                except:
                    pass

                # Verify Cloudflare bypass on content frame
                try:
                    title = await content_frame.title()
                except:
                    title = "Unknown"

                if "Verify you are human" in title or "Just a moment" in title:
                    logging.error("[Browser] Cloudflare challenge detected!")
                    return False

                logging.info(f"[Browser] Content loaded in shell: {title}")

                # Hide cursor on content frame navigations
                async def _hide_cursor_on_frame_nav(frame):
                    cf = self._get_content_frame()
                    if cf and frame == cf:
                        try:
                            await frame.add_style_tag(content="* { cursor: none !important; }")
                        except:
                            pass
                self.page.on("framenavigated", lambda frame: asyncio.create_task(_hide_cursor_on_frame_nav(frame)))
            else:
                # Non-shell mode (direct navigation)
                async def _hide_cursor_on_frame_nav(frame):
                    if frame == self.page.main_frame:
                        try:
                            await frame.add_style_tag(content="* { cursor: none !important; }")
                        except:
                            pass
                self.page.on("framenavigated", lambda frame: asyncio.create_task(_hide_cursor_on_frame_nav(frame)))

                title = await self.page.title()
                if "Verify you are human" in title or "Just a moment" in title:
                    logging.error("[Browser] Cloudflare challenge detected!")
                    return False

                logging.info(f"[Browser] Content loaded: {title}")

            # Position window
            try:
                await self.page.evaluate("window.moveTo(0, 0); window.resizeTo(1920, 1080);")

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
                    logging.info("[Browser] Window positioned")

            except Exception as e:
                logging.warning(f"[Browser] Window positioning: {e}")

            self.is_running = True
            if config.SHELL_ENABLED:
                logging.info("[Browser] Shell mode setup complete (single window)")
            else:
                logging.info("[Browser] Single-window setup complete!")
                logging.info("[Browser] VTuber overlay will be added by FFmpeg")

            # Warm up WAF token
            try:
                logging.info("[Browser] Warming up WAF token...")
                frame = self._get_content_frame()
                await self.page.wait_for_timeout(2000)

                search_input = frame.locator('#search-submited').or_(frame.locator('input[name="keyword"]')).first

                try:
                    await search_input.wait_for(state="visible", timeout=10000)
                    await search_input.fill('susu')
                    await self.page.wait_for_timeout(1000)
                    await search_input.press("Enter")
                    await frame.wait_for_load_state('networkidle', timeout=10000)

                    token = get_waf_token()
                    if token:
                        logging.info("[Browser] WAF token captured during warmup")
                    else:
                        logging.warning("[Browser] WAF token not captured during warmup")

                except Exception as e:
                    logging.warning(f"[Browser] Search input missing/timeout: {e}")

            except Exception as e:
                logging.warning(f"[Browser] WAF warmup failed: {e}")

            return True

        except Exception as e:
            logging.error(f"[Browser] Failed to start: {e}")
            traceback.print_exc()
            return False

    async def stop(self):
        self.is_running = False
        if self._loop_task:
            self._loop_task.cancel()
        if self.browser:
            try:
                await asyncio.wait_for(self.browser.close(), timeout=3.0)
            except asyncio.TimeoutError:
                logging.warning("[Browser] browser.close() timed out (browser may have crashed)")
            except Exception as e:
                logging.warning(f"[Browser] browser.close() failed: {e}")
        if self.playwright:
            try:
                await asyncio.wait_for(self.playwright.stop(), timeout=3.0)
            except asyncio.TimeoutError:
                logging.warning("[Browser] playwright.stop() timed out")
            except Exception as e:
                logging.warning(f"[Browser] playwright.stop() failed: {e}")
        self.browser = None
        self.playwright = None
        self.page = None
        logging.info("[Browser] Stopped")

    async def get_screenshot(self) -> Optional[str]:
        """Capture the full shell page (content + VTuber overlay composited)."""
        if not self.page or not self.is_running:
            return None
        try:
            screenshot_bytes = await self.page.screenshot(type='jpeg', quality=80)
            return base64.b64encode(screenshot_bytes).decode('utf-8')
        except Exception as e:
            logging.error(f"[Browser] Screenshot failed: {e}")
            if "Connection closed" in str(e) or "connection" in str(e).lower():
                logging.error("[Browser] Connection lost — marking browser as stopped")
                self.is_running = False
            return None

    async def get_current_url(self) -> str:
        frame = self._get_content_frame()
        return frame.url if frame else ""

    async def scroll_down(self, amount: Optional[int] = None):
        if not self.page or not self.is_running:
            return
        if amount is None:
            amount = random.randint(config.BROWSER_SCROLL_AMOUNT_MIN,
                                   config.BROWSER_SCROLL_AMOUNT_MAX)
        try:
            logging.info(f"[Browser] Smooth scrolling down {amount}px...")
            frame = self._get_content_frame()
            await Behavior.smooth_scroll(frame, amount, direction=1)
        except Exception as e:
            logging.error(f"[Browser] Scroll failed: {e}")
            if "Connection closed" in str(e) or "connection" in str(e).lower():
                self.is_running = False

    async def scroll_up(self, amount: Optional[int] = None):
        if not self.page or not self.is_running:
            return
        if amount is None:
            amount = random.randint(config.BROWSER_SCROLL_AMOUNT_MIN,
                                   config.BROWSER_SCROLL_AMOUNT_MAX)
        try:
            logging.info(f"[Browser] Smooth scrolling up {amount}px...")
            frame = self._get_content_frame()
            await Behavior.smooth_scroll(frame, amount, direction=-1)
        except Exception as e:
            logging.error(f"[Browser] Scroll failed: {e}")
            if "Connection closed" in str(e) or "connection" in str(e).lower():
                self.is_running = False

    async def click_random_product(self) -> bool:
        if not self.page:
            return False
        try:
            frame = self._get_content_frame()
            for selector in BROWSER_SELECTORS.get("product", []):
                products = await frame.query_selector_all(selector)
                if not products:
                    continue

                # Filter to only visible, in-viewport elements
                visible_products = []
                for p in products[:20]:
                    try:
                        if not await p.is_visible():
                            continue
                        box = await p.bounding_box()
                        if not box:
                            continue
                        viewport = await frame.evaluate(
                            "() => ({ w: window.innerWidth, h: window.innerHeight })"
                        )
                        if (box['y'] + box['height'] > 0 and box['y'] < viewport['h'] and
                                box['x'] + box['width'] > 0 and box['x'] < viewport['w']):
                            visible_products.append(p)
                    except:
                        continue

                if not visible_products:
                    continue

                product = random.choice(visible_products[:10])

                # Listen for new tabs (target="_blank" links)
                new_page_event = asyncio.get_event_loop().create_future()

                def on_popup(popup):
                    if not new_page_event.done():
                        new_page_event.set_result(popup)

                self.page.once("popup", on_popup)

                try:
                    await product.click(timeout=5000)
                except Exception:
                    self.page.remove_listener("popup", on_popup)
                    raise

                # Check if a new tab was opened
                try:
                    new_page = await asyncio.wait_for(
                        asyncio.shield(new_page_event), timeout=2.0
                    )
                    await new_page.wait_for_load_state("domcontentloaded", timeout=10000)
                    old_page = self.page
                    self.page = new_page

                    await self.page.add_style_tag(content="* { cursor: none !important; }")

                    try:
                        await old_page.close()
                    except:
                        pass
                    logging.info(f"[Browser] Clicked product (new tab) via selector: {selector}")
                except asyncio.TimeoutError:
                    # No new tab — content navigated within iframe, which is fine
                    self.page.remove_listener("popup", on_popup)
                    logging.info(f"[Browser] Clicked product via selector: {selector}")

                await asyncio.sleep(2)
                return True

            logging.warning("[Browser] No visible products found with any selector")
            return False
        except Exception as e:
            logging.error(f"[Browser] Click failed: {e}")
            return False

    async def navigate_to_page(self, url: str) -> bool:
        frame = self._get_content_frame()
        if not frame:
            return False
        try:
            logging.info(f"[Browser] Navigating to {url} (background)...")
            await frame.goto(url, wait_until="commit", timeout=30000)

            async def _apply_style():
                try:
                    await frame.add_style_tag(content="* { cursor: none !important; }")
                except:
                    pass
            asyncio.create_task(_apply_style())
            return True
        except Exception as e:
            logging.error(f"[Browser] Failed to navigate to {url}: {e}")
            return False

    async def go_back(self):
        frame = self._get_content_frame()
        if frame:
            await frame.go_back()
            await asyncio.sleep(2)
            if "about:blank" in frame.url:
                logging.warning("[Browser] go_back landed on about:blank, recovering to home...")
                await self.go_home()

    async def refresh(self, force_home: bool = False):
        frame = self._get_content_frame()
        if frame:
            try:
                if force_home:
                    logging.info("[Browser] Forcing navigation to home for refresh...")
                    await frame.goto(self.base_url, wait_until='domcontentloaded', timeout=30000)
                else:
                    logging.info("[Browser] Reloading page...")
                    await frame.evaluate("location.reload()")
                    try:
                        await frame.wait_for_load_state('domcontentloaded', timeout=30000)
                    except:
                        pass
                await asyncio.sleep(3)
                logging.info("[Browser] Refresh complete")
            except Exception as e:
                logging.error(f"[Browser] Refresh failed: {e}")
                try:
                    await frame.goto(self.base_url, wait_until='domcontentloaded', timeout=30000)
                except:
                    pass

    async def go_home(self):
        frame = self._get_content_frame()
        if frame:
            await frame.goto(self.base_url, wait_until='domcontentloaded')
            await asyncio.sleep(2)

    async def is_in_viewport(self, element) -> bool:
        frame = self._get_content_frame()
        if not frame:
            return False
        try:
            box = await element.bounding_box()
            if not box:
                return False
            viewport = await frame.evaluate("""() => ({
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
        frame = self._get_content_frame()
        if not frame:
            return False

        try:
            # Check the content frame and its child frames
            frames_to_check = [frame] + frame.child_frames
            for f in frames_to_check:
                try:
                    # Layer 1: Specific Selectors
                    for selector in BROWSER_SELECTORS.get("popup_close", []):
                        try:
                            button = await f.query_selector(selector)
                            if button and await button.is_visible():
                                box = await button.bounding_box()
                                if box:
                                    logging.info(f"[Browser] Popup detected in frame ({f.name or 'main'}) via selector ({selector}) at ({box['x']}, {box['y']}), closing...")
                                    await button.click()
                                    await asyncio.sleep(1)
                                    return True
                        except:
                            continue

                    # Layer 2: JS-based heuristic detection & click
                    did_click = await f.evaluate("""() => {
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

                                    if (closeChars.includes(text) ||
                                        className.includes('close') ||
                                        className.includes('modal_button') ||
                                        id.includes('close') ||
                                        src.includes('close') ||
                                        alt.includes('close')) {

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
                        logging.info(f"[Browser] Popup detected and clicked in frame ({f.name or 'main'}) via JS Heuristics")
                        await asyncio.sleep(1)
                        return True

                except Exception as e:
                    continue

            return False
        except Exception as e:
            logging.error(f"[Browser] Popup check failed: {e}")
            return False

    async def get_scroll_position(self) -> dict:
        frame = self._get_content_frame()
        if not frame:
            return {"scrollY": 0, "atBottom": False, "atTop": True}
        try:
            return await frame.evaluate("""() => {
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
                    atBottom: scrollPercent > 0.95,
                    atTop: scrollPercent < 0.15
                };
            }""")
        except:
            return {"scrollY": 0, "atBottom": False, "atTop": True}

    async def perform_random_action(self) -> str:
        if not self.page or not self.is_running:
            return "no_page"

        # 1. Recovery: If we are on about:blank, go home
        current_url = await self.get_current_url()
        if "about:blank" in current_url:
            logging.warning("[Browser] Detected about:blank! Navigating home...")
            await self.go_home()
            return "recovered_from_blank"

        # await self.check_and_close_popup()

        current_url = await self.get_current_url()
        is_product_page = "/xpress/" in current_url or "/product/" in current_url

        scroll_pos = await self.get_scroll_position()
        at_bottom = scroll_pos.get("atBottom", False)
        at_top = scroll_pos.get("atTop", True)

        if is_product_page and random.random() < 0.7:
            await Behavior.sleep(0.5, 1.5)
            await self.go_back()
            return "go_back"


        actions = ['scroll_down'] * 15 + ['scroll_up']

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

        return action


browser_controller: Optional[BrowserController] = None

async def get_browser_controller() -> BrowserController:
    global browser_controller
    if browser_controller is None:
        browser_controller = BrowserController()
    return browser_controller
