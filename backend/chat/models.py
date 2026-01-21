from dataclasses import dataclass, field
from typing import Optional
import time

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
