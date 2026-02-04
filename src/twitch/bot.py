from twitchio.ext import commands
import asyncio
import time
import logging
from datetime import datetime, timezone
from typing import Optional
from chat.aggregator import ChatMessage
from ws.manager import ws_manager


class TwitchBot(commands.Bot):
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
 
        logging.info(f"[TwitchBot] Logged in as {self.nick}")
        logging.info(f"[TwitchBot] Connected to channel: {self.channel_name}")
        logging.info(f"[TwitchBot] Bot is ready!")
    
    async def event_message(self, message):

        if message.echo:
            return
        
        if message.content.startswith(self._prefix):
            await self.handle_commands(message)
            return
        
        logging.debug(f"[TwitchBot] {message.author.name}: {message.content}")

        if hasattr(message, 'timestamp') and message.timestamp:
            try:
                ts = message.timestamp
                if hasattr(ts, 'replace') and ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                
                msg_time = ts.timestamp() if hasattr(ts, 'timestamp') else ts
                
                latency = time.time() - msg_time
                logging.info(f"[TwitchBot] Message received from Twitch. Latency: {latency:.3f}s")
            except Exception as e:
                logging.debug(f"[TwitchBot] Could not calculate latency: {e}")

        await ws_manager.broadcast_chat_message(
            username=message.author.name,
            message=message.content,
            user_id=str(message.author.id)
        )
        
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
        await ctx.send(f"Hi {ctx.author.name}! I'm Lumina, your Indomaret Brand Ambassador! 😊")
    
    @commands.command(name='promo')
    async def promo_command(self, ctx: commands.Context):
        await ctx.send("Check out our latest Harga Heboh deals at Indomaret! Ask me about specific products! 🛒")
    
    @commands.command(name='help')
    async def help_command(self, ctx: commands.Context):
        await ctx.send("Commands: !lumina, !promo, !help | Just chat with me normally and I'll respond! 💬")
    
    async def send_response(self, text: str):
 
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

        task = asyncio.create_task(twitch_bot.start())
        
        def on_task_done(t):
            try:
                exc = t.exception()
                if exc:
                    logging.error(f"[TwitchBot] Task failed: {exc}")
            except asyncio.CancelledError:
                logging.info("[TwitchBot] Task was cancelled")
            except Exception as e:
                logging.error(f"[TwitchBot] Error in done callback: {e}")
        
        task.add_done_callback(on_task_done)
        logging.info("[TwitchBot] Starting bot...")
        
        return twitch_bot
        
    except Exception as e:
        logging.error(f"[TwitchBot] Failed to start: {e}")
        return None

def get_twitch_bot():
    return twitch_bot
