import os
import pickle
import numpy as np
from typing import Optional
from sentence_transformers import SentenceTransformer
import logging

_embeddings_cache = None
_model_cache = None


def get_embedding_model():
    global _model_cache
    
    if _model_cache is not None:
        return _model_cache
    
    try:
        _model_cache = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        logging.info("[RAG] Loaded embedding model: paraphrase-multilingual-MiniLM-L12-v2")
        return _model_cache
    except ImportError:
        logging.error("[RAG] Error: sentence-transformers not installed. Run: pip install sentence-transformers")
        return None
    except Exception as e:
        logging.error(f"[RAG] Error loading embedding model: {e}")
        return None


def create_product_embeddings(force_rebuild: bool = False) -> Optional[np.ndarray]:

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
                logging.info(f"[RAG] Loaded {len(_embeddings_cache)} product embeddings from cache")
                return _embeddings_cache
        except Exception as e:
            logging.error(f"[RAG] Error loading cached embeddings: {e}")
    
    model = get_embedding_model()
    if model is None:
        return None
    
    # Import here to avoid circular dependency
    from .product_search import load_product_dataset
    
    dataset = load_product_dataset()
    products = dataset.get("products", [])
    
    if not products:
        logging.info("[RAG] No products found in dataset")
        return None
    
    product_texts = []
    for product in products:
        text = f"{product.get('name', '')} {product.get('description', '')} {' '.join(product.get('keywords', []))}"
        product_texts.append(text)
    
    logging.info(f"[RAG] Creating embeddings for {len(product_texts)} products...")
    embeddings = model.encode(product_texts, show_progress_bar=True, convert_to_numpy=True)
    
    _embeddings_cache = embeddings
    
    try:
        with open(cache_file, 'wb') as f:
            pickle.dump(embeddings, f)
        logging.info(f"[RAG] Saved embeddings to {cache_file}")
    except Exception as e:
        logging.error(f"[RAG] Warning: Could not save embeddings to disk: {e}")
    

    
    return embeddings


PRODUCT_QUERY_EXAMPLES = [
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

PROMOTION_QUERY_EXAMPLES = [
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

_product_example_embeddings = None
_promo_example_embeddings = None

def get_product_query_embeddings():
    """Get or compute embeddings for product query examples."""
    global _product_example_embeddings
    if _product_example_embeddings is not None:
        return _product_example_embeddings
        
    model = get_embedding_model()
    if model:
        _product_example_embeddings = model.encode(PRODUCT_QUERY_EXAMPLES, convert_to_numpy=True, show_progress_bar=False)
        return _product_example_embeddings
    return None

def get_promotion_query_embeddings():
    """Get or compute embeddings for promotion query examples."""
    global _promo_example_embeddings
    if _promo_example_embeddings is not None:
        return _promo_example_embeddings
        
    model = get_embedding_model()
    if model:
        _promo_example_embeddings = model.encode(PROMOTION_QUERY_EXAMPLES, convert_to_numpy=True, show_progress_bar=False)
        return _promo_example_embeddings
    return None

def precompute_detection_embeddings():
    """Trigger computation of detection embeddings (call during init)."""
    logging.info("[RAG] Pre-computing detection embeddings...")
    get_product_query_embeddings()
    get_promotion_query_embeddings()

