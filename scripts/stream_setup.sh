#!/bin/bash
# Stream Setup Script - Install dependencies for server-side streaming
# Run this once on a fresh Ubuntu 22.04+ server

set -e

# Ensure curl is installed (needed for NodeSource and Chrome)
sudo apt-get update
sudo apt-get install -y curl

echo "=== Installing Node.js (LTS Version) ==="
# We use Node 20.x (Current LTS) which is stable for Next.js
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

echo "=== Installing Xvfb (Virtual Display) ==="
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
# Note: Added 'libgbm1' specifically as it is vital for Chrome on VPS
sudo apt-get install -y \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libxcomposite1 \
    libxrandr2 \
    libxdamage1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
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
echo "Node version: $(node -v)"
echo "NPM version: $(npm -v)"
echo "Now configure your .env file with TWITCH_STREAM_KEY"
echo "Then run: ./scripts/start_stream.sh"

