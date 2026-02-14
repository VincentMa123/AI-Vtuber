#!/bin/bash
# Start Stream Script - Launch virtual display and stream to Twitch
# Usage: ./scripts/start_stream.sh

# Don't exit on error - we want to handle errors gracefully
set +e

# Load environment variables
if [ -f "src/.env" ]; then
    export $(grep -v '^#' src/.env | xargs)
fi

# Detect Windows Host IP for WSL checks if running in WSL
if grep -q Microsoft /proc/version; then
    # Prefer 192.168.56.1 if reachable (common for VirtualBox/Host-Only)
    if curl -s -m 1 http://192.168.56.1:3000 > /dev/null; then
        HOST_IP="192.168.56.1"
    else
        HOST_IP=$(ip route show | grep default | awk '{print $3}')
    fi

    if [ -z "$VTUBER_FRONTEND_URL" ]; then
        export VTUBER_FRONTEND_URL="http://$HOST_IP:3000"
        echo "Configured VTUBER_FRONTEND_URL=$VTUBER_FRONTEND_URL (Windows Host IP for WSL)"
    fi
fi

# Configuration
DISPLAY_NUM=55
RESOLUTION="1920x1080"
FPS=24
BITRATE="1500k"
TWITCH_URL="rtmp://live.twitch.tv/app"

# Check for stream key
if [ -z "$TWITCH_STREAM_KEY" ]; then
    echo "ERROR: TWITCH_STREAM_KEY not set in src/.env"
    echo "Add: TWITCH_STREAM_KEY=live_xxxxxxxxxxxxx"
    exit 1
fi

# Fix potential X11 socket permission issues and stale locks
echo "=== Cleaning up X11 locks ==="
rm -f /tmp/.X${DISPLAY_NUM}-lock 2>/dev/null || true
rm -f /tmp/.X11-unix/X${DISPLAY_NUM} 2>/dev/null || true

if [ -d "/tmp/.X11-unix" ]; then
    chmod 1777 /tmp/.X11-unix 2>/dev/null || true
else
    mkdir -p /tmp/.X11-unix
    chmod 1777 /tmp/.X11-unix 2>/dev/null || true
fi

# Audio Configuration (Headless FIFO)
AUDIO_PIPE="/tmp/tts_audio.fifo"
echo "=== Audio Configuration (Headless) ==="
echo "Pipe: $AUDIO_PIPE"

# Create FIFO if not exists
if [ ! -p "$AUDIO_PIPE" ]; then
    rm -f "$AUDIO_PIPE"
    mkfifo "$AUDIO_PIPE"
    echo "✓ Created FIFO pipe"
else
    echo "✓ FIFO pipe exists"
fi

# Ensure XDG_RUNTIME_DIR and Cookie if missing (just in case)
if [ -z "$XDG_RUNTIME_DIR" ]; then export XDG_RUNTIME_DIR="/run/user/$(id -u)"; fi

# Cleanup function
cleanup() {
    echo ""
    echo "Stopping stream..."
    pkill -f "Xvfb :$DISPLAY_NUM" 2>/dev/null || true
    pkill -f "ffmpeg.*twitch" 2>/dev/null || true
    pkill -f "google-chrome.*localhost:3000" 2>/dev/null || true
    pkill -f "python3.*api_server" 2>/dev/null || true
    pkill -f "node.*next" 2>/dev/null || true
    echo "Stream stopped."
    exit 0
}
trap cleanup SIGINT SIGTERM

# Kill existing processes
echo "=== Cleaning up existing processes ==="
pkill -f "Xvfb :$DISPLAY_NUM" 2>/dev/null || true
sleep 1

echo "=== Starting Virtual Display (TCP Mode) ==="
# WSLg mounts /tmp/.X11-unix as read-only/system, so we must use TCP
# and avoid trying to create unix sockets there.
Xvfb :$DISPLAY_NUM -screen 0 ${RESOLUTION}x24 \
    +extension GLX +render \
    -nolisten unix \
    -listen tcp \
    -ac &
XVFB_PID=$!
sleep 2

# Point clients to TCP display
export DISPLAY=127.0.0.1:$DISPLAY_NUM
echo "Debug: DISPLAY set to $DISPLAY"

echo "=== Detect Host IP ==="
# Try /etc/resolv.conf first (reliable in WSL2)
HOST_IP=$(grep -m 1 nameserver /etc/resolv.conf | awk '{print $2}')
if [ -z "$HOST_IP" ]; then
    # Fallback to route
    HOST_IP=$(ip route show | grep default | awk '{print $3}')
fi
echo "Host IP: $HOST_IP"

# Use the Host IP for internal services if needed, but for browser
# we might need to access the Next.js app running in WSL.
# Next.js is on localhost:3000 inside WSL.
VTUBER_URL="http://localhost:3000/vtuber/overlay"
echo "Overlay URL: $VTUBER_URL"

echo "=== Starting Chromium (Playwright) ==="
# Prepare browser arguments
# - Use TCP display
# - Force audio output
BROWSER_ARGS="--display=$DISPLAY \
  --window-size=${RESOLUTION%x*},${RESOLUTION#*x} \
  --window-position=0,0 \
  --no-sandbox \
  --disable-setuid-sandbox \
  --disable-dev-shm-usage \
  --autoplay-policy=no-user-gesture-required \
  --use-fake-ui-for-media-stream \
  --disable-features=IsolateOrigins,site-per-process \
  --allow-running-insecure-content \
  --disable-web-security"

echo "Browser Args: $BROWSER_ARGS"
echo "=== Activating Virtual Environment ==="
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
echo "Project directory: $PROJECT_DIR"

# Activate the WSL virtual environment
if [ -f "$PROJECT_DIR/venv_wsl/bin/activate" ]; then
    source "$PROJECT_DIR/venv_wsl/bin/activate"
    echo "Activated venv_wsl"
elif [ -f "$PROJECT_DIR/venv/bin/activate" ]; then
    source "$PROJECT_DIR/venv/bin/activate"
    echo "Activated venv"
fi

echo "=== Starting Backend (Python) ==="
cd "$PROJECT_DIR"
# Playwright browser runs VISIBLE (not headless) to show Klikindomaret
# It will inject the vtuber overlay iframe on top of the page
# Start the Python Backend
# Use -u for unbuffered output to see logs immediately
python3 -u src/api_server.py &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

# Wait for backend to ACTUALLY be ready (retry loop)
echo "Waiting for backend to start..."
MAX_RETRIES=240
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s http://localhost:8000 > /dev/null 2>&1; then
        echo "✓ Backend is running on port 8000"
        break
    fi
    
    # Check if the process is still alive
    if ! kill -0 $BACKEND_PID 2>/dev/null; then
        echo "✗ Backend process died! Check for errors above."
        exit 1
    fi
    
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "  Waiting for backend... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 3
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "✗ Backend failed to start after $MAX_RETRIES attempts"
    exit 1
fi

# Wait for Playwright browser to open and inject the vtuber overlay
echo "Waiting for Playwright browser to initialize..."
sleep 15

ffmpeg \
    -thread_queue_size 2048 \
    -f x11grab -video_size $RESOLUTION -framerate $FPS -i :$DISPLAY_NUM \
    -thread_queue_size 2048 \
    -f s16le -ar 48000 -ac 1 -i "$AUDIO_PIPE" \
    -c:v libx264 -preset ultrafast -tune zerolatency \
    -maxrate $BITRATE -bufsize 4000k \
    -pix_fmt yuv420p \
    -g $(($FPS * 2)) \
    -c:a aac -b:a 128k -ar 48000 \
    -af "aresample=async=1" \
    -map 0:v -map 1:a \
    -f flv "$TWITCH_URL/$TWITCH_STREAM_KEY" &
FFMPEG_PID=$!

echo ""
echo "=== Stream Started ==="
echo "Check your Twitch dashboard: https://dashboard.twitch.tv"
echo "Press Ctrl+C to stop"
echo ""
echo "PIDs: Xvfb=$XVFB_PID, Backend=$BACKEND_PID, FFmpeg=$FFMPEG_PID"

# Wait for FFmpeg (main process)
wait $FFMPEG_PID
