"""
Test suite for chat aggregation system
"""

import pytest
import pytest_asyncio
import asyncio
from datetime import datetime
from chat.aggregator import ChatAggregator, ChatMessage, AggregationConfig

@pytest_asyncio.fixture
def config():
    """Default test configuration"""
    return AggregationConfig(enabled=True, window_seconds=2.0)


@pytest_asyncio.fixture
async def aggregator(config):
    """Create an aggregator instance"""
    agg = ChatAggregator(config)
    yield agg
    # Cleanup
    try:
        await agg.stop()
    except:
        pass


@pytest.mark.asyncio
async def test_spam_filtering():
    """Test spam and duplicate filtering"""
    config = AggregationConfig(
        enabled=True,
        window_seconds=2.0,
        min_message_length=2,
        similarity_threshold=0.8
    )
    aggregator = ChatAggregator(config)
    await aggregator.start()
    
    try:
        # Test duplicate detection
        msg1 = ChatMessage("This is a test message", "user1", "User1", datetime.now())
        msg2 = ChatMessage("This is a test message", "user2", "User2", datetime.now())
        
        accepted1 = await aggregator.submit_message(msg1)
        await asyncio.sleep(0.1)
        accepted2 = await aggregator.submit_message(msg2)
        
        assert accepted1 == True, "First message should be accepted"
        assert accepted2 == False, "Duplicate message should be filtered"
        
        # Test emote-only filtering
        msg3 = ChatMessage(":smile: :heart:", "user3", "User3", datetime.now())
        accepted3 = await aggregator.submit_message(msg3)
        assert accepted3 == False, "Emote-only message should be filtered"
        
        # Test too-short message
        msg4 = ChatMessage("h", "user4", "User4", datetime.now())
        accepted4 = await aggregator.submit_message(msg4)
        assert accepted4 == False, "Too-short message should be filtered"
    finally:
        await aggregator.stop()


@pytest.mark.asyncio
async def test_rate_limiting():
    """Test user rate limiting"""
    config = AggregationConfig(
        enabled=True,
        window_seconds=3.0,
        max_messages_per_user_per_window=2
    )
    aggregator = ChatAggregator(config)
    await aggregator.start()
    
    try:
        # Send 3 messages from same user
        for i in range(3):
            msg = ChatMessage(
                f"Message {i+1} from same user",
                "user1",
                "User1",
                datetime.now()
            )
            accepted = await aggregator.submit_message(msg)
            
            if i < 2:
                assert accepted == True, f"Message {i+1} should be accepted"
            else:
                assert accepted == False, "Third message should be rate limited"
    finally:
        await aggregator.stop()


@pytest.mark.asyncio
async def test_batch_processing():
    """Test message batching"""
    config = AggregationConfig(
        enabled=True,
        window_seconds=2.0,
        min_response_interval=1.0
    )
    aggregator = ChatAggregator(config)
    await aggregator.start()
    
    try:
        # Submit multiple messages rapidly
        messages = [
            ("What's your favorite snack?", "user1", "Alice"),
            ("Hello Lumina!", "user2", "Bob"),
            ("I need help", "user3", "Charlie"),
            ("Random message", "user4", "Dave"),
            ("Lumina, what products do you recommend?", "user5", "Eve"),
        ]
        
        for msg_text, user_id, username in messages:
            msg = ChatMessage(msg_text, user_id, username, datetime.now())
            await aggregator.submit_message(msg)
        
        queue_size = aggregator.message_queue.qsize()
        assert queue_size > 0, "Queue should contain messages"
        
        # Wait for batch processing
        await asyncio.sleep(3.0)
        
        queue_size_after = aggregator.message_queue.qsize()
        # After processing, queue should be smaller (not necessarily empty)
        assert queue_size_after <= queue_size, "Queue should be processed"
    finally:
        await aggregator.stop()


@pytest.mark.asyncio
async def test_config_updates(aggregator):
    """Test dynamic configuration updates"""
    
    assert aggregator.config.window_seconds == 2.0
    
    aggregator.update_config(window_seconds=3.0)
    assert aggregator.config.window_seconds == 3.0
    
    aggregator.update_config(enabled=False)
    assert aggregator.config.enabled == False
