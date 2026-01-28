import re
import datetime
import os
import sys
import logging
from rag import (
    detect_product_query,
    detect_promotion_query,
    search_products_rag,
    get_all_promotions,
    format_products_for_prompt,
    format_promotions_for_prompt
)

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
