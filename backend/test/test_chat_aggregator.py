"""
Test suite for chat aggregation system
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from chat_aggregator import ChatAggregator, ChatMessage, AggregationConfig


async def test_priority_scoring():
    """Test that priority scoring works correctly"""
    print("\n=== Testing Priority Scoring ===")
    
    config = AggregationConfig(enabled=True, window_seconds=2.0)
    aggregator = ChatAggregator(config)
    
    # Test messages with different priorities
    test_cases = [
        ("hello", "user1", "User1", 0),  # Low priority
        ("What products do you recommend?", "user2", "User2", 3),  # Question
        ("Lumina, can you help me?", "user3", "User3", 5),  # Name + question
        ("Check out this product!", "user4", "User4", 0),  # No special features
        ("I love Indomaret snacks!", "user5", "User5", 2),  # Name mention
    ]
    
    for msg_text, user_id, username, expected_min_score in test_cases:
        msg = ChatMessage(
            message=msg_text,
            user_id=user_id,
            username=username,
            timestamp=asyncio.get_event_loop().time()
        )
        score = aggregator._calculate_priority(msg)
        print(f"  '{msg_text[:40]}...' -> Score: {score:.1f} (expected >= {expected_min_score})")
        assert score >= expected_min_score, f"Score {score} is less than expected {expected_min_score}"
    
    print("✓ Priority scoring test passed!")


async def test_spam_filtering():
    """Test spam and duplicate filtering"""
    print("\n=== Testing Spam Filtering ===")
    
    config = AggregationConfig(
        enabled=True,
        window_seconds=2.0,
        min_message_length=2,
        similarity_threshold=0.8
    )
    aggregator = ChatAggregator(config)
    await aggregator.start()
    
    # Test duplicate detection
    msg1 = ChatMessage("This is a test message", "user1", "User1", asyncio.get_event_loop().time())
    msg2 = ChatMessage("This is a test message", "user2", "User2", asyncio.get_event_loop().time())
    
    accepted1 = await aggregator.submit_message(msg1)
    await asyncio.sleep(0.1)
    accepted2 = await aggregator.submit_message(msg2)
    
    print(f"  First message accepted: {accepted1}")
    print(f"  Duplicate message accepted: {accepted2}")
    assert accepted1 == True, "First message should be accepted"
    assert accepted2 == False, "Duplicate message should be filtered"
    
    # Test emote-only filtering
    msg3 = ChatMessage(":smile: :heart:", "user3", "User3", asyncio.get_event_loop().time())
    accepted3 = await aggregator.submit_message(msg3)
    print(f"  Emote-only message accepted: {accepted3}")
    assert accepted3 == False, "Emote-only message should be filtered"
    
    # Test too-short message
    msg4 = ChatMessage("h", "user4", "User4", asyncio.get_event_loop().time())
    accepted4 = await aggregator.submit_message(msg4)
    print(f"  Too-short message accepted: {accepted4}")
    assert accepted4 == False, "Too-short message should be filtered"
    
    await aggregator.stop()
    print("✓ Spam filtering test passed!")


async def test_rate_limiting():
    """Test user rate limiting"""
    print("\n=== Testing Rate Limiting ===")
    
    config = AggregationConfig(
        enabled=True,
        window_seconds=3.0,
        max_messages_per_user_per_window=2
    )
    aggregator = ChatAggregator(config)
    await aggregator.start()
    
    # Send 3 messages from same user
    for i in range(3):
        msg = ChatMessage(
            f"Message {i+1} from same user",
            "user1",
            "User1",
            asyncio.get_event_loop().time()
        )
        accepted = await aggregator.submit_message(msg)
        print(f"  Message {i+1} accepted: {accepted}")
        
        if i < 2:
            assert accepted == True, f"Message {i+1} should be accepted"
        else:
            assert accepted == False, "Third message should be rate limited"
    
    await aggregator.stop()
    print("✓ Rate limiting test passed!")


async def test_batch_processing():
    """Test message batching"""
    print("\n=== Testing Batch Processing ===")
    
    config = AggregationConfig(
        enabled=True,
        window_seconds=2.0,
        min_response_interval=1.0
    )
    aggregator = ChatAggregator(config)
    await aggregator.start()
    
    # Submit multiple messages rapidly
    messages = [
        ("What's your favorite snack?", "user1", "Alice"),
        ("Hello Lumina!", "user2", "Bob"),
        ("I need help", "user3", "Charlie"),
        ("Random message", "user4", "Dave"),
        ("Lumina, what products do you recommend?", "user5", "Eve"),
    ]
    
    print(f"  Submitting {len(messages)} messages...")
    for msg_text, user_id, username in messages:
        msg = ChatMessage(msg_text, user_id, username, asyncio.get_event_loop().time())
        await aggregator.submit_message(msg)
    
    queue_size = aggregator.message_queue.qsize()
    print(f"  Queue size after submission: {queue_size}")
    assert queue_size > 0, "Queue should contain messages"
    
    # Wait for batch processing
    print("  Waiting for batch processing...")
    await asyncio.sleep(3.0)
    
    queue_size_after = aggregator.message_queue.qsize()
    print(f"  Queue size after processing: {queue_size_after}")
    
    await aggregator.stop()
    print("✓ Batch processing test passed!")


async def test_config_updates():
    """Test dynamic configuration updates"""
    print("\n=== Testing Config Updates ===")
    
    config = AggregationConfig(enabled=True, window_seconds=5.0)
    aggregator = ChatAggregator(config)
    
    print(f"  Initial window_seconds: {aggregator.config.window_seconds}")
    assert aggregator.config.window_seconds == 5.0
    
    aggregator.update_config(window_seconds=3.0)
    print(f"  Updated window_seconds: {aggregator.config.window_seconds}")
    assert aggregator.config.window_seconds == 3.0
    
    aggregator.update_config(enabled=False)
    print(f"  Updated enabled: {aggregator.config.enabled}")
    assert aggregator.config.enabled == False
    
    print("✓ Config updates test passed!")


async def main():
    """Run all tests"""
    print("=" * 60)
    print("CHAT AGGREGATOR TEST SUITE")
    print("=" * 60)
    
    try:
        await test_priority_scoring()
        await test_spam_filtering()
        await test_rate_limiting()
        await test_batch_processing()
        await test_config_updates()
        
        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED!")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
