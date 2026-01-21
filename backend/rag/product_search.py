import json
import os
import numpy as np
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
        print(f"[RAG] Error loading product dataset: {e}")
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
        print("[RAG] Error: Embedding model not available")
        return []
    
    product_embeddings = create_product_embeddings()
    if product_embeddings is None:
        print("[RAG] Error: Product embeddings not available")
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
        print(f"[RAG] Query: '{query}' -> Found {len(results)} products (threshold: {similarity_threshold})")
        for i, r in enumerate(results):
            print(f"  {i+1}. {r['name']} (similarity: {r['_similarity_score']:.3f})")
    
    return results


def get_all_promotions() -> List[Dict]:
    """Get all available promotions from the dataset."""
    dataset = load_product_dataset()
    return dataset.get("promotions", [])


def detect_product_query(message: str) -> bool:
    """Detect if a user message is asking about products."""
    if not message:
        return False
    
    message_lower = message.lower()
    
    # Indonesian + English product keywords
    keywords = [
        "produk", "beli", "jual", "harga", "promo", "diskon", 
        "rekomendasi", "ada", "cari", "butuh", "mau",
        "susu", "snack", "vitamin", "sabun", "deterjen", "minyak",
        "minuman", "makanan", "popok", "bayi", "obat", "roti",
        "product", "buy", "price", "recommend", "discount", 
        "need", "want", "looking for", "sell"
    ]
    
    return any(keyword in message_lower for keyword in keywords)


def detect_promotion_query(message: str) -> bool:
    """Detect if a user message is specifically asking about promotions."""
    if not message:
        return False
    
    message_lower = message.lower()
    
    promo_keywords = [
        "promo", "promosi", "diskon", "discount", "sale",
        "penawaran", "offer", "deal", "heboh", "gratis",
        "hadiah", "gift", "umroh"
    ]
    
    return any(keyword in message_lower for keyword in promo_keywords)


def initialize_rag():
    """
    Initialize RAG system by pre-loading model and embeddings.
    Call this once at backend startup for better performance.
    """
    print("[RAG] Initializing RAG system...")
    
    from .embeddings import get_embedding_model, create_product_embeddings
    
    model = get_embedding_model()
    if model is None:
        print("[RAG] Warning: Could not load embedding model")
        return False
    
    embeddings = create_product_embeddings()
    if embeddings is None:
        print("[RAG] Warning: Could not load product embeddings")
        return False
    
    print(f"[RAG] ✓ Ready! Model and {len(embeddings)} product embeddings loaded")
    return True
