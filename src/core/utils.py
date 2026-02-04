import re
import datetime
import os
import sys
import logging
import base64
import io
from typing import Optional, Tuple
from PIL import Image
from rag import (
    detect_product_query,
    detect_promotion_query,
    search_products_rag,
    get_all_promotions,
    format_products_for_prompt,
    format_promotions_for_prompt
)

VLM_TARGET_SIZE = (1280, 720)
SIMILARITY_THRESHOLD = 0.2

_last_image_hash: Optional[int] = None
_last_image_bytes: Optional[bytes] = None


def load_prompt_file(filename):

    try:
        # Get absolute path relative to this file
        # Get absolute path relative to this file (one level up from core)
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        file_path = os.path.join(base_dir, "prompts", filename)
        
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logging.error(f"Error loading prompt file {filename}: {e}")
        return ""

def get_system_prompt(user_message: str = ""):
    
    identity = load_prompt_file("soul.md")
    rules = load_prompt_file("rules.md")

    product_context = ""
    if user_message:
        try:
            backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if backend_dir not in sys.path:
                sys.path.insert(0, backend_dir)

            
            if detect_promotion_query(user_message):
                promotions = get_all_promotions()

                if promotions:
                    product_context = format_promotions_for_prompt(promotions)
                    logging.info(f"[System Prompt] Injected {len(promotions)} promotions into context")
            
            elif detect_product_query(user_message):
                products = search_products_rag(user_message, top_k=3)
                
                if products:
                    product_context = format_products_for_prompt(products)
                    logging.info(f"[System Prompt] Injected {len(products)} products into context")
        except Exception as e:
            logging.error(f"[System Prompt] Error loading product context: {e}", exc_info=True)

    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    context = f"""
    Current Context:
    - Time: {current_time}
    - Environment: You are currently live streaming.
    - System Status: All systems nominal.
    """

    full_prompt = f"{identity}\n\n{rules}\n\n{product_context}\n\n{context}"
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
        
        difference = bin(current_hash ^ _last_image_hash).count('1') / 64
        
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
        image = image.resize((8, 8), Image.Resampling.LANCZOS).convert('L')
        
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


def reset_similarity_state():

    global _last_image_hash, _last_image_bytes
    _last_image_hash = None
    _last_image_bytes = None

