import pytest
from chat.scoring import ChatScorer
from chat.models import ChatMessage
from datetime import datetime

@pytest.fixture
def scorer():
    return ChatScorer()

def test_priority_question(scorer):
    msg = ChatMessage(message="What is the price of this?", username="test", user_id = 1, timestamp = datetime.now())
    score = scorer.calculate_priority(msg)
    assert score >= 3.0

def test_priority_mention_lumina(scorer):
    msg = ChatMessage(message="Hello Lumina", username="test", user_id = 1, timestamp = datetime.now())
    score = scorer.calculate_priority(msg)
    assert score >= 2.5

def test_priority_mention_indomaret(scorer):
    msg = ChatMessage(message="Indomaret ada apa aja?", username="test", user_id = 1, timestamp = datetime.now())
    score = scorer.calculate_priority(msg)
    assert score >= 4

def test_priority_with_image(scorer):
    msg = ChatMessage(
        message="Check this out",
        username="test",
        user_id=1,
        timestamp=datetime.now(),
        image_base64="base64_encoded_image"
    )
    score = scorer.calculate_priority(msg)
    assert score >= 2.0 

def test_update_recent_topics(scorer):
    msg1 = ChatMessage(message="Testing python programming", username="test", user_id=1, timestamp=datetime.now())
    msg2 = ChatMessage(message="Streaming software testing", username="test", user_id=2, timestamp=datetime.now())
    
    scorer.update_recent_topics([msg1, msg2])
    assert len(scorer.recent_topics) > 0
    assert "testing" in scorer.recent_topics or "python" in scorer.recent_topics

def test_update_recent_topics_exceeds_limit(scorer):
    """Test that recent_topics only keeps last 20 items"""
    messages = []
    for i in range(25):
        msg = ChatMessage(
            message=f"Message number {i} about testing",
            username=f"user{i}",
            user_id=i,
            timestamp=datetime.now()
        )
        messages.append(msg)
    
    scorer.update_recent_topics(messages)
    assert len(scorer.recent_topics) <= 20

def test_reset(scorer):
    msg = ChatMessage(message="Testing the reset function", username="test", user_id=1, timestamp=datetime.now())
    scorer.update_recent_topics([msg])
    assert len(scorer.recent_topics) > 0
    
    scorer.reset()
    assert len(scorer.recent_topics) == 0

