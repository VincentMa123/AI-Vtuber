import sys
import os
import asyncio
import logging

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

import core.config as config
from llm.deepseek import DeepSeekProvider

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def test_deepseek_streaming():
    print("Testing DeepSeek Streaming...")
    
    # Check API Key

    provider = DeepSeekProvider()
    
    message = "Write a short poem about coding."
    print(f"User Message: {message}")
    print("-" * 20)
    
    try:
        chunk_count = 0
        full_response = ""
        
        async for chunk in provider.generate_stream(message):
            chunk_count += 1
            full_response += chunk
            print(chunk, end="", flush=True)
            
        print("\n" + "-" * 20)
        print(f"\nStream completed. Received {chunk_count} chunks.")
        
        if chunk_count > 1:
            print("SUCCESS: Streaming confirmed (multiple chunks received).")
        elif chunk_count == 1:
            print("WARNING: Only received 1 chunk. Streaming might not be working optimally, or response was very short.")
        else:
            print("ERROR: No chunks received.")
            
    except Exception as e:
        print(f"\nError during streaming test: {e}")

if __name__ == "__main__":
    asyncio.run(test_deepseek_streaming())
