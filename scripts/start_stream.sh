#!/bin/bash
# Efficient Streaming with FFmpeg Overlay
# Single browser window + FFmpeg composites VTuber overlay

set +e

# Load environment
if [ -f "src/.env" ]; then
    export $(grep -v '^#' src/.env | tr -d '\r' | xargs)
fi

# Configuration
DISPLAY_NUM=55
OVERLAY_DISPLAY_NUM=56  # Separate small display for VTuber
RESOLUTION="1920x1080"
OVERLAY_SIZE="600x800"  # Smaller VTuber window
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
    pkill -f "Xvfb :$OVERLAY_DISPLAY_NUM" 2>/dev/null || true
    pkill -f "ffmpeg.*twitch" 2>/dev/null || true
    pkill -f "ffmpeg.*youtube" 2>/dev/null || true
    pkill -f "chrome" 2>/dev/null || true
    pkill -f "python3.*api_server" 2>/dev/null || true
    pkill -f "node.*next-server" 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM

# Start main display (content)
echo "=== Starting Main Display :$DISPLAY_NUM ==="
Xvfb :$DISPLAY_NUM -screen 0 ${RESOLUTION}x24 \
    +extension GLX +render \
    -nolisten unix -listen tcp -ac &
XVFB_PID=$!
sleep 2

# Start small display for VTuber overlay
echo "=== Starting Overlay Display :$OVERLAY_DISPLAY_NUM ==="
Xvfb :$OVERLAY_DISPLAY_NUM -screen 0 ${OVERLAY_SIZE}x24 \
    +extension GLX +render \
    -nolisten unix -listen tcp -ac &
XVFB_OVERLAY_PID=$!
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

# Start frontend
echo "=== Starting Frontend (Next.js) ==="
cd "$PROJECT_DIR/vtuber"
npm run start > "$PROJECT_DIR/logs/frontend_dev.log" 2>&1 &
FRONTEND_PID=$!

echo "Waiting for frontend to be ready on http://localhost:3000..."
MAX_RETRIES=60
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s http://localhost:3000 > /dev/null 2>&1; then
        echo "✓ Frontend is ready"
        break
    fi
    if ! kill -0 $FRONTEND_PID 2>/dev/null; then
        echo "✗ Frontend failed to start (check logs/frontend_dev.log)"
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
        echo "✓ Backend is running"
        break
    fi
    if ! kill -0 $BACKEND_PID 2>/dev/null; then
        echo "✗ Backend died"
        exit 1
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    sleep 1
done

# Start small Chrome for VTuber overlay on separate display
echo "=== Starting VTuber Overlay Browser ==="
# Use a fresh temp profile every time to ensure no popups
OVERLAY_PROFILE="/tmp/vtuber_profile_$(date +%s)"
mkdir -p "$OVERLAY_PROFILE"

DISPLAY=:$OVERLAY_DISPLAY_NUM google-chrome \
    --no-sandbox \
    --test-type \
    --no-first-run \
    --no-default-browser-check \
    --password-store=basic \
    --user-data-dir="$OVERLAY_PROFILE" \
    --window-size=600,800 \
    --window-position=0,0 \
    --app="http://localhost:3000?autoplay=1&green=1" \
    --disable-infobars \
    --disable-extensions \
    --disable-notifications \
    --disable-translate \
    --disable-features=Translate,PrivacySandboxSettings4,OptimizationHints \
    --use-gl=angle \
    --use-angle=swiftshader \
    --enable-webgl \
    --ignore-gpu-blocklist \
    &
OVERLAY_CHROME_PID=$!

sleep 10

# FFmpeg with overlay filter
echo "=== Starting Stream with Overlay ==="

ffmpeg \
    -thread_queue_size 1024 \
    -f x11grab -video_size $RESOLUTION -framerate $FPS -i :$DISPLAY_NUM \
    -thread_queue_size 1024 \
    -f x11grab -video_size $OVERLAY_SIZE -framerate $FPS -i :$OVERLAY_DISPLAY_NUM \
    -thread_queue_size 2048 \
    -use_wallclock_as_timestamps 1 \
    -f s16le -ar 48000 -ac 1 -i "$AUDIO_PIPE" \
    -filter_complex "[1:v]colorkey=0x00ff00:0.1:0.1[ckey];[0:v][ckey]overlay=main_w-overlay_w:main_h-overlay_h[outv]" \
    -map "[outv]" -map 2:a \
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
echo "=== Stream Started ==="
echo "Content: Display :$DISPLAY_NUM (1920x1080)"
echo "Overlay: Display :$OVERLAY_DISPLAY_NUM (600x800) - bottom-right"
echo "Check: https://dashboard.twitch.tv"
echo ""
echo "PIDs: Xvfb=$XVFB_PID, Overlay=$XVFB_OVERLAY_PID, Backend=$BACKEND_PID, FFmpeg=$FFMPEG_PID"

wait $FFMPEG_PID