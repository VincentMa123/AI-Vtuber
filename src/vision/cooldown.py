import time
import logging
from typing import Dict

class CooldownManager:
    def __init__(self):
        self.last_reaction_time = 0
        self.topic_locks: Dict[str, float] = {}
        
        self.GLOBAL_COOLDOWN = 60.0
        self.TOPIC_LOCK_DURATION = 300.0 

    def can_react(self, category: str) -> bool:
        now = time.time()
        
        if now - self.last_reaction_time < self.GLOBAL_COOLDOWN:
            return False
            
        if category in self.topic_locks:
            lock_expiry = self.topic_locks[category]
            if now < lock_expiry:
                logging.debug(f"[Vision] Topic '{category}' locked until {lock_expiry}")
                return False
        
        return True

    def record_reaction(self, category: str):
        now = time.time()
        self.last_reaction_time = now
        self.topic_locks[category] = now + self.TOPIC_LOCK_DURATION
        logging.info(f"[Vision] Reaction recorded. global_cd={self.GLOBAL_COOLDOWN}s, topic_lock({category})={self.TOPIC_LOCK_DURATION}s")
