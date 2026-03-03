import logging

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


WEBPAGE_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search_website",
        "description": "Cari informasi detail di blog atau artikel website. Gunakan saat user bertanya tentang info perusahaan, layanan, atau topik yang ada di website.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Pertanyaan atau kata kunci pencarian, contoh: 'apa itu cybersecurity?', 'layanan apa saja yang ada?'"
                }
            },
            "required": ["query"]
        }
    }
}

NAVIGATE_PAGE_TOOL = {
    "type": "function",
    "function": {
        "name": "navigate_to_page",
        "description": "Berpindah ke halaman lain di website. WAJIB digunakan saat posisi scroll sudah 'At Bottom' untuk melanjutkan stream ke section baru. DILARANG navigasi jika masih di tengah halaman.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL lengkap halaman yang ingin dituju (WAJIB ambil dari sitemap)."
                }
            },
            "required": ["url"]
        }
    }
}

ALL_TOOLS = [PRODUCT_SEARCH_TOOL, WEBPAGE_SEARCH_TOOL, NAVIGATE_PAGE_TOOL]

CHAT_TOOLS = [PRODUCT_SEARCH_TOOL, WEBPAGE_SEARCH_TOOL]


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
    elif tool_name == "search_website":
        return await _handle_search_website(arguments)
    elif tool_name == "navigate_to_page":
        return await _handle_navigate_to_page(arguments)
    else:
        logger.warning(f"[Tools] Unknown tool: {tool_name}")
        return f"Error: Unknown tool '{tool_name}'"


async def _handle_search_product(arguments: dict) -> str:
    """Handle the search_product tool call."""
    keyword = arguments.get("keyword", "")
    
    if not keyword:
        return "Error: keyword is required"
    
    
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


async def _handle_search_website(arguments: dict) -> str:
    """Handle the search_website tool call."""
    query = arguments.get("query", "")
    if not query:
        return "Error: query is required"

    from .indexer import WebsiteIndexer
    try:
        indexer = WebsiteIndexer()
        results = indexer.search(query)
        
        if not results:
            return "Tidak ada informasi relevan ditemukan di website."
            
        formatted_results = []
        for r in results:
            formatted_results.append(f"Source: {r['title']} ({r['url']})\nContent: {r['content']}")
            
        return "\n---\n".join(formatted_results)
    except Exception as e:
        logger.error(f"[Tools] search_website error: {e}")
        return f"Error searching website: {str(e)}"


async def _handle_navigate_to_page(arguments: dict) -> str:
    """Handle the navigate_to_page tool call."""
    url = arguments.get("url", "")
    if not url:
        return "Error: url is required"

    from browser.controller import get_browser_controller
    try:
        controller = await get_browser_controller()
        if not controller:
            return "Error: Browser controller not initialized"
            
        success = await controller.navigate_to_page(url)
        if success:
            return f"Berhasil pindah ke halaman: {url}"
        else:
            return f"Gagal pindah ke halaman: {url}"
    except Exception as e:
        logger.error(f"[Tools] navigate_to_page error: {e}")
        return f"Error navigating: {str(e)}"
