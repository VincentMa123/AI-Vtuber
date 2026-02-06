import os
import pickle
import numpy as np
from typing import Optional, List
from sentence_transformers import SentenceTransformer
import logging

_embeddings_cache = None
_model_cache = None


def get_embedding_model():
    global _model_cache
    
    if _model_cache is not None:
        return _model_cache
    
    try:
        _model_cache = SentenceTransformer('LazarusNLP/all-indo-e5-small-v4')
        logging.info("[RAG] Loaded embedding model: LazarusNLP/all-indo-e5-small-v4")
        return _model_cache
    except ImportError:
        logging.error("[RAG] Error: sentence-transformers not installed. Run: pip install sentence-transformers")
        return None
    except Exception as e:
        logging.error(f"[RAG] Error loading embedding model: {e}")
        return None


def _load_query_examples(filename: str) -> List[str]:

    data_dir = os.path.join(os.path.dirname(__file__), "data")
    file_path = os.path.join(data_dir, filename)
    
    examples = []
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        examples.append(line)
            logging.info(f"[RAG] Loaded {len(examples)} examples from {filename}")
        except Exception as e:
            logging.error(f"[RAG] Error loading {filename}: {e}")
    else:
        logging.warning(f"[RAG] Query examples file not found: {file_path}")
    
    return examples


def create_product_embeddings(force_rebuild: bool = False) -> Optional[np.ndarray]:

    global _embeddings_cache
    
    if _embeddings_cache is not None and not force_rebuild:
        return _embeddings_cache
    
    # Get the rag/data directory path
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cache_file = os.path.join(base_dir, "data", "product_embeddings.pkl") # Changed filename to avoid conflict/stale cache
    
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
    
    from .product_search import load_product_dataset
    
    dataset = load_product_dataset()
    products = dataset.get("products", [])
    
    if not products:
        logging.info("[RAG] No products found in dataset")
        return None
    
    product_texts = []
    for product in products:
        # E5 requires "passage: " prefix for documents
        # Proposed format: passage: Category Subcategory Name Description Keywords
        text = f"passage: {product.get('category', '')} {product.get('subcategory', '')} {product.get('name', '')} {product.get('description', '')} {' '.join(product.get('keywords', []))}"
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


_product_example_embeddings = None
_promo_example_embeddings = None

def get_product_query_embeddings():
    
    global _product_example_embeddings
    if _product_example_embeddings is not None:
        return _product_example_embeddings
    
    examples = _load_query_examples("product_queries.md")
    if not examples:
        return None
        
    model = get_embedding_model()
    if model:
        # Symmetric semantic search (query vs query), usually uses 'query: ' for both or no prefix.
        # For E5, standard recommendation for STS is "query: " for both.
        prefixed_examples = [f"query: {ex}" for ex in examples]
        _product_example_embeddings = model.encode(prefixed_examples, convert_to_numpy=True, show_progress_bar=False)
        return _product_example_embeddings
    return None

def get_promotion_query_embeddings():

    global _promo_example_embeddings
    if _promo_example_embeddings is not None:
        return _promo_example_embeddings
    
    examples = _load_query_examples("promotion_queries.md")
    if not examples:
        return None
        
    model = get_embedding_model()
    if model:
        prefixed_examples = [f"query: {ex}" for ex in examples]
        _promo_example_embeddings = model.encode(prefixed_examples, convert_to_numpy=True, show_progress_bar=False)
        return _promo_example_embeddings
    return None

def precompute_detection_embeddings():

    logging.info("[RAG] Pre-computing detection embeddings...")
    get_product_query_embeddings()
    get_promotion_query_embeddings()
