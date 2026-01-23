import json
import os
import numpy as np
import logging
from typing import List, Dict, Optional


def load_product_dataset() -> Dict:
    """Load the product dataset from rag/data/product_dataset.json."""
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(base_dir, "data", "product_dataset.json")
        
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data
    except Exception as e:
        logging.error(f"[RAG] Error loading product dataset: {e}")
        return {"products": [], "categories": [], "promotions": []}


def search_products_rag(query: str, top_k: int = 3, similarity_threshold: float = 0.3) -> List[Dict]:
    """
    Search for products using RAG (semantic search with embeddings).
    
    Args:
        query: Search query
        top_k: Number of top results to return
        similarity_threshold: Minimum similarity score (0-1)
        
    Returns:
        List of matching products with similarity scores
    """
    if not query or not query.strip():
        return []
    
    from .embeddings import get_embedding_model, create_product_embeddings
    
    model = get_embedding_model()
    if model is None:
        logging.error("[RAG] Error: Embedding model not available")
        return []
    
    product_embeddings = create_product_embeddings()
    if product_embeddings is None:
        logging.error("[RAG] Error: Product embeddings not available")
        return []
    
    query_embedding = model.encode([query], convert_to_numpy=True)[0]
    
    query_norm = query_embedding / np.linalg.norm(query_embedding)
    product_norms = product_embeddings / np.linalg.norm(product_embeddings, axis=1, keepdims=True)
    
    similarities = np.dot(product_norms, query_norm)
    
    top_indices = np.argsort(similarities)[::-1][:top_k]
    
    dataset = load_product_dataset()
    products = dataset.get("products", [])
    
    results = []
    for idx in top_indices:
        if similarities[idx] >= similarity_threshold:
            product = products[idx].copy()
            product['_similarity_score'] = float(similarities[idx])
            results.append(product)
    
    if os.environ.get('RAG_VERBOSE') == '1':
        logging.debug(f"[RAG] Query: '{query}' -> Found {len(results)} products (threshold: {similarity_threshold})")
        for i, r in enumerate(results):
            logging.debug(f"  {i+1}. {r['name']} (similarity: {r['_similarity_score']:.3f})")
    
    return results


def get_all_promotions() -> List[Dict]:
    """Get all available promotions from the dataset."""
    dataset = load_product_dataset()
    return dataset.get("promotions", [])


def detect_product_query(message: str, threshold: float = 0.4) -> bool:
    """
    Detect if a user message is asking about products using semantic similarity.
    
    Args:
        message: User's message
        threshold: Similarity threshold (0-1), default 0.4 for better recall
    
    Returns:
        True if message is likely about products
    """
    if not message or len(message.strip()) < 3:
        return False
    
    from .embeddings import get_embedding_model
    
    model = get_embedding_model()
    if model is None:
        # Fallback to simple keyword matching if model unavailable
        keywords = ["produk", "beli", "harga", "rekomendasi", "product", "buy", "price"]
        return any(keyword in message.lower() for keyword in keywords)
    
    product_examples = [
        "Ada produk susu apa?",
        "Berapa harga snack?",
        
        "Mau beli sabun",
        "Butuh deterjen",
        "Pengen beli minyak goreng",
        
        "Cari vitamin murah",
        "Rekomendasi shampo dong",
        
        "What products do you have?",
        "Do you sell bread?",
        
        "I need to buy milk",
        "Looking for cooking oil",
        
        "Show me some snacks",
        "I'm looking for toothpaste"
    ]
    
    try:
        message_embedding = model.encode([message], convert_to_numpy=True)[0]
        example_embeddings = model.encode(product_examples, convert_to_numpy=True)
        
        message_norm = message_embedding / np.linalg.norm(message_embedding)
        example_norms = example_embeddings / np.linalg.norm(example_embeddings, axis=1, keepdims=True)
        similarities = np.dot(example_norms, message_norm)
        

        max_similarity = np.max(similarities)
        
        if os.environ.get('RAG_VERBOSE') == '1':
            logging.debug(f"[RAG] Product query detection: '{message}' -> similarity: {max_similarity:.3f}")
        
        return max_similarity >= threshold
    except Exception as e:
        logging.error(f"[RAG] Error in semantic product detection: {e}")
        # Fallback to keyword matching
        keywords = ["produk", "beli", "harga", "rekomendasi", "product", "buy", "price"]
        return any(keyword in message.lower() for keyword in keywords)


def detect_promotion_query(message: str, threshold: float = 0.4) -> bool:
    """
    Detect if a user message is asking about promotions using semantic similarity.
    
    Args:
        message: User's message
        threshold: Similarity threshold (0-1), default 0.4 for better recall
    
    Returns:
        True if message is likely about promotions
    """
    if not message or len(message.strip()) < 3:
        return False
    
    from .embeddings import get_embedding_model
    
    model = get_embedding_model()
    if model is None:
        # Fallback to keyword matching
        keywords = ["promo", "diskon", "discount", "sale", "offer"]
        return any(keyword in message.lower() for keyword in keywords)
    
    promo_examples = [
        "Ada promo apa hari ini?",
        "Diskon apa yang tersedia?",
        "Penawaran spesial dong",
        "Promo heboh bulan ini",
        "Ada hadiah gratis?",
        "What promotions are available?",
        "Any discounts today?",
        "Special offers?",
        "Current sales?"
    ]
    
    try:
        message_embedding = model.encode([message], convert_to_numpy=True)[0]
        example_embeddings = model.encode(promo_examples, convert_to_numpy=True)
        
        message_norm = message_embedding / np.linalg.norm(message_embedding)
        example_norms = example_embeddings / np.linalg.norm(example_embeddings, axis=1, keepdims=True)
        similarities = np.dot(example_norms, message_norm)
        
        max_similarity = np.max(similarities)
        
        if os.environ.get('RAG_VERBOSE') == '1':
            logging.debug(f"[RAG] Promotion query detection: '{message}' -> similarity: {max_similarity:.3f}")
        
        return max_similarity >= threshold
    except Exception as e:
        logging.error(f"[RAG] Error in semantic promotion detection: {e}")
        keywords = ["promo", "diskon", "discount", "sale", "offer"]
        return any(keyword in message.lower() for keyword in keywords)


def initialize_rag():

    logging.info("[RAG] Initializing RAG system...")
    
    from .embeddings import get_embedding_model, create_product_embeddings
    
    model = get_embedding_model()
    if model is None:
        logging.warning("[RAG] Warning: Could not load embedding model")
        return False
    
    embeddings = create_product_embeddings()
    if embeddings is None:
        logging.warning("[RAG] Warning: Could not load product embeddings")
        return False
    
    logging.info(f"[RAG] ✓ Ready! Model and {len(embeddings)} product embeddings loaded")
    return True
