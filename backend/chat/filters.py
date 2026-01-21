import time
import re
from typing import Dict, List, Tuple
from collections import defaultdict
from .models import AggregationConfig

class ChatFilter:
    """Handles message filtering (spam, rate limits, duplicates)"""
    
    def __init__(self, config: AggregationConfig):
        self.config = config
        self.user_message_counts: Dict[str, List[float]] = defaultdict(list)  
        self.processed_messages: List[Tuple[str, float]] = []  
        self.duplicate_expiry_seconds: float = 60.0

    def should_filter(self, message_text: str, user_id: str, username: str) -> bool:
        """
        Check if a message should be filtered out.
        Returns True if message should be filtered (discarded).
        """
        # Filter by message length
        if len(message_text.strip()) < self.config.min_message_length:
            print(f"[ChatFilter] Filtered: too short - '{message_text}'")
            return True
        
        # Filter emote-only messages
        if self._is_emote_only(message_text):
            print(f"[ChatFilter] Filtered: emote-only - '{message_text}'")
            return True
        
        # Check user rate limit
        if not self._check_user_rate_limit(user_id):
            print(f"[ChatFilter] Filtered: rate limit - user {username}")
            return True
        
        # Check for duplicates
        if self._is_duplicate(message_text):
            print(f"[ChatFilter] Filtered: duplicate - '{message_text}'")
            return True
            
        return False

    def record_message(self, message_text: str):
        """Record that a message was accepted (processed)"""
        msg_hash = self._hash_message(message_text)
        current_time = time.time()
        self.processed_messages.append((msg_hash, current_time))
        
        # Keep only last 100 messages (memory optimization)
        if len(self.processed_messages) > 100:
            self.processed_messages = self.processed_messages[-100:]

    def _is_emote_only(self, message: str) -> bool:
        """Check if message is emote-only (simple heuristic)"""
        # Remove common emote patterns
        text = re.sub(r':\w+:', '', message)  # :emoji:
        text = re.sub(r'[^\w\s]', '', text)  # Remove special chars
        text = text.strip()
        
        # If nothing left, it's emote-only
        return len(text) < 2

    def _check_user_rate_limit(self, user_id: str) -> bool:
        """Check if user has exceeded rate limit"""
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
        """Create a simple hash of message for duplicate detection"""
        # Normalize: lowercase, remove extra spaces
        normalized = ' '.join(message.lower().split())
        return normalized

    def _is_duplicate(self, message: str) -> bool:
        """Check if message is a duplicate or very similar to recent messages"""
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
