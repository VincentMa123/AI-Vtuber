import httpx
from typing import Optional, List, Dict, Any
import state
import config
import utils

def sanitize_history(history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Clean up history for the model:
    1. Remove any large base64 image data from previous turns to save tokens/bandwidth
    2. Ensure roles are correct
    """
    clean_history = []
    for msg in history:
        # Create a copy to avoid modifying the original
        clean_msg = msg.copy()
        
        # If content is a list (multimodal), we need to handle it
        if isinstance(clean_msg.get("content"), list):
            new_content = []
            for item in clean_msg["content"]:
                if item.get("type") == "text":
                    new_content.append(item)
                elif item.get("type") == "image_url" or item.get("type") == "image":
                    new_content.append({"type": "text", "text": "[User shared an image]"})
            
            if len(new_content) == 1 and new_content[0]["type"] == "text":
                clean_msg["content"] = new_content[0]["text"]
            else:
                clean_msg["content"] = new_content
        
        # If it's the assistant's message, ensure it's just text
        if clean_msg["role"] == "assistant":
            # Sometimes we might store metadata, just keep the content
            pass
            
        clean_history.append(clean_msg)
    
    # Limit to last 10 messages to prevent context overflow
    return clean_history[-10:]

async def call_openrouter(message: str, history: List[Dict[str, Any]] = [], image_base64: Optional[str] = None) -> Optional[str]:
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
    
    print(f"[DEBUG] call_api_model - image_base64 provided: {image_base64 is not None}")
    if image_base64:
        print(f"[DEBUG] image_base64 length: {len(image_base64)} chars")

    try:
        # Longer timeout for image requests (they take more time to process)
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
                    "messages": messages, # Use the full history now
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

async def call_deepseek(message: str, history: List[Dict[str, Any]] = [], image_base64: Optional[str] = None) -> Optional[str]:
    """Call DeepSeek API and return the response text, or None if failed.
    Note: DeepSeek doesn't support vision - images should be routed to OpenRouter.
    """
    if not config.DEEPSEEK_API_KEY:
        return None
    
    messages = [{"role": "system", "content": utils.get_system_prompt(user_message=message)}]
    
    if history:
        messages.extend(sanitize_history(history))
    
    # DeepSeek only supports text - images are handled by api_server routing
    messages.append({"role": "user", "content": message})
    
    try:
        timeout = 30.0
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                config.DEEPSEEK_BASE_URL,
                headers={
                    "Authorization": f"Bearer {config.DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": config.DEEPSEEK_MODEL,
                    "messages": messages,
                    "max_tokens": 256
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                if "choices" not in data:
                    print(f"DeepSeek API returned 200 but missing 'choices': {data}")
                    return None
                return data["choices"][0]["message"]["content"]
            else:
                print(f"DeepSeek API error: {response.status_code} - {response.text}")
                return None
                
    except Exception as e:
        print(f"DeepSeek API call failed: {type(e).__name__}: {e}")
        return None

def call_local_model(message: str, history: List[Dict[str, Any]] = [], image_base64: Optional[str] = None) -> str:
    """Call the local Qwen model and return the response text."""
    if not state.model or not state.processor:
        raise RuntimeError("Local model is not loaded!")

    # Debug: Check if image was received
    print(f"[DEBUG] call_local_model - image_base64 provided: {image_base64 is not None}")
    if image_base64:
        print(f"[DEBUG] image_base64 length: {len(image_base64)} chars")

    # Current message content
    content = [{"type": "text", "text": message}]
    if image_base64:
        content.insert(0, {"type": "image"})
    
    # Logic for system prompt (simplified for images to prevent hallucination)
    if image_base64:
        system_prompt = "You are Lumina, a helpful AI assistant. Describe the image and answer the user's question naturally."
    else:
        system_prompt = utils.get_system_prompt(user_message=message)
    
    # Build messages list
    messages = [{"role": "system", "content": system_prompt}]
    
    # Add sanitized history (keeping it text-only for local model to avoid complexity)
    if history:
        clean_history = sanitize_history(history)
        # Ensure format matches what Qwen expects (basic role/content)
        for msg in clean_history:
            # If content is list, extract text
            if isinstance(msg["content"], list):
                text_content = next((item["text"] for item in msg["content"] if item["type"] == "text"), "")
                messages.append({"role": msg["role"], "content": text_content})
            else:
                messages.append(msg)

    # Add current message
    messages.append({"role": "user", "content": content})
    
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
