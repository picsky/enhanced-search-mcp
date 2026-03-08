# Enhanced Search MCP

免费、强大的网络搜索 MCP 服务 — 无需任何 API 密钥。

## 特性

- **多引擎聚合**：SearXNG (100+ 引擎)，中国网络优化
- **中文支持**：jieba 分词，中文搜索/去重/分析全链路适配
- **智能去重**：SimHash + Band 分桶，中英文词组级别去重
- **内容抓取**：trafilatura + BeautifulSoup 提取页面正文
- **深度搜索**：搜索 + 全文获取 + 多轮 Agent 搜索
- **缓存加速**：可选 Redis 缓存热门查询
- **请求限流**：令牌桶算法防止封禁
- **健康检查**：自动监控引擎可用性并降级
- **一键部署**：Docker Compose + 部署脚本，Agent 可直接执行
- **完全免费**：所有功能无需付费 API

## 快速开始

### 一键部署（推荐）

```bash
git clone <repo-url> enhanced-search-mcp
cd enhanced-search-mcp
bash deploy.sh                # 标准部署
bash deploy.sh --china-mirror # 中国服务器 (Docker 镜像加速)
bash deploy.sh --with-cache   # 启用 Redis 缓存
```

详细部署说明见 [DEPLOY.md](DEPLOY.md)。

### 手动安装

```bash
# 1. 安装
pip install -e .

# 2. 配置
cp .env.example .env  # 编辑 .env

# 3. 启动 SearXNG
docker compose up -d

# 4. 启动 MCP
bash start.sh
```

### MCP 客户端配置

**Claude Desktop / Windsurf / Cursor / OpenClaw：**

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

或指定环境变量：

```json
{
  "mcpServers": {
    "enhanced-search": {
      "command": "python3",
      "args": ["-m", "enhanced_search.server"],
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

## 工具列表

| 工具 | 说明 |
|------|------|
| `search` | 多引擎聚合搜索，支持类别/语言/时间/引擎过滤 |
| `deep_search` | 搜索 + 自动获取前 N 个结果全文 + 关键段落提取 |
| `agent_search` | 多轮自动搜索，自动生成 follow-up 查询 |
| `search_images` | 图片搜索 |
| `fetch_content` | 获取页面正文内容 (text/markdown) |
| `extract_structured` | 从 URL 列表批量提取结构化信息 |
| `search_history` | 搜索历史管理 (list/execute/clear) |

## SearXNG 引擎配置

默认配置已针对**中国大陆网络**优化，仅启用已验证可访问的引擎。

部署后可运行引擎验证脚本检测实际可用引擎：

```bash
python3 scripts/verify-engines.py --url http://localhost:8888
```

详细引擎配置说明见 [DEPLOY.md](DEPLOY.md#searxng-引擎配置)。

## 文档

- **[DEPLOY.md](DEPLOY.md)** — 完整部署指南、环境变量参考、运维命令
- **[docs/tech-stack.md](docs/tech-stack.md)** — 技术架构文档

## License

MIT
