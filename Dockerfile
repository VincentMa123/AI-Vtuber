FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies + python full (needed for venv)
RUN apt-get update && apt-get install -y \
    python3 \
    python3-venv \
    python3-pip \
    python3-full \
    xvfb \
    ffmpeg \
    pulseaudio \
    portaudio19-dev \
    espeak-ng \
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
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*
    
# Install Chrome
RUN wget -q -O /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && dpkg -i /tmp/chrome.deb || apt-get install -f -y \
    && rm /tmp/chrome.deb

# Create virtual environment
RUN python3 -m venv /venv

# Activate venv for all future RUN/CMD
ENV PATH="/venv/bin:$PATH"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["bash"]