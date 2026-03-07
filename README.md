# AI VTuber Project

A streaming AI VTuber system: Python backend orchestrates LLM, TTS, vision, and chat integrations while a Next.js frontend renders a Live2D avatar with real-time audio and lip-sync over WebSocket.


More VODs: https://www.twitch.tv/vincentmato1000

## Important Notes

- **Inference Speed**: Response time for LLM and TTS varies depending on your internet connection and provider.
- **Voice Cloning**: The default Qwen TTS uses voice cloning. You may notice imperfections — switch to a non-cloning engine via `TTS_PROVIDER` if needed.

## Prerequisites

- **Python 3.10+** (recommend 3.11 or 3.12)
- **Node.js 18+**
- **ffmpeg** (for audio pipeline on Linux/Mac)
- **Playwright** browsers (`playwright install chromium`)

## Quick Start

```bash
# 1. Clone and configure
cp .env.example src/.env
# Edit src/.env with your API keys

# 2. Backend
pip install -r requirements.txt
python src/api_server.py

# 3. Frontend (separate terminal)
cd vtuber && npm install && npm run dev
```

Backend runs on `http://localhost:8000`, frontend on `http://localhost:3000`.

## Architecture

```
Chat Input (Twitch/YouTube)
    │
    ▼
ChatAggregator ──► Filter Chain ──► Emotion Detection ──► LLM Stream
                                                              │
                                                              ▼
Frontend (Live2D + Audio) ◄── WebSocket ◄── TTS Stream ◄── Response
    │
    ▼
OBS (Browser Source + Chroma Key)
```

**Concurrent Vision Loop:**
```
Browser Automation (scroll/click) ──► Screenshot Buffer ──► VLM Reaction ──► TTS ──► WebSocket
```

### Backend (`src/`)

| Module | Description |
| :--- | :--- |
| `api_server.py` | FastAPI entry point (port 8000). Routes: `GET /shell`, `WebSocket /ws/chat` |
| `core/config.py` | All configuration with `.env` overrides |
| `core/state.py` | Global state: speech slot lock, chat history (20 messages), audio signaling |
| `core/utils.py` | Prompt loading, system prompt construction, image compression |
| `llm/` | LLM providers: `deepseek.py`, `openrouter.py`, `qwen.py`, `remote_vllm.py` |
| `tts/` | TTS providers: `qwen_tts.py` (voice cloning), `realtimetts.py`. Text normalization |
| `chat/` | Aggregator, filters, emotion detection, scoring |
| `vision/` | VisionHeartbeat: browser automation + VLM reaction loop |
| `browser/` | Playwright controller for automated browsing and screenshots |
| `audio/` | Dual output: WebSocket (frontend) + FIFO pipe (OBS/system, Linux/Mac only) |
| `ws/` | WebSocket manager for client tracking and typed broadcasts |
| `rag/` | Tool calling: product search, website search, page navigation |
| `prompts/` | Persona (`soul.md`), rules (`rules.md`), vision instructions (`vision_reaction.md`) |

### Frontend (`vtuber/`)

| File | Description |
| :--- | :--- |
| `app/page.tsx` | Main component. WebSocket connection, emotion state, audio management |
| `components/Avatar.tsx` | Live2D model (PixiJS v6 + pixi-live2d-display). Emotion-to-motion mapping |
| `hooks/useAudioPlayer.ts` | Streaming chunked audio playback (WebAudio API, 8KB buffer merge) |
| `lib/chatWebSocket.ts` | WebSocket with auto-reconnect (3s delay) |
| `components/ScreenCapture.tsx` | Periodic screen capture (10s default) |

**Frontend Query Params:**
- `?green=1` or `?bg=green` — Green screen mode for chroma keying
- `?stream=1` or `?autoplay=1` — Auto-enable streaming audio

**Emotion-to-Motion Mapping:**

| Emotion | Motion |
| :--- | :--- |
| happy | Flick |
| excited | FlickUp |
| sad | Flick@Body |
| angry | FlickDown / Tap@Body |
| neutral | Idle |

## Configuration

Create `src/.env` from the template:

```bash
cp .env.example src/.env
```

### Provider Selection

| Variable | Options | Description |
| :--- | :--- | :--- |
| `LLM_PROVIDER` | `deepseek`, `openrouter` | Chat LLM provider |
| `VLLM_PROVIDER` | `qwen`, `remote` | Vision LLM provider |
| `TTS_PROVIDER` | `qwen`, `realtimetts` | Text-to-speech provider |

### API Keys

| Variable | Provider | Get From |
| :--- | :--- | :--- |
| `DEEPSEEK_API_KEY` | DeepSeek (chat) | [platform.deepseek.com](https://platform.deepseek.com/) |
| `OPENROUTER_API_KEY` | OpenRouter (chat) | [openrouter.ai](https://openrouter.ai/) |
| `QWEN_API_KEY` | Qwen/DashScope (vision + TTS) | [Alibaba Cloud ModelStudio](https://www.alibabacloud.com/en/product/modelstudio) |
| `ELEVENLABS_API_KEY` | ElevenLabs (TTS) | [elevenlabs.io](https://elevenlabs.io/) |

### Chat Integrations

**Twitch:**

| Variable | Description |
| :--- | :--- |
| `TWITCH_ENABLED` | `true` / `false` |
| `TWITCH_BOT_TOKEN` | OAuth token (`oauth:xxxx`) from [twitchtokengenerator.com](https://twitchtokengenerator.com/) |
| `TWITCH_CHANNEL` | Channel name to join |
| `TWITCH_CLIENT_ID` | App client ID |
| `TWITCH_STREAM_KEY` | Stream key (for server-side streaming) |
| `TWITCH_BOT_PREFIX` | Command prefix (default: `!`) |

**YouTube:**

| Variable | Description |
| :--- | :--- |
| `YOUTUBE_ENABLED` | `true` / `false` |
| `YOUTUBE_VIDEO_ID` | Direct video ID (for replays) |
| `YOUTUBE_CHANNEL_HANDLE` | Channel handle, e.g. `@YourChannel` (auto-detects live stream) |

### Chat Aggregation

| Variable | Default | Description |
| :--- | :--- | :--- |
| `CHAT_AGGREGATION_ENABLED` | `true` | Enable message batching |
| `AGGREGATION_WINDOW_SECONDS` | `5.0` | Time window for collecting messages |
| `MIN_RESPONSE_INTERVAL_SECONDS` | `5.0` | Minimum time between AI responses |
| `MAX_MESSAGES_PER_USER_PER_WINDOW` | `3` | Rate limit per user |
| `SIMILARITY_THRESHOLD` | `0.8` | Jaccard similarity for duplicate detection |
| `DUPLICATE_EXPIRY_SECONDS` | `60.0` | How long to track duplicates |
| `MAX_BATCH_SIZE` | `10` | Max messages per batch |

### Browser Automation

| Variable | Default | Description |
| :--- | :--- | :--- |
| `BROWSER_BASE_URL` | WEF Cybersecurity Report | Starting URL for browsing |
| `BROWSER_HEADLESS` | `false` | Run browser in headless mode |
| `BROWSER_SCROLL_AMOUNT_MIN` | `150` | Minimum scroll pixels |
| `BROWSER_SCROLL_AMOUNT_MAX` | `600` | Maximum scroll pixels |
| `SHELL_ENABLED` | `true` | Single-window OBS overlay mode |
| `VTUBER_FRONTEND_URL` | `http://localhost:3000` | Frontend URL for shell mode |

See `.env.example` for the complete list of options.

## Chat Processing Pipeline

Messages pass through a multi-layer filter chain before reaching the LLM:

1. **Length** — Minimum 2 characters
2. **Emote-only** — Strips emote patterns
3. **Gibberish** — Vowel ratio < 15%, long consonant clusters (4+), low character variety
4. **Off-topic** — Regex patterns from `chat/data/off_topic_patterns.md`
5. **Rate limit** — Max 3 messages per user per 5-second window
6. **Duplicates** — Exact match or Jaccard similarity >= 0.8 within last 60s

**Scoring** prioritizes messages with bonuses: questions (+3.0), name mentions (+2.0), long messages (+1.0), images (+2.0), recency (+0.5).

**Emotion Detection** uses sentence-transformer embeddings (`paraphrase-multilingual-MiniLM-L12-v2`) to classify into 5 emotions. Batch encoding runs in a thread pool to avoid blocking the event loop. Training data in `chat/data/emotions.md`.

## Audio Pipeline

Audio has a dual output path:

1. **Frontend (WebSocket)** — `audio/interceptor.py` monkey-patches TTS to base64-encode WAV chunks and broadcast via WebSocket for in-browser playback + lip-sync.
2. **System/OBS (FIFO)** — `audio/pipe.py` writes raw PCM to `/tmp/tts_audio.fifo` using ffmpeg (48kHz resampling). **Linux/Mac only** — disabled on Windows.

Speech serialization via `core/state.py` ensures only one audio stream plays at a time. A 1-second gap is enforced between responses.

## Tool Calling / RAG

The LLM supports three tools:

| Tool | Description |
| :--- | :--- |
| `search_product` | Search Klikindomaret product inventory (WAF token auto-managed) |
| `search_website` | Search current site content via embedding-based index |
| `navigate_to_page` | Trigger browser navigation to a new URL |

## OBS Setup

1. Add `http://localhost:3000?green=1` as a **Browser Source**
2. Right-click the source > **Filters** > Add **Chroma Key**
3. Default Green key color works automatically

Or use `http://localhost:8000/shell` for the single-window overlay mode (content iframe + vtuber iframe side by side).

## Streaming to Twitch / YouTube

To stream directly to Twitch and YouTube from a Linux server (uses Xvfb + FFmpeg):

```bash
# Start streaming (launches backend, frontend, browser, and FFmpeg)
./scripts/start_stream.sh

# Stop all processes
./scripts/kill_all.sh
```

Make sure `TWITCH_STREAM_KEY` and `YOUTUBE_STREAM_KEY` are set in `src/.env`.

## Docker Deployment

```bash
# Configure
cp .env.example src/.env
nano src/.env

# Build and run
chmod +x setup-docker.sh
./setup-docker.sh setup

# Or manually
docker-compose up -d
```

| Service | URL |
| :--- | :--- |
| Backend API | `http://your-ip:8000` |
| API Docs | `http://your-ip:8000/docs` |
| Frontend | `http://your-ip:3000` |

**Requirements:** 4GB RAM min (8GB recommended), 20GB+ disk, 2+ CPU cores.

See `DOCKER_QUICKSTART.md` for the full deployment guide.

## Testing

Run from the `src/` directory:

```bash
# All tests
cd src && pytest

# Single file
cd src && pytest test/unit_test/test_chat_aggregator.py

# Single function
cd src && pytest test/unit_test/test_emotions.py::test_detect_emotion
```

## Project Structure

```
.
├── src/
│   ├── api_server.py          # FastAPI entry point
│   ├── core/                  # Config, state, utilities
│   ├── llm/                   # LLM providers (DeepSeek, OpenRouter, Qwen, Remote)
│   ├── tts/                   # TTS providers (Qwen, RealtimeTTS) + text normalization
│   ├── chat/                  # Aggregator, filters, emotions, scoring
│   ├── vision/                # VisionHeartbeat + browser automation loop
│   ├── browser/               # Playwright controller + behavior definitions
│   ├── audio/                 # Interceptor (WebSocket) + pipe (FIFO)
│   ├── ws/                    # WebSocket manager
│   ├── rag/                   # Tool calling, product search, website indexing
│   ├── twitch/                # Twitch bot integration
│   ├── youtube/               # YouTube live chat integration
│   ├── prompts/               # soul.md, rules.md, vision_reaction.md
│   └── test/                  # Unit tests + manual tests
├── vtuber/                    # Next.js frontend (Live2D avatar)
│   ├── app/page.tsx           # Main component
│   ├── components/            # Avatar, ScreenCapture
│   ├── hooks/                 # useAudioPlayer
│   ├── lib/                   # chatWebSocket
│   └── public/model/          # Live2D model files
├── .env.example               # Configuration template
├── Dockerfile                 # Multi-stage Docker build
├── docker-compose.yml         # Docker orchestration
└── setup-docker.sh            # Interactive setup script
```

## Features

- **Multi-LLM Support** — DeepSeek, OpenRouter, Qwen, Remote vLLM
- **Voice-Cloned TTS** — Qwen TTS with custom voice cloning, ElevenLabs fallback
- **Live2D Avatar** — PixiJS rendering with 5-emotion motion mapping and lip-sync
- **Vision System** — Automated browser browsing with VLM reactions to on-screen content
- **Chat Aggregation** — Batches, deduplicates, and prioritizes messages from Twitch/YouTube
- **Emotion Detection** — Multilingual sentence-transformer classification (async batch processing)
- **Tool Calling** — Product search, website search, page navigation
- **RAG** — Embedding-based website content search + Klikindomaret product inventory
- **Dual Audio Output** — WebSocket (frontend) + FIFO pipe (OBS/system)
- **Docker Deployment** — One-command setup with `setup-docker.sh`
