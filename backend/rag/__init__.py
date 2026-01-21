"""RAG module for product search and retrieval-augmented generation."""

from .product_search import (
    search_products_rag,
    detect_product_query,
    detect_promotion_query,
    get_all_promotions,
    initialize_rag,
)
from .formatters import (
    format_products_for_prompt,
    format_promotions_for_prompt,
)

__all__ = [
    "search_products_rag",
    "detect_product_query",
    "detect_promotion_query",
    "get_all_promotions",
    "initialize_rag",
    "format_products_for_prompt",
    "format_promotions_for_prompt",
]
