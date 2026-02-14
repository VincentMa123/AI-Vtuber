"""
Lightweight Token Manager using Playwright (faster than Selenium)
Better for production apps - lighter and more efficient
"""

from playwright.sync_api import sync_playwright
import requests
import json
import time
from datetime import datetime, timedelta
import threading


class TokenManager:
    """
    Background service that maintains a fresh token
    Runs in a separate thread and auto-refreshes
    """
    
    def __init__(self, refresh_interval_minutes=25):
        self.token = None
        self.token_expires_at = None
        self.refresh_interval = refresh_interval_minutes
        self.browser = None
        self.context = None
        self.page = None
        self._running = False
        self._thread = None
        
    def start(self):
        """Start the background token refresh service"""
        print("🚀 Starting token manager...")
        
        # Get initial token
        self._refresh_token_sync()
        
        # Start background refresh thread
        self._running = True
        self._thread = threading.Thread(target=self._auto_refresh_loop, daemon=True)
        self._thread.start()
        
        print("✓ Token manager started")
    
    def stop(self):
        """Stop the background service"""
        self._running = False
        if self.browser:
            self.browser.close()
        print("✓ Token manager stopped")
    
    def _init_browser(self, playwright):
        """Initialize Playwright browser"""
        self.browser = playwright.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )
        
        self.context = self.browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36'
        )
        
        self.page = self.context.new_page()
    
    def _extract_token_from_request(self, route, request):
        """Extract token from network request"""
        headers = request.headers
        if 'x-aws-waf-token' in headers:
            self.token = headers['x-aws-waf-token']
            self.token_expires_at = datetime.now() + timedelta(minutes=30)
            print(f"✓ Token captured: {self.token[:50]}...")
    
    def _refresh_token_sync(self):
        """Synchronously refresh the token"""
        with sync_playwright() as playwright:
            if not self.browser:
                self._init_browser(playwright)
            
            try:
                # Intercept network requests to capture token
                self.page.route('**/*', lambda route, request: (
                    self._extract_token_from_request(route, request),
                    route.continue_()
                ))
                
                # Navigate and trigger API calls
                self.page.goto('https://www.klikindomaret.com')
                self.page.wait_for_timeout(2000)
                
                # Try to search to trigger API calls
                try:
                    search_input = self.page.locator('input[type="search"]').first
                    if search_input.is_visible(timeout=5000):
                        search_input.fill('indomilk')
                        self.page.wait_for_timeout(2000)
                except:
                    pass
                
                if self.token:
                    print(f"✓ Token refreshed at {datetime.now().strftime('%H:%M:%S')}")
                    return True
                else:
                    print("❌ Failed to capture token")
                    return False
                    
            except Exception as e:
                print(f"❌ Error refreshing token: {e}")
                return False
    
    def _auto_refresh_loop(self):
        """Background loop that auto-refreshes token"""
        while self._running:
            # Sleep until token needs refresh
            if self.token_expires_at:
                sleep_seconds = (self.token_expires_at - datetime.now() - timedelta(minutes=5)).total_seconds()
                if sleep_seconds > 0:
                    time.sleep(min(sleep_seconds, 60))  # Check every minute max
                    continue
            
            # Time to refresh
            self._refresh_token_sync()
            time.sleep(60)  # Wait at least 1 minute before next check
    
    def get_token(self):
        """Get current valid token"""
        if not self.token or not self.token_expires_at:
            self._refresh_token_sync()
        
        # Check if expired
        if datetime.now() >= (self.token_expires_at - timedelta(minutes=5)):
            self._refresh_token_sync()
        
        return self.token


class KlikIndomaretAPI:
    """
    Production-ready API client with automatic token management
    """
    
    def __init__(self, token_manager):
        # Two different base URLs - product and search use different endpoints!
        self.product_base_url = "https://ap-mc.klikindomaret.com/assets-klikidmgroceries/api/get/catalog-xpress/api/webapp"
        self.search_base_url = "https://ap-mc.klikindomaret.com/assets-klikidmsearch/api/get/catalog-xpress/api/webapp"
        self.token_manager = token_manager
    
    def _get_headers(self):
        """Get headers with fresh token"""
        return {
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'en-US,en;q=0.9,id-ID;q=0.8,id;q=0.7',
            'origin': 'https://www.klikindomaret.com',
            'referer': 'https://www.klikindomaret.com/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'x-aws-waf-token': self.token_manager.get_token(),
            'page': 'page'
        }
    
    def get_product(self, permalink, **params):
        """Get product details"""
        endpoint = f"{self.product_base_url}/product/detail-page"
        
        default_params = {
            'storeCode': 'TJKT',
            'latitude': -6.1763897,
            'longitude': 106.82667,
            'mode': 'DELIVERY',
            'districtId': 141100100,
            'permalink': permalink
        }
        default_params.update(params)
        
        response = requests.get(endpoint, headers=self._get_headers(), params=default_params)
        response.raise_for_status()
        return response.json()
    
    def search(self, keyword, page=0, size=15):
        """
        Search products - FIXED with correct endpoint!
        
        Args:
            keyword: Search term
            page: Page number (starts at 0!)
            size: Results per page
        """
        # CORRECT endpoint - different base URL!
        endpoint = f"{self.search_base_url}/search/result"
        
        params = {
            'keyword': keyword,  # Not 'q'!
            'type': 'keyword',
            'isUserFiltered': 'false',
            'page': page,  # 0-indexed
            'size': size,
            'storeCode': 'TJKT',
            'latitude': -6.1763897,
            'longitude': 106.82667,
            'mode': 'DELIVERY',
            'districtId': 141100100
        }
        
        response = requests.get(endpoint, headers=self._get_headers(), params=params)
        response.raise_for_status()
        return response.json()


# Example usage for a web app
def example_web_app():
    """
    Example: How to use this in a Flask/FastAPI app
    """
    # Initialize token manager once at app startup
    token_mgr = TokenManager()
    token_mgr.start()
    
    # Create API client
    api = KlikIndomaretAPI(token_mgr)
    
    try:
        # Your app can now make unlimited requests
        # The token manager handles refreshing in the background
        
        print("\n📦 Example 1: Get product")
        product = api.get_product("kental-manis-3")
        print("✓ Got product:", product.get('data', {}).get('name', 'Unknown'))
        
        print("\n🔍 Example 2: Search")
        results = api.search("indomilk")
        print("✓ Found results")
        
        print("\n🔁 Example 3: Multiple requests work seamlessly")
        for i in range(5):
            result = api.search(f"susu {i}")
            print(f"  ✓ Request {i+1} completed")
            time.sleep(1)
        
    finally:
        # Clean up when app shuts down
        token_mgr.stop()


if __name__ == "__main__":
    example_web_app()