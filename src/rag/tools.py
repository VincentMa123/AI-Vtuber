"""
Tool definitions for LLM function calling.
Defines the product search tool and handles tool call execution.
"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


PRODUCT_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search_product",
        "description": "Cari harga dan detail produk di Indomaret/Klikindomaret. Gunakan saat user bertanya tentang harga produk, ketersediaan, atau rekomendasi produk.",
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "Kata kunci pencarian produk, contoh: 'susu', 'mie instan', 'sabun', 'rinso'"
                }
            },
            "required": ["keyword"]
        }
    }
}

ALL_TOOLS = [PRODUCT_SEARCH_TOOL]


async def execute_tool_call(tool_name: str, arguments: dict) -> str:
    """
    Execute a tool call and return the result as a string.
    
    Args:
        tool_name: Name of the tool to execute
        arguments: Tool arguments as a dict
        
    Returns:
        Tool result as a string for the LLM
    """
    if tool_name == "search_product":
        return await _handle_search_product(arguments)
    else:
        logger.warning(f"[Tools] Unknown tool: {tool_name}")
        return f"Error: Unknown tool '{tool_name}'"


async def _handle_search_product(arguments: dict) -> str:
    """Handle the search_product tool call."""
    keyword = arguments.get("keyword", "")
    
    if not keyword:
        return "Error: keyword is required"
    
    logger.info(f"[Tools] Executing search_product(keyword='{keyword}')")
    
    from .klikindomaret_service import get_klikindomaret_service
    
    service = get_klikindomaret_service()
    result = await service.format_top_result(keyword)
    
    logger.info(f"[Tools] search_product result: {result[:100]}...")
    return result


def parse_tool_calls_from_sse(data: dict) -> Optional[list]:
    """
    Parse tool calls from an SSE response chunk (for httpx-based providers like DeepSeek).
    
    Returns list of tool calls if present, None otherwise.
    """
    if "choices" not in data or not data["choices"]:
        return None
    
    choice = data["choices"][0]
    
    # Check finish_reason
    if choice.get("finish_reason") == "tool_calls":
        message = choice.get("message", {})
        tool_calls = message.get("tool_calls", [])
        if tool_calls:
            return tool_calls
    
    # Check delta for streaming
    delta = choice.get("delta", {})
    tool_calls = delta.get("tool_calls", [])
    if tool_calls:
        return tool_calls
    
    return None
