import re
import datetime
import os

def load_prompt_file(filename):
    """Load content from a markdown file in the backend/prompts directory."""
    try:
        # Get absolute path relative to this file
        base_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(base_dir, "prompts", filename)
        
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"Error loading prompt file {filename}: {e}")
        return ""

def get_system_prompt(user_message: str = ""):
    """
    Get the combined system prompt for the VTuber using a layered approach.
    Layers:
    1. Identity (Soul): Loaded from soul.md
    2. Rules (Session): Loaded from rules.md
    3. Product Context (Dynamic): Relevant products if query detected
    4. Context (Dynamic): Real-time awareness.
    
    Args:
        user_message: The current user message to check for product queries
    """
    
    # --- Layer 1: Identity (Soul) ---
    identity = load_prompt_file("soul.md")
    if not identity:
        identity = "You are Lumina, an AI VTuber."

    # --- Layer 2: Rules (Session) ---
    rules = load_prompt_file("rules.md")

    # --- Layer 3: Product Context (Dynamic) ---
    product_context = ""
    if user_message:
        try:
            import sys
            import os
            # Add backend directory to path if not already there
            backend_dir = os.path.dirname(os.path.abspath(__file__))
            if backend_dir not in sys.path:
                sys.path.insert(0, backend_dir)
            
            # Use RAG-based semantic search
            import product_search
            
            # Check if asking about promotions specifically
            if product_search.detect_promotion_query(user_message):
                promotions = product_search.get_all_promotions()
                if promotions:
                    product_context = product_search.format_promotions_for_prompt(promotions)
                    print(f"[System Prompt] Injected {len(promotions)} promotions into context")
            # Otherwise check for product queries
            elif product_search.detect_product_query(user_message):
                # Search for relevant products using semantic similarity
                products = product_search.search_products_rag(user_message, top_k=3)
                if products:
                    product_context = product_search.format_products_for_prompt(products)
                    print(f"[System Prompt] Injected {len(products)} products into context")
        except Exception as e:
            print(f"[System Prompt] Error loading product context: {e}")
            import traceback
            traceback.print_exc()

    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # --- Layer 4: Context (Dynamic) ---
    context = f"""
    Current Context:
    - Time: {current_time}
    - Environment: You are currently live streaming.
    - System Status: All systems nominal.
    """

    full_prompt = f"{identity}\n\n{rules}\n\n{product_context}\n\n{context}"
    return full_prompt

def clean_text_for_tts(text):
    clean = re.sub(r'<component_call>.*?</component_call>', '', text, flags=re.DOTALL)
    # Remove markdown code blocks for TTS clarity
    clean = re.sub(r'```.*?```', ' [Code Block] ', clean, flags=re.DOTALL)
    clean = clean.strip()
    return str(clean)

def extract_component_call(text):
    match = re.search(r'<component_call>(.*?)</component_call>', text, re.DOTALL)
    if match:
        return match.group(1)
    return None
