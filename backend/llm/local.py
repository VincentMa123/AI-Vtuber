from typing import Optional, List, Dict, Any
import state
import utils
from .base import BaseLLMProvider, sanitize_history


class LocalModelProvider(BaseLLMProvider):
    """Local Qwen3-VL model provider for LLM inference with vision support."""
    
    def generate(
        self, 
        message: str, 
        history: List[Dict[str, Any]] = [], 
        image_base64: Optional[str] = None
    ) -> Optional[str]:
        """Call the local Qwen model and return the response text."""
        if not state.model or not state.processor:
            raise RuntimeError("Local model is not loaded!")

        print(f"[DEBUG] LocalModel - image_base64 provided: {image_base64 is not None}")
        if image_base64:
            print(f"[DEBUG] image_base64 length: {len(image_base64)} chars")

        content = [{"type": "text", "text": message}]
        if image_base64:
            content.insert(0, {"type": "image"})
        
        if image_base64:
            system_prompt = "You are Lumina, a helpful AI assistant. Describe the image and answer the user's question naturally."
        else:
            system_prompt = utils.get_system_prompt(user_message=message)
        
        messages = [{"role": "system", "content": system_prompt}]
        
        if history:
            clean_history = sanitize_history(history)
            for msg in clean_history:
                if isinstance(msg["content"], list):
                    text_content = next((item["text"] for item in msg["content"] if item["type"] == "text"), "")
                    messages.append({"role": msg["role"], "content": text_content})
                else:
                    messages.append(msg)

        messages.append({"role": "user", "content": content})
        
        text = state.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        
        if image_base64:
            import base64
            from PIL import Image
            import io
            
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
