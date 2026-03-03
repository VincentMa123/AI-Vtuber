from dataclasses import dataclass, field
from typing import Optional, Set
from pydantic import BaseModel
import time

@dataclass
class ChatMessage:

    message: str
    user_id: str
    username: str
    timestamp: float = field(default_factory=time.time)
    image_base64: Optional[str] = None
    priority_score: float = 0.0
    platform: str = "twitch"  # "twitch", "youtube", etc. Defaults to twitch for backward compatibility

@dataclass
class AggregationConfig:

    enabled: bool = True
    window_seconds: float = 5.0
    min_response_interval: float = 5.0
    max_messages_per_user_per_window: int = 3
    min_message_length: int = 2
    similarity_threshold: float = 0.8
    max_batch_size: int = 10

class BatchChatRequest(BaseModel):

    message: str
    user_id: str
    username: str = "Anonymous"
    image_base64: Optional[str] = None
    timestamp: Optional[float] = None


class AggregationConfigRequest(BaseModel):

    enabled: Optional[bool] = None
    window_seconds: Optional[float] = None
    min_response_interval: Optional[float] = None
    max_messages_per_user_per_window: Optional[int] = None  # Maximum messages to process in one batch


@dataclass(frozen=True)
class ScoringConfig:
    question_score: float = 3.0
    name_score: float = 2.0
    novelty_max: int = 2
    long_message_score: float = 1.0
    image_score: float = 2.0
    recency_score: float = 0.5
    min_words_for_length_bonus: int = 5
    max_topics: int = 3
    recent_topic_limit: int = 20
    keywords: Set[str] = frozenset({"lumina", "indomaret"})
    stopwords: Set[str] = frozenset(
        {"that", "this", "with", "have", "from", "they", "been", "were", "what", "when"}
    )
    
