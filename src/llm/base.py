import re
import json
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, AsyncGenerator


# Pattern to detect leaked tool call markup from DeepSeek models
# Matches fullwidth delimiter tags like <｜DSML｜function_calls> ... </｜DSML｜function_calls>
_LEAKED_TOOL_CALL_RE = re.compile(
    r'<[\uff5c｜].*?function_call.*$',
    re.DOTALL | re.IGNORECASE
)


def strip_leaked_tool_calls(text: str) -> str:
    """Remove leaked tool call XML markup that DeepSeek sometimes outputs as plain text."""
    return _LEAKED_TOOL_CALL_RE.sub('', text).rstrip()


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
        image_base64: Optional[Any] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:        
        # Abstract method, must be implemented by subclasses
        yield ""

async def parse_sse_stream(response) -> AsyncGenerator[str, None]:
    """Parse SSE streaming responses from OpenAI-compatible APIs."""
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

def build_user_content(message: str, image_base64: Optional[Any] = None, mime_type: str = "image/jpeg") -> List[Dict[str, Any]]:
    """Build user message content with optional image or list of images.
    
    Args:
        image_base64: Single base64 string or List of base64 strings.
        mime_type: Image MIME type (default jpeg since compress_image_for_vlm outputs JPEG)
    """
    content = []
    
    if image_base64:
        if isinstance(image_base64, list):
            for img in image_base64:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{img}"}
                })
        else:
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime_type};base64,{image_base64}"}
            })
            
    content.append({"type": "text", "text": message})
    return content