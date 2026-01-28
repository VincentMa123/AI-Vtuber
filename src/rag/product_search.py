import json
import os
import numpy as np
import logging
from typing import List, Dict, Optional
from .embeddings import (
    get_embedding_model, create_product_embeddings, 
    precompute_detection_embeddings, get_product_query_embeddings,
    get_promotion_query_embeddings)

def load_product_dataset() -> Dict:

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

    if not query or not query.strip():
        return []
    
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

    dataset = load_product_dataset()
    return dataset.get("promotions", [])


def detect_product_query(message: str, threshold: float = 0.4) -> bool:

    if not message or len(message.strip()) < 3:
        return False
    
    model = get_embedding_model()
    if model is None:
        return False
    try:
        example_embeddings = get_product_query_embeddings()
        if example_embeddings is None:
             return False

        # show_progress_bar=False to prevent terminal spam
        message_embedding = model.encode([message], convert_to_numpy=True, show_progress_bar=False)[0]
        
        message_norm = message_embedding / np.linalg.norm(message_embedding)
        example_norms = example_embeddings / np.linalg.norm(example_embeddings, axis=1, keepdims=True)
        similarities = np.dot(example_norms, message_norm)
        

        max_similarity = np.max(similarities)
        
        if os.environ.get('RAG_VERBOSE') == '1':
            logging.debug(f"[RAG] Product query detection: '{message}' -> similarity: {max_similarity:.3f}")
        
        return max_similarity >= threshold
    except Exception as e:
        logging.error(f"[RAG] Error in semantic product detection: {e}")
        return False


def detect_promotion_query(message: str, threshold: float = 0.4) -> bool:

    if not message or len(message.strip()) < 3:
        return False
    
    model = get_embedding_model()
    if model is None:
        return False
    
    try:
        example_embeddings = get_promotion_query_embeddings()
        if example_embeddings is None:
             return False

        # show_progress_bar=False to prevent terminal spam
        message_embedding = model.encode([message], convert_to_numpy=True, show_progress_bar=False)[0]
        
        message_norm = message_embedding / np.linalg.norm(message_embedding)
        
        # Safe normalization for examples
        example_norms = example_embeddings / np.linalg.norm(example_embeddings, axis=1, keepdims=True)
        similarities = np.dot(example_norms, message_norm)
        
        max_similarity = np.max(similarities)
        
        if os.environ.get('RAG_VERBOSE') == '1':
            logging.debug(f"[RAG] Promotion query detection: '{message}' -> similarity: {max_similarity:.3f}")
        
        return max_similarity >= threshold
    except Exception as e:
        logging.error(f"[RAG] Error in semantic promotion detection: {e}")
        return False


def initialize_rag():

    logging.info("[RAG] Initializing RAG system...")
    
    model = get_embedding_model()
    if model is None:
        logging.warning("[RAG] Warning: Could not load embedding model")
        return False
    
    embeddings = create_product_embeddings()
    if embeddings is None:
        logging.warning("[RAG] Warning: Could not load product embeddings")
        return False

    # Trigger pre-computation of detection embeddings
    precompute_detection_embeddings()
    
    logging.info(f"[RAG] ✓ Ready! Model and {len(embeddings)} product embeddings loaded")
    return True
