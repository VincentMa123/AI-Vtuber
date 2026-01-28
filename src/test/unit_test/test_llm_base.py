import pytest
from typing import List, Dict, Any
from llm.base import sanitize_history, BaseLLMProvider


class TestSanitizeHistory:
    def test_empty_history(self):
        """Should handle empty history"""
        result = sanitize_history([])
        assert result == []
    
    def test_text_only_message(self):
        """Should preserve text-only messages"""
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]
        result = sanitize_history(history)
        assert len(result) == 2
        assert result[0]["content"] == "Hello"
        assert result[1]["content"] == "Hi there!"
    
    def test_removes_base64_image_data(self):
        """Should replace base64 images with placeholder text"""
        history = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What's in this image?"},
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64,iVBORw0KGgoAAAANS..."}}
                ]
            }
        ]
        result = sanitize_history(history)
        assert len(result) == 1
        # Image should be replaced with placeholder
        content = result[0]["content"]
        assert isinstance(content, list)
        assert any("[User shared an image]" in str(item) for item in content)
    
    def test_removes_base64_image_type(self):

        history = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Look at this"},
                    {"type": "image", "image": "data:image/png;base64,abc123"}
                ]
            }
        ]
        result = sanitize_history(history)
        assert len(result) == 1
        content = result[0]["content"]
        assert "[User shared an image]" in str(content)
    
    def test_single_text_item_unwraps(self):

        history = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Single text"}
                ]
            }
        ]
        result = sanitize_history(history)
        assert result[0]["content"] == "Single text"
    
    def test_multiple_text_items_stays_list(self):

        history = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Text 1"},
                    {"type": "text", "text": "Text 2"}
                ]
            }
        ]
        result = sanitize_history(history)
        assert isinstance(result[0]["content"], list)
    
    def test_limits_to_last_10_messages(self):

        history = [{"role": "user", "content": f"Message {i}"} for i in range(20)]
        result = sanitize_history(history)
        assert len(result) == 10

        assert result[0]["content"] == "Message 10"
        assert result[-1]["content"] == "Message 19"
    
    def test_preserves_message_roles(self):

        history = [
            {"role": "user", "content": "User message"},
            {"role": "assistant", "content": "Assistant response"},
            {"role": "system", "content": "System prompt"}
        ]
        result = sanitize_history(history)
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"
        assert result[2]["role"] == "system"
    
    def test_complex_content_structure(self):

        history = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Question about image"},
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
                ]
            },
            {
                "role": "assistant",
                "content": "I see an image"
            }
        ]
        result = sanitize_history(history)
        assert len(result) == 2
        assert isinstance(result[0]["content"], list)
        assert result[1]["content"] == "I see an image"
    
    def test_empty_content_list(self):

        history = [
            {"role": "user", "content": []}
        ]
        result = sanitize_history(history)
        assert len(result) == 1
        assert result[0]["content"] == []
    
    def test_preserves_other_fields(self):

        history = [
            {
                "role": "user",
                "content": "Test",
                "timestamp": 123456,
                "user_id": "user1"
            }
        ]
        result = sanitize_history(history)
        assert result[0]["timestamp"] == 123456
        assert result[0]["user_id"] == "user1"


class TestBaseLLMProvider:

    
    def test_cannot_instantiate_abstract_class(self):

        with pytest.raises(TypeError):
            BaseLLMProvider()
    
    def test_concrete_implementation_required(self):

        class IncompleteProvider(BaseLLMProvider):
            pass
        
        with pytest.raises(TypeError):
            IncompleteProvider()
    
    def test_concrete_implementation_allowed(self):

        class ConcreteProvider(BaseLLMProvider):
            async def generate(self, message, history=[], image_base64=None, **kwargs):
                return "Response"
        
        provider = ConcreteProvider()
        assert isinstance(provider, BaseLLMProvider)


class TestBaseLLMProviderGenerate:
    
    @pytest.mark.asyncio
    async def test_generate_with_message_only(self):
        """Subclass should handle message-only calls"""
        class SimpleProvider(BaseLLMProvider):
            async def generate(self, message, history=[], image_base64=None, **kwargs):
                return f"You said: {message}"
        
        provider = SimpleProvider()
        result = await provider.generate("Hello")
        assert result == "You said: Hello"
    
    @pytest.mark.asyncio
    async def test_generate_with_history(self):

        class HistoryAwareProvider(BaseLLMProvider):
            async def generate(self, message, history=[], image_base64=None, **kwargs):
                return f"History has {len(history)} messages"
        
        provider = HistoryAwareProvider()
        history = [
            {"role": "user", "content": "msg1"},
            {"role": "assistant", "content": "resp1"}
        ]
        result = await provider.generate("New message", history=history)
        assert result == "History has 2 messages"
    
    @pytest.mark.asyncio
    async def test_generate_with_image(self):

        class ImageAwareProvider(BaseLLMProvider):
            async def generate(self, message, history=[], image_base64=None, **kwargs):
                if image_base64:
                    return "Image received"
                return "No image"
        
        provider = ImageAwareProvider()
        result = await provider.generate("What's in this?", image_base64="base64data")
        assert result == "Image received"
    
    @pytest.mark.asyncio
    async def test_generate_with_kwargs(self):

        class ConfigurableProvider(BaseLLMProvider):
            async def generate(self, message, history=[], image_base64=None, **kwargs):
                max_tokens = kwargs.get('max_tokens', 100)
                return f"Max tokens: {max_tokens}"
        
        provider = ConfigurableProvider()
        result = await provider.generate("Test", max_tokens=500)
        assert result == "Max tokens: 500"


class TestBaseLLMProviderGenerateStream:
    @pytest.mark.asyncio
    async def test_default_stream_implementation(self):

        class SimpleProvider(BaseLLMProvider):
            async def generate(self, message, history=[], image_base64=None, **kwargs):
                return "Hello world"
        
        provider = SimpleProvider()
        chunks = []
        async for chunk in provider.generate_stream("Hi"):
            chunks.append(chunk)
        
        assert len(chunks) == 1
        assert chunks[0] == "Hello world"
    
    @pytest.mark.asyncio
    async def test_stream_handles_none_response(self):

        class FailingProvider(BaseLLMProvider):
            async def generate(self, message, history=[], image_base64=None, **kwargs):
                return None
        
        provider = FailingProvider()
        chunks = []
        async for chunk in provider.generate_stream("Hi"):
            chunks.append(chunk)
        
        assert chunks == []
    
    @pytest.mark.asyncio
    async def test_custom_stream_implementation(self):

        class StreamingProvider(BaseLLMProvider):
            async def generate(self, message, history=[], image_base64=None, **kwargs):
                return "Not used in stream"
            
            async def generate_stream(self, message, history=[], image_base64=None, **kwargs):
                for token in ["Hello", " ", "world"]:
                    yield token
        
        provider = StreamingProvider()
        chunks = []
        async for chunk in provider.generate_stream("Hi"):
            chunks.append(chunk)
        
        assert chunks == ["Hello", " ", "world"]


class TestBaseLLMProviderIntegration:
    
    @pytest.mark.asyncio
    async def test_provider_with_sanitized_history(self):

        class HistoryAwareProvider(BaseLLMProvider):
            async def generate(self, message, history=[], image_base64=None, **kwargs):
                # Sanitize history for processing
                clean_history = sanitize_history(history)
                return f"Messages: {len(clean_history)}"
        
        provider = HistoryAwareProvider()
        history = [
            {"role": "user", "content": f"Message {i}"} for i in range(15)
        ]
        
        result = await provider.generate("New", history=history)
        assert result == "Messages: 10"  # Limited to last 10
    
    @pytest.mark.asyncio
    async def test_provider_signature_compatibility(self):

        class Provider1(BaseLLMProvider):
            async def generate(self, message, history=[], image_base64=None, **kwargs):
                return "P1"
        
        class Provider2(BaseLLMProvider):
            async def generate(self, message, history=[], image_base64=None, **kwargs):
                return "P2"
        
        providers = [Provider1(), Provider2()]
        
        # Both should be callable the same way
        for provider in providers:
            result = await provider.generate(
                message="Test",
                history=[],
                image_base64=None,
                max_tokens=100
            )
            assert result in ["P1", "P2"]


class TestSanitizeHistoryEdgeCases:
    def test_deeply_nested_content(self):

        history = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Complex"},
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64,very_long_base64_string" * 100}}
                ]
            }
        ]
        result = sanitize_history(history)
        # Should not crash and should remove the image
        assert len(result) == 1
    
    def test_mixed_content_types(self):

        history = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Text 1"},
                    {"type": "image", "image": "base64..."},
                    {"type": "text", "text": "Text 2"},
                    {"type": "image_url", "image_url": {"url": "url..."}}
                ]
            }
        ]
        result = sanitize_history(history)
        assert len(result) == 1
        assert isinstance(result[0]["content"], list)
    
    def test_exact_10_messages(self):

        history = [{"role": "user", "content": f"Msg {i}"} for i in range(10)]
        result = sanitize_history(history)
        assert len(result) == 10
    
    def test_less_than_10_messages(self):

        history = [{"role": "user", "content": f"Msg {i}"} for i in range(5)]
        result = sanitize_history(history)
        assert len(result) == 5
