import json
import os
import numpy as np
import logging
from typing import List, Dict, Optional
import re
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


def search_products_rag(query: str, top_k: int = 3, similarity_threshold: float = 0.4) -> List[Dict]:

    model = get_embedding_model()
    if model is None:
        logging.error("[RAG] Error: Embedding model not available")
        return []
    
    product_embeddings = create_product_embeddings()
    if product_embeddings is None:
        logging.error("[RAG] Error: Product embeddings not available")
        return []
    
    # E5 requires "query: " prefix for queries
    query_param = f"query: {query}"
    query_embedding = model.encode([query_param], convert_to_numpy=True)[0]
    
    query_norm = query_embedding / np.linalg.norm(query_embedding)
    product_norms = product_embeddings / np.linalg.norm(product_embeddings, axis=1, keepdims=True)
    
    similarities = np.dot(product_norms, query_norm)
    
    top_indices = np.argsort(similarities)[::-1][:top_k]
    
    dataset = load_product_dataset()
    products = dataset.get("products", [])
    
    if len(products) != len(product_embeddings):
        logging.warning("[RAG] Product count mismatch - embeddings may be stale, rebuilding...")
        product_embeddings = create_product_embeddings(force_rebuild=True)
        if product_embeddings is None:
            return []

    results = []
    
    # Pre-process query terms for keyword boosting
    query_terms = set(re.findall(r'\w+', query.lower()))
    
    for idx in top_indices:
        base_score = float(similarities[idx])
        product = products[idx].copy()
        
        # Check if any query term appears in product keywords
        product_keywords = set([k.lower() for k in product.get('keywords', [])])
        boost = 0.0
        # If we have a direct keyword match, give a significant boost
        if not query_terms.isdisjoint(product_keywords):
            boost = 0.3
            if os.environ.get('RAG_VERBOSE') == '1':
                logging.debug(f"[RAG] Boosting '{product['name']}' by {boost} (keyword match)")
        
        final_score = base_score + boost
        product['_similarity_score'] = final_score
        
        if final_score >= similarity_threshold:
            results.append(product)
            
    # Re-sort based on boosted scores
    results.sort(key=lambda x: x['_similarity_score'], reverse=True)
    
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
        # E5 requires "query: " prefix
        query_param = f"query: {message}"
        message_embedding = model.encode([query_param], convert_to_numpy=True, show_progress_bar=False)[0]
        
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
    
    model = get_embedding_model()
    if model is None:
        return False
    
    try:
        example_embeddings = get_promotion_query_embeddings()
        if example_embeddings is None:
             return False

        # show_progress_bar=False to prevent terminal spam
        # E5 requires "query: " prefix
        query_param = f"query: {message}"
        message_embedding = model.encode([query_param], convert_to_numpy=True, show_progress_bar=False)[0]
        
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
