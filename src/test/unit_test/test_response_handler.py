import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from chat.response_handler import (
    handle_aggregated_response,
    handle_streaming_response,
    EMOTION_CONTEXT
)


class TestEmotionContext:
    """Test EMOTION_CONTEXT mapping"""
    
    def test_all_emotions_have_context(self):
        """All emotions should have context instructions"""
        emotions = ["happy", "sad", "angry", "excited", "neutral"]
        
        for emotion in emotions:
            assert emotion in EMOTION_CONTEXT
    
    def test_happy_context(self):
        """Happy emotion should have positive context"""
        assert "enthusiasm" in EMOTION_CONTEXT["happy"].lower()
    
    def test_sad_context(self):
        """Sad emotion should have supportive context"""
        assert "gentle" in EMOTION_CONTEXT["sad"].lower() or "support" in EMOTION_CONTEXT["sad"].lower()
    
    def test_angry_context(self):
        """Angry emotion should have calming context"""
        assert "calm" in EMOTION_CONTEXT["angry"].lower()
    
    def test_excited_context(self):
        """Excited emotion should have energetic context"""
        assert "excit" in EMOTION_CONTEXT["excited"].lower()
    
    def test_neutral_context(self):
        """Neutral emotion should have empty context"""
        assert EMOTION_CONTEXT["neutral"] == ""


class TestHandleAggregatedResponse:
    """Test handle_aggregated_response function"""
    
    @pytest.mark.asyncio
    @patch('chat.response_handler.detect_emotion')
    @patch('chat.response_handler.state')
    @patch('chat.response_handler.ws_manager')
    async def test_emotion_detection(self, mock_ws, mock_state, mock_detect):
        """Should detect emotion from message"""
        mock_detect.return_value = "happy"
        mock_state.llm_provider = "deepseek"
        
        mock_provider = AsyncMock()
        mock_provider.generate = AsyncMock(return_value="Response!")
        mock_providers = {"deepseek": mock_provider}
        
        mock_tts = AsyncMock()
        mock_tts.generate_audio = AsyncMock(return_value="audio123")
        
        await handle_aggregated_response(
            message="Hello!",
            top_messages=[],
            llm_providers=mock_providers,
            tts_manager=mock_tts,
            use_streaming=False
        )
        
        mock_detect.assert_called_once_with("Hello!")
    
    @pytest.mark.asyncio
    @patch('chat.response_handler.detect_emotion')
    @patch('chat.response_handler.state')
    @patch('chat.response_handler.ws_manager')
    async def test_invalid_provider(self, mock_ws, mock_state, mock_detect):
        """Should handle invalid LLM provider gracefully"""
        mock_detect.return_value = "happy"
        mock_state.llm_provider = "nonexistent"
        
        mock_providers = {"deepseek": Mock()}
        mock_tts = AsyncMock()
        
        await handle_aggregated_response(
            message="Hello!",
            top_messages=[],
            llm_providers=mock_providers,
            tts_manager=mock_tts,
            use_streaming=False
        )
        
        assert True
    
    @pytest.mark.asyncio
    @patch('chat.response_handler.detect_emotion')
    @patch('chat.response_handler.state')
    @patch('chat.response_handler.ws_manager')
    @patch('chat.response_handler.config')
    async def test_with_emotion_context(self, mock_config, mock_ws, mock_state, mock_detect):
        """Should add emotion context to enhanced message"""
        mock_detect.return_value = "happy"
        mock_state.llm_provider = "deepseek"
        mock_config.TWITCH_ENABLED = False
        
        mock_provider = AsyncMock()
        mock_provider.generate = AsyncMock(return_value="Response!")
        mock_providers = {"deepseek": mock_provider}
        
        mock_tts = AsyncMock()
        mock_tts.generate_audio = AsyncMock(return_value="audio123")
        
        await handle_aggregated_response(
            message="Hello!",
            top_messages=[],
            llm_providers=mock_providers,
            tts_manager=mock_tts,
            use_streaming=False
        )
        
        # Check that enhanced_message included emotion context
        call_args = mock_provider.generate.call_args[0][0]
        assert "EMOTION CONTEXT" in call_args or "enthusiasm" in call_args


class TestHandleStreamingResponse:
    """Test handle_streaming_response function"""
    
    @pytest.mark.asyncio
    @patch('chat.response_handler.ws_manager')
    @patch('chat.response_handler.config')
    async def test_streaming_broadcast_start(self, mock_config, mock_ws):
        """Should broadcast stream start event"""
        mock_config.TWITCH_ENABLED = False
        mock_ws.broadcast_stream_start = AsyncMock()
        mock_ws.broadcast_stream_end = AsyncMock()
        mock_ws.broadcast_text_chunk = AsyncMock()
        mock_ws.broadcast_audio_chunk = AsyncMock()
        
        async def mock_text_stream(*args, **kwargs):
            yield "Hello "
            yield "world"
        
        mock_provider = Mock()
        mock_provider.generate_stream = Mock(return_value=mock_text_stream())
        
        mock_tts = Mock()
        async def mock_audio_stream(*args, **kwargs):
            yield "audio1"
            yield "audio2"
        
        mock_tts.generate_audio_stream = Mock(return_value=mock_audio_stream())
        
        await handle_streaming_response(
            enhanced_message="Test",
            llm_provider="deepseek",
            provider=mock_provider,
            llm_providers={"deepseek": mock_provider},
            tts_manager=mock_tts,
            user_emotion="happy"
        )
        
        mock_ws.broadcast_stream_start.assert_called_once_with("happy")
    
    @pytest.mark.asyncio
    @patch('chat.response_handler.ws_manager')
    @patch('chat.response_handler.config')
    async def test_streaming_broadcast_end(self, mock_config, mock_ws):
        """Should broadcast stream end event"""
        mock_config.TWITCH_ENABLED = False
        mock_ws.broadcast_stream_start = AsyncMock()
        mock_ws.broadcast_stream_end = AsyncMock()
        mock_ws.broadcast_text_chunk = AsyncMock()
        mock_ws.broadcast_audio_chunk = AsyncMock()
        
        async def mock_text_stream(*args, **kwargs):
            yield "Test"
        
        mock_provider = Mock()
        mock_provider.generate_stream = Mock(return_value=mock_text_stream())
        
        mock_tts = Mock()
        async def mock_audio_stream(*args, **kwargs):
            yield "audio"
        
        mock_tts.generate_audio_stream = Mock(return_value=mock_audio_stream())
        
        await handle_streaming_response(
            enhanced_message="Test",
            llm_provider="deepseek",
            provider=mock_provider,
            llm_providers={"deepseek": mock_provider},
            tts_manager=mock_tts,
            user_emotion="happy"
        )
        
        mock_ws.broadcast_stream_end.assert_called()
    
    @pytest.mark.asyncio
    @patch('chat.response_handler.ws_manager')
    @patch('chat.response_handler.config')
    async def test_streaming_text_chunks(self, mock_config, mock_ws):
        """Should broadcast text chunks"""
        mock_config.TWITCH_ENABLED = False
        mock_ws.broadcast_stream_start = AsyncMock()
        mock_ws.broadcast_stream_end = AsyncMock()
        mock_ws.broadcast_text_chunk = AsyncMock()
        mock_ws.broadcast_audio_chunk = AsyncMock()
        
        async def mock_text_stream(*args, **kwargs):
            yield "Hello "
            yield "world"
        
        mock_provider = Mock()
        mock_provider.generate_stream = Mock(return_value=mock_text_stream())
        
        mock_tts = Mock()
        async def mock_audio_stream(*args, **kwargs):
            yield "audio"
        
        mock_tts.generate_audio_stream = Mock(return_value=mock_audio_stream())
        
        await handle_streaming_response(
            enhanced_message="Test",
            llm_provider="deepseek",
            provider=mock_provider,
            llm_providers={"deepseek": mock_provider},
            tts_manager=mock_tts,
            user_emotion="happy"
        )
        
        # Should call broadcast_text_chunk at least once
        assert mock_ws.broadcast_text_chunk.called
    
    @pytest.mark.asyncio
    @patch('chat.response_handler.ws_manager')
    @patch('chat.response_handler.config')
    async def test_streaming_audio_chunks(self, mock_config, mock_ws):
        """Should broadcast audio chunks"""
        mock_config.TWITCH_ENABLED = False
        mock_ws.broadcast_stream_start = AsyncMock()
        mock_ws.broadcast_stream_end = AsyncMock()
        mock_ws.broadcast_text_chunk = AsyncMock()
        mock_ws.broadcast_audio_chunk = AsyncMock()
        
        async def mock_text_stream(*args, **kwargs):
            yield "Test"
        
        mock_provider = Mock()
        mock_provider.generate_stream = Mock(return_value=mock_text_stream())
        
        mock_tts = Mock()
        async def mock_audio_stream(*args, **kwargs):
            yield "audio1"
            yield "audio2"
        
        mock_tts.generate_audio_stream = Mock(return_value=mock_audio_stream())
        
        await handle_streaming_response(
            enhanced_message="Test",
            llm_provider="deepseek",
            provider=mock_provider,
            llm_providers={"deepseek": mock_provider},
            tts_manager=mock_tts,
            user_emotion="happy"
        )
        
        # Should call broadcast_audio_chunk
        assert mock_ws.broadcast_audio_chunk.called


class TestResponseHandlerErrorHandling:
    """Test error handling in response handler"""
    
    @pytest.mark.asyncio
    @patch('chat.response_handler.detect_emotion')
    @patch('chat.response_handler.state')
    @patch('chat.response_handler.ws_manager')
    async def test_provider_failure_fallback(self, mock_ws, mock_state, mock_detect):
        """Should fallback to other providers on failure"""
        mock_detect.return_value = "happy"
        mock_state.llm_provider = "deepseek"
        
        # Primary provider fails
        mock_primary = AsyncMock()
        mock_primary.generate = AsyncMock(return_value=None)
        
        # Fallback provider succeeds
        mock_fallback = AsyncMock()
        mock_fallback.generate = AsyncMock(return_value="Fallback response!")
        
        mock_providers = {
            "deepseek": mock_primary,
            "openrouter": mock_fallback,
            "remote": AsyncMock()
        }
        
        mock_tts = AsyncMock()
        mock_tts.generate_audio = AsyncMock(return_value="audio123")
        
        await handle_aggregated_response(
            message="Hello!",
            top_messages=[],
            llm_providers=mock_providers,
            tts_manager=mock_tts,
            use_streaming=False
        )
        
        # Should try fallback provider
        assert mock_fallback.generate.called


class TestResponseHandlerIntegration:
    """Integration tests for response handler"""
    
    @pytest.mark.asyncio
    @patch('chat.response_handler.detect_emotion')
    @patch('chat.response_handler.state')
    @patch('chat.response_handler.ws_manager')
    @patch('chat.response_handler.config')
    async def test_complete_response_flow(self, mock_config, mock_ws, mock_state, mock_detect):
        """Test complete flow: emotion detection -> LLM -> TTS -> broadcast"""
        mock_config.TWITCH_ENABLED = False
        mock_detect.return_value = "happy"
        mock_state.llm_provider = "deepseek"
        
        mock_provider = AsyncMock()
        mock_provider.generate = AsyncMock(return_value="Great question!")
        mock_providers = {"deepseek": mock_provider}
        
        mock_tts = AsyncMock()
        mock_tts.generate_audio = AsyncMock(return_value="audio_data_123")
        
        mock_ws.broadcast_ai_response = AsyncMock()
        
        await handle_aggregated_response(
            message="Tell me a joke",
            top_messages=[],
            llm_providers=mock_providers,
            tts_manager=mock_tts,
            use_streaming=False
        )
        
        # Verify complete flow
        mock_detect.assert_called_once()
        mock_provider.generate.assert_called_once()
        mock_tts.generate_audio.assert_called_once()
        mock_ws.broadcast_ai_response.assert_called_once()
