import time
import re
from typing import Dict, List, Tuple
from collections import defaultdict
from .models import AggregationConfig
import logging

# Off-topic patterns: personal questions, greetings, random chatter, spam
OFF_TOPIC_PATTERNS = [
    # Greetings / filler (Indonesian + English)
    r'^(h[ae]llo|hi+|hey+|halo+|hai+|yo+|woi+|bang+|kak+|sis+|bro+|guys?)[!?.\s]*$',
    r'^(selamat\s+(pagi|siang|sore|malam)|good\s+(morning|afternoon|evening|night))[!?.\s]*$',
    r'^(assalamualaikum|waalaikumsalam|salam)[!?.\s]*$',
    # Personal questions about the VTuber
    r'\b(umur|usia|age)\s*(kamu|mu|lo|lu|nya|you)',
    r'\b(nama\s*(asli|real)|real\s*name)\b',
    r'\b(tinggal\s*di\s*mana|where.*live|domisili)\b',
    r'\b(nomor|nomer|no)\s*(hp|telp|telepon|wa|whatsapp|phone)\b',
    r'\b(ig|instagram|twitter|tiktok|sosmed|social\s*media)\s*(kamu|mu|lo|lu|nya|you)',
    r'\b(pacar|jomblo|single|taken|married|nikah|suami|istri|boyfriend|girlfriend)\b',
    r'\b(makan\s*apa|sarapan\s*apa|eat\s*what|breakfast|lunch|dinner)\b',
    r'\b(agama|religion)\s*(kamu|mu|apa)',
    r'\b(gaji|salary|penghasilan|income)\b',
    # Random chatter / spam
    r'^(wkwk|haha|lol|lmao|rofl|xixi|kwkw|awkwk|ngakak)+[!?.\s]*$',
    r'^(gg|ez|noob|bot|L|W|ratio|cap|sus|sheesh|bruh|oof)[!?.\s]*$',
    r'^(first|pertama|p$|f$|tes|test)[!?.\s]*$',
    # Requests unrelated to content
    r'\b(nyanyi|sing|dance|joget|goyang)\b',
    r'\b(main\s*game|gaming|play\s*game)\b',
    r'\b(follow|subscribe|sub)\s*(balik|back|dong|ya)\b',
]

# Compiled patterns for performance
_OFF_TOPIC_COMPILED = [re.compile(p, re.IGNORECASE) for p in OFF_TOPIC_PATTERNS]


class ChatFilter:
    def __init__(self, config: AggregationConfig):
        self.config = config
        self.user_message_counts: Dict[str, List[float]] = defaultdict(list)
        self.processed_messages: List[Tuple[str, float]] = []
        self.duplicate_expiry_seconds: float = 60.0

    def should_filter(self, message_text: str, user_id: str, username: str) -> bool:

        # Filter by message length
        if len(message_text.strip()) < self.config.min_message_length:
            logging.info(f"[ChatFilter] Filtered: too short - '{message_text}'")
            return True

        # Filter emote-only messages
        if self._is_emote_only(message_text):
            logging.info(f"[ChatFilter] Filtered: emote-only - '{message_text}'")
            return True

        # Filter off-topic / unrelated messages
        if self._is_off_topic(message_text):
            logging.info(f"[ChatFilter] Filtered: off-topic - '{message_text}'")
            return True

        # Check user rate limit
        if not self._check_user_rate_limit(user_id):
            logging.info(f"[ChatFilter] Filtered: rate limit - user {username}")
            return True

        # Check for duplicates
        if self._is_duplicate(message_text):
            logging.info(f"[ChatFilter] Filtered: duplicate - '{message_text}'")
            return True

        return False

    def record_message(self, message_text: str):
        msg_hash = self._hash_message(message_text)
        current_time = time.time()
        self.processed_messages.append((msg_hash, current_time))
        
        # Keep only last 100 messages (memory optimization)
        if len(self.processed_messages) > 100:
            self.processed_messages = self.processed_messages[-100:]

    def _is_off_topic(self, message: str) -> bool:

        text = message.strip()
        for pattern in _OFF_TOPIC_COMPILED:
            if pattern.search(text):
                return True
        return False

    def _is_emote_only(self, message: str) -> bool:

        # Remove common emote patterns
        text = re.sub(r':\w+:', '', message)  # :emoji:
        text = re.sub(r'[^\w\s]', '', text)  # Remove special chars
        text = text.strip()
        
        # If nothing left, it's emote-only
        return len(text) < 2

    def _check_user_rate_limit(self, user_id: str) -> bool:
 
        current_time = time.time()
        window_start = current_time - self.config.window_seconds
        
        # Clean old timestamps
        self.user_message_counts[user_id] = [
            ts for ts in self.user_message_counts[user_id]
            if ts > window_start
        ]
        
        # Check limit
        if len(self.user_message_counts[user_id]) >= self.config.max_messages_per_user_per_window:
            return False
        
        # Add current timestamp
        self.user_message_counts[user_id].append(current_time)
        return True

    def _hash_message(self, message: str) -> str:
 
        # Normalize: lowercase, remove extra spaces
        normalized = ' '.join(message.lower().split())
        return normalized

    def _is_duplicate(self, message: str) -> bool:
      
        current_time = time.time()
        msg_hash = self._hash_message(message)
        
        cutoff_time = current_time - self.duplicate_expiry_seconds
        self.processed_messages = [
            (hash_val, timestamp) for hash_val, timestamp in self.processed_messages
            if timestamp > cutoff_time
        ]
        
        if any(hash_val == msg_hash for hash_val, _ in self.processed_messages):
            return True
        
        msg_words = set(msg_hash.split())
        if not msg_words: return False

        for recent_hash, _ in self.processed_messages[-10:]: 
            recent_words = set(recent_hash.split())
            if not recent_words:
                continue
            
            intersection = len(msg_words & recent_words)
            union = len(msg_words | recent_words)
            similarity = intersection / union if union > 0 else 0
            
            if similarity >= self.config.similarity_threshold:
                return True
        
        return False
        
    def reset(self):
        self.processed_messages.clear()
        self.user_message_counts.clear()
