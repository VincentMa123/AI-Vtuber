"""
Simulate multiple users chatting to test chat aggregation
Run this while the backend is running to see aggregation in action
"""

import asyncio
import aiohttp
import time
import random

# Simulated chat messages from different users
CHAT_MESSAGES = [
    ("User1", "hello"),
    ("User2", "What's your favorite snack?"),
    ("User3", "hi lumina!"),
    ("User4", "test test test"),
    ("User5", "Lumina, what products do you recommend?"),
    ("User6", "hello"),  # duplicate
    ("User7", ":smile: :heart:"),  # emote only
    ("User8", "Can you help?"),
    ("User9", "What about drinks?"),
    ("User10", "I love Indomaret!"),
    ("User11", "h"),  # too short
    ("User12", "What's on sale today?"),
    ("User13", "random message"),
    ("User14", "Lumina, show me snacks"),
    ("User15", "hello"),  # another duplicate
]

async def send_message(session, username, message, user_id):
    """Send a single message to the batch endpoint"""
    url = "http://localhost:8000/api/chat/batch"
    payload = {
        "message": message,
        "user_id": user_id,
        "username": username,
        "timestamp": time.time()
    }
    
    try:
        async with session.post(url, json=payload) as response:
            result = await response.json()
            status = "✓ ACCEPTED" if result.get("accepted") else "✗ FILTERED"
            print(f"[{status}] {username}: {message[:40]}")
            return result
    except Exception as e:
        print(f"[ERROR] Failed to send message: {e}")
        return None

async def get_status(session):
    """Get current aggregation status"""
    url = "http://localhost:8000/api/chat/aggregation-status"
    try:
        async with session.get(url) as response:
            return await response.json()
    except Exception as e:
        print(f"[ERROR] Failed to get status: {e}")
        return None

async def simulate_chat_burst():
    """Simulate a burst of chat messages"""
    print("=" * 60)
    print("SIMULATING CHAT BURST")
    print("=" * 60)
    print()
    
    async with aiohttp.ClientSession() as session:
        # Reset aggregator state before testing
        try:
            async with session.post("http://localhost:8000/api/chat/aggregation-reset") as response:
                if response.ok:
                    print("✓ Aggregator state reset")
        except Exception as e:
            print(f"⚠️  Could not reset aggregator: {e}")
        
        # Check if aggregation is enabled
        status = await get_status(session)
        if status:
            if not status.get("enabled"):
                print("⚠️  WARNING: Aggregation is DISABLED")
                print("   Enable it in the UI or via API first!")
                print()
            else:
                print(f"✓ Aggregation enabled (window: {status['window_seconds']}s)")
                print()
        
        # Send all messages rapidly
        print("Sending messages...")
        tasks = []
        for i, (username, message) in enumerate(CHAT_MESSAGES):
            user_id = f"user{i+1}"
            tasks.append(send_message(session, username, message, user_id))
            await asyncio.sleep(0.1)  # Small delay between messages
        
        results = await asyncio.gather(*tasks)
        
        # Show summary
        print()
        print("=" * 60)
        accepted = sum(1 for r in results if r and r.get("accepted"))
        filtered = len(results) - accepted
        print(f"SUMMARY: {accepted} accepted, {filtered} filtered")
        
        # Show final status
        await asyncio.sleep(1)
        status = await get_status(session)
        if status:
            print(f"Queue size: {status['queue_size']}")
            print(f"Time since last response: {status['time_since_last_response']:.1f}s")
        print("=" * 60)

async def simulate_with_ai_responses():
    """Simulate chat and show AI responses"""
    print("=" * 60)
    print("SIMULATING CHAT WITH AI RESPONSES")
    print("=" * 60)
    print()
    
    async with aiohttp.ClientSession() as session:
        # Reset aggregator
        try:
            async with session.post("http://localhost:8000/api/chat/aggregation-reset") as response:
                if response.ok:
                    print("✓ Aggregator state reset\n")
        except Exception as e:
            print(f"⚠️  Could not reset: {e}\n")
        
        # Get batch window
        status = await get_status(session)
        batch_window = status.get("window_seconds", 5.0) if status else 5.0
        
        print(f"📝 Sending {len(CHAT_MESSAGES)} messages...")
        print()
        
        # Send messages
        for i, (username, message) in enumerate(CHAT_MESSAGES):
            user_id = f"user{i+1}"
            result = await send_message(session, username, message, user_id)
            await asyncio.sleep(0.15)
        
        print()
        print(f"⏳ Waiting {batch_window}s for batch processing...")
        await asyncio.sleep(batch_window + 1)
        
        # Now send a message through the regular chat endpoint to trigger AI response
        print()
        print("=" * 60)
        print("🤖 GENERATING AI RESPONSE TO AGGREGATED MESSAGES")
        print("=" * 60)
        print()
        
        # Get the top messages from the batch
        top_messages = [
            "What's your favorite snack?",
            "Lumina, what products do you recommend?",
            "What about drinks?",
            "Can you help?",
            "I love Indomaret!"
        ]
        
        aggregated_prompt = "Multiple chat messages:\n"
        for i, msg in enumerate(top_messages[:5], 1):
            aggregated_prompt += f"{i}. {msg}\n"
        
        try:
            async with session.post("http://localhost:8000/api/chat", json={
                "message": aggregated_prompt,
                "conversation_history": [],
                "tts_enabled": False
            }) as response:
                if response.ok:
                    data = await response.json()
                    print("💬 Lumina's Response:")
                    print("-" * 60)
                    print(data.get("text", "No response"))
                    print("-" * 60)
                else:
                    print(f"❌ Failed to get AI response: {response.status}")
        except Exception as e:
            print(f"❌ Error getting AI response: {e}")
        
        print()
        print("=" * 60)

async def simulate_continuous_chat(duration_seconds=30):
    """Simulate continuous chat for a duration"""
    print("=" * 60)
    print(f"SIMULATING CONTINUOUS CHAT ({duration_seconds}s)")
    print("=" * 60)
    print()
    
    async with aiohttp.ClientSession() as session:
        start_time = time.time()
        message_count = 0
        
        while time.time() - start_time < duration_seconds:
            # Pick random message
            username, message = random.choice(CHAT_MESSAGES)
            user_id = f"user{random.randint(1, 20)}"
            
            await send_message(session, username, message, user_id)
            message_count += 1
            
            # Random delay between messages (0.5-2 seconds)
            await asyncio.sleep(random.uniform(0.5, 2.0))
        
        print()
        print(f"Sent {message_count} messages over {duration_seconds}s")

async def main():
    """Main menu"""
    print()
    print("╔════════════════════════════════════════════════════════╗")
    print("║       CHAT AGGREGATION SIMULATOR                      ║")
    print("╚════════════════════════════════════════════════════════╝")
    print()
    print("Choose a test mode:")
    print("  1. Burst Test (15 rapid messages)")
    print("  2. Continuous Chat (30 seconds)")
    print("  3. Burst Test + AI Response (see Lumina's reply!)")
    print("  4. Custom Burst (specify count)")
    print()
    
    choice = input("Enter choice (1-4): ").strip()
    
    if choice == "1":
        await simulate_chat_burst()
    elif choice == "2":
        await simulate_continuous_chat(30)
    elif choice == "3":
        await simulate_with_ai_responses()
    elif choice == "4":
        count = int(input("How many messages? "))
        messages = CHAT_MESSAGES * (count // len(CHAT_MESSAGES) + 1)
        messages = messages[:count]
        
        async with aiohttp.ClientSession() as session:
            for i, (username, message) in enumerate(messages):
                await send_message(session, username, message, f"user{i+1}")
                await asyncio.sleep(0.1)
    else:
        print("Invalid choice!")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nSimulation stopped by user")
