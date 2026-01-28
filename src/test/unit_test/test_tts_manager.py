import pytest
import base64
from unittest.mock import AsyncMock, patch
from tts.manager import TTSManager


class TestTTSManagerInitialization:
    
    def test_manager_initialization(self):

        with patch('tts.manager.ElevenLabsProvider'):
            manager = TTSManager()
            
            assert hasattr(manager, 'providers')
            assert isinstance(manager.providers, dict)
            assert 'elevenlabs' in manager.providers
            assert 'realtimetts' in manager.providers
    
    def test_elevenlabs_initialized_on_init(self):

        with patch('tts.manager.ElevenLabsProvider') as mock_provider:
            manager = TTSManager()
            
            # ElevenLabs should be initialized
            mock_provider.assert_called_once()
    
    def test_realtimetts_lazy_initialized(self):

        with patch('tts.manager.ElevenLabsProvider'):
            manager = TTSManager()
            assert manager.providers["realtimetts"] is None


class TestTTSManagerAudioGeneration:
    @pytest.mark.asyncio
    async def test_generate_audio_empty_text(self):

        with patch('tts.manager.ElevenLabsProvider'):
            manager = TTSManager()
            
            result = await manager.generate_audio("")
            assert result is None
    
    @pytest.mark.asyncio
    async def test_generate_audio_whitespace_text(self):

        """Should return None for whitespace-only text"""
        with patch('tts.manager.ElevenLabsProvider'):
            manager = TTSManager()
            
            result = await manager.generate_audio("   ")
            assert result is None
    
    @pytest.mark.asyncio
    async def test_generate_audio_elevenlabs(self):

        with patch('tts.manager.ElevenLabsProvider') as mock_provider_class:
            mock_instance = AsyncMock()
            mock_instance.generate_audio.return_value = b"audio bytes"
            mock_provider_class.return_value = mock_instance
            
            with patch('tts.manager.config.TTS_PROVIDER', 'elevenlabs'):
                manager = TTSManager()
                result = await manager.generate_audio("test text")
                
                # Should be base64 encoded
                expected = base64.b64encode(b"audio bytes").decode('utf-8')
                assert result == expected
    
    @pytest.mark.asyncio
    async def test_generate_audio_elevenlabs_failure(self):

        with patch('tts.manager.ElevenLabsProvider') as mock_provider_class:
            mock_instance = AsyncMock()
            mock_instance.generate_audio.return_value = None
            mock_provider_class.return_value = mock_instance
            
            with patch('tts.manager.config.TTS_PROVIDER', 'elevenlabs'):
                manager = TTSManager()
                result = await manager.generate_audio("test")
                
                assert result is None
    
    @pytest.mark.asyncio
    async def test_generate_audio_realtimetts(self):

        with patch('tts.manager.ElevenLabsProvider'):
            with patch('tts.manager.RealtimeTTSProvider') as mock_provider_class:
                mock_instance = AsyncMock()
                mock_instance.generate_audio.return_value = b"realtime audio"
                mock_provider_class.return_value = mock_instance
                
                with patch('tts.manager.config.TTS_PROVIDER', 'realtimetts'):
                    with patch('tts.manager.config.REALTIMETTS_ENGINE', 'test_engine'):
                        manager = TTSManager()
                        result = await manager.generate_audio("test text")
                        
                        expected = base64.b64encode(b"realtime audio").decode('utf-8')
                        assert result == expected
    
    @pytest.mark.asyncio
    async def test_generate_audio_unknown_provider(self):

        with patch('tts.manager.ElevenLabsProvider'):
            with patch('tts.manager.config.TTS_PROVIDER', 'unknown'):
                manager = TTSManager()
                result = await manager.generate_audio("test")
                
                assert result is None
    
    @pytest.mark.asyncio
    async def test_generate_audio_exception_handling(self):

        with patch('tts.manager.ElevenLabsProvider') as mock_provider_class:
            mock_instance = AsyncMock()
            mock_instance.generate_audio.side_effect = RuntimeError("Provider error")
            mock_provider_class.return_value = mock_instance
            
            with patch('tts.manager.config.TTS_PROVIDER', 'elevenlabs'):
                manager = TTSManager()
                result = await manager.generate_audio("test")
                
                assert result is None
    
    @pytest.mark.asyncio
    async def test_generate_audio_base64_encoding(self):

        with patch('tts.manager.ElevenLabsProvider') as mock_provider_class:
            mock_instance = AsyncMock()
            test_audio = b"test audio data"
            mock_instance.generate_audio.return_value = test_audio
            mock_provider_class.return_value = mock_instance
            
            with patch('tts.manager.config.TTS_PROVIDER', 'elevenlabs'):
                manager = TTSManager()
                result = await manager.generate_audio("test")
                
                # Verify it's valid base64
                decoded = base64.b64decode(result)
                assert decoded == test_audio


class TestTTSManagerLazyInitialization:

    
    @pytest.mark.asyncio
    async def test_realtimetts_lazy_init_on_first_use(self):

        with patch('tts.manager.ElevenLabsProvider'):
            with patch('tts.manager.RealtimeTTSProvider') as mock_provider_class:
                mock_instance = AsyncMock()
                mock_instance.generate_audio.return_value = b"audio"
                mock_provider_class.return_value = mock_instance
                
                with patch('tts.manager.config.TTS_PROVIDER', 'realtimetts'):
                    with patch('tts.manager.config.REALTIMETTS_ENGINE', 'engine'):
                        manager = TTSManager()
                        
                        assert manager.providers["realtimetts"] is None
                        await manager.generate_audio("test")
                        assert manager.providers["realtimetts"] is not None
    
    @pytest.mark.asyncio
    async def test_realtimetts_init_error_handling(self):

        with patch('tts.manager.ElevenLabsProvider'):
            with patch('tts.manager.RealtimeTTSProvider') as mock_provider_class:
                mock_provider_class.side_effect = RuntimeError("Init failed")
                
                with patch('tts.manager.config.TTS_PROVIDER', 'realtimetts'):
                    with patch('tts.manager.config.REALTIMETTS_ENGINE', 'engine'):
                        manager = TTSManager()
                        result = await manager.generate_audio("test")
                        
                        assert result is None
    
    @pytest.mark.asyncio
    async def test_realtimetts_reused_after_init(self):

        with patch('tts.manager.ElevenLabsProvider'):
            with patch('tts.manager.RealtimeTTSProvider') as mock_provider_class:
                mock_instance = AsyncMock()
                mock_instance.generate_audio.return_value = b"audio"
                mock_provider_class.return_value = mock_instance
                
                with patch('tts.manager.config.TTS_PROVIDER', 'realtimetts'):
                    with patch('tts.manager.config.REALTIMETTS_ENGINE', 'engine'):
                        manager = TTSManager()
                        
                        # First call initializes
                        await manager.generate_audio("first")
                        first_init_count = mock_provider_class.call_count
                        
                        # Second call reuses
                        await manager.generate_audio("second")
                        second_init_count = mock_provider_class.call_count
                        
                        # Should only initialize once
                        assert first_init_count == second_init_count


class TestTTSManagerStreaming:
    @pytest.mark.asyncio
    async def test_stream_with_realtimetts(self):

        with patch('tts.manager.ElevenLabsProvider'):
            with patch('tts.manager.RealtimeTTSProvider') as mock_provider_class:
                mock_instance = AsyncMock()
                
                async def mock_stream(text_stream, min_chunk_size):
                    yield b"chunk1"
                    yield b"chunk2"
                
                mock_instance.generate_audio_stream = mock_stream
                mock_provider_class.return_value = mock_instance
                
                with patch('tts.manager.config.TTS_PROVIDER', 'realtimetts'):
                    with patch('tts.manager.config.REALTIMETTS_ENGINE', 'engine'):
                        manager = TTSManager()
                        
                        async def text_gen():
                            yield "hello "
                            yield "world"
                        
                        chunks = []
                        async for chunk in manager.generate_audio_stream(text_gen()):
                            chunks.append(chunk)
                        
                        # Should be base64 encoded
                        assert len(chunks) == 2
                        assert chunks[0] == base64.b64encode(b"chunk1").decode('utf-8')
                        assert chunks[1] == base64.b64encode(b"chunk2").decode('utf-8')
    
    @pytest.mark.asyncio
    async def test_stream_with_non_streaming_provider(self):

        with patch('tts.manager.ElevenLabsProvider') as mock_provider_class:
            mock_instance = AsyncMock()
            mock_instance.generate_audio.return_value = b"full audio"
            mock_provider_class.return_value = mock_instance
            
            with patch('tts.manager.config.TTS_PROVIDER', 'elevenlabs'):
                manager = TTSManager()
                
                async def text_gen():
                    yield "hello "
                    yield "world"
                
                chunks = []
                async for chunk in manager.generate_audio_stream(text_gen()):
                    chunks.append(chunk)
                
                # Should yield once with full collected audio
                assert len(chunks) == 1
                expected = base64.b64encode(b"full audio").decode('utf-8')
                assert chunks[0] == expected
    
    @pytest.mark.asyncio
    async def test_stream_error_handling(self):

        with patch('tts.manager.ElevenLabsProvider') as mock_provider_class:
            mock_instance = AsyncMock()
            mock_instance.generate_audio.side_effect = RuntimeError("Stream error")
            mock_provider_class.return_value = mock_instance
            
            with patch('tts.manager.config.TTS_PROVIDER', 'elevenlabs'):
                manager = TTSManager()
                
                async def text_gen():
                    yield "test"
                
                chunks = []
                async for chunk in manager.generate_audio_stream(text_gen()):
                    chunks.append(chunk)
                
                # Should gracefully handle error and yield nothing
                assert len(chunks) == 0
    
    @pytest.mark.asyncio
    async def test_stream_empty_text(self):

        with patch('tts.manager.ElevenLabsProvider'):
            manager = TTSManager()
            
            async def empty_gen():
                return
                yield
            
            with patch('tts.manager.config.TTS_PROVIDER', 'elevenlabs'):
                chunks = []
                async for chunk in manager.generate_audio_stream(empty_gen()):
                    chunks.append(chunk)
                
                assert len(chunks) == 0
    
    @pytest.mark.asyncio
    async def test_stream_with_min_chunk_size(self):

        with patch('tts.manager.ElevenLabsProvider'):
            with patch('tts.manager.RealtimeTTSProvider') as mock_provider_class:
                mock_instance = AsyncMock()
                mock_stream = AsyncMock()
                mock_instance.generate_audio_stream = mock_stream
                mock_provider_class.return_value = mock_instance
                
                with patch('tts.manager.config.TTS_PROVIDER', 'realtimetts'):
                    with patch('tts.manager.config.REALTIMETTS_ENGINE', 'engine'):
                        manager = TTSManager()
                        
                        async def text_gen():
                            yield "test"
                        
                        try:
                            async for _ in manager.generate_audio_stream(text_gen(), min_chunk_size=20):
                                break
                        except (StopAsyncIteration, TypeError):
                            pass
                        
                        # Verify min_chunk_size was passed
                        mock_stream.assert_called_once()
                        call_args = mock_stream.call_args
                        assert call_args[1].get('min_chunk_size') == 20 or len(call_args[0]) > 1


class TestTTSManagerIntegration:
    def test_manager_providers_dict_structure(self):

        """Verify manager has correct provider structure"""
        with patch('tts.manager.ElevenLabsProvider'):
            manager = TTSManager()
            
            assert 'elevenlabs' in manager.providers
            assert 'realtimetts' in manager.providers
            assert manager.providers['realtimetts'] is None
    
    @pytest.mark.asyncio
    async def test_generate_audio_with_valid_text(self):

        with patch('tts.manager.ElevenLabsProvider') as mock_provider_class:
            mock_instance = AsyncMock()
            mock_instance.generate_audio.return_value = b"audio data"
            mock_provider_class.return_value = mock_instance
            
            with patch('tts.manager.config.TTS_PROVIDER', 'elevenlabs'):
                manager = TTSManager()
                result = await manager.generate_audio("This is a test")
                
                assert result is not None
                assert isinstance(result, str)
                # Verify it's valid base64
                decoded = base64.b64decode(result)
                assert decoded == b"audio data"
    
    @pytest.mark.asyncio
    async def test_provider_called_with_text(self):

        with patch('tts.manager.ElevenLabsProvider') as mock_provider_class:
            mock_instance = AsyncMock()
            mock_instance.generate_audio.return_value = b"audio"
            mock_provider_class.return_value = mock_instance
            
            with patch('tts.manager.config.TTS_PROVIDER', 'elevenlabs'):
                manager = TTSManager()
                test_text = "Hello, this is a test message"
                await manager.generate_audio(test_text)
                
                mock_instance.generate_audio.assert_called_once_with(test_text)
