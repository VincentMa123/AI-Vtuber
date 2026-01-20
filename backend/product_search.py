"""
RAG-based product search using embeddings for semantic similarity.
Provides better search results by understanding meaning, not just keywords.
"""

import json
import os
import numpy as np
from typing import List, Dict, Optional
import pickle

# Cache for embeddings and model
_embeddings_cache = None
_model_cache = None

def get_embedding_model():
    """Load and cache the sentence transformer model."""
    global _model_cache
    
    if _model_cache is not None:
        return _model_cache
    
    try:
        from sentence_transformers import SentenceTransformer
        # Using a lightweight multilingual model (supports Indonesian + English)
        # Model size: ~120MB, good balance of speed and quality
        _model_cache = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        print("[RAG] Loaded embedding model: paraphrase-multilingual-MiniLM-L12-v2")
        return _model_cache
    except ImportError:
        print("[RAG] Error: sentence-transformers not installed. Run: pip install sentence-transformers")
        return None
    except Exception as e:
        print(f"[RAG] Error loading embedding model: {e}")
        return None

def load_product_dataset() -> Dict:
    """Load the product dataset from JSON."""
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(base_dir, "product_dataset.json")
        
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data
    except Exception as e:
        print(f"[RAG] Error loading product dataset: {e}")
        return {"products": [], "categories": [], "promotions": []}

def create_product_embeddings(force_rebuild: bool = False) -> Optional[np.ndarray]:
    """
    Create embeddings for all products and cache them.
    
    Args:
        force_rebuild: If True, rebuild embeddings even if cache exists
    
    Returns:
        Numpy array of embeddings, shape (num_products, embedding_dim)
    """
    global _embeddings_cache
    
    # Check if embeddings are already cached in memory
    if _embeddings_cache is not None and not force_rebuild:
        return _embeddings_cache
    
    # Check if embeddings are saved to disk
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cache_file = os.path.join(base_dir, "product_embeddings.pkl")
    
    if os.path.exists(cache_file) and not force_rebuild:
        try:
            with open(cache_file, 'rb') as f:
                _embeddings_cache = pickle.load(f)
                print(f"[RAG] Loaded {len(_embeddings_cache)} product embeddings from cache")
                return _embeddings_cache
        except Exception as e:
            print(f"[RAG] Error loading cached embeddings: {e}")
    
    # Create new embeddings
    model = get_embedding_model()
    if model is None:
        return None
    
    dataset = load_product_dataset()
    products = dataset.get("products", [])
    
    if not products:
        print("[RAG] No products found in dataset")
        return None
    
    # Create text representations for each product
    product_texts = []
    for product in products:
        # Combine name, description, and keywords for rich semantic representation
        text = f"{product.get('name', '')} {product.get('description', '')} {' '.join(product.get('keywords', []))}"
        product_texts.append(text)
    
    print(f"[RAG] Creating embeddings for {len(product_texts)} products...")
    embeddings = model.encode(product_texts, show_progress_bar=True, convert_to_numpy=True)
    
    # Cache to memory
    _embeddings_cache = embeddings
    
    # Save to disk for faster loading next time
    try:
        with open(cache_file, 'wb') as f:
            pickle.dump(embeddings, f)
        print(f"[RAG] Saved embeddings to {cache_file}")
    except Exception as e:
        print(f"[RAG] Warning: Could not save embeddings to disk: {e}")
    
    return embeddings

def search_products_rag(query: str, top_k: int = 3, similarity_threshold: float = 0.3) -> List[Dict]:
    """
    Search for products using semantic similarity (RAG approach).
    
    Args:
        query: Search query string
        top_k: Number of top results to return
        similarity_threshold: Minimum similarity score (0-1) to include results
    
    Returns:
        List of product dictionaries sorted by semantic similarity
    """
    if not query or not query.strip():
        return []
    
    model = get_embedding_model()
    if model is None:
        print("[RAG] Error: Embedding model not available")
        return []
    
    # Get or create product embeddings
    product_embeddings = create_product_embeddings()
    if product_embeddings is None:
        print("[RAG] Error: Product embeddings not available")
        return []
    
    # Encode the query
    query_embedding = model.encode([query], convert_to_numpy=True)[0]
    
    # Calculate cosine similarity
    # Normalize vectors
    query_norm = query_embedding / np.linalg.norm(query_embedding)
    product_norms = product_embeddings / np.linalg.norm(product_embeddings, axis=1, keepdims=True)
    
    # Compute similarities
    similarities = np.dot(product_norms, query_norm)
    
    # Get top K indices
    top_indices = np.argsort(similarities)[::-1][:top_k]
    
    # Filter by threshold and get products
    dataset = load_product_dataset()
    products = dataset.get("products", [])
    
    results = []
    for idx in top_indices:
        if similarities[idx] >= similarity_threshold:
            product = products[idx].copy()
            product['_similarity_score'] = float(similarities[idx])
            results.append(product)
    
    # Only log if verbose mode or first few queries
    if os.environ.get('RAG_VERBOSE') == '1':
        print(f"[RAG] Query: '{query}' -> Found {len(results)} products (threshold: {similarity_threshold})")
        for i, r in enumerate(results):
            print(f"  {i+1}. {r['name']} (similarity: {r['_similarity_score']:.3f})")
    
    return results

def format_products_for_prompt(products: List[Dict]) -> str:
    """
    Format a list of products into readable text for LLM context.
    Same as the simple search version.
    """
    if not products:
        return ""
    
    formatted = "\n## Relevant Indomaret Products:\n"
    
    for i, product in enumerate(products, 1):
        name = product.get("name", "Unknown Product")
        price = product.get("price", 0)
        description = product.get("description", "")
        
        # Format price with thousand separators
        price_formatted = f"Rp {price:,}"
        
        formatted += f"{i}. **{name}** - {price_formatted}\n"
        formatted += f"   {description}\n"
    
    formatted += "\nFeel free to recommend these products naturally in your response!\n"
    
    return formatted

def get_all_promotions() -> List[Dict]:
    """Get all available promotions from the dataset."""
    dataset = load_product_dataset()
    return dataset.get("promotions", [])

def format_promotions_for_prompt(promotions: List[Dict]) -> str:
    """Format promotions into readable text for LLM context."""
    if not promotions:
        return ""
    
    formatted = "\n## Current Indomaret Promotions:\n"
    
    for i, promo in enumerate(promotions, 1):
        promo_type = promo.get("type", "Unknown Promo")
        description = promo.get("description", "")
        time_range = promo.get("time_range", "")
        
        formatted += f"{i}. **{promo_type}**"
        if time_range:
            formatted += f" ({time_range})"
        formatted += f"\n   {description}\n"
    
    formatted += "\nShare these promotions naturally with viewers!\n"
    
    return formatted

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
    
    # Pre-load the embedding model
    model = get_embedding_model()
    if model is None:
        print("[RAG] Warning: Could not load embedding model")
        return False
    
    # Pre-load embeddings
    embeddings = create_product_embeddings()
    if embeddings is None:
        print("[RAG] Warning: Could not load product embeddings")
        return False
    
    print(f"[RAG] ✓ Ready! Model and {len(embeddings)} product embeddings loaded")
    return True

# Test function
if __name__ == "__main__":
    print("=== RAG Product Search Test ===\n")
    
    # Test 1: Create embeddings
    print("1. Creating product embeddings...")
    embeddings = create_product_embeddings()
    if embeddings is not None:
        print(f"   Created {len(embeddings)} embeddings, dimension: {embeddings.shape[1]}\n")
    
    # Test 2: Semantic search examples
    test_queries = [
        "popok bayi",  # Should find Merries diapers
        "vitamin untuk daya tahan tubuh",  # Should find CDR, Redoxon
        "minuman segar",  # Should find drinks
        "pembersih pakaian",  # Should find Rinso
        "susu frisian flag",  # Should find Frisian Flag
    ]
    
    for query in test_queries:
        print(f"Query: '{query}'")
        results = search_products_rag(query, top_k=3)
        if results:
            for r in results:
                print(f"  - {r['name']} (score: {r.get('_similarity_score', 0):.3f})")
        else:
            print("  No results found")
        print()
