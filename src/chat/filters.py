import time
import re
from pathlib import Path
from typing import Dict, List, Tuple
from collections import defaultdict
from .models import AggregationConfig
import logging


def _load_off_topic_patterns() -> list[re.Pattern]:
    """Load off-topic regex patterns from chat/data/off_topic_patterns.md."""
    patterns_file = Path(__file__).parent / "data" / "off_topic_patterns.md"
    patterns = []
    for line in patterns_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(re.compile(line, re.IGNORECASE))
    return patterns


_OFF_TOPIC_COMPILED = _load_off_topic_patterns()


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

        # Filter gibberish / keyboard mashing
        if self._is_gibberish(message_text):
            logging.info(f"[ChatFilter] Filtered: gibberish - '{message_text}'")
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

    def _is_gibberish(self, message: str) -> bool:

        # Strip to just letters
        letters = re.sub(r'[^a-zA-Z]', '', message)
        if len(letters) < 4:
            return False  # Too short to judge

        # Check vowel ratio — real words (Indonesian/English) have ~35-50% vowels
        vowels = sum(1 for c in letters.lower() if c in 'aiueo')
        vowel_ratio = vowels / len(letters)
        if vowel_ratio < 0.15:
            return True

        # Check for long consonant clusters (3+ consonants in a row)
        clusters = re.findall(r'[^aiueoAIUEO\s]{4,}', letters)
        cluster_chars = sum(len(c) for c in clusters)
        if cluster_chars / len(letters) > 0.6:
            return True

        # Check character variety — keyboard mashing often repeats few chars
        unique_ratio = len(set(letters.lower())) / len(letters)
        if len(letters) >= 6 and unique_ratio < 0.3:
            return True

        # Check dominant character — real words rarely have one letter at 40%+
        if len(letters) >= 5:
            from collections import Counter
            freq = Counter(letters.lower())
            max_freq = max(freq.values())
            if max_freq / len(letters) > 0.4:
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
