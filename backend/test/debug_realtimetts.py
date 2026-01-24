
import asyncio
import logging
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tts.realtimetts import RealtimeTTSProvider
import core.config as config

# Configure logging to show everything
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

async def test_tts_streaming_standalone():
    print("\n=== DEBUG: Testing RealtimeTTS Streaming Standalone ===")
    
    # Force system engine for local testing if likely available
    print(f"Current Config Engine: {config.REALTIMETTS_ENGINE}")
    
    try:
        provider = RealtimeTTSProvider(config.REALTIMETTS_ENGINE)
    except Exception as e:
        print(f"Failed to init provider: {e}")
        return

    async def text_iterator():
        words = ["Hello", " world", ",", " this", " is", " a", " test", "."]
        for word in words:
            print(f"Yielding text: {word}")
            yield word
            await asyncio.sleep(0.1)

    print("Starting audio stream generation...")
    audio_chunks = []
    
    try:
        async for chunk in provider.generate_audio_stream(text_iterator(), min_chunk_size=10):
            print(f"Received chunk: {len(chunk)} bytes")
            audio_chunks.append(chunk)
    except Exception as e:
        print(f"Error during streaming: {e}")
        import traceback
        traceback.print_exc()

    print(f"\nTotal chunks received: {len(audio_chunks)}")
    if len(audio_chunks) == 0:
        print("FAIL: No chunks received.")
    else:
        print("SUCCESS: Chunks received.")

if __name__ == "__main__":
    asyncio.run(test_tts_streaming_standalone())
