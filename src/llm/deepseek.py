import httpx
import logging
import json
from typing import Optional, List, Dict, Any, AsyncGenerator
import core.config as config
import core.utils as utils
from .base import BaseLLMProvider, sanitize_history, parse_sse_stream


class DeepSeekProvider(BaseLLMProvider):
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def generate_stream(
        self, 
        message: str, 
        history: Optional[List[Dict[str, Any]]] = None, 
        image_base64: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:

        if not config.DEEPSEEK_API_KEY:
            return
            
        history = history or []
        
        system_prompt = kwargs.get("system_prompt")
        if not system_prompt:
             system_prompt = utils.get_system_prompt(user_message=message)

        messages = [{"role": "system", "content": system_prompt}]
        
        if history:
            messages.extend(sanitize_history(history))
        
        messages.append({"role": "user", "content": message})
        
        max_tokens = kwargs.get("max_tokens", 256)
        
        try:
            async with self.client.stream(
                "POST",
                config.DEEPSEEK_BASE_URL,
                headers={
                    "Authorization": f"Bearer {config.DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": config.DEEPSEEK_MODEL,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "stream": True
                },
                # Use client timeout default
            ) as response:
                if response.status_code != 200:
                    logging.error(f"DeepSeek streaming error: {response.status_code}")
                    return
                
                async for chunk in BaseLLMProvider.parse_sse_stream(response):
                    yield chunk

                        
        except Exception as e:
            logging.error(f"DeepSeek streaming failed: {type(e).__name__}: {e}")
