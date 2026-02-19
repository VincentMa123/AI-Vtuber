import logging
from typing import Optional, List, Dict, Any, AsyncGenerator
from openai import AsyncOpenAI, APIError
import core.config as config
import core.utils as utils
from .base import BaseLLMProvider, sanitize_history, build_user_content

class QwenProvider(BaseLLMProvider):
    
    def __init__(self):
        self.api_key = config.QWEN_API_KEY
        self.base_url = config.QWEN_BASE_URL
        self.model = config.QWEN_MODEL
        self.client = None
        
        if self.api_key and self.base_url:
            self.client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        else:
            logging.warning("Qwen API key or Base URL not configured.")
    
    async def generate_stream(
        self, 
        message: str, 
        history: Optional[List[Dict[str, Any]]] = None, 
        image_base64: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:

        if not self.client:
            logging.error("Qwen client not initialized.")
            return

        history = history or []
        
        user_content = build_user_content(message, image_base64)
        
        system_prompt = utils.get_system_prompt(user_message=message)
        messages = [{"role": "system", "content": system_prompt}]
        
        if history:
            messages.extend(sanitize_history(history))
        
        messages.append({
            "role": "user", 
            "content": user_content
        })
        
        max_tokens = kwargs.get("max_tokens", 128)
        
        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                stream=True,
                stream_options={"include_usage": True}
            )
            
            async for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        yield delta.content
                        
        except APIError as e:
             logging.error(f"Qwen streaming error: {e}")
        except Exception as e:
            logging.error(f"Qwen streaming failed: {type(e).__name__}: {e}")
