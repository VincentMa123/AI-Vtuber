# Docker Quick Start Guide

**Deploy AI VTuber to Ubuntu 20.04 LTS in Minutes**

## 📦 Files Created

- `Dockerfile` - Multi-stage Docker build configuration
- `docker-compose.yml` - Docker Compose orchestration
- `setup-docker.sh` - Interactive setup and management script
- `DOCKER_DEPLOYMENT.md` - Comprehensive deployment guide
- `.env.example` - Configuration template with instructions
- `.dockerignore` - Optimizes Docker build

## 🚀 Quick Start (5 Minutes)

### On Your Ubuntu Server:

```bash
# 1. Install Docker (if not already installed)
sudo apt-get update && sudo apt-get install -y docker.io docker-compose

# 2. Copy your project to server
# (use scp, git clone, or file transfer)

# 3. Configure your API keys
cp .env.example src/.env
nano src/.env  # Edit with your DeepSeek/OpenRouter/Qwen keys

# 4. Run (automatic build + start)
chmod +x setup-docker.sh
./setup-docker.sh setup
```

**Done!** Your app is running at:
- Backend: `http://your-ip:8000`
- Frontend: `http://your-ip:3000`

## 📋 Commands Reference

```bash
# Using setup-docker.sh (Recommended)
./setup-docker.sh setup      # Interactive wizard (full setup)
./setup-docker.sh build      # Build Docker image
./setup-docker.sh run        # Run container
./setup-docker.sh logs       # View live logs
./setup-docker.sh stop       # Stop container
./setup-docker.sh restart    # Restart container
./setup-docker.sh status     # Check status

# Using docker-compose
docker-compose up -d         # Start
docker-compose down          # Stop
docker-compose logs -f       # View logs
docker-compose restart       # Restart
```

## 🔑 Configuration

Create `src/.env` with your API keys:

```bash
# Required: Choose ONE LLM provider
DEEPSEEK_API_KEY=sk-xxxxx              # or OPENROUTER_API_KEY=sk-or-xxxxx

# Required: TTS
QWEN_API_KEY=xxxxx                     # or ELEVENLABS_API_KEY=xxxxx

# Optional: Twitch streaming
TWITCH_BOT_TOKEN=oauth:xxxxx
TWITCH_CHANNEL=your_channel
TWITCH_STREAM_KEY=live_xxxxx
```

See `.env.example` for complete configuration options.

## 📊 System Requirements

- **OS**: Ubuntu 20.04 LTS (or similar)
- **RAM**: 4GB minimum, 8GB recommended
- **Disk**: 20GB+ (includes dependencies)
- **CPU**: 2+ cores recommended

## 🐛 Troubleshooting

```bash
# View detailed logs
docker-compose logs vtuber-app

# Access container shell
docker-compose exec vtuber-app bash

# Check if container is running
docker-compose ps

# Free up disk space
docker system prune

# Rebuild from scratch (if issues)
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## 📚 Full Documentation

See `DOCKER_DEPLOYMENT.md` for:
- Detailed installation instructions
- Production deployment practices
- Performance tuning
- SSL/HTTPS setup
- Monitoring and logs
- Troubleshooting guide

## 🔗 Access Points

After starting, access via:

| Service | URL | Purpose |
|---------|-----|---------|
| Backend API | `http://your-ip:8000` | REST API endpoints |
| API Docs | `http://your-ip:8000/docs` | Interactive API documentation |
| Frontend | `http://your-ip:3000` | Web UI |

## 💡 Common Tasks

```bash
# View real-time logs
docker-compose logs -f

# Stop application
docker-compose down

# Update to latest version
git pull  # (if using git)
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Run Python command in container
docker-compose exec vtuber-app python -c "import torch; print('GPU:', torch.cuda.is_available())"

# Copy file to/from container
docker-compose cp src/file.txt vtuber-app:/app/src/
docker-compose cp vtuber-app:/app/src/logs/app.log ./

# Backup logs
docker-compose cp vtuber-app:/app/src/logs ./logs-backup-$(date +%Y%m%d)
```

## 🔐 Security Tips

1. **Keep keys safe**: Don't commit `.env` file to git
2. **Use unique keys**: Generate separate keys for dev/prod
3. **Rotate regularly**: Change API keys periodically
4. **Monitor logs**: Watch for errors or unusual activity
5. **Keep secret**: Never share TWITCH_STREAM_KEY

## 📝 Deployment Checklist

- [ ] Ubuntu 20.04 LTS server ready
- [ ] Docker installed (`docker --version`)
- [ ] Project copied to server
- [ ] `.env` file configured with API keys
- [ ] Run `./setup-docker.sh setup`
- [ ] Verify backend at `http://ip:8000/docs`
- [ ] Verify frontend at `http://ip:3000`
- [ ] Test Twitch integration
- [ ] Set up monitoring/logs collection
- [ ] Configure SSL/HTTPS (if exposed to internet)

## 🆘 Need Help?

```bash
# Show all available commands
./setup-docker.sh help

# View logs for errors
docker-compose logs vtuber-app

# Check system resources
docker stats vtuber-container

# Get container details
docker inspect vtuber-container
```

## ✅ Verification Steps

```bash
# 1. Check container is running
docker-compose ps

# 2. Check backend is healthy
curl http://localhost:8000/docs

# 3. Check logs for errors
docker-compose logs --tail=50

# 4. Verify environment variables loaded
docker-compose exec vtuber-app env | grep DEEPSEEK
```

---

**For complete details, see `DOCKER_DEPLOYMENT.md`**
