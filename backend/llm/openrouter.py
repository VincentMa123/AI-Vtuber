import httpx
from typing import Optional, List, Dict, Any
import config
import utils
from .base import BaseLLMProvider, sanitize_history


class OpenRouterProvider(BaseLLMProvider):
    """OpenRouter API provider for LLM inference."""
    
    async def generate(
        self, 
        message: str, 
        history: List[Dict[str, Any]] = [], 
        image_base64: Optional[str] = None
    ) -> Optional[str]:
        """Call OpenRouter API and return the response text, or None if failed."""
        if not config.OPENROUTER_API_KEY:
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
        
        print(f"[DEBUG] OpenRouter - image_base64 provided: {image_base64 is not None}")
        if image_base64:
            print(f"[DEBUG] image_base64 length: {len(image_base64)} chars")

        try:
            timeout = 60.0 if image_base64 else 30.0
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
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
                        "max_tokens": 256
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if "choices" not in data:
                        print(f"OpenRouter API returned 200 but missing 'choices': {data}")
                        return None
                    return data["choices"][0]["message"]["content"]
                else:
                    print(f"OpenRouter API error: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            print(f"OpenRouter API call failed: {type(e).__name__}: {e}")
            return None
