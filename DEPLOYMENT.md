# Deployment Guide

This guide covers deploying the AI Vtuber to stream directly to Twitch from a server (no local PC needed).

## Quick Start (Server-Side Streaming)

```bash
# 1. Setup server (Ubuntu 22.04+)
chmod +x scripts/*.sh
./scripts/stream_setup.sh

# 2. Configure
echo "TWITCH_STREAM_KEY=live_xxxxxxxxxxxx" >> src/.env
# Add other API keys...

# 3. Build frontend
cd vtuber && npm install && npm run build && cd ..

# 4. Start everything (frontend + stream)!
./scripts/start_stream.sh
```

---

## Architecture

```
┌─────────────────── SERVER ───────────────────┐
│  Xvfb (Virtual Display :99)                  │
│  ├── Chrome: Vtuber UI (localhost:3000)      │
│  └── Chrome: Playwright (product browsing)   │
│           │                                   │
│           ▼                                   │
│       FFmpeg ──── RTMP ───► Twitch           │
└───────────────────────────────────────────────┘
```

## Server Requirements

- **OS**: Ubuntu 22.04+ (other Linux distros work too)
- **RAM**: 4GB minimum, 8GB recommended
- **CPU**: 4 cores recommended (for video encoding)
- **Python**: 3.10+
- **Node.js**: 18+

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/stream_setup.sh` | Install Xvfb, FFmpeg, Chrome |
| `scripts/start_stream.sh` | Start virtual display + stream to Twitch |
| `scripts/stop_stream.sh` | Stop all streaming processes |

## Configuration (src/.env)

```ini
# Required for streaming
TWITCH_STREAM_KEY=live_xxxxxxxxxxxxxxxxxxxx

# Get from: Twitch Dashboard → Settings → Stream → Primary Stream Key

# API Keys (as before)
OPENROUTER_API_KEY=...
DEEPSEEK_API_KEY=...
QWEN_API_KEY=...
```

## Testing

### On Server
```bash
./scripts/start_stream.sh
# Check: https://dashboard.twitch.tv/u/YOUR_CHANNEL/stream-manager
```

### Local Testing (Linux/WSL2 only)
Xvfb requires Linux. On Windows, either:
1. Use WSL2 with GUI support (`wslg`)
2. Deploy to a cloud VM (DigitalOcean, Vultr, etc.)

## Troubleshooting

### Stream not starting
```bash
# Check if virtual display is running
ps aux | grep Xvfb

# Check FFmpeg output
./scripts/start_stream.sh 2>&1 | tee stream.log
```

### No audio
```bash
# Ensure PulseAudio is running
pulseaudio --start
pactl info
```

### Chrome crashes
```bash
# Install missing dependencies
sudo apt-get install -f
playwright install-deps
```
