import httpx
from typing import Optional
import state
import config
import utils

async def call_openrouter(message: str) -> Optional[str]:
    """Call OpenRouter API and return the response text, or None if failed."""
    if not config.OPENROUTER_API_KEY:
        return None
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
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
                    "messages": [
                        {"role": "system", "content": utils.get_system_prompt()},
                        {"role": "user", "content": message}
                    ],
                    "max_tokens": 256
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"]
            else:
                print(f"OpenRouter API error: {response.status_code} - {response.text}")
                return None
                
    except Exception as e:
        print(f"OpenRouter API call failed: {e}")
        return None

def call_local_model(message: str) -> str:
    """Call the local Qwen model and return the response text."""
    if not state.model or not state.processor:
        raise RuntimeError("Local model is not loaded!")

    messages = [
        {"role": "system", "content": utils.get_system_prompt()},
        {"role": "user", "content": [{"type": "text", "text": message}]}
    ]
    
    text = state.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = state.processor(text=[text], padding=True, return_tensors="pt")
    inputs = inputs.to("cuda")
    
    generated_ids = state.model.generate(**inputs, max_new_tokens=256)
    generated_ids_trimmed = [
        out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
    ]
    
    output_text = state.processor.batch_decode(
        generated_ids_trimmed, 
        skip_special_tokens=True, 
        clean_up_tokenization_spaces=False
    )[0]
    
    return output_text
