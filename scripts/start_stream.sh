#!/bin/bash
# Shell Mode Streaming — Single Display
# Playwright opens /shell page (content iframe + VTuber iframe)
# FFmpeg captures one display, no overlay filter needed

set +e

# Load environment
if [ -f "src/.env" ]; then
    export $(grep -v '^#' src/.env | tr -d '\r' | xargs)
fi

# Configuration
DISPLAY_NUM=55
RESOLUTION="1920x1080"
FPS=30
BITRATE="1500k"
TWITCH_URL="rtmps://live.twitch.tv:443/app"
YOUTUBE_URL="rtmps://a.rtmp.youtube.com:443/live2"

# Force correct display
export DISPLAY=:$DISPLAY_NUM

if [ -z "$TWITCH_STREAM_KEY" ]; then
    echo "ERROR: TWITCH_STREAM_KEY not set"
    exit 1
fi

# Cleanup
cleanup() {
    echo "Stopping stream..."
    pkill -f "Xvfb :$DISPLAY_NUM" 2>/dev/null || true
    pkill -f "ffmpeg.*twitch" 2>/dev/null || true
    pkill -f "ffmpeg.*youtube" 2>/dev/null || true
    pkill -f "chrome" 2>/dev/null || true
    pkill -f "python3.*api_server" 2>/dev/null || true
    pkill -f "node.*next-server" 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM

# Start display
echo "=== Starting Display :$DISPLAY_NUM ==="
Xvfb :$DISPLAY_NUM -screen 0 ${RESOLUTION}x24 \
    +extension GLX +render \
    -nolisten unix -listen tcp -ac &
XVFB_PID=$!
sleep 2

# Audio FIFO
AUDIO_PIPE="/tmp/tts_audio.fifo"
if [ ! -p "$AUDIO_PIPE" ]; then
    rm -f "$AUDIO_PIPE"
    mkfifo "$AUDIO_PIPE"
fi

# Activate venv
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
if [ -f "$PROJECT_DIR/venv_wsl/bin/activate" ]; then
    source "$PROJECT_DIR/venv_wsl/bin/activate"
elif [ -f "$PROJECT_DIR/venv/bin/activate" ]; then
    source "$PROJECT_DIR/venv/bin/activate"
fi

# Kill stale processes from previous runs
echo "=== Cleaning up stale processes ==="
pkill -f "node.*next-server" 2>/dev/null || true
pkill -f "python3.*api_server" 2>/dev/null || true
sleep 1

# Start frontend
echo "=== Starting Frontend (Next.js) ==="
cd "$PROJECT_DIR/vtuber"
npm run dev -- -p 3001 > "$PROJECT_DIR/logs/frontend_dev.log" 2>&1 &
FRONTEND_PID=$!

echo "Waiting for frontend to be ready on http://localhost:3001..."
MAX_RETRIES=60
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -sf http://localhost:3001 > /dev/null 2>&1; then
        echo "Frontend is ready"
        break
    fi
    if ! kill -0 $FRONTEND_PID 2>/dev/null; then
        echo "Frontend failed to start (check logs/frontend_dev.log)"
        exit 1
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    sleep 1
done


echo "=== Starting Backend ==="
cd "$PROJECT_DIR"
python3 -u src/api_server.py &
BACKEND_PID=$!

# Wait for backend
echo "Waiting for backend..."
MAX_RETRIES=60
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s http://localhost:8000 > /dev/null 2>&1; then
        echo "Backend is running"
        break
    fi
    if ! kill -0 $BACKEND_PID 2>/dev/null; then
        echo "Backend died"
        exit 1
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    sleep 1
done

# Backend starts Playwright which opens the /shell page on this display.
# The shell page contains both the content iframe and the VTuber iframe.
# Wait for browser to initialize
echo "Waiting for browser to initialize..."
sleep 15

# FFmpeg — single display capture, no overlay filter
echo "=== Starting Stream ==="

ffmpeg \
    -thread_queue_size 1024 \
    -f x11grab -video_size $RESOLUTION -framerate $FPS -i :$DISPLAY_NUM \
    -thread_queue_size 2048 \
    -use_wallclock_as_timestamps 1 \
    -f s16le -ar 48000 -ac 1 -i "$AUDIO_PIPE" \
    -map 0:v -map 1:a \
    -c:v libx264 -preset veryfast -tune zerolatency \
    -b:v 6800k -maxrate 6800k -bufsize 13600k \
    -pix_fmt yuv420p \
    -g $(($FPS * 2)) \
    -c:a aac -b:a 128k -ar 48000 \
    -af "aresample=async=1" \
    -max_muxing_queue_size 1024 \
    -fflags +nobuffer -flags +low_delay \
    -f tee "[f=flv]$TWITCH_URL/$TWITCH_STREAM_KEY|[f=flv]$YOUTUBE_URL/$YOUTUBE_STREAM_KEY" &
FFMPEG_PID=$!

echo ""
echo "=== Stream Started (Shell Mode) ==="
echo "Display: :$DISPLAY_NUM (1920x1080) - Content + VTuber in single window"
echo "Check: https://dashboard.twitch.tv"
echo ""
echo "PIDs: Xvfb=$XVFB_PID, Backend=$BACKEND_PID, FFmpeg=$FFMPEG_PID"

wait $FFMPEG_PID
