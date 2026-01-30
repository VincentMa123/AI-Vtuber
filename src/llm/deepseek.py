import httpx
import logging
import json
from typing import Optional, List, Dict, Any, AsyncGenerator
import core.config as config
import core.utils as utils
from .base import BaseLLMProvider, sanitize_history


class DeepSeekProvider(BaseLLMProvider):
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)

    async def generate(
        self, 
        message: str, 
        history: List[Dict[str, Any]] = [], 
        image_base64: Optional[str] = None,
        **kwargs
    ) -> Optional[str]:
  
        if not config.DEEPSEEK_API_KEY:
            return None
        
        system_prompt = kwargs.get("system_prompt")
        if not system_prompt:
            system_prompt = utils.get_system_prompt(user_message=message)

        messages = [{"role": "system", "content": system_prompt}]
        
        if history:
            messages.extend(sanitize_history(history))
        
        messages.append({"role": "user", "content": message})
        
        max_tokens = kwargs.get("max_tokens", 100)
        
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
    
    async def generate_stream(
        self, 
        message: str, 
        history: List[Dict[str, Any]] = [], 
        image_base64: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:

        if not config.DEEPSEEK_API_KEY:
            return
        
        system_prompt = kwargs.get("system_prompt")
        if not system_prompt:
             system_prompt = utils.get_system_prompt(user_message=message)

        messages = [{"role": "system", "content": system_prompt}]
        
        if history:
            messages.extend(sanitize_history(history))
        
        messages.append({"role": "user", "content": message})
        
        max_tokens = kwargs.get("max_tokens", 256)
        
        try:
            timeout = 30.0
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
                timeout=timeout
            ) as response:
                if response.status_code != 200:
                    logging.error(f"DeepSeek streaming error: {response.status_code}")
                    return
                
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
                    except Exception as e:
                        logging.error(f"Error parsing DeepSeek streaming response: {e}")
                        continue
                        
        except Exception as e:
            logging.error(f"DeepSeek streaming failed: {type(e).__name__}: {e}")
