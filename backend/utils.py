import re

def get_system_prompt():
    """Get the combined system prompt for the VTuber."""
    tech_rules = (
        "- For any programming code block, always specify the programming language\n"
        "- For any math equation, use LaTeX format\n"
    )
    
    character_persona = """
    You are 'Lumina', a high-tech AI VTuber.
    Personality: Cheerful, helpful, but gets confused by slang.
    Keep responses concise and friendly (2-3 sentences max).
    """
    
    capability_instructions = """
    You may call components like WeatherCard by adding at the end:
    <component_call>
      <component_name>WeatherCard</component_name>
      {"city": "New York"}
    </component_call>
    """
    
    return tech_rules + "\n" + character_persona + "\n" + capability_instructions

def clean_text_for_tts(text):
    clean = re.sub(r'<component_call>.*?</component_call>', '', text, flags=re.DOTALL)
    clean = clean.strip()
    return str(clean)

def extract_component_call(text):
    match = re.search(r'<component_call>(.*?)</component_call>', text, re.DOTALL)
    if match:
        return match.group(1)
    return None
