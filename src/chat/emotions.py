import numpy as np
from typing import Literal, Tuple
from sentence_transformers import SentenceTransformer
import logging
import os
import pickle


EmotionType = Literal["happy", "sad", "angry", "excited", "neutral"]

_emotion_embeddings_cache = None
_model = None

def preload():
    """Preload model and embeddings during startup to avoid cold-start latency."""
    _get_model()
    _get_emotion_embeddings()
    logging.info("[Emotions] Model and embeddings preloaded")

def _get_model():

    global _model
    if _model is not None:
        return _model
    
    try:
        _model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        logging.debug("[Emotions] Loaded embedding model directly")
        return _model
    except Exception as e:
        logging.error(f"[Emotions] Failed to load model: {e}")
        return None
            
def _load_emotion_references() -> dict:
    references = {}
    current_emotion = None
    
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    file_path = os.path.join(data_dir, "emotions.md")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                    
                if line.startswith("#"):
                    current_emotion = line.lstrip("#").strip().lower()
                    references[current_emotion] = []
                elif line.startswith("-") and current_emotion:
                    example = line.lstrip("-").strip()
                    references[current_emotion].append(example)
                    
        return references
    except Exception as e:
        logging.error(f"[Emotions] Failed to load references: {e}")
        return {}

def _get_emotion_embeddings():
    global _emotion_embeddings_cache
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "data")
    cache_file = os.path.join(data_dir, "emotion_embeddings.pkl")
    
    if _emotion_embeddings_cache is None:
        try:
            with open(cache_file, 'rb') as f:
                _emotion_embeddings_cache = pickle.load(f)
                logging.info(f"[Emotions] Loaded embeddings from disk cache: {cache_file}")
                return _emotion_embeddings_cache
        except Exception as e:
            logging.error(f"[Emotions] Failed to load disk cache: {e}")

    model = _get_model()
    if model is None:
        return None
    
    emotion_references = _load_emotion_references()
    if not emotion_references:
        logging.error("[Emotions] No emotion references loaded!")
        return None

    _emotion_embeddings_cache = {}
    
    for emotion, sentences in emotion_references.items():
        if not sentences:
            continue
        embeddings = model.encode(sentences, convert_to_numpy=True)
        _emotion_embeddings_cache[emotion] = np.mean(embeddings, axis=0)
    
    logging.info(f"[Emotions] Pre-computed embeddings for {len(_emotion_embeddings_cache)} emotions")
    
    try:
        os.makedirs(data_dir, exist_ok=True)
        with open(cache_file, 'wb') as f:
            pickle.dump(_emotion_embeddings_cache, f)
        logging.info(f"[Emotions] Saved embeddings to disk cache: {cache_file}")
    except Exception as e:
        logging.error(f"[Emotions] Failed to save disk cache: {e}")
        
    return _emotion_embeddings_cache


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def detect_emotion(text: str) -> EmotionType:

    best_emotion, scores = detect_emotion_with_scores(text)
    if scores:
        logging.info(f"[Emotions] Detected '{best_emotion}' (score: {scores.get(best_emotion, 0):.3f})")
    return best_emotion


def detect_emotion_with_scores(text: str) -> Tuple[EmotionType, dict]:

    model = _get_model()
    emotion_embeddings = _get_emotion_embeddings()
    
    if model is None or emotion_embeddings is None:
        return "neutral", {}
    
    text_embedding = model.encode(text, convert_to_numpy=True)
    
    similarities = {}
    for emotion, ref_embedding in emotion_embeddings.items():
        similarities[emotion] = float(cosine_similarity(text_embedding, ref_embedding))
    
    best_emotion = max(similarities, key=similarities.get)
    
    return best_emotion, similarities


def get_emotion_intensity(text: str, emotion: EmotionType) -> float:

    model = _get_model()
    emotion_embeddings = _get_emotion_embeddings()
    
    if model is None or emotion_embeddings is None or emotion not in emotion_embeddings:
        return 0.5
    
    text_embedding = model.encode(text, convert_to_numpy=True)
    similarity = cosine_similarity(text_embedding, emotion_embeddings[emotion])
    
    intensity = max(0.0, min(1.0, (similarity - 0.2) / 0.6))
    return intensity
