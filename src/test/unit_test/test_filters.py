import pytest
import time
from chat.filters import ChatFilter
from chat.models import AggregationConfig


@pytest.fixture
def config():
    """Default test configuration"""
    return AggregationConfig(
        enabled=True,
        window_seconds=5.0,
        min_message_length=2,
        max_messages_per_user_per_window=3,
        similarity_threshold=0.7
    )


@pytest.fixture
def filter(config):
    """Create a ChatFilter instance"""
    return ChatFilter(config)


class TestEmoteOnlyFilter:
    
    def test_emote_only_message(self, filter):
        """Should filter pure emote messages"""
        result = filter._is_emote_only(":smile: :heart: :laughing:")
        assert result == True
    
    def test_message_with_text_and_emotes(self, filter):
        """Should not filter messages with text and emotes"""
        result = filter._is_emote_only(":smile: Hello world")
        assert result == False
    
    def test_regular_text(self, filter):
        """Should not filter regular text"""
        result = filter._is_emote_only("This is a normal message")
        assert result == False
    
    def test_empty_message(self, filter):
        """Empty message is considered emote-only"""
        result = filter._is_emote_only("")
        assert result == True
    
    def test_only_special_chars(self, filter):
        """Should filter messages with only special characters"""
        result = filter._is_emote_only("!@#$%^&*()")
        assert result == True


class TestMessageLengthFilter:
    """Test message length filtering"""
    
    def test_too_short_message(self, filter):
        """Should filter messages shorter than min_message_length"""
        result = filter.should_filter("a", "user1", "User1")
        assert result == True
    
    def test_exact_min_length(self, filter):
        """Should accept message at minimum length"""
        result = filter.should_filter("ab", "user1", "User1")
        assert result == False
    
    def test_whitespace_only(self, filter):
        """Should filter whitespace-only messages"""
        result = filter.should_filter("   ", "user1", "User1")
        assert result == True
    
    def test_long_message(self, filter):
        """Should accept long messages"""
        result = filter.should_filter("This is a very long message that exceeds minimum length", "user1", "User1")
        assert result == False


class TestRateLimiting:
    def test_under_rate_limit(self, filter):
        """User under limit should be accepted"""
        for i in range(3):
            result = filter._check_user_rate_limit("user1")
            assert result == True
    
    def test_exceeds_rate_limit(self, filter):
        """User exceeding limit should be rejected"""
        # Max is 3 per window
        for i in range(3):
            filter._check_user_rate_limit("user1")
        
        # Fourth message should be rejected
        result = filter._check_user_rate_limit("user1")
        assert result == False
    
    def test_different_users_independent(self, filter):
        """Different users should have independent rate limits"""
        for i in range(3):
            result1 = filter._check_user_rate_limit("user1")
            result2 = filter._check_user_rate_limit("user2")
        
        assert result1 == True
        assert result2 == True

        # Both at limit
        result1 = filter._check_user_rate_limit("user1")
        assert result1 == False
        assert result2 == True
        result2 = filter._check_user_rate_limit("user2")
        assert result2 == False
        assert result2 == False

    
    def test_rate_limit_resets_after_window(self, filter):
        """Rate limit should reset after window expires"""
        # Fill up the window
        for i in range(3):
            filter._check_user_rate_limit("user1")
        
        # Should be at limit
        assert filter._check_user_rate_limit("user1") == False
        
        # Simulate time passing (window is 5 seconds)
        filter.config.window_seconds = 0.1
        time.sleep(0.2)
        
        # Should accept again
        result = filter._check_user_rate_limit("user1")
        assert result == True


class TestDuplicateDetection:
    """Test duplicate message detection"""
    
    def test_exact_duplicate(self, filter):
        message = "This is a test message"
        filter.record_message(message)
        
        result = filter._is_duplicate(message)
        assert result == True
    
    def test_case_insensitive_duplicate(self, filter):
        """Duplicate detection should be case-insensitive"""
        filter.record_message("Hello World")
        
        result = filter._is_duplicate("hello world")
        assert result == True
    
    def test_whitespace_normalized(self, filter):
        """Whitespace should be normalized for duplicate detection"""
        filter.record_message("Hello    World")
        
        result = filter._is_duplicate("hello world")
        assert result == True
    
    def test_not_duplicate_different_message(self, filter):
        """Different messages should not be detected as duplicates"""
        filter.record_message("This is message A")
        
        result = filter._is_duplicate("This is message B")
        assert result == False
    
    def test_similar_messages_above_threshold(self, filter):
        """Similar messages above threshold should be detected"""
        filter.record_message("The quick brown fox jumps over the lazy dog")
        
        # Very similar message (high overlap)
        result = filter._is_duplicate("The quick brown fox jumps over the lazy cat")
        assert result == True
    
    def test_similar_messages_below_threshold(self, filter):
        """Similar messages below threshold should not be detected"""
        filter.record_message("Apple banana cherry")
        
        # Very different message
        result = filter._is_duplicate("Dog elephant fish")
        assert result == False
    
    def test_duplicate_expiry(self, filter):
        """Old duplicates should expire and not be detected"""
        filter.record_message("Test message")
        filter.duplicate_expiry_seconds = 0.1
        
        # Should be duplicate initially
        assert filter._is_duplicate("Test message") == True
        
        # Wait for expiry
        time.sleep(0.2)
        
        # Should not be duplicate anymore
        result = filter._is_duplicate("Test message")
        assert result == False


class TestHashMessage:
    """Test message hashing for duplicates"""
    
    def test_hash_normalizes_case(self, filter):
        """Hash should normalize case"""
        hash1 = filter._hash_message("Hello World")
        hash2 = filter._hash_message("hello world")
        assert hash1 == hash2
    
    def test_hash_normalizes_whitespace(self, filter):
        """Hash should normalize whitespace"""
        hash1 = filter._hash_message("hello    world")
        hash2 = filter._hash_message("hello world")
        assert hash1 == hash2
    
    def test_hash_different_for_different_text(self, filter):
        """Different texts should have different hashes"""
        hash1 = filter._hash_message("Hello World")
        hash2 = filter._hash_message("Goodbye World")
        assert hash1 != hash2


class TestShouldFilter:
    """Test complete filter logic"""
    
    def test_filter_short_message(self, filter):
        """Should filter short messages"""
        result = filter.should_filter("a", "user1", "User1")
        assert result == True
    
    def test_filter_emote_only(self, filter):
        """Should filter emote-only messages"""
        result = filter.should_filter(":smile: :heart:", "user1", "User1")
        assert result == True
    
    def test_filter_rate_limited_user(self, filter):
        """Should filter messages from rate-limited users"""
        for i in range(3):
            filter.should_filter(f"Message {i}", "user1", "User1")
        
        # Fourth message should be filtered
        result = filter.should_filter("Message 4", "user1", "User1")
        assert result == True
    
    def test_filter_duplicate(self, filter):
        """Should filter duplicate messages"""
        filter.record_message("Test message")
        
        result = filter._is_duplicate("Test message")
        assert result == True
    
    def test_accept_valid_message(self, filter):
        """Should accept valid messages"""
        result = filter.should_filter("This is a valid message", "user1", "User1")
        assert result == False


class TestRecordMessage:
    """Test message recording"""
    
    def test_record_message(self, filter):
        """Should record processed messages"""
        filter.record_message("Test message")
        assert len(filter.processed_messages) == 1
    
    def test_record_multiple_messages(self, filter):
        """Should record multiple messages"""
        for i in range(5):
            filter.record_message(f"Message {i}")
        
        assert len(filter.processed_messages) == 5
    
    def test_memory_optimization_limit(self, filter):
        """Should keep only last 100 messages"""
        for i in range(150):
            filter.record_message(f"Message {i}")
        
        assert len(filter.processed_messages) <= 100


class TestReset:
    """Test filter reset"""
    
    def test_reset_clears_processed_messages(self, filter):
        """Reset should clear processed messages"""
        filter.record_message("Test")
        assert len(filter.processed_messages) > 0
        
        filter.reset()
        assert len(filter.processed_messages) == 0
    
    def test_reset_clears_rate_limits(self, filter):
        """Reset should clear rate limit tracking"""
        filter._check_user_rate_limit("user1")
        assert len(filter.user_message_counts) > 0
        
        filter.reset()
        assert len(filter.user_message_counts) == 0
    
    def test_filter_works_after_reset(self, filter):
        """Filter should work normally after reset"""
        filter.record_message("Test")
        filter.reset()
        
        result = filter.should_filter("Valid message", "user1", "User1")
        assert result == False
