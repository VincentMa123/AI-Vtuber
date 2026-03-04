import re
import os
import logging

class IndonesianTextNormalizer:
    
    def __init__(self):
        self._load_abbreviations()
        
        # Currency patterns (Rp 14.000 -> 14000 rupiah)
        self.currency_patterns = [
            (re.compile(r'Rp\.?\s*(\d+(?:[.,]\d+)*)', re.IGNORECASE), self._format_rupiah),
            (re.compile(r'\$\s*(\d+(?:[.,]\d+)*)', re.IGNORECASE), self._format_dollar),
        ]
        
        # Percentage pattern
        self.percentage_pattern = re.compile(r'(\d+(?:[.,]\d+)?)\s*%')
        
        # Unit patterns: number directly followed by unit (198g, 500ml, etc.)
        self.unit_patterns = [
            # Weight
            (re.compile(r'(\d+)\s*kg\b', re.IGNORECASE), r'\1 kilogram'),
            (re.compile(r'(\d+)\s*mg\b', re.IGNORECASE), r'\1 miligram'),
            (re.compile(r'(\d+)\s*g\b', re.IGNORECASE), r'\1 gram'),
            # Volume
            (re.compile(r'(\d+)\s*ml\b', re.IGNORECASE), r'\1 mililiter'),
            (re.compile(r'(\d+)\s*l\b', re.IGNORECASE), r'\1 liter'),
            # Length
            (re.compile(r'(\d+)\s*km\b', re.IGNORECASE), r'\1 kilometer'),
            (re.compile(r'(\d+)\s*cm\b', re.IGNORECASE), r'\1 sentimeter'),
            (re.compile(r'(\d+)\s*mm\b', re.IGNORECASE), r'\1 milimeter'),
            (re.compile(r'(\d+)\s*m\b', re.IGNORECASE), r'\1 meter'),
        ]
    
    def _load_abbreviations(self):
        self.abbreviations = {}
        data_file = os.path.join(os.path.dirname(__file__), "data", "abbreviations.txt")
        
        if not os.path.exists(data_file):
            logging.warning(f"[TextNormalizer] Abbreviations file not found: {data_file}")
            return
        
        try:
            with open(data_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    if '=' in line:
                        abbr, replacement = line.split('=', 1)
                        abbr = abbr.strip()
                        replacement = replacement.strip()
                        
                        # Skip unit abbreviations (handled by unit_patterns above)
                        if abbr in ['kg', 'g', 'mg', 'ml', 'l', 'km', 'm', 'cm', 'mm']:
                            continue
                        
                        # Create case-insensitive word boundary pattern
                        pattern = rf'\b{re.escape(abbr)}\b'
                        self.abbreviations[pattern] = replacement
                        
            logging.info(f"[TextNormalizer] Loaded {len(self.abbreviations)} abbreviations")
        except Exception as e:
            logging.error(f"[TextNormalizer] Error loading abbreviations: {e}")
    
    def _format_rupiah(self, match):
        amount_str = match.group(1)
        # Remove dots/commas used as thousand separators
        amount_str = amount_str.replace('.', '').replace(',', '')
        return f"{amount_str} rupiah"
    
    def _format_dollar(self, match):
        amount_str = match.group(1)
        amount_str = amount_str.replace('.', '').replace(',', '')
        return f"{amount_str} dollar"
    
    def normalize(self, text: str) -> str:
        if not text:
            return text
        
        original_text = text
        
        # 1. Handle currency (Rp, $) - must come first
        for pattern, formatter in self.currency_patterns:
            text = pattern.sub(formatter, text)
        
        # 2. Handle units (198g -> 198 gram) - order matters: longer units first
        for pattern, replacement in self.unit_patterns:
            text = pattern.sub(replacement, text)
        
        # 3. Handle percentages (50% -> 50 persen)
        text = self.percentage_pattern.sub(r'\1 persen', text)
        
        # 4. Handle other abbreviations (from file)
        for abbr_pattern, replacement in self.abbreviations.items():
            text = re.sub(abbr_pattern, replacement, text, flags=re.IGNORECASE)
        
        if text != original_text:
            logging.debug(f"[TextNormalizer] '{original_text}' -> '{text}'")
        
        return text
    
    def clean_for_tts(self, text: str) -> str:
        if not text:
            return text
        
        # Remove emojis and special Unicode characters
        # Keep: letters (any language), digits, basic punctuation, spaces
        cleaned = ""
        for char in text:
            # Keep alphanumeric (including Indonesian/international chars)
            if char.isalnum():
                cleaned += char
            # Keep basic punctuation and spaces
            elif char in ' .,!?;:\'"()-\n':
                cleaned += char
            # Skip everything else (emojis, symbols, etc.)
        
        # Clean up multiple spaces
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        # Remove standalone punctuation (like just "..." or "!!!")
        cleaned = re.sub(r'^[.,!?;:\'"()\-\s]+$', '', cleaned)
        
        return cleaned
    
    def normalize_for_tts(self, text: str, min_length: int = 3) -> str:
        if not text:
            return ""
        
        # First normalize (currency, units, abbreviations)
        normalized = self.normalize(text)
        
        # Then clean non-speakable characters
        cleaned = self.clean_for_tts(normalized)
        
        # Check minimum length (avoid tiny fragments that cause static)
        if len(cleaned.strip()) < min_length:
            logging.debug(f"[TextNormalizer] Skipping short fragment: '{cleaned}'")
            return ""
        
        return cleaned

# Global instance
_normalizer = IndonesianTextNormalizer()

def normalize_for_tts(text: str, min_length: int = 3) -> str:
    return _normalizer.normalize_for_tts(text, min_length)

async def buffer_sentences(text_stream):
    """
    Buffers text tokens from an async text stream, yielding normalized
    complete sentences as detected by is_sentence_boundary.
    Flushes any remaining text at stream end.
    """
    text_buffer = ""
    async for token in text_stream:
        if not token:
            continue
        text_buffer += token

        last_boundary_idx = -1
        for i in range(len(text_buffer)):
            if is_sentence_boundary(text_buffer, i):
                last_boundary_idx = i

        if last_boundary_idx >= 0:
            complete_text = text_buffer[:last_boundary_idx + 1]
            text_buffer = text_buffer[last_boundary_idx + 1:]
            normalized = normalize_for_tts(complete_text)
            if normalized:
                yield normalized

    if text_buffer:
        normalized = normalize_for_tts(text_buffer)
        if normalized:
            yield normalized


def is_sentence_boundary(text: str, idx: int) -> bool:
    char = text[idx]
    
    if char == '\n':
        return True
    
    # ! and ? are always sentence endings
    if char in {'!', '?'}:
        return True
    
    # For period, check if it's between digits (number separator)
    if char == '.':
        # Check character before: if digit, might be number
        if idx > 0 and text[idx - 1].isdigit():
            # If at end of buffer AND preceded by digit, DON'T break
            # (might be incomplete like "14." waiting for "000")
            if idx + 1 >= len(text):
                return False  # Wait for more text
            # Check character after: if digit, it's a number separator
            if text[idx + 1].isdigit():
                return False  # "16.000" - not a sentence boundary
        
        # Period followed by space or uppercase = sentence end
        if idx + 1 >= len(text):  
            return True  # End of stream
        next_char = text[idx + 1]
        if next_char == ' ' or next_char.isupper():
            return True

        return False 
    
    return False
