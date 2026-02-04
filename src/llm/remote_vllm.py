import httpx
import logging
from typing import Optional, List, Dict, Any, AsyncGenerator
import core.config as config
import core.utils as utils
from .base import BaseLLMProvider, sanitize_history, parse_sse_stream, build_user_content
import json


async def get_remote_model_name() -> Optional[str]:

    if not config.REMOTE_VLLM_BASE_URL:
        return None
    
    try:
        # Extract base URL (remove /v1/chat/completions)
        base_url = config.REMOTE_VLLM_BASE_URL.replace("/v1/chat/completions", "")
        models_url = f"{base_url}/v1/models"
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(models_url)
            if response.status_code == 200:
                data = response.json()
                if "data" in data and len(data["data"]) > 0:
                    model_name = data["data"][0]["id"]
                    logging.debug(f"[RemoteVLLM] Auto-detected model name: {model_name}")
                    return model_name
    except Exception as e:
        logging.error(f"[RemoteVLLM] Failed to auto-detect model name: {e}")
    
    return None


class RemoteVLLMProvider(BaseLLMProvider):
    
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

        if not config.REMOTE_VLLM_BASE_URL:
            return
            
        history = history or []
        
        model_name = config.REMOTE_VLLM_MODEL
        if not model_name:
            model_name = await get_remote_model_name()
            if not model_name:
                logging.error("[RemoteVLLM] Could not determine model name for streaming")
                return
        
        # Allow overriding system prompt
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
        
        max_tokens = kwargs.get("max_tokens", 100)
        
        try:
            timeout = 60.0 if image_base64 else 30.0
            async with self.client.stream(
                "POST",
                config.REMOTE_VLLM_BASE_URL,
                headers={"Content-Type": "application/json"},
                json={
                    "model": model_name,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "stream": True
                },
                timeout=timeout
            ) as response:
                if response.status_code != 200:
                    logging.error(f"Remote vLLM streaming error: {response.status_code}")
                    return
                
                async for chunk in parse_sse_stream(response):
                    yield chunk
                        
        except Exception as e:
            logging.error(f"Remote vLLM streaming failed: {type(e).__name__}: {e}")

