"""
Chat Aggregation Service for AI VTuber
Handles message batching, priority scoring, and spam filtering
Similar to how Neuro-sama processes high-volume chat
"""

import asyncio
import time
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import re


@dataclass
class ChatMessage:
    """Represents a single chat message with metadata"""
    message: str
    user_id: str
    username: str
    timestamp: float
    image_base64: Optional[str] = None
    priority_score: float = 0.0
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()


@dataclass
class AggregationConfig:
    """Configuration for chat aggregation behavior"""
    enabled: bool = True
    window_seconds: float = 5.0
    min_response_interval: float = 5.0
    max_messages_per_user_per_window: int = 3
    min_message_length: int = 2
    similarity_threshold: float = 0.8
    max_batch_size: int = 10  # Maximum messages to process in one batch


class ChatAggregator:
    """
    Aggregates and prioritizes chat messages for AI processing
    
    Features:
    - Time-windowed message batching
    - Priority scoring (questions, mentions, novelty)
    - Spam and duplicate filtering
    - Response rate limiting
    """
    
    def __init__(self, config: AggregationConfig = None):
        self.config = config or AggregationConfig()
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.last_response_time: float = 0
        self.recent_topics: List[str] = []  # Track recent topics for novelty detection
        self.user_message_counts: Dict[str, List[float]] = defaultdict(list)  # user_id -> timestamps
        self.processed_messages: List[Tuple[str, float]] = []  # (message_hash, timestamp) for time-based expiration
        self._processing_task: Optional[asyncio.Task] = None
        self._is_running: bool = False
        self.duplicate_expiry_seconds: float = 60.0  # Messages older than this are no longer considered duplicates
        self.response_callback = None  # Callback function to generate AI responses
        
    async def start(self):
        """Start the aggregation service"""
        if self._is_running:
            return
        
        self._is_running = True
        self._processing_task = asyncio.create_task(self._process_queue())
        print("[ChatAggregator] Service started")
    
    async def stop(self):
        """Stop the aggregation service"""
        self._is_running = False
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass
        print("[ChatAggregator] Service stopped")
    
    async def submit_message(self, message: ChatMessage) -> bool:
        """
        Submit a message to the aggregation queue
        
        Returns:
            bool: True if message was accepted, False if filtered/rejected
        """
        # Check if aggregation is enabled
        if not self.config.enabled:
            return True  # Pass through without aggregation
        
        # Filter by message length
        if len(message.message.strip()) < self.config.min_message_length:
            print(f"[ChatAggregator] Filtered: too short - '{message.message}'")
            return False
        
        # Filter emote-only messages (simple heuristic)
        if self._is_emote_only(message.message):
            print(f"[ChatAggregator] Filtered: emote-only - '{message.message}'")
            return False
        
        # Check user rate limit
        if not self._check_user_rate_limit(message.user_id):
            print(f"[ChatAggregator] Filtered: rate limit - user {message.username}")
            return False
        
        # Check for duplicates
        if self._is_duplicate(message.message):
            print(f"[ChatAggregator] Filtered: duplicate - '{message.message}'")
            return False
        
        # Calculate priority score
        message.priority_score = self._calculate_priority(message)
        
        # Add to processed messages list with timestamp for future duplicate detection
        msg_hash = self._hash_message(message.message)
        current_time = time.time()
        self.processed_messages.append((msg_hash, current_time))
        
        # Keep only last 100 messages (memory optimization)
        if len(self.processed_messages) > 100:
            self.processed_messages = self.processed_messages[-100:]
        
        # Add to queue
        await self.message_queue.put(message)
        print(f"[ChatAggregator] Queued message from {message.username} (priority: {message.priority_score:.2f})")
        
        return True
    
    async def _process_queue(self):
        """Background task that processes message batches"""
        while self._is_running:
            try:
                await asyncio.sleep(self.config.window_seconds)

                batch = []
                while not self.message_queue.empty() and len(batch) < self.config.max_batch_size:
                    try:
                        msg = self.message_queue.get_nowait()
                        batch.append(msg)
                    except asyncio.QueueEmpty:
                        break
                
                if batch:
                    time_since_last = time.time() - self.last_response_time
                    if time_since_last < self.config.min_response_interval:
                        wait_time = self.config.min_response_interval - time_since_last
                        print(f"[ChatAggregator] Rate limiting: waiting {wait_time:.1f}s before next response")
                        await asyncio.sleep(wait_time)
                    
                    # Process the batch
                    await self._process_batch(batch)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[ChatAggregator] Error in processing loop: {e}")
                import traceback
                traceback.print_exc()
    
    async def _process_batch(self, batch: List[ChatMessage]):
        """
        Process a batch of messages and generate AI response
        """
        # Sort by priority (highest first)
        batch.sort(key=lambda m: m.priority_score, reverse=True)
        
        print(f"\n[ChatAggregator] Processing batch of {len(batch)} messages:")
        for msg in batch:
            print(f"  - {msg.username}: {msg.message[:50]}... (priority: {msg.priority_score:.2f})")
        
        # Update last response time
        self.last_response_time = time.time()
        
        # Extract topics for novelty tracking
        for msg in batch:
            topics = self._extract_topics(msg.message)
            self.recent_topics.extend(topics)
            # Keep only last 20 topics
            if len(self.recent_topics) > 20:
                self.recent_topics = self.recent_topics[-20:]
        
        # Generate AI response
        try:
            # Format messages for LLM
            formatted_message, top_messages = self.get_batch_for_llm(batch)
            
            print(f"[ChatAggregator] Generating AI response for: {formatted_message[:100]}...")
            
            # Call the response callback if set (will be set by api_server)
            if hasattr(self, 'response_callback') and self.response_callback:
                await self.response_callback(formatted_message, top_messages)
            else:
                print("[ChatAggregator] Warning: No response callback set. AI response not generated.")
                
        except Exception as e:
            print(f"[ChatAggregator] Error generating response: {e}")
            import traceback
            traceback.print_exc()

    
    def get_batch_for_llm(self, batch: List[ChatMessage]) -> Tuple[str, List[ChatMessage]]:
        """
        Format a batch of messages for LLM processing
        
        Returns:
            Tuple of (formatted_message_string, prioritized_messages)
        """
        top_messages = batch[:5] 
        
        if len(top_messages) == 1:
            msg = top_messages[0]
            formatted = msg.message
        else:
            formatted_parts = ["Multiple chat messages:"]
            for i, msg in enumerate(top_messages, 1):
                formatted_parts.append(f"{i}. {msg.username}: {msg.message}")
            formatted = "\n".join(formatted_parts)
        
        return formatted, top_messages
    
    def _calculate_priority(self, message: ChatMessage) -> float:
        """
        Calculate priority score for a message
        
        Scoring factors:
        - Questions: +3
        - Name mentions (Lumina/Indomaret): +2
        - Novelty (new topics): +1-2
        - Length (5+ words): +1
        - Image attachment: +2
        - Recency: +0.5
        """
        score = 0.0
        text = message.message.lower()
        
        # Question detection
        question_patterns = [
            r'\?',
            r'\b(how|what|why|when|where|who|can you|could you|would you|do you)\b'
        ]
        for pattern in question_patterns:
            if re.search(pattern, text):
                score += 3.0
                break
        
        # Name mentions
        if 'lumina' in text:
            score += 2.0
        if 'indomaret' in text:
            score += 2.0
        
        topics = self._extract_topics(message.message)
        new_topics = [t for t in topics if t not in self.recent_topics]
        if new_topics:
            score += min(len(new_topics), 2)
        
        word_count = len(message.message.split())
        if word_count >= 5:
            score += 1.0
        
        if message.image_base64:
            score += 2.0
        
        score += 0.5
        
        return score
    
    def _extract_topics(self, message: str) -> List[str]:
        """Extract key topics/words from a message"""
        # Simple topic extraction - get words longer than 4 characters
        words = re.findall(r'\b\w{4,}\b', message.lower())
        # Filter out common words
        stopwords = {'that', 'this', 'with', 'have', 'from', 'they', 'been', 'were', 'what', 'when'}
        topics = [w for w in words if w not in stopwords]
        return topics[:3]  # Return top 3 topics
    
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
        for recent_hash, _ in self.processed_messages[-10:]: 
            recent_words = set(recent_hash.split())
            if not msg_words or not recent_words:
                continue
            
            intersection = len(msg_words & recent_words)
            union = len(msg_words | recent_words)
            similarity = intersection / union if union > 0 else 0
            
            if similarity >= self.config.similarity_threshold:
                return True
        
        return False
    
    def get_status(self) -> Dict:
        """Get current aggregator status"""
        return {
            "enabled": self.config.enabled,
            "queue_size": self.message_queue.qsize(),
            "time_since_last_response": time.time() - self.last_response_time,
            "recent_topics_count": len(self.recent_topics),
            "window_seconds": self.config.window_seconds,
            "min_response_interval": self.config.min_response_interval
        }
    
    def reset(self):
        self.processed_messages.clear()
        self.recent_topics.clear()
        self.user_message_counts.clear()
        self.last_response_time = 0
    
    def update_config(self, **kwargs):
        """Update configuration dynamically"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                print(f"[ChatAggregator] Config updated: {key} = {value}")
