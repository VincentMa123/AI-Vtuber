    # Multi-stage build for AI VTuber project
# Stage 1: Build stage
FROM ubuntu:24.04 AS builder

# Prevent interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install basic build tools and Python 3
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    wget \
    git \
    python3 \
    python3-venv \
    python3-dev \
    python3-full \
    python3-pip \
    portaudio19-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 18
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
    nodejs \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements and package files
COPY requirements.txt ./
COPY vtuber/package.json vtuber/package-lock.json ./vtuber/

# Create Python virtual environment and install dependencies
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir torch==2.10.0 torchaudio==2.10.0 --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

# Install npm dependencies
RUN cd vtuber && npm ci && cd ..

# Stage 2: Runtime stage
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PATH="/opt/venv/bin:$PATH"
ENV NODE_ENV=production
ENV PYTHONPATH=/app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-full \
    curl \
    libportaudio2 \
    libsndfile1 \
    libsndfile1-dev \
    ffmpeg \
    libssl-dev \
    libffi-dev \
    librsvg2-bin \
    ca-certificates \
    xvfb \
    && rm -rf /var/lib/apt/lists/*


# Copy virtual environment and node_modules from builder
COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY --from=builder /app/vtuber/node_modules ./vtuber/node_modules

# Copy application code
COPY src/ ./src/
COPY vtuber/ ./vtuber/
COPY scripts/ ./scripts/
COPY README.md DEPLOYMENT.md ./

# Create .env template if it doesn't exist
RUN if [ ! -f src/.env ]; then \
    echo "# Environment variables - configure these\n\
DEEPSEEK_API_KEY=\n\
OPENROUTER_API_KEY=\n\
QWEN_API_KEY=\n\
ELEVENLABS_API_KEY=\n\
TWITCH_BOT_TOKEN=\n\
TWITCH_CHANNEL=\n\
TWITCH_CLIENT_ID=\n\
TWITCH_STREAM_KEY=" > src/.env; \
    fi

# Create logs directory and make scripts executable
RUN mkdir -p /app/logs
RUN chmod +x scripts/*.sh

# Expose ports
# 8000: FastAPI backend
# 3000: Next.js frontend
EXPOSE 8000 3000

# Health check for FastAPI backend
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/docs || exit 1

# Default command: keep container alive for manual debugging
CMD ["tail", "-f", "/dev/null"]
