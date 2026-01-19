import httpx
from typing import Optional
import state
import config
import utils

async def call_openrouter(message: str, image_base64: Optional[str] = None) -> Optional[str]:
    """Call OpenRouter API and return the response text, or None if failed."""
    if not config.OPENROUTER_API_KEY:
        return None
    
    # Build user message content based on whether image is provided
    user_content = []
    if image_base64:
        user_content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{image_base64}"}
        })
    user_content.append({"type": "text", "text": message})
    
    print(f"[DEBUG] call_api_model - image_base64 provided: {image_base64 is not None}")
    if image_base64:
        print(f"[DEBUG] image_base64 length: {len(image_base64)} chars")

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
                        {"role": "user", "content": user_content if image_base64 else message}
                    ],
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

def call_local_model(message: str, image_base64: Optional[str] = None) -> str:
    """Call the local Qwen model and return the response text."""
    if not state.model or not state.processor:
        raise RuntimeError("Local model is not loaded!")

    # Debug: Check if image was received
    print(f"[DEBUG] call_local_model - image_base64 provided: {image_base64 is not None}")
    if image_base64:
        print(f"[DEBUG] image_base64 length: {len(image_base64)} chars")

    content = [{"type": "text", "text": message}]
    if image_base64:
        content.insert(0, {"type": "image"})

    system_prompt = utils.get_system_prompt()
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": content}
    ]
    
    text = state.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    
    # For vision models, pass images parameter
    if image_base64:
        import base64
        from PIL import Image
        import io
        
        # Decode base64 to PIL Image
        image_data = base64.b64decode(image_base64)
        image = Image.open(io.BytesIO(image_data))
        
        inputs = state.processor(text=[text], images=[image], padding=True, return_tensors="pt")
    else:
        inputs = state.processor(text=[text], padding=True, return_tensors="pt")
    
    inputs = inputs.to("cuda")
    
    generated_ids = state.model.generate(**inputs, max_new_tokens=512)
    generated_ids_trimmed = [
        out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
    ]
    
    output_text = state.processor.batch_decode(
        generated_ids_trimmed, 
        skip_special_tokens=True, 
        clean_up_tokenization_spaces=False
    )[0]
    
    return output_text
