import logging
import json
from typing import Optional, List, Dict, Any, AsyncGenerator
from openai import AsyncOpenAI, APIError
import core.config as config
import core.utils as utils
from .base import BaseLLMProvider, sanitize_history, build_user_content
from rag.tools import ALL_TOOLS, CHAT_TOOLS, execute_tool_call

class QwenProvider(BaseLLMProvider):
    
    def __init__(self):
        self.api_key = config.QWEN_API_KEY
        self.base_url = config.QWEN_BASE_URL
        self.model = config.QWEN_MODEL
        self.client = None
        
        if self.api_key and self.base_url:
            self.client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        else:
            logging.warning("Qwen API key or Base URL not configured.")
    
    async def generate_stream(
        self, 
        message: str, 
        history: Optional[List[Dict[str, Any]]] = None, 
        image_base64: Optional[Any] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:

        if not self.client:
            logging.error("Qwen client not initialized.")
            return

        history = history or []
        
        user_content = build_user_content(message, image_base64)
        
        system_prompt = kwargs.get("system_prompt")
        if not system_prompt:
             system_prompt = utils.get_system_prompt(user_message=message)

        messages = [{"role": "system", "content": system_prompt}]
        
        if history:
            messages.extend(sanitize_history(history))
        
        messages.append({
            "role": "user", 
            "content": user_content
        })
        
        max_tokens = kwargs.get("max_tokens", 512)
        tools = kwargs.get("tools", ALL_TOOLS)

        try:
            # First call: determine if it needs tools
            first_response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                tools=tools,
                stream=False,
            )
            
            if not first_response.choices:
                return
                
            choice = first_response.choices[0]
            tool_calls = getattr(choice.message, "tool_calls", None)
            
            if tool_calls:
                logging.info(f"[Qwen] Tool call detected: {len(tool_calls)} calls")
                
                # Check if any tool call is a navigation action
                has_navigation = any(
                    tc.function.name == "navigate_to_page" for tc in tool_calls
                )
                
                if has_navigation:
                    # For navigation: always force a dedicated transition speech.
                    # We discard whatever text the model returned (it often ignores
                    # the "only say the transition" instruction) and instead make
                    # a focused call that only asks for a short farewell sentence.
                    logging.info("[Qwen] Navigation tool detected — forcing transition speech")
                    transition_messages = [
                        {"role": "system", "content": (
                            "Kamu adalah Mora, seorang VTuber yang sedang livestream. "
                            "Kamu baru saja selesai menjelaskan sebuah halaman web dan akan pindah ke halaman berikutnya. "
                            "Ucapkan SATU kalimat singkat transisi untuk memberitahu penonton bahwa kamu akan pindah ke section berikutnya. "
                            "Variasikan gaya bicaramu setiap kali. Jangan pakai simbol apapun."
                        )},
                        {"role": "user", "content": "Ucapkan kalimat transisi singkat."}
                    ]
                    speech_stream = await self.client.chat.completions.create(
                        model=self.model,
                        messages=transition_messages,
                        max_tokens=100,
                        stream=True,
                    )
                    async for chunk in speech_stream:
                        if chunk.choices and len(chunk.choices) > 0:
                            delta = chunk.choices[0].delta
                            if delta.content:
                                yield delta.content
                else:
                    # For non-navigation tools: use model's text if available,
                    # otherwise force text generation from the original context
                    if choice.message.content:
                        yield choice.message.content
                    else:
                        logging.info("[Qwen] No text with tool call — forcing text generation via tool_choice='none'")
                        speech_stream = await self.client.chat.completions.create(
                            model=self.model,
                            messages=messages,
                            max_tokens=max_tokens,
                            tool_choice="none",
                            stream=True,
                        )
                        async for chunk in speech_stream:
                            if chunk.choices and len(chunk.choices) > 0:
                                delta = chunk.choices[0].delta
                                if delta.content:
                                    yield delta.content

                # Execute all tool calls
                messages.append(choice.message.model_dump())
                
                for tool_call in choice.message.tool_calls:
                    tool_name = tool_call.function.name
                    try:
                        tool_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        tool_args = {}
                    
                    logging.info(f"[Qwen] Executing tool: {tool_name}({tool_args})")
                    tool_result = await execute_tool_call(tool_name, tool_args)
                        
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_result,
                    })
                
                if has_navigation:
                    logging.info("[Qwen] Navigation detected, stopping recursion.")
                    return

                # Second call: stream the final response
                stream = await self.client.chat.completions.create(
                    model=self.model,
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
                if choice.message.content:
                    yield choice.message.content
                        
        except APIError as e:
             logging.error(f"Qwen streaming error: {e}")
        except Exception as e:
            logging.error(f"Qwen streaming failed: {type(e).__name__}: {e}")
