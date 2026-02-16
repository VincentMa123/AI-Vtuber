import asyncio
import logging
import ssl
import re
from datetime import datetime, timezone
import time
from typing import Optional
from twitchio.ext import commands
from chat.aggregator import ChatMessage
from ws.manager import ws_manager

class TwitchBot:
    def __init__(self, token: str, channel: str, prefix: str = "!", aggregator=None, 
                 client_id: str = "", client_secret: str = "", bot_id: str = ""):
        self.token = token
        self.channel = channel.lower()
        if not self.channel.startswith("#"):
            self.channel = f"#{self.channel}"
        self.prefix = prefix
        self.aggregator = aggregator
        self.username = self.channel[1:] # Assume bot is same as channel for user token
        
        # Ensure oauth: prefix
        if not self.token.startswith("oauth:"):
            self.token = f"oauth:{self.token}"
            
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.running = False
        self.reconnect_delay = 5

    async def start(self):
        self.running = True
        while self.running:
            try:
                await self._connect()
                await self._listen()
            except asyncio.CancelledError:
                logging.info("[TwitchBot] Task cancelled.")
                self.running = False
                break
            except Exception as e:
                logging.error(f"[TwitchBot] Connection error: {e}")
                logging.info(f"[TwitchBot] Reconnecting in {self.reconnect_delay}s...")
                await asyncio.sleep(self.reconnect_delay)
            finally:
                await self._disconnect()

    async def _connect(self):
        logging.info(f"[TwitchBot] Connecting to Twitch IRC (SSL)...")
        ctx = ssl.create_default_context()
        self.reader, self.writer = await asyncio.open_connection(
            'irc.chat.twitch.tv', 6697, ssl=ctx,
            ssl_handshake_timeout=10.0
        )
        
        # Authenticate
        self.writer.write(f"PASS {self.token}\r\n".encode())
        self.writer.write(f"NICK {self.username}\r\n".encode())
        self.writer.write(f"JOIN {self.channel}\r\n".encode())
        await self.writer.drain()
        logging.info(f"[TwitchBot] Auth sent. Joining {self.channel}...")

    async def _disconnect(self):
        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except:
                pass
        self.reader = None
        self.writer = None

    async def _listen(self):
        if not self.reader:
            return

        while self.running:
            line_bytes = await self.reader.readline()
            if not line_bytes:
                logging.warning("[TwitchBot] Connection closed by server.")
                break
            
            line = line_bytes.decode('utf-8').strip()
            
            # Keep-alive
            if line.startswith("PING"):
                pong = line.replace("PING", "PONG")
                logging.debug(f"[TwitchBot] Sending {pong}")
                self.writer.write(f"{pong}\r\n".encode())
                await self.writer.drain()
                continue
            
            # Handle Login Success
            if "001" in line and ":Welcome" in line:
                logging.info(f"[TwitchBot] ✅ Login Successful! Connected as {self.username}")
                continue

            # Handle Chat Messages
            # Format: :username!user@user.tmi.twitch.tv PRIVMSG #channel :message
            # Regex to parse IRV privmsg
            # Group 1: Username, Group 2: Channel, Group 3: Message
            match = re.search(r":(\w+)!\w+@\w+\.tmi\.twitch\.tv PRIVMSG (#\w+) :(.*)", line)
            if match:
                user = match.group(1)
                chan = match.group(2)
                msg = match.group(3)
                await self.handle_message(user, msg)
            elif "PRIVMSG" in line:
                # Fallback logging if regex fails but it's a message
                logging.debug(f"[TwitchBot] Unparsed PRIVMSG: {line}")

    async def handle_message(self, user: str, message: str):
        
        # Broadcast to UI
        await ws_manager.broadcast_chat_message(
            username=user,
            message=message,
            user_id="0" # We don't have ID from raw IRC easily without tags, but 0 is fine for display
        )
        
        # Aggregator
        if self.aggregator:
            chat_msg = ChatMessage(
                message=message,
                user_id="0",
                username=user,
                timestamp=time.time()
            )
            await self.aggregator.submit_message(chat_msg)

        # Commands
        if message.startswith(self.prefix):
            cmd = message[len(self.prefix):].split(" ")[0].lower()
            if cmd == "lumina":
                await self.send_response(f"Hi {user}! I'm Lumina, your Indomaret Brand Ambassador! 😊")
            elif cmd == "promo":
                await self.send_response("Check out our latest Harga Heboh deals at Indomaret! Ask me about specific products! 🛒")
            elif cmd == "help":
                await self.send_response("Commands: !lumina, !promo, !refresh, !help | Just chat with me normally and I'll respond! 💬")
            elif cmd == "refresh":
                 # Import locally to avoid circular imports
                import core.state as state
                if state.vision_heartbeat and state.vision_heartbeat.browser_controller:
                    await state.vision_heartbeat.browser_controller.refresh(force_home=True)
                    await self.send_response("Refreshing the page (Force Home)! 🔄")
                else:
                    await self.send_response("I can't access the browser right now. 😢")

    async def send_response(self, text: str):
        if not self.writer:
            logging.warning("[TwitchBot] Cannot send message: Not connected.")
            return

        try:
             # Twitch limit 500 chars
            if len(text) > 450:
                text = text[:447] + "..."
            
            # IRC command: PRIVMSG #channel :message
            cmd = f"PRIVMSG {self.channel} :{text}\r\n"
            self.writer.write(cmd.encode('utf-8'))
            await self.writer.drain()
            logging.info(f"[TwitchBot] Sent: {text}")
        except Exception as e:
            logging.error(f"[TwitchBot] Error sending message: {e}")

# Global bot instance
twitch_bot: Optional[TwitchBot] = None

async def start_twitch_bot(token: str, channel: str, prefix: str = "!", aggregator=None, client_id: str = "", client_secret: str = "", bot_id: str = ""):
    global twitch_bot
    
    if not token or not channel:
        logging.warning("[TwitchBot] Token or channel not configured. Skipping Twitch integration.")
        return None
    
    try:
        logging.info(f"[TwitchBot] Initializing Simple AsyncBot for channel: {channel}")

        twitch_bot = TwitchBot(
            token=token,
            channel=channel,
            prefix=prefix,
            aggregator=aggregator,
            client_id=client_id,
            client_secret=client_secret,
            bot_id=bot_id
        )

        logging.info("[TwitchBot] Starting background task...")
        asyncio.create_task(twitch_bot.start())
        
        return twitch_bot
        
    except Exception as e:
        logging.error(f"[TwitchBot] Failed to start: {e}")
        return None

def get_twitch_bot():
    return twitch_bot
