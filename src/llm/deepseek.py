import logging
import json
from typing import Optional, List, Dict, Any, AsyncGenerator
from openai import AsyncOpenAI, APIError
import core.config as config
import core.utils as utils
from .base import BaseLLMProvider, sanitize_history, build_user_content
from rag.tools import ALL_TOOLS, CHAT_TOOLS, execute_tool_call


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
        image_base64: Optional[Any] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:

        if not self.client:
            logging.error("DeepSeek client not initialized.")
            return
            
        history = history or []
        
        system_prompt = kwargs.get("system_prompt")
        if not system_prompt:
             # Fetch dynamic scroll status for the prompt
             scroll_status = "Middle of page"
             try:
                 from browser.controller import get_browser_controller
                 controller = await get_browser_controller()
                 if controller and controller.page:
                     pos = await controller.get_scroll_position()
                     if pos.get("atBottom"):
                         scroll_status = "At Bottom of page"
                     elif pos.get("atTop"):
                         scroll_status = "At Top of page"
             except Exception as e:
                 logging.warning(f"[DeepSeek] Failed to get scroll status for prompt: {e}")
                 
             system_prompt = utils.get_system_prompt(user_message=message, scroll_status=scroll_status)

        messages = [{"role": "system", "content": system_prompt}]
        
        if history:
            messages.extend(sanitize_history(history))
        
        user_content = build_user_content(message, image_base64)
        messages.append({"role": "user", "content": user_content})
        
        max_tokens = kwargs.get("max_tokens", 512)
        tools = kwargs.get("tools", ALL_TOOLS)

        try:
            # First call: non-streaming with tools to check for tool calls
            first_response = await self.client.chat.completions.create(
                model=config.DEEPSEEK_MODEL,
                messages=messages,
                max_tokens=max_tokens,
                tools=tools,
                stream=False,
            )
            
            if not first_response.choices:
                logging.warning("DeepSeek returned empty choices")
                return
                
            choice = first_response.choices[0]
            tool_calls = getattr(choice.message, "tool_calls", None)
            
            # Check if the model wants to call a tool
            if tool_calls:
                logging.info(f"[DeepSeek] Tool call detected: {len(tool_calls)} calls")
                
                # If there's content in the first message (e.g., transition speech), yield it
                if choice.message.content:
                    yield choice.message.content

                # Add the assistant's tool call message
                messages.append(choice.message.model_dump())
                
                # Execute each tool call
                has_navigated = False
                for tool_call in choice.message.tool_calls:
                    tool_name = tool_call.function.name
                    try:
                        tool_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        tool_args = {}
                    
                    logging.info(f"[DeepSeek] Executing tool: {tool_name}({tool_args})")
                    tool_result = await execute_tool_call(tool_name, tool_args)
                    
                    if tool_name == "navigate_to_page":
                        has_navigated = True

                    # Add tool result message
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_result,
                    })
                
                if has_navigated:
                    # Break here for navigation tools to ensure speech is standalone
                    logging.info("[DeepSeek] Navigation detected, stopping recursion.")
                    return
                
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
