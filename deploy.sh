#!/bin/bash
# ============================================================
# Enhanced Search MCP - One-Click Deployment Script
# Usage: bash deploy.sh [--with-cache] [--china-mirror]
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# --- Parse arguments ---
USE_CACHE=false
USE_CHINA_MIRROR=false
for arg in "$@"; do
    case $arg in
        --with-cache)   USE_CACHE=true ;;
        --china-mirror) USE_CHINA_MIRROR=true ;;
        --help|-h)
            echo "Usage: bash deploy.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --with-cache     Deploy with Redis cache"
            echo "  --china-mirror   Use China Docker mirror for image pull"
            echo "  -h, --help       Show this help"
            exit 0
            ;;
        *) echo "Unknown argument: $arg"; exit 1 ;;
    esac
done

echo "============================================================"
echo " Enhanced Search MCP - Deployment"
echo "============================================================"

# --- Step 1: Environment file ---
if [ ! -f .env ]; then
    echo "[1/5] Creating .env from template..."
    cp .env.example .env
    if $USE_CHINA_MIRROR; then
        sed -i 's|^SEARXNG_IMAGE=.*|SEARXNG_IMAGE=docker.1ms.run/searxng/searxng:latest|' .env
        sed -i 's|^# SEARXNG_IMAGE=docker.1ms.run|SEARXNG_IMAGE=docker.1ms.run|' .env
    fi
    echo "  -> .env created. Edit it if needed before continuing."
else
    echo "[1/5] .env already exists, skipping."
fi

# --- Step 2: Python dependencies ---
echo "[2/5] Installing Python dependencies..."
if command -v uv &>/dev/null; then
    uv pip install -e . --quiet
elif command -v pip3 &>/dev/null; then
    pip3 install -e . --quiet
else
    echo "ERROR: Neither uv nor pip3 found. Install Python 3.10+ first."
    exit 1
fi

if $USE_CACHE; then
    echo "  -> Installing Redis cache support..."
    if command -v uv &>/dev/null; then
        uv pip install -e ".[cache]" --quiet
    else
        pip3 install -e ".[cache]" --quiet
    fi
fi

# --- Step 3: Docker check ---
echo "[3/5] Checking Docker..."
if ! command -v docker &>/dev/null; then
    echo "ERROR: Docker not found. Install Docker first:"
    echo "  curl -fsSL https://get.docker.com | sh"
    exit 1
fi
if ! docker info &>/dev/null 2>&1; then
    echo "ERROR: Docker daemon not running. Start it with: sudo systemctl start docker"
    exit 1
fi

# --- Step 4: Start SearXNG ---
echo "[4/5] Starting SearXNG container..."
source .env 2>/dev/null || true

if $USE_CHINA_MIRROR; then
    export SEARXNG_IMAGE="${SEARXNG_IMAGE:-docker.1ms.run/searxng/searxng:latest}"
fi

if $USE_CACHE; then
    docker compose --profile cache up -d
else
    docker compose up -d
fi

# Wait for SearXNG to be ready
echo "  -> Waiting for SearXNG to start..."
SEARXNG_PORT="${SEARXNG_PORT:-8888}"
for i in $(seq 1 30); do
    if curl -sf "http://localhost:${SEARXNG_PORT}/" > /dev/null 2>&1; then
        echo "  -> SearXNG is ready at http://localhost:${SEARXNG_PORT}/"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "WARNING: SearXNG did not start within 30s. Check: docker logs searxng"
    fi
    sleep 1
done

# --- Step 5: Verify ---
echo "[5/5] Verifying search functionality..."
RESULT=$(curl -sf "http://localhost:${SEARXNG_PORT}/search?q=test&format=json&engines=bing" 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
n = len(data.get('results', []))
print(f'{n} results')
" 2>/dev/null || echo "FAILED")
echo "  -> SearXNG search test: $RESULT"

echo ""
echo "============================================================"
echo " Deployment Complete!"
echo "============================================================"
echo ""
echo " SearXNG URL:  http://localhost:${SEARXNG_PORT}/"
if $USE_CACHE; then
    echo " Redis URL:    redis://localhost:6379"
fi
echo ""
echo " To start the MCP server:"
echo "   export SEARXNG_URL=http://localhost:${SEARXNG_PORT}/"
echo "   enhanced-search-mcp"
echo ""
echo " Or use the start script:"
echo "   bash start.sh"
echo ""
echo " To check SearXNG status:"
echo "   docker compose ps"
echo "   docker logs searxng --tail 20"
echo "============================================================"
