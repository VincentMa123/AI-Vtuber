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
        

            
        clean_history.append(clean_msg)
    
    return clean_history[-10:]


class BaseLLMProvider(ABC):
    
    @abstractmethod
    async def generate_stream(
        self, 
        message: str, 
        history: Optional[List[Dict[str, Any]]] = None, 
        image_base64: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:        
        # Abstract method, must be implemented by subclasses
        yield ""

async def parse_sse_stream(response) -> AsyncGenerator[str, None]:
    """Parse SSE streaming responses from OpenAI-compatible APIs."""
    import json
    async for line in response.aiter_lines():
        if not line or not line.startswith("data: "):
            continue
        if line.strip() == "data: [DONE]":
            break
        try:
            data = json.loads(line[6:])
            if "choices" in data and len(data["choices"]) > 0:
                delta = data["choices"][0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    yield content
        except json.JSONDecodeError:
            continue

def build_user_content(message: str, image_base64: Optional[str] = None, mime_type: str = "image/jpeg") -> List[Dict[str, Any]]:
    """Build user message content with optional image.
    
    Args:
        mime_type: Image MIME type (default jpeg since compress_image_for_vlm outputs JPEG)
    """
    content = []
    if image_base64:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:{mime_type};base64,{image_base64}"}
        })
    content.append({"type": "text", "text": message})
    return content