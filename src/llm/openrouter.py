import httpx
import logging
import json
from typing import Optional, List, Dict, Any, AsyncGenerator
import core.config as config
import core.utils as utils
from .base import BaseLLMProvider, sanitize_history, parse_sse_stream, build_user_content


class OpenRouterProvider(BaseLLMProvider):
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self.client.aclose()
    
    async def generate_stream(
        self, 
        message: str, 
        history: Optional[List[Dict[str, Any]]] = None, 
        image_base64: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:

        if not config.OPENROUTER_API_KEY:
            return
            
        history = history or []
        
        system_prompt = kwargs.get("system_prompt")
        if not system_prompt:
            system_prompt = utils.get_system_prompt(user_message=message)
            
        messages = [{"role": "system", "content": system_prompt}]
        
        if history:
            messages.extend(sanitize_history(history))
        
        user_content = build_user_content(message, image_base64)
        messages.append({
            "role": "user", 
            "content": user_content
        })
        
        max_tokens = kwargs.get("max_tokens", 256)
        
        try:
            timeout = 60.0 if image_base64 else 30.0
            async with self.client.stream(
                "POST",
                config.OPENROUTER_BASE_URL,
                headers={
                    "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost:3000",
                    "X-Title": "VTuber Chat"
                },
                json={
                    "model": config.OPENROUTER_MODEL,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "stream": True
                },
                timeout=timeout
            ) as response:
                if response.status_code != 200:
                    logging.error(f"OpenRouter streaming error: {response.status_code}")
                    return
                
                async for chunk in parse_sse_stream(response):
                    yield chunk
                        
        except Exception as e:
            logging.error(f"OpenRouter streaming failed: {type(e).__name__}: {e}")
