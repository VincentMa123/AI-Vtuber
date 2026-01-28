"""
Unit tests for chat models module
"""

import pytest
import time
from datetime import datetime
from chat.models import (
    ChatMessage,
    AggregationConfig,
    BatchChatRequest,
)


class TestChatMessage:
    """Test ChatMessage dataclass"""
    
    def test_create_basic_message(self):
        """Should create a basic chat message"""
        msg = ChatMessage(
            message="Hello",
            user_id="user1",
            username="Alice",
            timestamp=123456.0
        )
        assert msg.message == "Hello"
        assert msg.user_id == "user1"
        assert msg.username == "Alice"
        assert msg.timestamp == 123456.0
    
    def test_default_priority_score(self):
        """Priority score should default to 0.0"""
        msg = ChatMessage(
            message="Test",
            user_id="user1",
            username="Bob",
            timestamp=123456.0
        )
        assert msg.priority_score == 0.0
    
    def test_optional_image_base64(self):
        """image_base64 should be optional"""
        msg = ChatMessage(
            message="Test",
            user_id="user1",
            username="Bob",
            timestamp=123456.0,
            image_base64="abc123"
        )
        assert msg.image_base64 == "abc123"
    
    def test_auto_timestamp_if_none(self):
        """Should auto-set timestamp if None"""
        before = time.time()
        msg = ChatMessage(
            message="Test",
            user_id="user1",
            username="Bob",
            timestamp=None
        )
        after = time.time()
        
        assert before <= msg.timestamp <= after
    
    def test_priority_score_assignment(self):
        """Should allow priority score assignment"""
        msg = ChatMessage(
            message="Test",
            user_id="user1",
            username="Bob",
            timestamp=123456.0,
            priority_score=5.5
        )
        assert msg.priority_score == 5.5


class TestAggregationConfig:
    """Test AggregationConfig dataclass"""
    
    def test_default_config(self):
        """Should create config with defaults"""
        config = AggregationConfig()
        assert config.enabled == True
        assert config.window_seconds == 5.0
        assert config.min_response_interval == 5.0
        assert config.max_messages_per_user_per_window == 3
        assert config.min_message_length == 2
        assert config.similarity_threshold == 0.8
        assert config.max_batch_size == 10
    
    def test_custom_config(self):
        """Should allow custom config values"""
        config = AggregationConfig(
            enabled=False,
            window_seconds=3.0,
            max_messages_per_user_per_window=5,
            similarity_threshold=0.7
        )
        assert config.enabled == False
        assert config.window_seconds == 3.0
        assert config.max_messages_per_user_per_window == 5
        assert config.similarity_threshold == 0.7
    
    def test_individual_field_modification(self):
        """Should allow modification of individual fields"""
        config = AggregationConfig()
        config.window_seconds = 10.0
        config.enabled = False
        
        assert config.window_seconds == 10.0
        assert config.enabled == False

class TestBatchChatRequest:
    """Test BatchChatRequest Pydantic model"""
    
    def test_required_fields(self):
        """message and user_id are required"""
        with pytest.raises(Exception):
            BatchChatRequest()
        
        with pytest.raises(Exception):
            BatchChatRequest(message="Hello")
    
    def test_minimal_request(self):
        """Should create with required fields"""
        req = BatchChatRequest(
            message="Hello",
            user_id="user1"
        )
        assert req.message == "Hello"
        assert req.user_id == "user1"
        assert req.username == "Anonymous"
        assert req.image_base64 is None
        assert req.timestamp is None
    
    def test_full_request(self):
        """Should create with all fields"""
        req = BatchChatRequest(
            message="Hello",
            user_id="user1",
            username="Alice",
            image_base64="img123",
            timestamp=123456.0
        )
        assert req.message == "Hello"
        assert req.user_id == "user1"
        assert req.username == "Alice"
        assert req.image_base64 == "img123"
        assert req.timestamp == 123456.0

class TestModelIntegration:
    """Test interactions between models"""
    
    def test_chat_message_to_batch_request(self):
        """Should convert ChatMessage to BatchChatRequest"""
        msg = ChatMessage(
            message="Test",
            user_id="user1",
            username="Alice",
            timestamp=123456.0
        )
        req = BatchChatRequest(
            message=msg.message,
            user_id=msg.user_id,
            username=msg.username,
            timestamp=msg.timestamp
        )
        assert req.message == msg.message
        assert req.user_id == msg.user_id
        assert req.username == msg.username
    
