#!/bin/bash
# Enhanced Search MCP - Start Script
# Loads .env if present, then starts the MCP server via stdio.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load .env file if it exists
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

export PATH="$HOME/.local/bin:$PATH"

# Defaults (override via .env or environment)
export SEARXNG_URL="${SEARXNG_URL:-http://localhost:8888/}"
export SEARCH_TIMEOUT="${SEARCH_TIMEOUT:-30}"
export SEARCH_OP_TIMEOUT="${SEARCH_OP_TIMEOUT:-15}"
export FETCH_OP_TIMEOUT="${FETCH_OP_TIMEOUT:-30}"
export DEEP_SEARCH_OP_TIMEOUT="${DEEP_SEARCH_OP_TIMEOUT:-60}"
export DEFAULT_LIMIT="${DEFAULT_LIMIT:-10}"
export MAX_CONTENT_LENGTH="${MAX_CONTENT_LENGTH:-10000}"
export RATE_LIMIT_RPM="${RATE_LIMIT_RPM:-200}"
export MAX_CONCURRENT="${MAX_CONCURRENT:-20}"
export ENABLE_DDG="${ENABLE_DDG:-false}"
export SEARXNG_DEFAULT_ENGINES="${SEARXNG_DEFAULT_ENGINES:-bing,baidu,sogou,360search,mojeek,presearch}"
export SEARXNG_IMAGE_ENGINES="${SEARXNG_IMAGE_ENGINES:-sogou images,unsplash,pexels,mojeek images,presearch images}"
export HEALTH_CHECK_INTERVAL="${HEALTH_CHECK_INTERVAL:-300}"

exec python3 -m enhanced_search.server "$@"
