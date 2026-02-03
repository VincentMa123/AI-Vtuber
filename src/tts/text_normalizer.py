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

# Global instance
_normalizer = IndonesianTextNormalizer()

def normalize_indonesian_text(text: str) -> str:
    return _normalizer.normalize(text)
