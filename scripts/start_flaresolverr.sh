#!/bin/bash
echo "=== Starting FlareSolverr ==="
# Remove existing container if it exists (to ensure fresh start)
docker rm -f flaresolverr 2>/dev/null || true

# Run FlareSolverr
# -d: Detached mode
# -p 8191:8191: Expose port
# --restart unless-stopped: Auto-restart
sudo docker run -d \
  --name=flaresolverr \
  --network host \
  -e LOG_LEVEL=info \
  --restart unless-stopped \
  flaresolverr/flaresolverr:latest

echo "=== FlareSolverr Started ==="
echo "URL: http://localhost:8191"
