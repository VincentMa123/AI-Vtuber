import re
from typing import List
from .models import ChatMessage, ScoringConfig

class ChatScorer:
    def __init__(self, config: ScoringConfig | None = None):
        self.recent_topics: List[str] = []
        self.config = config or ScoringConfig()

    def calculate_priority(self, message: ChatMessage) -> float:
        """
        Calculate priority score for a message
        
        Scoring factors (weights from ScoringConfig):
        - Questions
        - Name mentions (configurable keywords)
        - Novelty (new topics)
        - Length (configurable min words)
        - Image attachment
        - Recency
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
                score += self.config.question_score
                break
        
        # Name mentions
        for keyword in self.config.keywords:
            if keyword in text:
                score += self.config.name_score
        
        topics = self.extract_topics(message.message)
        new_topics = [t for t in topics if t not in self.recent_topics]
        if new_topics:
            score += min(len(new_topics), self.config.novelty_max)
        
        word_count = len(message.message.split())
        if word_count >= self.config.min_words_for_length_bonus:
            score += self.config.long_message_score
        
        if message.image_base64:
            score += self.config.image_score
        
        score += self.config.recency_score
        
        return score

    def extract_topics(self, message: str) -> List[str]:

        # Simple topic extraction - get words longer than 4 characters
        words = re.findall(r'\b\w{4,}\b', message.lower())
        # Filter out common words
        topics = [w for w in words if w not in self.config.stopwords]
        return topics[:self.config.max_topics]  # Return top N topics

    def update_recent_topics(self, messages: List[ChatMessage]):

        for msg in messages:
            topics = self.extract_topics(msg.message)
            self.recent_topics.extend(topics)
            # Keep only last N topics
            if len(self.recent_topics) > self.config.recent_topic_limit:
                self.recent_topics = self.recent_topics[-self.config.recent_topic_limit:]

    def reset(self):
        self.recent_topics.clear()
