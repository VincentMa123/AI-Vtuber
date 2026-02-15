#!/bin/bash
echo "Killing all AI-Vtuber processes..."

echo "- Stopping Python backend..."
pkill -f "python3.*api_server" || true

echo "- Stopping Node.js frontend..."
pkill -f "node.*next" || true

echo "- Stopping Chrome/Chromium..."
pkill -f "google-chrome" || true
pkill -f "chrome" || true

echo "- Stopping FFmpeg..."
pkill -f "ffmpeg" || true

echo "- Stopping Xvfb..."
pkill -f "Xvfb" || true

echo "- Stopping Compositor..."
pkill -f "xcompmgr" || true

echo "Done. Environment clean."
