"""
Twitch Bot Integration
Connects to Twitch IRC and forwards chat messages to the chat aggregator
"""

from twitchio.ext import commands
import asyncio
import time
import logging
from typing import Optional
from chat.aggregator import ChatMessage
from websocket.manager import ws_manager


class TwitchBot(commands.Bot):
    """Twitch IRC bot that integrates with chat aggregation"""
    
    def __init__(self, token: str, channel: str, prefix: str, aggregator=None):
        super().__init__(
            token=token,
            prefix=prefix,
            initial_channels=[channel]
        )
        self.aggregator = aggregator
        self.channel_name = channel
        logging.info(f"[TwitchBot] Initialized for channel: {channel}")
    
    async def event_ready(self):
        """Called when the bot is ready"""
        logging.info(f"[TwitchBot] Logged in as {self.nick}")
        logging.info(f"[TwitchBot] Connected to channel: {self.channel_name}")
        logging.info(f"[TwitchBot] Bot is ready!")
    
    async def event_message(self, message):
        """Called when a message is received in chat"""
        # Ignore messages from the bot itself
        if message.echo:
            return
        
        # Ignore commands (messages starting with prefix)
        if message.content.startswith(self._prefix):
            await self.handle_commands(message)
            return
        
        logging.debug(f"[TwitchBot] {message.author.name}: {message.content}")
        
        # Broadcast to WebSocket clients
        await ws_manager.broadcast_chat_message(
            username=message.author.name,
            message=message.content,
            user_id=str(message.author.id)
        )
        
        # Submit to chat aggregator if available
        if self.aggregator:
            chat_msg = ChatMessage(
                message=message.content,
                user_id=str(message.author.id),
                username=message.author.name,
                timestamp=time.time()
            )
            
            accepted = await self.aggregator.submit_message(chat_msg)
            
            if not accepted:
                logging.debug(f"[TwitchBot] Message from {message.author.name} was filtered")
    
    @commands.command(name='lumina')
    async def lumina_command(self, ctx: commands.Context):
        """Example command: !lumina"""
        await ctx.send(f"Hi {ctx.author.name}! I'm Lumina, your Indomaret Brand Ambassador! 😊")
    
    @commands.command(name='promo')
    async def promo_command(self, ctx: commands.Context):
        """Show current promotions"""
        await ctx.send("Check out our latest Harga Heboh deals at Indomaret! Ask me about specific products! 🛒")
    
    @commands.command(name='help')
    async def help_command(self, ctx: commands.Context):
        """Show available commands"""
        await ctx.send("Commands: !lumina, !promo, !help | Just chat with me normally and I'll respond! 💬")
    
    async def send_response(self, text: str):
        """Send Lumina's response to Twitch chat"""
        try:
            channel = self.get_channel(self.channel_name)
            if channel:
                # Split long messages (Twitch has 500 char limit)
                if len(text) > 450:
                    text = text[:447] + "..."
                
                await channel.send(text)
                logging.info(f"[TwitchBot] Sent to chat: {text}")
        except Exception as e:
            logging.error(f"[TwitchBot] Error sending message: {e}")


# Global bot instance
twitch_bot: Optional[TwitchBot] = None


async def start_twitch_bot(token: str, channel: str, prefix: str = "!", aggregator=None):
    """Start the Twitch bot"""
    global twitch_bot
    
    if not token or not channel:
        logging.warning("[TwitchBot] Token or channel not configured. Skipping Twitch integration.")
        return None
    
    try:
        twitch_bot = TwitchBot(
            token=token,
            channel=channel,
            prefix=prefix,
            aggregator=aggregator
        )
        
        # Run bot in background
        asyncio.create_task(twitch_bot.start())
        logging.info("[TwitchBot] Starting bot...")
        
        return twitch_bot
        
    except Exception as e:
        logging.error(f"[TwitchBot] Failed to start: {e}")
        return None


def get_twitch_bot():
    """Get the global Twitch bot instance"""
    return twitch_bot
