import json
import os
import numpy as np
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer
import logging

logger = logging.getLogger(__name__)

class WebsiteIndexer:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", index_path: str = "website_index.json"):
        self.model_name = model_name
        self.index_path = index_path
        self._model: Optional[SentenceTransformer] = None
        self.chunks: List[Dict[str, Any]] = []
        self.embeddings: Optional[np.ndarray] = None

    @property
    def model(self):
        if self._model is None:
            logger.info(f"[Indexer] Loading model {self.model_name}...")
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def chunk_text(self, text: str, url: str, title: str, chunk_size: int = 1000, overlap: int = 100) -> List[Dict[str, Any]]:
        """Splits text into smaller chunks with overlap."""
        chunks = []
        if not text:
            return chunks
            
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk_content = text[start:end]
            
            chunks.append({
                "url": url,
                "title": title,
                "content": chunk_content
            })
            
            if end >= len(text):
                break
            start += chunk_size - overlap
            
        return chunks

    def build_index(self, crawl_result_path: str):
        """Processes crawl results, chunks content, and generates embeddings."""
        if not os.path.exists(crawl_result_path):
            logger.error(f"[Indexer] Crawl result not found: {crawl_result_path}")
            return

        with open(crawl_result_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        content_list = data.get("content", [])
        all_chunks = []
        
        logger.info(f"[Indexer] Chunking content from {len(content_list)} pages...")
        for item in content_list:
            item_chunks = self.chunk_text(item["content"], item["url"], item["title"])
            all_chunks.extend(item_chunks)

        if not all_chunks:
            logger.warning("[Indexer] No content to index.")
            return

        self.chunks = all_chunks
        texts = [c["content"] for c in all_chunks]
        
        logger.info(f"[Indexer] Generating embeddings for {len(texts)} chunks...")
        self.embeddings = self.model.encode(texts, convert_to_numpy=True)
        
        # Save to file
        self.save_index()

    def save_index(self):
        """Saves chunks and embeddings to disk."""
        if self.embeddings is None:
            return

        data = {
            "chunks": self.chunks,
            # We store embeddings as a list for JSON compatibility, 
            # though it's less efficient than a binary format
            "embeddings": self.embeddings.tolist() 
        }
        
        with open(self.index_path, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        logger.info(f"[Indexer] Index saved to {self.index_path}")

    def load_index(self) -> bool:
        """Loads index from disk."""
        if not os.path.exists(self.index_path):
            return False
            
        with open(self.index_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        self.chunks = data["chunks"]
        self.embeddings = np.array(data["embeddings"])
        logger.info(f"[Indexer] Loaded index with {len(self.chunks)} chunks.")
        return True

    def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Finds the most relevant chunks for a query."""
        if self.embeddings is None:
            if not self.load_index():
                logger.error("[Indexer] No index loaded. Call build_index first.")
                return []

        query_embedding = self.model.encode([query], convert_to_numpy=True)
        
        # Simple cosine similarity (dot product of normalized vectors)
        # Sentence-transformers usually return normalized vectors, but let's be safe
        norms = np.linalg.norm(self.embeddings, axis=1, keepdims=True)
        normalized_embeddings = self.embeddings / norms
        
        query_norm = np.linalg.norm(query_embedding, axis=1, keepdims=True)
        normalized_query = query_embedding / query_norm
        
        similarities = np.dot(normalized_embeddings, normalized_query.T).flatten()
        
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        results = []
        for idx in top_indices:
            results.append({
                "score": float(similarities[idx]),
                "content": self.chunks[idx]["content"],
                "url": self.chunks[idx]["url"],
                "title": self.chunks[idx]["title"]
            })
            
        return results

if __name__ == "__main__":
    # Test indexer
    logging.basicConfig(level=logging.INFO)
    indexer = WebsiteIndexer()
    indexer.build_index("crawl_result.json")
    
    # Test search
    try:
        test_query = "What are the key trends in 2026?"
        results = indexer.search(test_query)
        print(f"\nSearch results for: '{test_query}'")
        for r in results:
            # Use .encode().decode() trick or repr to avoid Windows console encoding issues
            title_clean = r['title'].encode('ascii', 'ignore').decode('ascii')
            content_clean = r['content'][:200].encode('ascii', 'ignore').decode('ascii')
            print(f"[{r['score']:.4f}] {title_clean} ({r['url']})")
            print(f"Content: {content_clean}...\n")
    except Exception as e:
        print(f"Search result print error (likely Unicode): {e}")
