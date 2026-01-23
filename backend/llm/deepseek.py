import httpx
from typing import Optional, List, Dict, Any
import core.config as config
import core.utils as utils
from .base import BaseLLMProvider, sanitize_history


class DeepSeekProvider(BaseLLMProvider):
    """DeepSeek API provider for LLM inference (text-only, no vision)."""
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)

    async def generate(
        self, 
        message: str, 
        history: List[Dict[str, Any]] = [], 
        image_base64: Optional[str] = None,
        **kwargs
    ) -> Optional[str]:
        """
        Call DeepSeek API and return the response text, or None if failed.
        Note: DeepSeek doesn't support vision - images should be routed to OpenRouter.
        """
        if not config.DEEPSEEK_API_KEY:
            return None
        
        messages = [{"role": "system", "content": utils.get_system_prompt(user_message=message)}]
        
        if history:
            messages.extend(sanitize_history(history))
        
        messages.append({"role": "user", "content": message})
        
        max_tokens = kwargs.get("max_tokens", 256)
        
        try:
            timeout = 30.0
            response = await self.client.post(
                config.DEEPSEEK_BASE_URL,
                headers={
                    "Authorization": f"Bearer {config.DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": config.DEEPSEEK_MODEL,
                    "messages": messages,
                    "max_tokens": max_tokens
                },
                timeout=timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                if "choices" not in data:
                    logging.error(f"DeepSeek API returned 200 but missing 'choices': {data}")
                    return None
                return data["choices"][0]["message"]["content"]
            else:
                logging.error(f"DeepSeek API error: {response.status_code} - {response.text}")
                return None
                    
        except Exception as e:
            logging.error(f"DeepSeek API call failed: {type(e).__name__}: {e}")
            return None
