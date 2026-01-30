from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, AsyncGenerator


def sanitize_history(history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Clean up history for the model:
    1. Remove any large base64 image data from previous turns to save tokens/bandwidth
    2. Ensure roles are correct
    """
    clean_history = []
    for msg in history:
        clean_msg = msg.copy()

        if isinstance(clean_msg.get("content"), list):
            new_content = []
            for item in clean_msg["content"]:
                if item.get("type") == "text":
                    new_content.append(item)
                elif item.get("type") == "image_url" or item.get("type") == "image":
                    new_content.append({"type": "text", "text": "[User shared an image]"})
            
            if len(new_content) == 1 and new_content[0]["type"] == "text":
                clean_msg["content"] = new_content[0]["text"]
            else:
                clean_msg["content"] = new_content
        
        if clean_msg["role"] == "assistant":
            pass
            
        clean_history.append(clean_msg)
    
    return clean_history[-10:]


class BaseLLMProvider(ABC):
    
    @abstractmethod
    async def generate(
        self, 
        message: str, 
        history: List[Dict[str, Any]] = [], 
        image_base64: Optional[str] = None,
        **kwargs
    ) -> Optional[str]:
        """
        Generate a response from the LLM.
        
        Args:
            message: The user's message
            history: Conversation history
            image_base64: Optional base64-encoded image
            **kwargs: Additional arguments (e.g., max_tokens, temperature)
            
        Returns:
            Generated text response, or None if failed
        """
        pass
    
    async def generate_stream(
        self, 
        message: str, 
        history: Optional[List[Dict[str, Any]]] = None, 
        image_base64: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:        
    
        # Default implementation: fallback to non-streaming and yield full response
        result = await self.generate(message, history, image_base64, **kwargs)
        if result:
            yield result
