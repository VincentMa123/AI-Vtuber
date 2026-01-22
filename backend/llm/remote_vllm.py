import httpx
from typing import Optional, List, Dict, Any
import config
import utils
from .base import BaseLLMProvider, sanitize_history


async def get_remote_model_name() -> Optional[str]:
    """Auto-detect the model name from the remote vLLM server."""
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
                    print(f"[RemoteVLLM] Auto-detected model name: {model_name}")
                    return model_name
    except Exception as e:
        print(f"[RemoteVLLM] Failed to auto-detect model name: {e}")
    
    return None


class RemoteVLLMProvider(BaseLLMProvider):
    """Remote vLLM server provider for LLM inference with vision support (OpenAI-compatible API)."""
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)

    async def generate(
        self, 
        message: str, 
        history: List[Dict[str, Any]] = [], 
        image_base64: Optional[str] = None
    ) -> Optional[str]:
        """Call remote vLLM API and return the response text, or None if failed."""
        if not config.REMOTE_VLLM_BASE_URL:
            return None
        
        # Auto-detect model name if not configured
        model_name = config.REMOTE_VLLM_MODEL
        if not model_name:
            model_name = await get_remote_model_name()
            if not model_name:
                print("[RemoteVLLM] Could not determine model name. Please set REMOTE_VLLM_MODEL in config.")
                return None
        
        current_human_msg = []
        if image_base64:
            current_human_msg.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{image_base64}"}
            })
        current_human_msg.append({"type": "text", "text": message})
        
        messages = [{"role": "system", "content": utils.get_system_prompt(user_message=message)}]
        
        if history:
            messages.extend(sanitize_history(history))
            
        messages.append({
            "role": "user", 
            "content": current_human_msg if image_base64 else message
        })
        
        print(f"[DEBUG] RemoteVLLM - image_base64 provided: {image_base64 is not None}")
        if image_base64:
            print(f"[DEBUG] image_base64 length: {len(image_base64)} chars")

        try:
            timeout = 60.0 if image_base64 else 30.0
            response = await self.client.post(
                config.REMOTE_VLLM_BASE_URL,
                headers={
                    "Content-Type": "application/json"
                },
                json={
                    "model": model_name,
                    "messages": messages, 
                    "max_tokens": 100
                },
                timeout=timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                if "choices" not in data:
                    print(f"Remote vLLM API returned 200 but missing 'choices': {data}")
                    return None
                return data["choices"][0]["message"]["content"]
            else:
                print(f"Remote vLLM API error: {response.status_code} - {response.text}")
                return None
                    
        except Exception as e:
            print(f"Remote vLLM API call failed: {type(e).__name__}: {e}")
            return None

