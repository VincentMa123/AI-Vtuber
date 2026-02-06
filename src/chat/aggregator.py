import asyncio
import time
import logging
from typing import List, Dict, Optional, Tuple
from .models import ChatMessage, AggregationConfig
from .scoring import ChatScorer
from .filters import ChatFilter
from chat.emotions import detect_emotion
from collections import Counter

class ChatAggregator:
    def __init__(self, config: AggregationConfig = None):
        self.config = config or AggregationConfig()
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.last_response_time: float = 0
        
        # Helper components
        self.scorer = ChatScorer()
        self.filter = ChatFilter(self.config)
        
        self._processing_task: Optional[asyncio.Task] = None
        self._is_running: bool = False
        self.response_callback = None
        
    @property
    def duplicate_expiry_seconds(self):
        return self.filter.duplicate_expiry_seconds
    
    @duplicate_expiry_seconds.setter
    def duplicate_expiry_seconds(self, value):
        self.filter.duplicate_expiry_seconds = value
        
    async def start(self):

        if self._is_running:
            return
        
        self._is_running = True
        self._processing_task = asyncio.create_task(self._process_queue())
        logging.info("[ChatAggregator] Service started")
    
    async def stop(self):

        self._is_running = False
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass
        logging.info("[ChatAggregator] Service stopped")
    
    async def submit_message(self, message: ChatMessage) -> bool:

        if not self.config.enabled:
            return True 
        
        if self.filter.should_filter(message.message, message.user_id, message.username):
            return False

        message.priority_score = self.scorer.calculate_priority(message)
        
        self.filter.record_message(message.message)
        
        await self.message_queue.put(message)
        logging.info(f"[ChatAggregator] Queued message from {message.username} (priority: {message.priority_score:.2f})")
        
        return True
    
    async def _process_queue(self):

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
                        logging.info(f"[ChatAggregator] Rate limiting: waiting {wait_time:.1f}s before next response")
                        await asyncio.sleep(wait_time)

                    await self._process_batch(batch)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"[ChatAggregator] Error in processing loop: {e}", exc_info=True)
    
    async def _process_batch(self, batch: List[ChatMessage]):

        batch.sort(key=lambda m: m.priority_score, reverse=True)
        
        logging.info(f"[ChatAggregator] Processing batch of {len(batch)} messages:")
        for msg in batch:
            logging.debug(f"  - {msg.username}: {msg.message[:50]}... (priority: {msg.priority_score:.2f})")
        
        self.last_response_time = time.time()
        
        self.scorer.update_recent_topics(batch)
        
        try:
            formatted_message = self.get_batch_for_llm(batch)
            
            # Determine dominant emotion from the batch
            emotions = []
            for msg in batch:
                # Remove [TEST] prefix to detect emotion (only for testing)
                clean_msg = msg.message.replace("[TEST] ", "") 
                emotions.append(detect_emotion(clean_msg))

            if emotions:
                dominant_emotion = Counter(emotions).most_common(1)[0][0]
                           
            logging.info(f"[ChatAggregator] Generating AI response for: {formatted_message[:100]}... (Emotion: {dominant_emotion})")
            
            start_time = time.time()
            if self.response_callback:
                if asyncio.iscoroutinefunction(self.response_callback):
                    try:
                        # Try passing emotion if supported
                        await self.response_callback(formatted_message, dominant_emotion)
                    except TypeError:
                        # Fallback for callbacks that don't accept emotion yet
                        await self.response_callback(formatted_message)
                else:
                    self.response_callback(formatted_message)
                end_time = time.time()
                logging.info(f"[ChatAggregator] Response processing took {end_time - start_time:.2f}s")
            else:
                logging.warning("[ChatAggregator] Warning: No response callback set. AI response not generated.")
                
        except Exception as e:
            logging.error(f"[ChatAggregator] Error generating response: {e}", exc_info=True)

    def get_batch_for_llm(self, batch: List[ChatMessage]) -> str:

        top_messages = batch[:5] 
        
        if len(top_messages) == 1:
            msg = top_messages[0]
            formatted = msg.message
        else:
            formatted_parts = ["Multiple chat messages:"]
            for i, msg in enumerate(top_messages, 1):
                formatted_parts.append(f"{i}. {msg.username}: {msg.message}")
            formatted = "\n".join(formatted_parts)
        
        return formatted    
    def get_status(self) -> Dict:

        return {
            "enabled": self.config.enabled,
            "queue_size": self.message_queue.qsize(),
            "time_since_last_response": time.time() - self.last_response_time,
            "recent_topics_count": len(self.scorer.recent_topics),
            "window_seconds": self.config.window_seconds,
            "min_response_interval": self.config.min_response_interval
        }
    
    def reset(self):

        self.filter.reset()
        self.scorer.reset()
        self.last_response_time = 0
    
    def update_config(self, **kwargs):

        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                logging.info(f"[ChatAggregator] Config updated: {key} = {value}")
