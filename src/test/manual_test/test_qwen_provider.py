import asyncio
import os
import sys
import sys
import os

# dynamic path resolution to import from src
current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../../"))
sys.path.append(src_path)

import sys
import os

# dynamic path resolution to import from src
current_dir = os.path.dirname(os.path.abspath(__file__))
# current_dir is inside src/test/manual_test
# we need to go up 2 levels to reach src/ -> which contains llm module
src_path = os.path.abspath(os.path.join(current_dir, "../../"))
if src_path not in sys.path:
    sys.path.append(src_path)

try:
    from llm.qwen import QwenProvider
except ImportError:
    # If standard import fails, try relative import hack if path wasn't enough
    sys.path.append(os.path.join(src_path, "..")) # project root
    from src.llm.qwen import QwenProvider
import core.config as config

async def test_qwen_generate():
    print("\n--- Testing QwenProvider.generate ---")
    provider = QwenProvider()
    
    if not provider.client:
        print("Skipping test: Qwen client not initialized (missing API key/Url)")
        return

    response = await provider.generate(
        message="Hello, who are you?",
    )
    print(f"Response: {response}")
    assert response is not None
    assert len(response) > 0

async def test_qwen_stream():
    print("\n--- Testing QwenProvider.generate_stream ---")
    provider = QwenProvider()
    
    if not provider.client:
        print("Skipping test: Qwen client not initialized")
        return

    print("Stream content: ", end="", flush=True)
    async for chunk in provider.generate_stream(message="Count to 5"):
        print(chunk, end="", flush=True)
    print("\n")

if __name__ == "__main__":
    asyncio.run(test_qwen_generate())
    asyncio.run(test_qwen_stream())
