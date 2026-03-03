import logging
import asyncio
import requests
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

# Shared WAF token storage — set by the browser controller or fallback
_waf_token: Optional[str] = None
_waf_token_expires: Optional[datetime] = None
_token_lock = threading.Lock()


def set_waf_token(token: str):
    """Called by the browser controller when it captures a WAF token from network requests."""
    global _waf_token, _waf_token_expires
    with _token_lock:
        if _waf_token == token:
            return
        _waf_token = token
        _waf_token_expires = datetime.now() + timedelta(minutes=25)
        logger.info(f"[Klikindomaret] WAF token updated: {token[:40]}...")


def get_waf_token() -> Optional[str]:

    global _waf_token, _waf_token_expires
    with _token_lock:
        if _waf_token and _waf_token_expires and datetime.now() < _waf_token_expires:
            return _waf_token
    return None


async def _refresh_token_fallback():

    try:

        logger.info("[Klikindomaret] No WAF token from browser controller, using fallback...")
        captured_token = None
        
        pw = await async_playwright().start()
        try:
            browser = await pw.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36'
            )
            page = await context.new_page()
            
            async def on_request(request):
                nonlocal captured_token
                headers = request.headers
                if 'x-aws-waf-token' in headers and not captured_token:
                    captured_token = headers['x-aws-waf-token']
            
            page.on("request", on_request)
            await page.goto('https://www.klikindomaret.com', timeout=15000)
            await page.wait_for_timeout(3000)
            
            # Trigger a search to ensure WAF token is generated
            try:
                search_input = page.locator('input[type="search"]').first
                if await search_input.is_visible(timeout=3000):
                    await search_input.fill('susu')
                    await page.wait_for_timeout(2000)
            except:
                pass
            
            await browser.close()
        finally:
            await pw.stop()
        
        if captured_token:
            set_waf_token(captured_token)
            return captured_token
        else:
            logger.error("[Klikindomaret] Fallback failed to capture WAF token")
            return None
            
    except Exception as e:
        logger.error(f"[Klikindomaret] Fallback token refresh error: {e}")
        return None


async def _ensure_token() -> Optional[str]:

    token = get_waf_token()
    if token:
        return token
        
    # Main browser didn't provide a token — use heavyweight fallback
    logger.warning("[Klikindomaret] Browser didn't provide token, using fallback...")
    return await _refresh_token_fallback()


class KlikindomaretService:

    PRODUCT_BASE_URL = "https://ap-mc.klikindomaret.com/assets-klikidmgroceries/api/get/catalog-xpress/api/webapp"
    SEARCH_BASE_URL = "https://ap-mc.klikindomaret.com/assets-klikidmsearch/api/get/catalog-xpress/api/webapp"
    
    DEFAULT_PARAMS = {
        'storeCode': 'TJKT',
        'latitude': -6.1763897,
        'longitude': 106.82667,
        'mode': 'DELIVERY',
        'districtId': 141100100
    }
    
    def _get_headers(self, token: str) -> dict:
        return {
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'en-US,en;q=0.9,id-ID;q=0.8,id;q=0.7',
            'origin': 'https://www.klikindomaret.com',
            'referer': 'https://www.klikindomaret.com/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'x-aws-waf-token': token,
            'page': 'page'
        }
    
    async def search_products(self, keyword: str, limit: int = 5) -> List[Dict]:

        token = await _ensure_token()
        if not token:
            logger.error("[Klikindomaret] No WAF token available, cannot search")
            return []
        
        try:
            endpoint = f"{self.SEARCH_BASE_URL}/search/result"
            params = {
                'keyword': keyword,
                'type': 'keyword',
                'isUserFiltered': 'false',
                'page': 0,
                'size': limit,
                **self.DEFAULT_PARAMS
            }
            
            response = requests.get(
                endpoint,
                headers=self._get_headers(token),
                params=params,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            # Extract products from response (data.content[])
            products_raw = data.get('data', {}).get('content', [])
            
            results = []
            for p in products_raw[:limit]:
                product = {
                    'name': p.get('productName', 'Unknown'),
                    'price': p.get('price', 0),
                    'final_price': p.get('finalPrice', p.get('price', 0)),
                    'brand': p.get('brandName', ''),
                    'size': p.get('size', ''),
                    'promo': p.get('promoText', ''),
                    'discount': p.get('discountText', ''),
                    'url': f"https://www.klikindomaret.com/product/{p.get('permalink', '')}",
                    'available': p.get('selling', False),
                }
                results.append(product)
            
            logger.info(f"[Klikindomaret] Search '{keyword}' -> {len(results)} results")
            return results
            
        except requests.exceptions.RequestException as e:
            logger.error(f"[Klikindomaret] Search failed for '{keyword}': {e}")
            # Token might be expired, clear it
            with _token_lock:
                global _waf_token, _waf_token_expires
                _waf_token = None
                _waf_token_expires = None
            return []        
        except Exception as e:
            logger.error(f"[Klikindomaret] Unexpected error searching '{keyword}': {e}")
            return []
    
    async def format_top_result(self, keyword: str) -> str:

        products = await self.search_products(keyword, limit=3)
        
        if not products:
            return f"Tidak ada produk ditemukan untuk '{keyword}' di Klikindomaret."
        
        # Pick the top result
        top = products[0]
        
        # Format price
        price = top['final_price'] or top['price']
        price_str = f"Rp {price:,}"
        
        # Build result string
        parts = [f"Produk: {top['name']}"]
        parts.append(f"Harga: {price_str}")
        
        if top['final_price'] and top['price'] and top['final_price'] < top['price']:
            parts.append(f"Harga asli: Rp {top['price']:,}")
            if top['discount']:
                parts.append(f"Diskon: {top['discount']}")
        
        if top['promo']:
            parts.append(f"Promo: {top['promo']}")
        
        if top['brand']:
            parts.append(f"Brand: {top['brand']}")
        
        if top['size']:
            parts.append(f"Ukuran: {top['size']}")
        
        # Also include a couple more options
        if len(products) > 1:
            parts.append("\nProduk lainnya:")
            for p in products[1:3]:
                p_price = p['final_price'] or p['price']
                parts.append(f"- {p['name']}: Rp {p_price:,}")
        
        return "\n".join(parts)

_service: Optional[KlikindomaretService] = None


def get_klikindomaret_service() -> KlikindomaretService:

    global _service
    if _service is None:
        _service = KlikindomaretService()
    return _service
