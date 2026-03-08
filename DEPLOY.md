# Enhanced Search MCP - 部署指南

面向 OpenClaw 或任意 Linux 服务器的快速部署文档。Agent 可直接按步骤执行完成部署。

## 架构概览

```
┌─────────────────────────────────────────────┐
│  MCP Client (Claude/Windsurf/OpenClaw)      │
│         ↕ stdio (JSON-RPC)                  │
│  enhanced-search-mcp (Python)               │
│         ↕ HTTP                              │
│  SearXNG (Docker, port 8888)                │
│    ├── bing, baidu, sogou, 360search ...    │
│    ├── github, stackoverflow, arxiv ...     │
│    └── unsplash, pexels, mojeek images ...  │
│         ↕ (optional)                        │
│  Redis (Docker, port 6379)                  │
└─────────────────────────────────────────────┘
```

## 前置要求

| 组件 | 最低版本 | 检查命令 |
|------|---------|---------|
| Python | 3.10+ | `python3 --version` |
| pip | 22+ | `pip3 --version` |
| Docker | 20+ | `docker --version` |
| Docker Compose | v2+ | `docker compose version` |
| Git | 2.0+ | `git --version` |

## 一键部署

```bash
# 1. 克隆仓库
git clone <repo-url> enhanced-search-mcp
cd enhanced-search-mcp

# 2. 执行部署脚本
bash deploy.sh

# 中国服务器 (Docker Hub 加速):
bash deploy.sh --china-mirror

# 启用 Redis 缓存:
bash deploy.sh --with-cache

# 两者兼用:
bash deploy.sh --china-mirror --with-cache
```

部署脚本自动完成：创建 `.env` → 安装 Python 依赖 → 启动 SearXNG Docker → 验证搜索功能。

## 手动部署（逐步）

### Step 1: 环境配置

```bash
cd enhanced-search-mcp
cp .env.example .env
```

编辑 `.env`，关键配置项：

```bash
# SearXNG 实例地址 (Docker 部署后默认此值)
SEARXNG_URL=http://localhost:8888/

# 搜索引擎列表 (已针对中国网络优化)
SEARXNG_DEFAULT_ENGINES=bing,baidu,sogou,360search,mojeek,presearch
SEARXNG_IMAGE_ENGINES=sogou images,unsplash,pexels,mojeek images,presearch images

# DuckDuckGo (中国服务器建议关闭)
ENABLE_DDG=false
```

完整配置项见 [.env.example](.env.example)。

### Step 2: 安装 Python 依赖

```bash
pip3 install -e .

# 可选：Redis 缓存支持
pip3 install -e ".[cache]"

# 可选：Playwright 动态页面
pip3 install -e ".[playwright]"
playwright install chromium
```

### Step 3: 启动 SearXNG

```bash
# 标准启动
docker compose up -d

# 带 Redis 缓存
docker compose --profile cache up -d

# 中国服务器 (Docker Hub 镜像加速)
SEARXNG_IMAGE=docker.1ms.run/searxng/searxng:latest docker compose up -d
```

验证启动成功：

```bash
# 检查容器状态
docker compose ps

# 检查日志
docker logs searxng --tail 10

# 测试搜索
curl -s "http://localhost:8888/search?q=test&format=json&engines=bing" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'Results: {len(data.get(\"results\", []))}')"
```

### Step 4: 验证引擎可用性

部署后建议运行引擎验证脚本，检测当前服务器实际可用的搜索引擎：

```bash
python3 scripts/verify-engines.py --url http://localhost:8888
```

脚本会逐个测试引擎并输出推荐的 `SEARXNG_DEFAULT_ENGINES` 和 `SEARXNG_IMAGE_ENGINES` 配置。如果输出的推荐配置与当前 `.env` 不同，更新 `.env` 后重启 MCP 即可。

JSON 输出（适合 Agent 解析）：

```bash
python3 scripts/verify-engines.py --url http://localhost:8888 --json
```

### Step 5: 启动 MCP Server

```bash
# 方式 1: 使用启动脚本 (推荐, 自动加载 .env)
bash start.sh

# 方式 2: 直接运行
source .env
enhanced-search-mcp

# 方式 3: 指定 Python 模块
source .env
python3 -m enhanced_search.server
```

## MCP 客户端配置

### OpenClaw / Claude Desktop / Windsurf

```json
{
  "mcpServers": {
    "enhanced-search": {
      "command": "/path/to/enhanced-search-mcp/start.sh",
      "disabled": false
    }
  }
}
```

或者直接指定 Python 和环境变量：

```json
{
  "mcpServers": {
    "enhanced-search": {
      "command": "python3",
      "args": ["-m", "enhanced_search.server"],
      "cwd": "/path/to/enhanced-search-mcp",
      "env": {
        "SEARXNG_URL": "http://localhost:8888/",
        "ENABLE_DDG": "false",
        "SEARXNG_DEFAULT_ENGINES": "bing,baidu,sogou,360search,mojeek,presearch",
        "SEARXNG_IMAGE_ENGINES": "sogou images,unsplash,pexels,mojeek images,presearch images",
        "SEARCH_OP_TIMEOUT": "15"
      }
    }
  }
}
```

## SearXNG 引擎配置

### 配置文件

SearXNG 引擎由 `searxng/settings.yml` 控制，通过 Docker volume 挂载到容器内。

当前默认配置已针对**中国大陆网络**优化，仅保留了经过验证可用的引擎（约 100 个），移除了 Google、DuckDuckGo、YouTube、Reddit 等被墙服务。

### 引擎分类

| 分类 | 已启用引擎 | 说明 |
|------|-----------|------|
| 通用搜索 | bing, baidu, sogou, 360search, mojeek, presearch | 默认搜索引擎 |
| 图片搜索 | sogou images, unsplash, pexels, mojeek/presearch images | 默认图片引擎 |
| 新闻 | bing news, mojeek news, presearch news, reuters | |
| 视频 | bing videos, bilibili, iqiyi, acfun, niconico | |
| 学术 | arxiv, pubmed, semantic scholar, crossref, openalex | |
| 代码 | github, gitlab, stackoverflow, pypi, npm, crates.io 等 | 20+ 引擎 |
| 百科 | wikipedia, wikidata, mdn, microsoft learn 等 | |
| 其他 | currency, openmeteo, wolframalpha, openstreetmap 等 | |

### 自定义引擎配置

编辑 `searxng/settings.yml` 后重启容器：

```bash
# 编辑配置
vim searxng/settings.yml

# 重启生效
docker compose restart searxng

# 验证
python3 scripts/verify-engines.py
```

### 海外服务器配置

如果服务器在海外（无网络限制），可以启用更多引擎：

```yaml
# searxng/settings.yml
use_default_settings: true  # 启用全部默认引擎

general:
  instance_name: "Search MCP"
search:
  formats: [html, json, csv]
server:
  limiter: false
  secret_key: "your-secret-key"
```

对应 `.env`：

```bash
SEARXNG_DEFAULT_ENGINES=google,bing,duckduckgo,baidu,wikipedia,mojeek
SEARXNG_IMAGE_ENGINES=google images,bing images,unsplash,pexels,pixabay images
ENABLE_DDG=true
```

## 可用工具列表

| 工具 | 说明 | 关键参数 |
|------|------|---------|
| `search` | 多引擎聚合搜索 | query, limit, language, time_range, engines |
| `deep_search` | 搜索+自动抓取全文 | query, mode(quick/deep), fetch_limit |
| `agent_search` | 多轮自动搜索 | query, max_rounds, fetch_limit |
| `search_images` | 图片搜索 | query, limit |
| `fetch_content` | 抓取页面正文 | url, max_length, output_format(text/markdown) |
| `extract_structured` | URL 批量结构化提取 | urls, fields, schema |
| `search_history` | 搜索历史管理 | action(list/execute/clear), query_id |

## 环境变量参考

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SEARXNG_URL` | `https://search.rhscz.eu/` | SearXNG 实例 URL |
| `SEARXNG_DEFAULT_ENGINES` | `bing,baidu,sogou,360search,mojeek,presearch` | 通用搜索引擎 |
| `SEARXNG_IMAGE_ENGINES` | `sogou images,unsplash,pexels,mojeek images,presearch images` | 图片搜索引擎 |
| `ENABLE_DDG` | `false` | 启用 DuckDuckGo |
| `SEARCH_TIMEOUT` | `30` | 全局超时(秒) |
| `SEARCH_OP_TIMEOUT` | `10` | 搜索操作超时 |
| `FETCH_OP_TIMEOUT` | `30` | 内容抓取超时 |
| `DEEP_SEARCH_OP_TIMEOUT` | `60` | 深度搜索超时 |
| `DEFAULT_LIMIT` | `10` | 默认结果数量 |
| `DEEP_SEARCH_MAX_PAGES` | `5` | 深度搜索最大页数 |
| `MAX_CONTENT_LENGTH` | `10000` | 页面内容最大字符数 |
| `RATE_LIMIT_RPM` | `200` | 请求限速(次/分钟) |
| `MAX_CONCURRENT` | `20` | 最大并发数 |
| `REDIS_URL` | `""` | Redis URL(空=禁用缓存) |
| `CACHE_TTL` | `3600` | 缓存过期时间(秒) |
| `HEALTH_CHECK_INTERVAL` | `300` | 健康检查间隔(秒) |
| `ENABLE_PLAYWRIGHT` | `false` | 启用 Playwright |

## 运维

### 常用命令

```bash
# 查看状态
docker compose ps

# 查看日志
docker logs searxng --tail 50
docker logs searxng-redis --tail 50  # if using cache

# 重启 SearXNG (配置变更后)
docker compose restart searxng

# 停止所有服务
docker compose down

# 完全清除 (含数据卷)
docker compose down -v

# 更新 SearXNG 镜像
docker compose pull && docker compose up -d
```

### 故障排查

| 问题 | 排查命令 | 常见原因 |
|------|---------|---------|
| SearXNG 无法启动 | `docker logs searxng` | settings.yml 语法错误 |
| 搜索返回 0 结果 | `python3 scripts/verify-engines.py` | 引擎被墙或超时 |
| 搜索很慢 (>10s) | 检查 `.env` 中 `SEARXNG_DEFAULT_ENGINES` | 未指定默认引擎，触发全部引擎 |
| MCP 连接超时 | `curl http://localhost:8888/` | SearXNG 未启动 |
| Redis 连接失败 | `docker logs searxng-redis` | Redis 未启动或端口冲突 |

## 文件结构

```
enhanced-search-mcp/
├── .env.example              # 环境变量模板 (复制为 .env)
├── docker-compose.yml        # Docker 编排 (SearXNG + Redis)
├── deploy.sh                 # 一键部署脚本
├── start.sh                  # MCP 启动脚本 (加载 .env)
├── searxng/
│   └── settings.yml          # SearXNG 引擎配置 (中国优化版)
├── scripts/
│   └── verify-engines.py     # 引擎可用性验证工具
├── src/enhanced_search/      # MCP 核心代码
│   ├── server.py             # 入口
│   ├── config.py             # 配置管理
│   ├── engines/              # 搜索引擎客户端
│   ├── handlers/             # 工具处理逻辑
│   ├── utils/                # 去重/分词/限速等
│   └── cache/                # Redis 缓存
├── tests/                    # 单元测试
├── test_mcp_capabilities.py  # 综合能力测试脚本
├── pyproject.toml            # 项目依赖
└── DEPLOY.md                 # 本文档
```

## Agent 快速部署流程 (TL;DR)

供 Agent 直接执行的最小步骤：

```bash
# 1. Clone & enter
cd /path/to/workspace
git clone <repo-url> enhanced-search-mcp && cd enhanced-search-mcp

# 2. Deploy (one command)
bash deploy.sh --china-mirror

# 3. Verify engines
python3 scripts/verify-engines.py --json

# 4. Start MCP
bash start.sh
```

如果是海外服务器，去掉 `--china-mirror`，并将 `.env` 中的引擎列表改为包含 Google/DDG。
