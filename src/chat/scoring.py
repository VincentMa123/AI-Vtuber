import re
from typing import List
from .models import ChatMessage

class ChatScorer:
    def __init__(self):
        self.recent_topics: List[str] = []

    def calculate_priority(self, message: ChatMessage) -> float:
        """
        Calculate priority score for a message
        
        Scoring factors:
        - Questions: +3
        - Name mentions (Lumina/Indomaret): +2
        - Novelty (new topics): +1-2
        - Length (5+ words): +1
        - Image attachment: +2
        - Recency: +0.5
        """
        score = 0.0
        text = message.message.lower()
        
        # Question detection
        question_patterns = [
            r'\?',
            r'\b(how|what|why|when|where|who|can you|could you|would you|do you)\b'
        ]
        for pattern in question_patterns:
            if re.search(pattern, text):
                score += 3.0
                break
        
        # Name mentions
        if 'lumina' in text:
            score += 2.0
        if 'indomaret' in text:
            score += 2.0
        
        topics = self.extract_topics(message.message)
        new_topics = [t for t in topics if t not in self.recent_topics]
        if new_topics:
            score += min(len(new_topics), 2)
        
        word_count = len(message.message.split())
        if word_count >= 5:
            score += 1.0
        
        if message.image_base64:
            score += 2.0
        
        score += 0.5
        
        return score

    def extract_topics(self, message: str) -> List[str]:

        # Simple topic extraction - get words longer than 4 characters
        words = re.findall(r'\b\w{4,}\b', message.lower())
        # Filter out common words
        stopwords = {'that', 'this', 'with', 'have', 'from', 'they', 'been', 'were', 'what', 'when'}
        topics = [w for w in words if w not in stopwords]
        return topics[:3]  # Return top 3 topics

    def update_recent_topics(self, messages: List[ChatMessage]):

        for msg in messages:
            topics = self.extract_topics(msg.message)
            self.recent_topics.extend(topics)
            # Keep only last 20 topics
            if len(self.recent_topics) > 20:
                self.recent_topics = self.recent_topics[-20:]

    def reset(self):
        self.recent_topics.clear()
