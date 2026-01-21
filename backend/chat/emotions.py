"""
Semantic Emotion Detection using Embeddings
Uses SentenceTransformer to compare AI response with emotion reference texts
"""

import numpy as np
from typing import Literal, Tuple

EmotionType = Literal["happy", "sad", "angry", "excited", "neutral"]

# Reference sentences for each emotion
EMOTION_REFERENCES = {
    "happy": [
        "I'm so happy and joyful right now!",
        "This is wonderful, I love it!",
        "That makes me really glad!",
        "Yay! This is amazing!",
        "I'm delighted to help you with that!",
        "What a lovely thing to say!",
        "That's so sweet, thank you!",
    ],
    "sad": [
        "I'm feeling sad and disappointed.",
        "That's really unfortunate.",
        "I'm sorry to hear that.",
        "This makes me feel melancholy.",
        "I wish things were different.",
        "That's too bad, I feel for you.",
    ],
    "angry": [
        "That's really frustrating and annoying!",
        "I'm upset about this situation.",
        "This is unacceptable behavior!",
        "That makes me so mad!",
        "I can't believe this happened!",
        "This is ridiculous!",
    ],
    "excited": [
        "Oh wow! This is incredible!",
        "I'm so excited about this!",
        "This is absolutely amazing, I can't wait!",
        "OMG this is the best thing ever!",
        "Let's gooo! This is awesome!",
        "I'm thrilled about this opportunity!",
    ],
    "neutral": [
        "I understand what you're saying.",
        "Here's the information you requested.",
        "Let me explain that for you.",
        "That's a good question.",
        "I can help you with that.",
    ]
}

# Cache for emotion embeddings
_emotion_embeddings_cache = None
_model = None


def _get_model():
    """Get or load the embedding model."""
    global _model
    if _model is not None:
        return _model
    
    try:
        from rag.embeddings import get_embedding_model
        _model = get_embedding_model()
        return _model
    except ImportError:
        try:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
            print("[Emotions] Loaded embedding model directly")
            return _model
        except Exception as e:
            print(f"[Emotions] Failed to load model: {e}")
            return None


def _get_emotion_embeddings():
    """Pre-compute embeddings for all emotion reference sentences."""
    global _emotion_embeddings_cache
    
    if _emotion_embeddings_cache is not None:
        return _emotion_embeddings_cache
    
    model = _get_model()
    if model is None:
        return None
    
    _emotion_embeddings_cache = {}
    
    for emotion, sentences in EMOTION_REFERENCES.items():
        embeddings = model.encode(sentences, convert_to_numpy=True)
        _emotion_embeddings_cache[emotion] = np.mean(embeddings, axis=0)
    
    print(f"[Emotions] Pre-computed embeddings for {len(_emotion_embeddings_cache)} emotions")
    return _emotion_embeddings_cache


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def detect_emotion(text: str) -> EmotionType:
    """
    Detect emotion from text using semantic embeddings.
    """
    model = _get_model()
    emotion_embeddings = _get_emotion_embeddings()
    
    if model is None or emotion_embeddings is None:
        return "neutral"
    
    text_embedding = model.encode(text, convert_to_numpy=True)
    
    similarities = {}
    for emotion, ref_embedding in emotion_embeddings.items():
        similarities[emotion] = cosine_similarity(text_embedding, ref_embedding)

    best_emotion = max(similarities, key=similarities.get)
    best_score = similarities[best_emotion]
    
    if best_score < 0.3:
        return "neutral"
    
    print(f"[Emotions] Detected '{best_emotion}' (score: {best_score:.3f})")
    return best_emotion


def detect_emotion_with_scores(text: str) -> Tuple[EmotionType, dict]:
    """Detect emotion and return all similarity scores."""
    model = _get_model()
    emotion_embeddings = _get_emotion_embeddings()
    
    if model is None or emotion_embeddings is None:
        return "neutral", {}
    
    text_embedding = model.encode(text, convert_to_numpy=True)
    
    similarities = {}
    for emotion, ref_embedding in emotion_embeddings.items():
        similarities[emotion] = float(cosine_similarity(text_embedding, ref_embedding))
    
    best_emotion = max(similarities, key=similarities.get)
    
    if similarities[best_emotion] < 0.3:
        return "neutral", similarities
    
    return best_emotion, similarities


def get_emotion_intensity(text: str, emotion: EmotionType) -> float:
    """Get the intensity of a specific emotion (0.0 to 1.0)."""
    model = _get_model()
    emotion_embeddings = _get_emotion_embeddings()
    
    if model is None or emotion_embeddings is None or emotion not in emotion_embeddings:
        return 0.5
    
    text_embedding = model.encode(text, convert_to_numpy=True)
    similarity = cosine_similarity(text_embedding, emotion_embeddings[emotion])
    
    intensity = max(0.0, min(1.0, (similarity - 0.2) / 0.6))
    return intensity
