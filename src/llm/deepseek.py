import logging
import json
from typing import Optional, List, Dict, Any, AsyncGenerator
from openai import AsyncOpenAI, APIError
import core.config as config
import core.utils as utils
from .base import BaseLLMProvider, sanitize_history
from rag.tools import ALL_TOOLS, execute_tool_call


class DeepSeekProvider(BaseLLMProvider):
    
    def __init__(self):
        self.client = None
        
        if config.DEEPSEEK_API_KEY:
            self.client = AsyncOpenAI(
                api_key=config.DEEPSEEK_API_KEY,
                base_url="https://api.deepseek.com",
            )
        else:
            logging.warning("DeepSeek API key not configured.")
    
    async def generate_stream(
        self, 
        message: str, 
        history: Optional[List[Dict[str, Any]]] = None, 
        image_base64: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:

        if not self.client:
            logging.error("DeepSeek client not initialized.")
            return
            
        history = history or []
        
        system_prompt = kwargs.get("system_prompt")
        if not system_prompt:
             system_prompt = utils.get_system_prompt(user_message=message)

        messages = [{"role": "system", "content": system_prompt}]
        
        if history:
            messages.extend(sanitize_history(history))
        
        messages.append({"role": "user", "content": message})
        
        max_tokens = kwargs.get("max_tokens", 256)
        
        try:
            # First call: non-streaming with tools to check for tool calls
            first_response = await self.client.chat.completions.create(
                model=config.DEEPSEEK_MODEL,
                messages=messages,
                max_tokens=max_tokens,
                tools=ALL_TOOLS,
                stream=False,
            )
            
            choice = first_response.choices[0]
            
            # Check if the model wants to call a tool
            if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
                logging.info(f"[DeepSeek] Tool call detected: {len(choice.message.tool_calls)} calls")
                
                # Add the assistant's tool call message
                messages.append(choice.message.model_dump())
                
                # Execute each tool call
                for tool_call in choice.message.tool_calls:
                    tool_name = tool_call.function.name
                    try:
                        tool_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        tool_args = {}
                    
                    logging.info(f"[DeepSeek] Executing tool: {tool_name}({tool_args})")
                    tool_result = await execute_tool_call(tool_name, tool_args)
                    
                    # Add tool result message
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_result,
                    })
                
                # Second call: stream the final response with tool results
                stream = await self.client.chat.completions.create(
                    model=config.DEEPSEEK_MODEL,
                    messages=messages,
                    max_tokens=max_tokens,
                    stream=True,
                )
                
                async for chunk in stream:
                    if chunk.choices and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta
                        if delta.content:
                            yield delta.content
            else:
                # No tool call — yield content directly
                if choice.message.content:
                    yield choice.message.content
                        
        except APIError as e:
             logging.error(f"DeepSeek error: {e}")
        except Exception as e:
            logging.error(f"DeepSeek failed: {type(e).__name__}: {e}")
