"""RAG module — live product search via Klikindomaret API + tool calling."""

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
