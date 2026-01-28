import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from chat.emotions import (
    detect_emotion,
    detect_emotion_with_scores,
    get_emotion_intensity,
    cosine_similarity,
    EmotionType,
    EMOTION_REFERENCES
)


class TestCosineSimarity:
    """Test cosine similarity function"""
    
    def test_identical_vectors(self):
        """Identical vectors should have similarity of 1.0"""
        a = np.array([1, 0, 0])
        b = np.array([1, 0, 0])
        similarity = cosine_similarity(a, b)
        assert similarity == pytest.approx(1.0, abs=1e-6)
    
    def test_orthogonal_vectors(self):
        """Orthogonal vectors should have similarity of 0.0"""
        a = np.array([1, 0, 0])
        b = np.array([0, 1, 0])
        similarity = cosine_similarity(a, b)
        assert similarity == pytest.approx(0.0, abs=1e-6)
    
    def test_opposite_vectors(self):
        """Opposite vectors should have similarity of -1.0"""
        a = np.array([1, 0, 0])
        b = np.array([-1, 0, 0])
        similarity = cosine_similarity(a, b)
        assert similarity == pytest.approx(-1.0, abs=1e-6)
    
    def test_normalized_vectors(self):
        """Similarity should be scale-invariant"""
        a = np.array([1, 2, 3])
        b = np.array([2, 4, 6])  # Same direction, double magnitude
        similarity = cosine_similarity(a, b)
        assert similarity == pytest.approx(1.0, abs=1e-6)


class TestDetectEmotion:
    """Test emotion detection function"""
    
    @patch('chat.emotions._get_model')
    @patch('chat.emotions._get_emotion_embeddings')
    def test_detect_happy_emotion(self, mock_embeddings, mock_model):
        """Should detect happy emotion"""
        # Mock setup
        mock_text_embedding = np.array([1, 0, 0])
        mock_happy_embedding = np.array([1, 0, 0])
        mock_sad_embedding = np.array([0, 1, 0])
        
        mock_model_instance = Mock()
        mock_model_instance.encode.return_value = mock_text_embedding
        mock_model.return_value = mock_model_instance
        
        mock_embeddings.return_value = {
            "happy": mock_happy_embedding,
            "sad": mock_sad_embedding,
            "angry": np.array([0, 0, 1]),
            "excited": np.array([0.5, 0.5, 0]),
            "neutral": np.array([0.5, 0.5, 0.5])
        }
        
        result = detect_emotion("I'm so happy!")
        assert result == "happy"
    
    @patch('chat.emotions._get_model')
    @patch('chat.emotions._get_emotion_embeddings')
    def test_detect_emotion_no_model(self, mock_embeddings, mock_model):
        """Should return neutral if model is unavailable"""
        mock_model.return_value = None
        
        result = detect_emotion("Some text")
        assert result == "neutral"
    
    @patch('chat.emotions._get_model')
    @patch('chat.emotions._get_emotion_embeddings')
    def test_detect_emotion_no_embeddings(self, mock_embeddings, mock_model):
        """Should return neutral if embeddings are unavailable"""
        mock_model.return_value = Mock()
        mock_embeddings.return_value = None
        
        result = detect_emotion("Some text")
        assert result == "neutral"
    
    @patch('chat.emotions._get_model')
    @patch('chat.emotions._get_emotion_embeddings')
    def test_detect_low_score_emotion(self, mock_embeddings, mock_model):
        """Should return neutral for low similarity scores"""
        mock_text_embedding = np.array([1, 0, 0])
        
        mock_model_instance = Mock()
        mock_model_instance.encode.return_value = mock_text_embedding
        mock_model.return_value = mock_model_instance
        
        # All embeddings are orthogonal (0 similarity)
        mock_embeddings.return_value = {
            "happy": np.array([0, 1, 0]),
            "sad": np.array([0, 0, 1]),
            "angry": np.array([-1, 0, 0]),
            "excited": np.array([0, 0, 1]),
            "neutral": np.array([0, 1, 0])
        }
        
        result = detect_emotion("Random text")
        assert result == "neutral"


class TestDetectEmotionWithScores:
    """Test emotion detection with all scores"""
    
    @patch('chat.emotions._get_model')
    @patch('chat.emotions._get_emotion_embeddings')
    def test_returns_emotion_and_scores(self, mock_embeddings, mock_model):
        """Should return emotion and similarity scores"""
        mock_text_embedding = np.array([1, 0, 0])
        
        mock_model_instance = Mock()
        mock_model_instance.encode.return_value = mock_text_embedding
        mock_model.return_value = mock_model_instance
        
        mock_embeddings.return_value = {
            "happy": np.array([1, 0, 0]),
            "sad": np.array([0, 1, 0]),
            "angry": np.array([0, 0, 1]),
            "excited": np.array([0.5, 0.5, 0]),
            "neutral": np.array([0.5, 0.5, 0.5])
        }
        
        emotion, scores = detect_emotion_with_scores("I'm happy!")
        
        assert emotion == "happy"
        assert isinstance(scores, dict)
        assert len(scores) == 5
        assert all(isinstance(v, float) for v in scores.values())
    
    @patch('chat.emotions._get_model')
    @patch('chat.emotions._get_emotion_embeddings')
    def test_returns_scores_for_all_emotions(self, mock_embeddings, mock_model):
        """Should return scores for all emotions"""
        mock_model_instance = Mock()
        mock_model_instance.encode.return_value = np.array([1, 0, 0])
        mock_model.return_value = mock_model_instance
        
        mock_embeddings.return_value = {
            "happy": np.array([1, 0, 0]),
            "sad": np.array([0, 1, 0]),
            "angry": np.array([0, 0, 1]),
            "excited": np.array([0.5, 0.5, 0]),
            "neutral": np.array([0.5, 0.5, 0.5])
        }
        
        emotion, scores = detect_emotion_with_scores("Some text")
        
        assert "happy" in scores
        assert "sad" in scores
        assert "angry" in scores
        assert "excited" in scores
        assert "neutral" in scores
    
    @patch('chat.emotions._get_model')
    @patch('chat.emotions._get_emotion_embeddings')
    def test_returns_empty_scores_no_model(self, mock_embeddings, mock_model):
        """Should return empty scores if model unavailable"""
        mock_model.return_value = None
        
        emotion, scores = detect_emotion_with_scores("Text")
        
        assert emotion == "neutral"
        assert scores == {}


class TestGetEmotionIntensity:
    """Test emotion intensity calculation"""
    
    @patch('chat.emotions._get_model')
    @patch('chat.emotions._get_emotion_embeddings')
    def test_high_intensity(self, mock_embeddings, mock_model):
        """High similarity should result in high intensity"""
        mock_text_embedding = np.array([1, 0, 0])
        
        mock_model_instance = Mock()
        mock_model_instance.encode.return_value = mock_text_embedding
        mock_model.return_value = mock_model_instance
        
        mock_embeddings.return_value = {
            "happy": np.array([1, 0, 0]),
            "sad": np.array([0, 1, 0]),
            "angry": np.array([0, 0, 1]),
            "excited": np.array([0.5, 0.5, 0]),
            "neutral": np.array([0.5, 0.5, 0.5])
        }
        
        intensity = get_emotion_intensity("I'm very happy!", "happy")
        assert 0.7 <= intensity <= 1.0
    
    @patch('chat.emotions._get_model')
    @patch('chat.emotions._get_emotion_embeddings')
    def test_low_intensity(self, mock_embeddings, mock_model):
        """Low similarity should result in low intensity"""
        mock_text_embedding = np.array([1, 0, 0])
        
        mock_model_instance = Mock()
        mock_model_instance.encode.return_value = mock_text_embedding
        mock_model.return_value = mock_model_instance
        
        mock_embeddings.return_value = {
            "happy": np.array([1, 0, 0]),
            "sad": np.array([0, 1, 0]),
            "angry": np.array([0, 0, 1]),
            "excited": np.array([0.5, 0.5, 0]),
            "neutral": np.array([0.5, 0.5, 0.5])
        }
        
        intensity = get_emotion_intensity("Let me explain", "angry")
        assert 0.0 <= intensity <= 0.3
    
    @patch('chat.emotions._get_model')
    @patch('chat.emotions._get_emotion_embeddings')
    def test_intensity_bounds(self, mock_embeddings, mock_model):
        """Intensity should be between 0.0 and 1.0"""
        mock_model_instance = Mock()
        mock_model_instance.encode.return_value = np.array([1, 0, 0])
        mock_model.return_value = mock_model_instance
        
        mock_embeddings.return_value = {
            "happy": np.array([1, 0, 0]),
            "sad": np.array([0, 1, 0]),
            "angry": np.array([0, 0, 1]),
            "excited": np.array([0.5, 0.5, 0]),
            "neutral": np.array([0.5, 0.5, 0.5])
        }
        
        for emotion in ["happy", "sad", "angry", "excited", "neutral"]:
            intensity = get_emotion_intensity("Some random text", emotion)
            assert 0.0 <= intensity <= 1.0, f"Intensity for {emotion} out of bounds: {intensity}"
    
    @patch('chat.emotions._get_model')
    @patch('chat.emotions._get_emotion_embeddings')
    def test_unknown_emotion_default(self, mock_embeddings, mock_model):
        """Unknown emotion should return 0.5"""
        mock_model_instance = Mock()
        mock_model_instance.encode.return_value = np.array([1, 0, 0])
        mock_model.return_value = mock_model_instance
        
        mock_embeddings.return_value = {
            "happy": np.array([1, 0, 0]),
            "sad": np.array([0, 1, 0]),
        }
        
        intensity = get_emotion_intensity("Text", "unknown_emotion")
        assert intensity == 0.5
    
    @patch('chat.emotions._get_model')
    @patch('chat.emotions._get_emotion_embeddings')
    def test_no_model_default(self, mock_embeddings, mock_model):
        """Should return 0.5 if model unavailable"""
        mock_model.return_value = None
        
        intensity = get_emotion_intensity("Text", "happy")
        assert intensity == 0.5


class TestEmotionReferences:
    """Test emotion reference sentences"""
    
    def test_all_emotions_have_references(self):
        """All emotion types should have reference sentences"""
        emotions = ["happy", "sad", "angry", "excited", "neutral"]
        
        for emotion in emotions:
            assert emotion in EMOTION_REFERENCES, f"Missing references for {emotion}"
            assert len(EMOTION_REFERENCES[emotion]) > 0, f"Empty references for {emotion}"
    
    def test_references_are_non_empty_strings(self):
        """All references should be non-empty strings"""
        for emotion, sentences in EMOTION_REFERENCES.items():
            for sentence in sentences:
                assert isinstance(sentence, str), f"Non-string reference in {emotion}"
                assert len(sentence) > 0, f"Empty string in {emotion} references"
