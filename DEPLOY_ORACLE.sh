#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════
# SHADOW MONARCH PROTOCOL — Oracle Cloud Free Tier Deployment
# ═══════════════════════════════════════════════════════════════════════
# Run this script ON your Oracle Cloud VM after SSH'ing in.
# Prerequisites: Ubuntu ARM64 VM (Always Free), Docker installed.
#
# Usage:
#   1. SSH into your Oracle VM:  ssh -i <key> ubuntu@<vm-ip>
#   2. Clone the repo:           git clone https://github.com/billu1012/shadow-monarch-bot.git
#   3. cd shadow-monarch-bot
#   4. Create .env file:         nano .env  (add DISCORD_BOT_TOKEN and DISCORD_CHANNEL_ID)
#   5. Run this script:          bash DEPLOY_ORACLE.sh
# ═══════════════════════════════════════════════════════════════════════

set -e

echo "============================================"
echo "  SHADOW MONARCH — Oracle Cloud Deploy"
echo "============================================"
echo ""

# ── Step 1: Install Docker if not present ──
if ! command -v docker &> /dev/null; then
    echo "[1/5] Installing Docker..."
    sudo apt-get update -y
    sudo apt-get install -y docker.io docker-compose
    sudo systemctl enable docker
    sudo systemctl start docker
    sudo usermod -aG docker $USER
    echo "  Docker installed. You may need to re-login for group changes."
else
    echo "[1/5] Docker already installed ✓"
fi

# ── Step 2: Check .env file ──
if [ ! -f .env ]; then
    echo ""
    echo "ERROR: .env file not found!"
    echo "Create one with:"
    echo "  DISCORD_BOT_TOKEN=your_token_here"
    echo "  DISCORD_CHANNEL_ID=your_channel_id_here"
    echo "  API_PORT=8080"
    echo ""
    exit 1
fi
echo "[2/5] .env file found ✓"

# ── Step 3: Build Docker image ──
echo "[3/5] Building Docker image..."
sudo docker build -t shadow-monarch-bot .

# ── Step 4: Stop any existing container ──
echo "[4/5] Stopping old container (if any)..."
sudo docker stop shadow-monarch 2>/dev/null || true
sudo docker rm shadow-monarch 2>/dev/null || true

# ── Step 5: Run the bot ──
echo "[5/5] Starting Shadow Monarch Bot..."
sudo docker run -d \
    --name shadow-monarch \
    --restart unless-stopped \
    --env-file .env \
    -p 8080:8080 \
    -v $(pwd)/data:/app/data \
    -v $(pwd)/agent_state:/app/agent_state \
    shadow-monarch-bot

echo ""
echo "============================================"
echo "  SHADOW MONARCH BOT IS LIVE!"
echo "============================================"
echo ""
echo "  Container: shadow-monarch"
echo "  Status:    $(sudo docker ps --filter name=shadow-monarch --format '{{.Status}}')"
echo "  API:       http://$(curl -s ifconfig.me):8080"
echo "  Logs:      sudo docker logs -f shadow-monarch"
echo ""
echo "  The bot will auto-restart on crash/reboot."
echo "  Two-Way Listener API is exposed on port 8080."
echo ""
echo "  To update later:"
echo "    git pull && sudo docker build -t shadow-monarch-bot . && sudo docker restart shadow-monarch"
echo ""
