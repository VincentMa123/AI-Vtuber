from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import time


# =============================================================================
# DATACLASS MODELS (for internal chat processing)
# =============================================================================

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
    max_batch_size: int = 10


# =============================================================================
# PYDANTIC MODELS (for API request/response validation)
# =============================================================================

class ChatRequest(BaseModel):
    """Request model for /chat endpoint"""
    message: str
    conversation_history: list = []
    image_base64: Optional[str] = None
    tts_enabled: bool = True
    use_aggregation: bool = False


class BatchChatRequest(BaseModel):
    """Request model for /batch-chat endpoint"""
    message: str
    user_id: str
    username: str = "Anonymous"
    image_base64: Optional[str] = None
    timestamp: Optional[float] = None


class ChatResponse(BaseModel):
    """Response model for /chat endpoint"""
    text: str
    audio_base64: str
    component_call: Optional[str] = None
    source: Optional[str] = None


class SetProviderRequest(BaseModel):
    """Request model for /llm-provider endpoint"""
    provider: str


class AggregationConfigRequest(BaseModel):
    """Request model for /aggregation/config endpoint"""
    enabled: Optional[bool] = None
    window_seconds: Optional[float] = None
    min_response_interval: Optional[float] = None
    max_messages_per_user_per_window: Optional[int] = None  # Maximum messages to process in one batch
