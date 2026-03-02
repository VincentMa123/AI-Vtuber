import asyncio
import logging
import re
from typing import List, Dict, Set, Optional
from urllib.parse import urljoin, urlparse
from playwright.async_api import async_playwright, Page

logger = logging.getLogger(__name__)

class WebsiteCrawler:
    """
    Crawls a website to build a sitemap and extract text content for RAG.
    """
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.domain = urlparse(base_url).netloc
        self.visited_urls: Set[str] = set()
        self.sitemap: List[Dict[str, str]] = [] # Tier 1: {name, url}
        self.content_index: List[Dict[str, str]] = [] # Tier 2: {url, title, content}

    def _is_internal(self, url: str) -> bool:
        parsed = urlparse(url)
        return parsed.netloc == '' or parsed.netloc == self.domain

    def _clean_url(self, url: str) -> str:
        # Remove fragments and trailing slashes for consistency
        parsed = urlparse(url)
        url = urljoin(self.base_url, parsed.path)
        return url.rstrip('/')

    async def get_nav_links(self, page: Page) -> List[Dict[str, str]]:
        """Extracts primary navigation links from the homepage."""
        links = []
        # Common navigation selectors
        nav_selectors = [
            'nav a', 
            'header a', 
            '.menu a', 
            '.navigation a',
            'a:has-text("Home")',
            'a:has-text("About")',
            'a:has-text("Service")',
            'a:has-text("Contact")'
        ]
        
        seen_urls = set()
        
        for selector in nav_selectors:
            try:
                elements = await page.query_selector_all(selector)
                for el in elements:
                    text = (await el.inner_text()).strip()
                    href = await el.get_attribute('href')
                    
                    if not text or not href:
                        continue
                        
                    full_url = self._clean_url(urljoin(self.base_url, href))
                    
                    if self._is_internal(full_url) and full_url not in seen_urls:
                        # Filter out common non-content links
                        if any(x in full_url.lower() for x in ['tel:', 'mailto:', 'javascript:']):
                            continue
                            
                        links.append({
                            "name": text,
                            "url": full_url
                        })
                        seen_urls.add(full_url)
            except Exception as e:
                logger.debug(f"Error extracting with selector {selector}: {e}")
                
        return links

    async def extract_page_content(self, page: Page, url: str):
        """Extracts meaningful text from a specific page."""
        title = await page.title()
        
        # Remove script, style, nav, and footer to get clean content
        await page.evaluate("""() => {
            const toRemove = ['nav', 'header', 'footer', 'script', 'style', 'aside', '.ads', '.sidebar'];
            toRemove.forEach(tag => {
                document.querySelectorAll(tag).forEach(el => el.remove());
            });
        }""")
        
        # Get main text
        content = await page.inner_text('body')
        # Clean up whitespace
        content = re.sub(r'\n+', '\n', content).strip()
        
        self.content_index.append({
            "url": url,
            "title": title,
            "content": content
        })

    async def crawl(self, max_pages: int = 10):
        """Main entry point to crawl the site."""
        async with async_playwright() as p:
            # For local dev/testing, headless can be True for speed
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            
            logger.info(f"[Crawler] Starting crawl on {self.base_url}")
            await page.goto(self.base_url, wait_until="domcontentloaded")
            
            # 1. Get Sitemap (Tier 1)
            self.sitemap = await self.get_nav_links(page)
            logger.info(f"[Crawler] Found {len(self.sitemap)} nav links: {[l['name'] for l in self.sitemap]}")
            
            # 2. Extract content from nav links (Tier 2)
            # Add home first
            await self.extract_page_content(page, self.base_url)
            self.visited_urls.add(self._clean_url(self.base_url))
            
            for link in self.sitemap[:max_pages]:
                url = link['url']
                if url in self.visited_urls:
                    continue
                    
                logger.info(f"[Crawler] Visiting {url} ({link['name']})...")
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    await self.extract_page_content(page, url)
                    self.visited_urls.add(url)
                except Exception as e:
                    logger.error(f"[Crawler] Failed to crawl {url}: {e}")
            
            await browser.close()
            
        return {
            "sitemap": self.sitemap,
            "content": self.content_index
        }
