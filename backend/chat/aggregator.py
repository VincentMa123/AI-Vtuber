"""
Chat Aggregation Service for AI VTuber
Handles message batching, priority scoring, and spam filtering
"""

import asyncio
import time
from typing import List, Dict, Optional, Tuple
from .models import ChatMessage, AggregationConfig
from .scoring import ChatScorer
from .filters import ChatFilter

class ChatAggregator:
    """
    Aggregates and prioritizes chat messages for AI processing
    Delegates logic to ChatFilter and ChatScorer
    """
    
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
        """Submit a message to the aggregation queue"""
        # Check if aggregation is enabled
        if not self.config.enabled:
            return True  # Pass through without aggregation
        
        # Apply filters (spam, rate limit, duplicates)
        if self.filter.should_filter(message.message, message.user_id, message.username):
            return False
            
        # Calculate priority score
        message.priority_score = self.scorer.calculate_priority(message)
        
        # Record successful message (for duplicate checking)
        self.filter.record_message(message.message)
        
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
        """Process a batch of messages and generate AI response"""
        # Sort by priority (highest first)
        batch.sort(key=lambda m: m.priority_score, reverse=True)
        
        print(f"\n[ChatAggregator] Processing batch of {len(batch)} messages:")
        for msg in batch:
            print(f"  - {msg.username}: {msg.message[:50]}... (priority: {msg.priority_score:.2f})")
        
        # Update last response time
        self.last_response_time = time.time()
        
        # Update scorer topics
        self.scorer.update_recent_topics(batch)
        
        # Generate AI response
        try:
            formatted_message, top_messages = self.get_batch_for_llm(batch)
            
            print(f"[ChatAggregator] Generating AI response for: {formatted_message[:100]}...")
            
            # Call the response callback if set
            if self.response_callback:
                await self.response_callback(formatted_message, top_messages)
            else:
                print("[ChatAggregator] Warning: No response callback set. AI response not generated.")
                
        except Exception as e:
            print(f"[ChatAggregator] Error generating response: {e}")
            import traceback
            traceback.print_exc()

    def get_batch_for_llm(self, batch: List[ChatMessage]) -> Tuple[str, List[ChatMessage]]:
        """Format a batch of messages for LLM processing"""
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
    
    def get_status(self) -> Dict:
        """Get current aggregator status"""
        return {
            "enabled": self.config.enabled,
            "queue_size": self.message_queue.qsize(),
            "time_since_last_response": time.time() - self.last_response_time,
            "recent_topics_count": len(self.scorer.recent_topics),
            "window_seconds": self.config.window_seconds,
            "min_response_interval": self.config.min_response_interval
        }
    
    def reset(self):
        """Reset all state"""
        self.filter.reset()
        self.scorer.reset()
        self.last_response_time = 0
    
    def update_config(self, **kwargs):
        """Update configuration dynamically"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                print(f"[ChatAggregator] Config updated: {key} = {value}")
