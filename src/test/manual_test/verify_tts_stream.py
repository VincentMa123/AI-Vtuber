
import sys
import os
import asyncio
import logging
import time
import winsound

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tts.realtimetts import RealtimeTTSProvider

# Setup logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s', datefmt='%H:%M:%S')

async def mock_text_stream():
    """Simulate a streaming LLM response"""
    text = "Hello there! I am testing the smart buffering capabilities. " \
           "I want to see if waiting for a few chunks before playing really solves the stuttering issue. " \
           "We should hear a slight pause at the beginning, followed by a continuous stream of smooth audio."
    
    words = text.split(' ')
    for word in words:
        yield word + " "
        await asyncio.sleep(0.1) # Simulate token generation delay

async def test_smart_buffering():
    print("============================================================")
    print("TTS SMART BUFFERING SIMULATION")
    print("============================================================")
    
    try:
        # Initialize provider
        provider = RealtimeTTSProvider(engine_name="coqui") 
        print(f"Initialized TTS Provider: {provider.engine_name}")

        start_time = time.time()
        
        # Audio Queue (Simulating the frontend queue)
        audio_queue = []
        is_playing = False
        
        print("\n--- Starting Stream ---")
        
        # Generator for audio
        audio_generator = provider.generate_audio_stream(mock_text_stream())
        
        chunk_index = 0
        
        async for chunk in audio_generator:
            chunk_index += 1
            chunk_size = len(chunk)
            arrival_time = time.time() - start_time
            
            print(f"[Time {arrival_time:.2f}s] Received chunk #{chunk_index}: {chunk_size} bytes")
            
            # --- SIMULATED FRONTEND LOGIC ---
            audio_queue.append(chunk)
            
            # SMART BUFFERING CHECK:
            # Wait for 2 chunks before starting playback
            MIN_CHUNKS_TO_START = 4
            
            if not is_playing:
                if len(audio_queue) >= MIN_CHUNKS_TO_START:
                    print(f"   >>> BUFFER FILLED ({len(audio_queue)} chunks). STARTED PLAYBACK! <<<")
                    is_playing = True
                    # Start playback "thread" (simulated)
                    asyncio.create_task(play_queue(audio_queue))
                else:
                    print(f"   ... Buffering ({len(audio_queue)}/{MIN_CHUNKS_TO_START})...")
            else:
                 print(f"   (Queueing chunk. Current Queue Size: {len(audio_queue)})")

        
        # Determine if stream finished before playback caught up (for short streams)
        if not is_playing and len(audio_queue) > 0:
             print(f"   >>> STREAM COMPLETE. FLUSHING BUFFER! <<<")
             asyncio.create_task(play_queue(audio_queue))

        # Keep alive to finish playback
        # Wait long enough for the queue to drain (queue length * approx 1s per chunk)
        wait_time = len(audio_queue) * 1.5 + 5
        print(f"   [Test] Waiting {wait_time:.1f}s for playback to finish...")
        await asyncio.sleep(wait_time) 
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

async def play_queue(queue):
    """Simulate audio playback consuming the queue"""
    while True:
        if len(queue) == 0:
            print("   [Playback] Queue empty. Waiting...")
            # In real app, we check if stream ended. Here we just break if empty for too long.
            await asyncio.sleep(1)
            if len(queue) == 0:
                print("   [Playback] Finished.")
                return

        chunk = queue.pop(0)
        # Approximate duration based on bytes (assuming 16kHz mono 16-bit = 32000 bytes/sec)
        # This is rough, but allows us to "simulate" playback time
        duration = len(chunk) / 32000.0 
        
        print(f"   🔊 [Playback] Playing chunk ({len(chunk)} bytes, ~{duration:.2f}s)...")
        
        # Actually play sound (Windows)
        try:
             # SND_NOSTOP ensures we don't cut off previous sound if overlapping (though we await here)
            winsound.PlaySound(chunk, winsound.SND_MEMORY)
        except:
            pass
            
        # Wait for the duration of the audio to simulate playback time
        # This is CRITICAL. If we generate slower than we play, we stutter.

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_smart_buffering())
