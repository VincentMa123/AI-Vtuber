import requests
import datetime
import os
import logging
import base64
import io
import numpy as np
from typing import Optional, Tuple
from PIL import Image
from rag import CRAWL_RESULT_PATH

VLM_TARGET_SIZE = (1280, 720)
SIMILARITY_THRESHOLD = 0.05

_last_image_hash: Optional[int] = None
_last_image_bytes: Optional[bytes] = None


def load_prompt_file(filename):

    try:
        # Get absolute path relative to this file (one level up from core)
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        file_path = os.path.join(base_dir, "prompts", filename)
        
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logging.error(f"Error loading prompt file {filename}: {e}")
        return ""


def get_system_prompt(user_message: str = "", **kwargs):
    
    identity = load_prompt_file("soul.md")
    rules = load_prompt_file("rules.md")

    # Load sitemap for context
    sitemap_context = ""
    visited = kwargs.get("visited_urls", [])
    current_url = kwargs.get("current_url", "")
    try:
        import json
        if os.path.exists(CRAWL_RESULT_PATH):
            with open(CRAWL_RESULT_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                sitemap = data.get("sitemap", [])
                if sitemap:
                    norm_visited = [u.rstrip("/") for u in visited]
                    norm_current = current_url.rstrip("/")
                    
                    unvisited = [item for item in sitemap if item['url'].rstrip("/") not in norm_visited and item['url'].rstrip("/") != norm_current]
                    explored = [item for item in sitemap if item['url'].rstrip("/") in norm_visited or item['url'].rstrip("/") == norm_current]
                    
                    sitemap_str = "Available New Sections (Priority):\n"
                    if unvisited:
                        sitemap_str += "\n".join([f"- {item['name']}: {item['url']}" for item in unvisited[:20]])
                        # Suggest the very first unvisited one as recommendation
                        recommendation = unvisited[0]['url']
                        kwargs["next_recommendation"] = recommendation
                    else:
                        sitemap_str += "(No new sections found in sitemap)\n"
                    
                    if explored:
                        sitemap_str += "\n\nAlready Explored Sections:\n"
                        sitemap_str += "\n".join([f"- {item['url']}" for item in explored[:5]])
                    
                    sitemap_context = f"\nWebsite Sitemap Context:\n{sitemap_str}\n"
    except Exception as e:
        logging.warning(f"Error loading sitemap for prompt: {e}")

    # DeepSeek discovers tools from the API 'tools' parameter, not the system prompt.
    # Do NOT mention tools here — it confuses the model into outputting fake XML.

    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # Previously Explored Sections is now handled within Sitemap Context

    # Navigation Hint
    nav_hint = ""
    scroll_status = kwargs.get("scroll_status", "Middle of page")
    if isinstance(scroll_status, str) and scroll_status.startswith("At Bottom"):
        rec = kwargs.get("next_recommendation", "(Check Unvisited List)")
        nav_hint = f"\n[SYSTEM HINT]: Position: At Bottom. You MUST call the 'navigate_to_page' tool now. \nRecommended Target: {rec}\nFor your verbal response, ONLY say: 'Halo guys, webpage ini saya sudah jelaskan jadi kita ke section berikutnya ya'.\n"

    context = f"""
    Current Context:
    - Time: {current_time}
    - Environment: You are currently live streaming.
    - System Status: All systems nominal.
    - Current URL: {kwargs.get("current_url", "Unknown")}
    - Current Page: {kwargs.get("page_title", "Unknown")}
    - Scroll Position: {scroll_status}
    {sitemap_context}
    {nav_hint}
    """

    full_prompt = f"{identity}\n\n{rules}\n\n{context}"
    return full_prompt

def compress_image_for_vlm(
    image_base64: str, 
    max_size: Tuple[int, int] = VLM_TARGET_SIZE,
    quality: int = 80
) -> str:

    try:
        image_data = base64.b64decode(image_base64)
        image = Image.open(io.BytesIO(image_data))
        
        original_size = len(image_data)
        
        if image.mode in ('RGBA', 'P'):
            image = image.convert('RGB')
        
        if image.width > max_size[0] or image.height > max_size[1]:
            image.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG', quality=quality, optimize=True)
        compressed_data = buffer.getvalue()
        
        new_size = len(compressed_data)
        reduction = (1 - new_size / original_size) * 100
        
        if reduction > 10:
            logging.debug(f"[ImageUtils] Compressed: {original_size//1024}KB -> {new_size//1024}KB ({reduction:.0f}% reduction)")
        
        return base64.b64encode(compressed_data).decode('utf-8')
        
    except Exception as e:
        logging.warning(f"[ImageUtils] Compression failed, using original: {e}")
        return image_base64


def is_similar_to_last(image_base64: str, threshold: float = SIMILARITY_THRESHOLD) -> bool:

    global _last_image_hash, _last_image_bytes
    
    try:
        image_data = base64.b64decode(image_base64)
        
        if _last_image_bytes is not None:
            size_diff = abs(len(image_data) - len(_last_image_bytes)) / max(len(_last_image_bytes), 1)
            if size_diff > 0.2:
                _last_image_bytes = image_data
                _last_image_hash = _compute_image_hash(image_data)
                return False
        
        current_hash = _compute_image_hash(image_data)
        
        if _last_image_hash is None:
            _last_image_hash = current_hash
            _last_image_bytes = image_data
            return False
        
        difference = bin(current_hash ^ _last_image_hash).count('1') / 256
        
        _last_image_hash = current_hash
        _last_image_bytes = image_data
        
        is_similar = difference < threshold
        if is_similar:
            logging.debug(f"[ImageUtils] Image similar to last ({difference:.1%} diff), skipping VLM")
        
        return is_similar
        
    except Exception as e:
        logging.warning(f"[ImageUtils] Similarity check failed: {e}")
        return False


def _compute_image_hash(image_data: bytes) -> int:

    try:
        image = Image.open(io.BytesIO(image_data))
        image = image.resize((16, 16), Image.Resampling.LANCZOS).convert('L')
        
        pixels = list(image.getdata())
        avg = sum(pixels) / len(pixels)
        
        hash_value = 0
        for i, pixel in enumerate(pixels):
            if pixel > avg:
                hash_value |= (1 << i)
        
        return hash_value
        
    except Exception as e:
        logging.warning(f"[ImageUtils] Hash computation failed: {e}")
        return 0

def calculate_rms_volume(pcm_data: bytes, sensitivity: float = 3000.0) -> float:
    """
    Calculates the Root Mean Square (RMS) volume of 16-bit PCM audio data.
    
    Args:
        pcm_data: Raw 16-bit PCM audio bytes.
        sensitivity: Divisor for normalization. Lower value = higher sensitivity.
                     Default 3000.0 provides good sensitivity for speech.
                     
    Returns:
        float: Normalized volume between 0.0 and 1.0.
    """
    try:
        if not pcm_data:
            return 0.0
            
        # Ensure even number of bytes for 16-bit samples
        if len(pcm_data) % 2 != 0:
            return 0.0
            
        samples = np.frombuffer(pcm_data, dtype=np.int16)
        if len(samples) == 0:
            return 0.0
            
        # Calculate RMS
        rms = np.sqrt(np.mean(samples.astype(np.float32)**2))
        
        # Normalize and clamp
        volume = min(1.0, rms / sensitivity)
        return volume
        
    except Exception as e:
        logging.error(f"[Audio Utils] Error calculating RMS: {e}")
        return 0.0


def get_flaresolverr_cookies(url: str, flaresolverr_url: str = "http://localhost:8191/v1") -> Tuple[list, Optional[str]]:

    try:
        logging.info(f"[FlareSolverr] Requesting solution for {url}...")
        response = requests.post(flaresolverr_url, json={
            "cmd": "request.get",
            "url": url,
            "maxTimeout": 60000
        }, timeout=65)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "ok":
                solution = data.get("solution", {})
                user_agent = solution.get("userAgent")
                cookies = solution.get("cookies", [])
                logging.info(f"[FlareSolverr] ✓ Got {len(cookies)} cookies")
                return cookies, user_agent
            else:
                logging.error(f"[FlareSolverr] Failed: {data.get('message')}")
        else:
            logging.error(f"[FlareSolverr] HTTP error: {response.status_code}")
            
    except Exception as e:
        logging.error(f"[FlareSolverr] Error: {e}")
        
    return [], None
