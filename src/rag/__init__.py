"""RAG module — live product search via Klikindomaret API + tool calling."""

import os

_RAG_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(_RAG_DATA_DIR, exist_ok=True)
CRAWL_RESULT_PATH = os.path.join(_RAG_DATA_DIR, "crawl_result.json")
WEBSITE_INDEX_PATH = os.path.join(_RAG_DATA_DIR, "website_index.json")

from .klikindomaret_service import (
    KlikindomaretService,
    get_klikindomaret_service,
    set_waf_token,
    get_waf_token,
)
from .tools import (
    ALL_TOOLS,
    execute_tool_call,
    PRODUCT_SEARCH_TOOL,
)

__all__ = [
    # Live API service
    "KlikindomaretService",
    "get_klikindomaret_service",
    "set_waf_token",
    "get_waf_token",
    # Tool calling
    "ALL_TOOLS",
    "execute_tool_call",
    "PRODUCT_SEARCH_TOOL",
]
