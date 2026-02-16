"""
Twitch Chat Sender - Sends messages to ACTUAL Twitch chat for full-loop testing.
Messages go: This Script → Twitch → Your Bot → AI Response → Bot → Twitch

Run: python src/test/manual_test/twitch_chat_sender.py

Note: Uses the same OAuth token as your bot. Messages will appear as your bot account.
Make sure your bot is already running (python src/api_server.py) to receive the messages.

This version uses `websockets` (like bot.py) to be independent of `twitchio` version issues.
"""
import asyncio
import logging
import random
import time
import sys
import os

# Ensure src can be imported
sys.path.append(os.getcwd())

import websockets
import src.core.config as config

TWITCH_WS_URL = "wss://irc-ws.chat.twitch.tv:443"

# Sample messages for testing
MESSAGES = [
    # Product questions
    "Kak ada promo apa hari ini?",
    "Harga minyak goreng berapa ya?",
    "Indomie goreng ready stock?",
    "Ada diskon gak minggu ini?",
    
    # Reactions
    "Wah keren banget!",
    "HAHAHA lucu kak",
    "Setuju banget tuh",
    "Mantap!",
    
    # Random chat  
    "Halo kak lagi ngapain?",
    "Baru join nih",
    "Suaranya bagus kak",
    "Salam dari Bandung!",
    
    # Complex questions
    "Rekomendasiin snack enak dong kak",
    "Ada produk baru gak bulan ini?",
    "Bedanya harga heboh sama promo biasa apa kak?",
    
    # Fun/spam
    "GG",
    "KEK",
    "Kak Lumina cantik deh",
]


class WebsocketSender:
    def __init__(self, token: str, channel: str):
        self.token = token
        self.channel = channel.lower()
        if not self.channel.startswith("#"):
            self.channel = f"#{self.channel}"
        
        # Ensure oauth: prefix
        if not self.token.startswith("oauth:"):
            self.token = f"oauth:{self.token}"

        self.username = self.channel[1:] # Assume same username as channel for simplicity
        
        self.ws = None
        self.ready = False
        self.running = False
        
    async def connect(self):
        print(f"Connecting to Twitch IRC via WebSocket ({TWITCH_WS_URL})...")
        try:
            self.ws = await websockets.connect(TWITCH_WS_URL, open_timeout=10)
            
            # Authenticate
            await self.ws.send(f"PASS {self.token}")
            await self.ws.send(f"NICK {self.username}")
            await self.ws.send(f"JOIN {self.channel}")
            
            # Start listener loop to handle PING/PONG and login success
            asyncio.create_task(self._listen())
            
            # Wait a bit for initial handshake
            await asyncio.sleep(2)
            if self.ready:
                print(f"✓ Connected to Twitch as: {self.username}")
                print(f"✓ Target channel: {self.channel}")
            else:
                 print(f"⚠ Connected but not yet authenticated/joined. Waiting...")
                 
        except Exception as e:
            print(f"✗ Connection failed: {e}")
            self.ready = False

    async def _listen(self):
        self.running = True
        while self.running and self.ws:
            try:
                msg = await self.ws.recv()
                for line in msg.split("\r\n"):
                    line = line.strip()
                    if not line: continue
                    
                    if line.startswith("PING"):
                        await self.ws.send(line.replace("PING", "PONG"))
                        continue
                        
                    if "001" in line and ":Welcome" in line:
                         self.ready = True
                         print("✓ Login successful!")
                         
                    # Check for PART/JOIN/PRIVMSG/NOTICE errors/etc if needed
                    
            except websockets.ConnectionClosed:
                print("⚠ Connection closed by server")
                self.ready = False
                break
            except Exception as e:
                print(f"⚠ Listener error: {e}")
                break

    async def send_test_message(self, message: str):
        """Send a message to the channel with [TEST] prefix."""
        if not self.ws or not self.ready:
            print("✗ Not ready/connected yet...")
            return False
            
        try:
            # Add [TEST] prefix so the bot processes it
            prefixed_message = f"[TEST] {message}"
            cmd = f"PRIVMSG {self.channel} :{prefixed_message}"
            await self.ws.send(cmd)
            print(f"→ Sent: \"{message}\"")
            return True
        except Exception as e:
            print(f"✗ Error sending: {e}")
            return False
            
    async def close(self):
        self.running = False
        if self.ws:
            await self.ws.close()


async def run_sender(duration: int = 60, interval_min: float = 5, interval_max: float = 15):
    """Run the Twitch chat sender."""
    
    # Check config
    if not config.TWITCH_BOT_TOKEN:
        print("✗ Error: TWITCH_BOT_TOKEN not configured in .env")
        return
    if not config.TWITCH_CHANNEL:
        print("✗ Error: TWITCH_CHANNEL not configured in .env")
        return
    
    print("\n" + "="*60)
    print("🎮 Twitch Chat Sender (Full Loop Test) - WebSocket Version")
    print(f"Channel: {config.TWITCH_CHANNEL}")
    print(f"Duration: {duration}s | Interval: {interval_min}-{interval_max}s")
    print("="*60)
    print("\n⚠️  Make sure 'python src/api_server.py' is running!")
    print("⚠️  Messages will appear as YOUR bot account! Check Twitch Chat.\n")
    
    sender = WebsocketSender(
        token=config.TWITCH_BOT_TOKEN,
        channel=config.TWITCH_CHANNEL
    )
    
    await sender.connect()
    
    # Wait for connection
    for _ in range(15):
        if sender.ready:
            break
        await asyncio.sleep(1)
    
    if not sender.ready:
        print("✗ Failed to connect/authenticate to Twitch within 15 seconds")
        await sender.close()
        return
    
    print("\n--- Starting message loop ---\n")
    
    messages_sent = 0
    start_time = time.time()
    
    try:
        while time.time() - start_time < duration:
            message = random.choice(MESSAGES)
            if await sender.send_test_message(message):
                messages_sent += 1
            
            wait_time = random.uniform(interval_min, interval_max)
            print(f"   (waiting {wait_time:.1f}s...)")
            await asyncio.sleep(wait_time)
            
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\nError in loop: {e}")
    
    # Summary
    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"📊 Summary")
    print(f"Duration: {elapsed:.1f}s")
    print(f"Messages sent: {messages_sent}")
    if elapsed > 0:
        print(f"Rate: {messages_sent/elapsed*60:.1f} messages/min")
    print(f"{'='*60}\n")
    
    # Cleanup
    await sender.close()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Send messages to actual Twitch chat")
    parser.add_argument("--duration", type=int, default=120, help="Duration in seconds (default: 60)")
    parser.add_argument("--min", type=float, default=1, help="Min interval between messages (default: 5)")
    parser.add_argument("--max", type=float, default=1.5, help="Max interval between messages (default: 15)")
    
    args = parser.parse_args()
    
    print("\nStarting in 3 seconds...")
    time.sleep(3)
    
    try:
        asyncio.run(run_sender(
            duration=args.duration,
            interval_min=args.min,
            interval_max=args.max
        ))
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
