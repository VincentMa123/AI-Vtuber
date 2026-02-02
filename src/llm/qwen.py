import logging
import os
from typing import Optional, List, Dict, Any, AsyncGenerator
from openai import AsyncOpenAI, APIError
import core.config as config
import core.utils as utils
from .base import BaseLLMProvider, sanitize_history

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
        history: List[Dict[str, Any]] = [], 
        image_base64: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:

        if not self.client:
            logging.error("Qwen client not initialized.")
            return
        
        current_human_msg = []
        if image_base64:
             current_human_msg.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{image_base64}"}
            })
        current_human_msg.append({"type": "text", "text": message})
        
        system_prompt = utils.get_system_prompt(user_message=message)
        messages = [{"role": "system", "content": system_prompt}]
        
        if history:
            messages.extend(sanitize_history(history))
        
        messages.append({
            "role": "user", 
            "content": current_human_msg if image_base64 else message
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
