import asyncio
import logging
import os
import threading
import time
from typing import Optional

# Prevent chat_downloader's colorama from corrupting Windows terminal state
os.environ.setdefault('NO_COLOR', '1')

from chat_downloader import ChatDownloader
from chat_downloader.errors import NoChatReplay, ChatDisabled, VideoNotFound, LoginRequired
from chat.aggregator import ChatMessage
from ws.manager import ws_manager

logger = logging.getLogger(__name__)

# Suppress chat_downloader's verbose internal logging.
from chat_downloader import debugging as _cd_debug
_cd_debug.set_log_level('WARNING')


class YouTubeBot:
    def __init__(self, video_id: str = "", channel_handle: str = "", aggregator=None):
        self.video_id = video_id
        self.channel_handle = channel_handle
        self.aggregator = aggregator
        self.running = False
        self.shutting_down = False
        self._downloader: Optional[ChatDownloader] = None
        self._reconnect_delay = 5
        self._max_reconnect_delay = 30

    def _get_url(self) -> str:
        """Build the YouTube URL. Prefer channel handle (auto-detects current live stream)."""
        if self.channel_handle:
            handle = self.channel_handle
            if not handle.startswith("@"):
                handle = f"@{handle}"
            return f"https://www.youtube.com/{handle}/live"
        return f"https://www.youtube.com/watch?v={self.video_id}"

    async def start(self):
        self.running = True
        url = self._get_url()

        while self.running and not self.shutting_down:
            try:
                logger.info(f"[YouTubeBot] Connecting to live chat: {url}")
                self._downloader = ChatDownloader()

                chat = await asyncio.to_thread(
                    self._downloader.get_chat,
                    url=url,
                    chat_type='live',
                    message_receive_timeout=0.1,
                    inactivity_timeout=None,
                    timeout=None,
                )
                logger.info(f"[YouTubeBot] Connected to YouTube live chat")
                self._reconnect_delay = 5

                await self._poll_loop(chat)

            except (NoChatReplay, ChatDisabled) as e:
                logger.info(f"[YouTubeBot] Chat not available: {e}. Retrying in {self._reconnect_delay}s...")
            except VideoNotFound:
                if self.channel_handle:
                    logger.info(f"[YouTubeBot] No active live stream found for {self.channel_handle}. Retrying in {self._reconnect_delay}s...")
                else:
                    logger.error(f"[YouTubeBot] Video {self.video_id} not found. Stopping.")
                    self.running = False
                    break
            except LoginRequired:
                logger.error(f"[YouTubeBot] Video requires login. Stopping.")
                self.running = False
                break
            except asyncio.CancelledError:
                logger.info("[YouTubeBot] Task cancelled.")
                self.running = False
                break
            except Exception as e:
                logger.error(f"[YouTubeBot] Error: {type(e).__name__}: {e}")

            if not self.running or self.shutting_down:
                break

            try:
                end_time = asyncio.get_event_loop().time() + self._reconnect_delay
                while asyncio.get_event_loop().time() < end_time and not self.shutting_down:
                    await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                break

            self._reconnect_delay = min(self._reconnect_delay + 5, self._max_reconnect_delay)

    async def _poll_loop(self, chat):
        """Iterate over chat messages from chat-downloader using a dedicated reader thread."""
        queue = asyncio.Queue()

        def _reader_thread():
            """Runs in a background thread — only one next() call at a time."""
            try:
                for msg in chat:
                    queue.put_nowait(msg)
                    if not self.running:
                        break
            except Exception as e:
                queue.put_nowait(e)
            finally:
                queue.put_nowait(None)  # Sentinel: stream ended

        reader = threading.Thread(target=_reader_thread, daemon=True)
        reader.start()

        while self.running and not self.shutting_down:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=10.0)

                if item is None:
                    logger.info("[YouTubeBot] Chat stream ended.")
                    break

                if isinstance(item, Exception):
                    raise item

                author = item.get('author', {}).get('name', 'Unknown')
                message = item.get('message', '')

                if message:
                    await self.handle_message(author=author, message=message)

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"[YouTubeBot] Poll error: {type(e).__name__}: {e}")
                if self.shutting_down:
                    break
                await asyncio.sleep(1)

    async def handle_message(self, author: str, message: str):

        await ws_manager.broadcast_chat_message(
            username=author,
            message=message,
            user_id="yt_0"
        )

        if self.aggregator:
            chat_msg = ChatMessage(
                message=message,
                user_id="yt_0",
                username=author,
                timestamp=time.time(),
            )
            await self.aggregator.submit_message(chat_msg)
        else:
            logger.warning("[YouTubeBot] No aggregator available")

    async def stop(self):
        logger.info("[YouTubeBot] Stopping...")
        self.shutting_down = True
        self.running = False

    async def close(self):
        await self.stop()


youtube_bot: Optional[YouTubeBot] = None
_youtube_task: Optional[asyncio.Task] = None


async def start_youtube_bot(video_id: str = "", channel_handle: str = "", aggregator=None):
    global youtube_bot, _youtube_task

    if not video_id and not channel_handle:
        logger.warning("[YouTubeBot] No video ID or channel handle configured. Skipping YouTube integration.")
        return None

    try:
        target = channel_handle or video_id
        logger.info(f"[YouTubeBot] Initializing for: {target}")
        youtube_bot = YouTubeBot(
            video_id=video_id,
            channel_handle=channel_handle,
            aggregator=aggregator,
        )

        logger.info("[YouTubeBot] Starting background task...")
        _youtube_task = asyncio.create_task(youtube_bot.start())

        return youtube_bot

    except Exception as e:
        logger.error(f"[YouTubeBot] Failed to start: {e}")
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
            logger.warning(f"[YouTubeBot] Error stopping task: {e}")
        _youtube_task = None
