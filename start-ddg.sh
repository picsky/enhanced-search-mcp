#!/bin/bash
# Enhanced Search MCP 启动脚本 - DuckDuckGo 模式

export PATH="$HOME/.local/bin:$PATH"

# 禁用 SearXNG，使用 DuckDuckGo 作为主力引擎
export SEARXNG_URL=""  # 留空禁用
export DDGS_ENGINE="duckduckgo"

export SEARCH_TIMEOUT="60"
export DEFAULT_LIMIT="10"
export MAX_CONTENT_LENGTH="10000"
export RATE_LIMIT_RPM="100"
export MAX_CONCURRENT="10"

cd /home/shunkang/openclaw/enhanced-search-mcp
exec python3 -m enhanced_search.server "$@"
