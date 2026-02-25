import asyncio
import logging
import time
from typing import Optional
import pytchat
from chat.aggregator import ChatMessage
from ws.manager import ws_manager

# Suppress pytchat's HTTP logging spam
logging.getLogger('pytchat').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)

class YouTubeBot:
    def __init__(self, video_id: str, aggregator=None):
        self.video_id = video_id
        self.aggregator = aggregator
        self.running = False
        self.shutting_down = False  # Add shutdown flag
        self._livechat: Optional[pytchat.LiveChat] = None
        self._reconnect_delay = 3  # Start with 3 seconds
        self._max_reconnect_delay = 10

    async def start(self):
        self.running = True
        while self.running and not self.shutting_down:
            try:
                logging.info(f"[YouTubeBot] Connecting to live chat for video: {self.video_id}")
                self._livechat = pytchat.create(video_id=self.video_id, interruptable=False)
                logging.info(f"[YouTubeBot] ✅ Connected to YouTube live chat (video: {self.video_id})")
                poll_start = asyncio.get_event_loop().time()
                await self._poll_loop()
                # Only reset delay if the chat was alive for a meaningful duration
                if asyncio.get_event_loop().time() - poll_start > 10:
                    self._reconnect_delay = 3
            except asyncio.CancelledError:
                logging.info("[YouTubeBot] Task cancelled.")
                self.running = False
                break
            except Exception as e:
                logging.error(f"[YouTubeBot] Error: {e}")
            finally:
                self._cleanup_livechat()

            # Don't reconnect if we're shutting down
            if not self.running or self.shutting_down:
                break

            # Apply backoff delay before reconnecting (handles BOTH exceptions and is_alive() failures)
            logging.info(f"[YouTubeBot] Reconnecting in {self._reconnect_delay}s...")
            try:
                end_time = asyncio.get_event_loop().time() + self._reconnect_delay
                while asyncio.get_event_loop().time() < end_time and not self.shutting_down:
                    await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                break
            # Increase delay with backoff (3s -> 5s -> 7s -> 10s -> 10s)
            self._reconnect_delay = min(self._reconnect_delay + 2, self._max_reconnect_delay)

    async def _poll_loop(self):
   
        while self.running and not self.shutting_down:
            if self._livechat is None or not self._livechat.is_alive():
                logging.warning("[YouTubeBot] LiveChat is no longer alive.")
                break

            try:
                # get() is blocking, run in thread with timeout to avoid blocking forever
                try:
                    # pytchat.get() doesn't accept timeout parameter, so just call it
                    chat_data = await asyncio.wait_for(
                        asyncio.to_thread(self._livechat.get),
                        timeout=6.0
                    )
                    for item in chat_data.items:
                        await self.handle_message(
                            author=item.author.name,
                            message=item.message
                        )
                except asyncio.TimeoutError:
                    # Timeout is normal, just means no new messages in that interval
                    pass
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logging.error(f"[YouTubeBot] Poll error: {e}")
                # Check if we should exit
                if self.shutting_down:
                    break

            # Short sleep that can be interrupted
            await asyncio.sleep(0.5)

    async def handle_message(self, author: str, message: str):
        logging.debug(f"[YouTubeBot] handle_message called: {author}: {message}")

        # Broadcast to frontend UI
        await ws_manager.broadcast_chat_message(
            username=author,
            message=message,
            user_id="yt_0"
        )

        # Submit to aggregator
        if self.aggregator:
            chat_msg = ChatMessage(
                message=message,
                user_id="yt_0",
                username=author,
                timestamp=time.time(),
                platform="youtube"  # Track that this is a YouTube message
            )
            await self.aggregator.submit_message(chat_msg)
        else:
            logging.warning(f"[YouTubeBot] No aggregator available")

    async def stop(self):
        logging.info("[YouTubeBot] Stopping...")
        self.shutting_down = True  # Set shutdown flag first
        self.running = False
        self._cleanup_livechat()

    async def close(self):

        await self.stop()


    def _cleanup_livechat(self):
        if self._livechat is not None:
            try:
                self._livechat.terminate()
            except Exception:
                pass
            self._livechat = None


youtube_bot: Optional[YouTubeBot] = None
_youtube_task: Optional[asyncio.Task] = None


async def start_youtube_bot(video_id: str, aggregator=None):
    global youtube_bot, _youtube_task

    if not video_id:
        logging.warning("[YouTubeBot] Video ID not configured. Skipping YouTube integration.")
        return None

    try:
        logging.info(f"[YouTubeBot] Initializing for video: {video_id}")
        youtube_bot = YouTubeBot(video_id=video_id, aggregator=aggregator)

        logging.info("[YouTubeBot] Starting background task...")
        _youtube_task = asyncio.create_task(youtube_bot.start())

        return youtube_bot

    except Exception as e:
        logging.error(f"[YouTubeBot] Failed to start: {e}")
        return None


def get_youtube_bot():
    return youtube_bot


async def stop_youtube_task():

    global _youtube_task
    if _youtube_task and not _youtube_task.done():
        try:
            _youtube_task.cancel()
            await _youtube_task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logging.warning(f"[YouTubeBot] Error stopping task: {e}")
        _youtube_task = None
