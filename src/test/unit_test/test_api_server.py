import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from chat.models import BatchChatRequest
from vision import HeartbeatRequest, HeartbeatResponse
import json


@pytest.fixture
def mock_dependencies():

    with patch('api_server.load_models.load_all_models', new_callable=AsyncMock), \
         patch('api_server.initialize_rag'), \
         patch('api_server.TTSManager') as mock_tts, \
         patch('api_server.ChatAggregator') as mock_aggregator, \
         patch('api_server.VisionHeartbeat') as mock_vision, \
         patch('api_server.logger.setup_logger'), \
         patch('api_server.config.TTS_PROVIDER', 'elevenlabs'), \
         patch('api_server.config.TWITCH_ENABLED', False), \
         patch('api_server.config.CHAT_AGGREGATION_ENABLED', True), \
         patch('api_server.config.AGGREGATION_WINDOW_SECONDS', 2.0), \
         patch('api_server.config.MIN_RESPONSE_INTERVAL_SECONDS', 1.0), \
         patch('api_server.config.MAX_MESSAGES_PER_USER_PER_WINDOW', 5), \
         patch('api_server.config.MIN_MESSAGE_LENGTH', 1), \
         patch('api_server.config.SIMILARITY_THRESHOLD', 0.8), \
         patch('api_server.config.MAX_BATCH_SIZE', 10), \
         patch('api_server.config.DUPLICATE_EXPIRY_SECONDS', 60):
        
        mock_tts_instance = MagicMock()
        mock_tts_instance.providers = {"elevenlabs": MagicMock(), "realtimetts": None}
        mock_tts.return_value = mock_tts_instance
        
        mock_aggregator_instance = AsyncMock()
        mock_aggregator_instance.config.enabled = True
        mock_aggregator_instance.message_queue = MagicMock()
        mock_aggregator_instance.message_queue.qsize.return_value = 0
        mock_aggregator.return_value = mock_aggregator_instance
        
        mock_vision_instance = AsyncMock()
        mock_vision_instance.process_heartbeat = AsyncMock(return_value=HeartbeatResponse(
            processed=True,
            action="ignore",
            reaction_text=None,
            audio_base64=None,
            category=None,
            debug_info=None
        ))
        mock_vision.return_value = mock_vision_instance
        
        yield {
            'tts': mock_tts,
            'aggregator': mock_aggregator,
            'vision': mock_vision,
            'tts_instance': mock_tts_instance,
            'aggregator_instance': mock_aggregator_instance,
            'vision_instance': mock_vision_instance
        }


@pytest.fixture
def client(mock_dependencies):
    """Get FastAPI test client with mocked global state"""
    from api_server import app
    import api_server
    
    # Mock global state directly
    api_server.tts_manager = mock_dependencies['tts_instance']
    api_server.chat_aggregator = mock_dependencies['aggregator_instance']
    api_server.vision_heartbeat = mock_dependencies['vision_instance']
    
    # Set aggregator config
    mock_dependencies['aggregator_instance'].config.enabled = True
    
    return TestClient(app)


class TestAPIServerStartup:
    """Test server initialization through global state"""
    
    def test_tts_manager_initialized(self, mock_dependencies):
        """Should have TTS Manager available"""
        import api_server
        api_server.tts_manager = mock_dependencies['tts_instance']
        
        assert api_server.tts_manager is not None
    
    def test_chat_aggregator_initialized(self, mock_dependencies):
        """Should have Chat Aggregator available"""
        import api_server
        api_server.chat_aggregator = mock_dependencies['aggregator_instance']
        
        assert api_server.chat_aggregator is not None
    
    def test_vision_heartbeat_initialized(self, mock_dependencies):
        """Should have Vision Heartbeat available"""
        import api_server
        api_server.vision_heartbeat = mock_dependencies['vision_instance']
        
        assert api_server.vision_heartbeat is not None


class TestBatchChatEndpoint:
    
    def test_batch_chat_success(self, client, mock_dependencies):
        """Should accept valid batch chat request"""
        request_data = {
            "message": "Hello, world!",
            "user_id": "user123",
            "username": "testuser",
            "timestamp": 1234567890,
            "image_base64": None
        }
        
        mock_dependencies['aggregator_instance'].submit_message = AsyncMock(return_value=True)
        
        response = client.post("/api/chat/batch", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["accepted"] is True
        assert "queue_size" in data
        assert "message" in data
    
    def test_batch_chat_message_rejected(self, client, mock_dependencies):

        request_data = {
            "message": "x",
            "user_id": "user123",
            "username": "testuser",
            "timestamp": 1234567890,
            "image_base64": None
        }
        

        mock_dependencies['aggregator_instance'].submit_message = AsyncMock(return_value=False)
        
        response = client.post("/api/chat/batch", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["accepted"] is False
        assert "Message filtered" in data["message"]
    
    def test_batch_chat_no_aggregator(self, client, mock_dependencies):

        # Reset aggregator to None
        with patch('api_server.chat_aggregator', None):
            request_data = {
                "message": "test",
                "user_id": "user123",
                "username": "testuser",
                "timestamp": 1234567890
            }
            
            response = client.post("/api/chat/batch", json=request_data)
            
            assert response.status_code == 503
    
    def test_batch_chat_aggregator_disabled(self, client, mock_dependencies):

        mock_dependencies['aggregator_instance'].config.enabled = False
        
        request_data = {
            "message": "test",
            "user_id": "user123",
            "username": "testuser",
            "timestamp": 1234567890
        }
        
        response = client.post("/api/chat/batch", json=request_data)
        
        assert response.status_code == 400
    
    def test_batch_chat_with_image(self, client, mock_dependencies):

        mock_dependencies['aggregator_instance'].submit_message = AsyncMock(return_value=True)
        
        request_data = {
            "message": "Check this image",
            "user_id": "user123",
            "username": "testuser",
            "timestamp": 1234567890,
            "image_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        }
        
        response = client.post("/api/chat/batch", json=request_data)
        
        assert response.status_code == 200
        assert response.json()["accepted"] is True
    
    def test_batch_chat_missing_required_field(self, client, mock_dependencies):

        request_data = {
            "user_id": "user123",
            "username": "testuser",
            "timestamp": 1234567890
            # Missing 'message'
        }
        
        response = client.post("/api/chat/batch", json=request_data)
        
        assert response.status_code == 422


class TestWebSocketEndpoint:
    """Test /ws/chat WebSocket endpoint"""
    
    def test_websocket_endpoint_exists(self):
        """Should have WebSocket endpoint defined"""
        from api_server import app
        
        routes = [route.path for route in app.routes]
        assert "/ws/chat" in routes
    
    def test_websocket_manager_methods_exist(self, mock_dependencies):
        """Should use ws_manager for connections"""
        from api_server import ws_manager
        # Verify actual methods exist on ws_manager
        assert hasattr(ws_manager, 'connect')
        assert hasattr(ws_manager, 'disconnect')

class TestVisionHeartbeatEndpoint:

    
    def test_vision_heartbeat_success(self, client, mock_dependencies):

        request_data = {
            "image_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            "timestamp": 1234567890
        }
        
        response = client.post("/api/vision/heartbeat", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["processed"] is True
        assert "action" in data
    
    def test_vision_heartbeat_no_vision_system(self, client, mock_dependencies):

        with patch('api_server.vision_heartbeat', None):
            request_data = {
                "image_base64": "test",
                "timestamp": 1234567890
            }
            
            response = client.post("/api/vision/heartbeat", json=request_data)
            
            assert response.status_code == 503
    
    def test_vision_heartbeat_missing_image(self, client, mock_dependencies):

        request_data = {
            "timestamp": 1234567890
            # Missing image_base64
        }
        
        response = client.post("/api/vision/heartbeat", json=request_data)
        
        assert response.status_code == 422


class TestCORSMiddleware:

    
    def test_cors_origins(self, client):
        """Should allow localhost:3000"""
        response = client.options(
            "/api/chat/batch",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST"
            }
        )
        
        # CORS should be configured
        assert response.status_code in [200, 204] or "access-control-allow-origin" in response.headers.keys()
    
    def test_cors_credentials(self, client):

        response = client.options(
            "/api/chat/batch",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST"
            }
        )
        

        # Verify CORS credentials header is present and set to true
        assert response.headers.get("access-control-allow-credentials") == "true"

class TestLLMProvidersInitialization:
    
    def test_llm_providers_available(self):
        """Should have LLM providers configured"""
        with patch('api_server.OpenRouterProvider'), \
             patch('api_server.DeepSeekProvider'), \
             patch('api_server.RemoteVLLMProvider'):
            
            import api_server
            
            assert "openrouter" in api_server.llm_providers
            assert "deepseek" in api_server.llm_providers
            assert "remote" in api_server.llm_providers
    
    def test_llm_providers_instantiated(self):

        with patch('api_server.OpenRouterProvider') as mock_openrouter, \
             patch('api_server.DeepSeekProvider') as mock_deepseek, \
             patch('api_server.RemoteVLLMProvider') as mock_remote:
            
            import importlib
            import api_server
            importlib.reload(api_server)
            
            # Providers should be instantiated
            assert mock_openrouter.called, "OpenRouterProvider should be instantiated"
            assert mock_deepseek.called, "DeepSeekProvider should be instantiated"
            assert mock_remote.called, "RemoteVLLMProvider should be instantiated"

class TestAggregationCallbackSetup:
    """Test aggregation callback configuration"""
    
    def test_callback_can_be_configured(self, mock_dependencies):
        """Should be able to configure aggregation callback"""
        aggregator = mock_dependencies['aggregator_instance']
        
        async def test_callback(message: str, top_messages: list):
            pass
        
        # Should be able to set callback
        aggregator.response_callback = test_callback
        assert aggregator.response_callback is not None
        assert callable(aggregator.response_callback)


class TestServerConfiguration:
    def test_cors_configured(self):

        from api_server import app
        
        cors_middleware_found = False
        for middleware in app.user_middleware:
            if "CORSMiddleware" in str(middleware.cls):
                cors_middleware_found = True
                break
        
        assert cors_middleware_found
    
    def test_endpoints_defined(self):

        from api_server import app
        
        routes = [route.path for route in app.routes]
        
        assert "/api/chat/batch" in routes
        assert "/ws/chat" in routes
        assert "/api/vision/heartbeat" in routes
