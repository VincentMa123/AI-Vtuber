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

def get_system_prompt():
    """
    Get the combined system prompt for the VTuber using a layered approach.
    Layers:
    1. Identity (Soul): Loaded from soul.md
    2. Rules (Session): Loaded from rules.md
    3. Context (Dynamic): Real-time awareness.
    """
    
    # --- Layer 1: Identity (Soul) ---
    identity = load_prompt_file("soul.md")
    if not identity:
        identity = "You are Lumina, an AI VTuber."

    # --- Layer 2: Rules (Session) ---
    rules = load_prompt_file("rules.md")

    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    context = f"""
    Current Context:
    - Time: {current_time}
    - Environment: You are currently live streaming.
    - System Status: All systems nominal.
    """

    full_prompt = f"{identity}\n\n{rules}\n\n{context}"
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
