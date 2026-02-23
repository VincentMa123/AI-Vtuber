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
    
    try:
        service = get_klikindomaret_service()
        result = await service.format_top_result(keyword)
        
        if result is None:
            result = "Tidak ada produk ditemukan"
        
        logger.info(f"[Tools] search_product result: {result[:100] if len(result) > 100 else result}")
        return result
    except Exception as e:
        logger.error(f"[Tools] search_product error: {e}")
        return f"Error searching for product: {str(e)}"
