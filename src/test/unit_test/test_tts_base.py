import pytest
from tts.base import BaseTTSProvider

class TestBaseTTSProvider:
    def test_cannot_instantiate_abstract_class(self):
        with pytest.raises(TypeError):
            BaseTTSProvider()
    
    def test_requires_generate_audio_implementation(self):
        class IncompleteProvider(BaseTTSProvider):
            pass
        
        with pytest.raises(TypeError):
            IncompleteProvider()
    
    def test_can_instantiate_with_implementation(self):
        class ConcreteProvider(BaseTTSProvider):
            async def generate_audio(self, text: str):
                return b"fake audio"
        
        provider = ConcreteProvider()
        assert provider is not None
    
    @pytest.mark.asyncio
    async def test_default_stream_implementation(self):
        class ConcreteProvider(BaseTTSProvider):
            async def generate_audio(self, text: str):
                return b"test audio" if text else None
        
        provider = ConcreteProvider()
        
        async def text_generator():
            yield "hello "
            yield "world"
        
        chunks = []
        async for chunk in provider.generate_audio_stream(text_generator()):
            chunks.append(chunk)
        
        assert len(chunks) == 1
        assert chunks[0] == b"test audio"
    
    @pytest.mark.asyncio
    async def test_stream_with_empty_text(self):
        class ConcreteProvider(BaseTTSProvider):
            async def generate_audio(self, text: str):
                return b"audio"
        
        provider = ConcreteProvider()
        
        async def empty_generator():
            return
            yield  # Never reached
        
        chunks = []
        async for chunk in provider.generate_audio_stream(empty_generator()):
            chunks.append(chunk)
        
        assert len(chunks) == 0
    
    @pytest.mark.asyncio
    async def test_stream_with_min_chunk_size(self):
        class ConcreteProvider(BaseTTSProvider):
            async def generate_audio(self, text: str):
                return b"audio"
        
        provider = ConcreteProvider()
        
        async def text_generator():
            yield "hi"
        
        # Should still generate audio even if below min_chunk_size
        chunks = []
        async for chunk in provider.generate_audio_stream(text_generator()):
            chunks.append(chunk)
        
        assert len(chunks) == 1
    
    @pytest.mark.asyncio
    async def test_stream_concatenates_text(self):
        class ConcreteProvider(BaseTTSProvider):
            async def generate_audio(self, text: str):
                # Return the text we received to verify concatenation
                return text.encode('utf-8')
        
        provider = ConcreteProvider()
        
        async def text_generator():
            yield "hello"
            yield " "
            yield "world"
        
        chunks = []
        async for chunk in provider.generate_audio_stream(text_generator()):
            chunks.append(chunk)
        
        assert len(chunks) == 1
        assert chunks[0] == b"hello world"
    
    @pytest.mark.asyncio
    async def test_stream_returns_none_handling(self):
        class ConcreteProvider(BaseTTSProvider):
            async def generate_audio(self, text: str):
                return None  # Return None
        
        provider = ConcreteProvider()
        
        async def text_generator():
            yield "test"
        
        chunks = []
        async for chunk in provider.generate_audio_stream(text_generator()):
            chunks.append(chunk)
        
        # Should yield nothing when audio is None
        assert len(chunks) == 0
