#!/bin/bash
# Stream Setup Script - Install dependencies for server-side streaming
# Run this once on a fresh Ubuntu 22.04+ server

set -e

echo "=== Installing Xvfb (Virtual Display) ==="
sudo apt-get update
sudo apt-get install -y xvfb

echo "=== Installing FFmpeg ==="
sudo apt-get install -y ffmpeg

echo "=== Installing PulseAudio (Virtual Audio) ==="
sudo apt-get install -y pulseaudio

echo "=== Installing PortAudio ==="
sudo apt-get install -y portaudio19-dev

echo "=== Installing eSpeak (TTS) ==="
sudo apt-get install -y espeak-ng

echo "=== Installing Chrome Dependencies ==="
sudo apt-get install -y \
    libnss3 \
    libatk1.0-0t64 \
    libatk-bridge2.0-0t64 \
    libcups2t64 \
    libxcomposite1 \
    libxrandr2 \
    libxdamage1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2t64 \
    libxshmfence1 \
    libgbm1 \
    fonts-liberation \
    libappindicator3-1 \
    xdg-utils \
    build-essential \
    python3-dev

echo "=== Installing Google Chrome ==="
if ! command -v google-chrome &> /dev/null; then
    wget -q -O /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
    sudo dpkg -i /tmp/chrome.deb || sudo apt-get install -f -y
    rm /tmp/chrome.deb
fi

echo "=== Setup Complete ==="
echo "Now configure your .env file with TWITCH_STREAM_KEY"
echo "Then run: ./scripts/start_stream.sh"
