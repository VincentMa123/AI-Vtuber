import os
import pickle
import numpy as np
from typing import Optional
from sentence_transformers import SentenceTransformer

_embeddings_cache = None
_model_cache = None


def get_embedding_model():
    """Get or load the embedding model."""
    global _model_cache
    
    if _model_cache is not None:
        return _model_cache
    
    try:
        _model_cache = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        print("[RAG] Loaded embedding model: paraphrase-multilingual-MiniLM-L12-v2")
        return _model_cache
    except ImportError:
        print("[RAG] Error: sentence-transformers not installed. Run: pip install sentence-transformers")
        return None
    except Exception as e:
        print(f"[RAG] Error loading embedding model: {e}")
        return None


def create_product_embeddings(force_rebuild: bool = False) -> Optional[np.ndarray]:
    """
    Create embeddings for all products and cache them.
    
    Args:
        force_rebuild: If True, rebuild embeddings even if cache exists
    
    Returns:
        Numpy array of embeddings, shape (num_products, embedding_dim)
    """
    global _embeddings_cache
    
    if _embeddings_cache is not None and not force_rebuild:
        return _embeddings_cache
    
    # Get the rag/data directory path
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cache_file = os.path.join(base_dir, "data", "product_embeddings.pkl")
    
    if os.path.exists(cache_file) and not force_rebuild:
        try:
            with open(cache_file, 'rb') as f:
                _embeddings_cache = pickle.load(f)
                print(f"[RAG] Loaded {len(_embeddings_cache)} product embeddings from cache")
                return _embeddings_cache
        except Exception as e:
            print(f"[RAG] Error loading cached embeddings: {e}")
    
    model = get_embedding_model()
    if model is None:
        return None
    
    # Import here to avoid circular dependency
    from .product_search import load_product_dataset
    
    dataset = load_product_dataset()
    products = dataset.get("products", [])
    
    if not products:
        print("[RAG] No products found in dataset")
        return None
    
    product_texts = []
    for product in products:
        text = f"{product.get('name', '')} {product.get('description', '')} {' '.join(product.get('keywords', []))}"
        product_texts.append(text)
    
    print(f"[RAG] Creating embeddings for {len(product_texts)} products...")
    embeddings = model.encode(product_texts, show_progress_bar=True, convert_to_numpy=True)
    
    _embeddings_cache = embeddings
    
    try:
        with open(cache_file, 'wb') as f:
            pickle.dump(embeddings, f)
        print(f"[RAG] Saved embeddings to {cache_file}")
    except Exception as e:
        print(f"[RAG] Warning: Could not save embeddings to disk: {e}")
    
    return embeddings
