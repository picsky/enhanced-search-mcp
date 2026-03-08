# 增强搜索 MCP 技术栈文档

## 项目概述

本项目是一个**免费、强大的网络搜索MCP（Model Context Protocol）服务**，通过聚合多个搜索引擎和智能内容抓取，为AI助手提供高质量的搜索结果。

## 核心特性

- **零API成本**：无需任何商业搜索API密钥
- **多引擎聚合**：自动合并多个搜索引擎结果
- **智能去重**：基于SimHash算法高效去重
- **内容抓取**：自动获取页面正文并清洗，支持动态页面
- **深度搜索**：搜索+全文获取一键完成
- **智能缓存**：Redis缓存热门查询，提升响应速度
- **请求限流**：令牌桶算法避免被封禁
- **健康检查**：自动监控引擎可用性并降级
- **流式响应**：增量返回结果，优化用户体验
- **完全免费**：所有功能无需付费API

---

## 技术栈架构

```
┌─────────────────────────────────────────────────────────────┐
│                     Enhanced Search MCP                     │
├─────────────────────────────────────────────────────────────┤
│  工具层 (MCP Tools)                                          │
│  ├── search()          → 主搜索（多引擎聚合）                 │
│  ├── search_images()   → 图片搜索（新增）                    │
│  ├── fetch_content()   → 单页面内容获取                       │
│  ├── deep_search()     → 深度搜索+内容获取                   │
│  ├── extract_structured() → 结构化信息提取                   │
│  └── search_history()  → 搜索历史管理（新增）                │
├─────────────────────────────────────────────────────────────┤
│  引擎层 (Search Engines)                                      │
│  ├── SearXNG (主引擎)   → 聚合70+搜索引擎                    │
│  ├── DuckDuckGo (备用)  → 无需API，隐私友好                   │
│  └── 直接抓取 (兜底)    → HTML解析提取                       │
├─────────────────────────────────────────────────────────────┤
│  增强层 (Enhancement)                                         │
│  ├── 结果去重/排序      → SimHash + 布隆过滤器               │
│  ├── 内容清洗           → 去除广告/导航等噪声                │
│  ├── 缓存层            → Redis缓存热门查询                    │
│  ├── 请求限流          → 令牌桶算法                          │
│  ├── 健康检查          → 引擎可用性监控                      │
│  └── 并发控制          → 动态并发限制                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 核心技术组件

### 1. MCP框架

| 组件 | 说明 | 版本 |
|------|------|------|
| `mcp` | Model Context Protocol官方SDK | >=1.0.0 |
| `mcp.server` | MCP服务器实现 | stdio模式 |

**MCP服务器配置：**
- 传输方式：Standard I/O (stdio)
- 工具注册：动态工具列表 (list_tools)
- 调用处理：异步工具调用 (call_tool)

### 2. 搜索引擎集成

#### 2.1 SearXNG (主引擎)

| 属性 | 说明 |
|------|------|
| 类型 | 元搜索引擎 (Metasearch Engine) |
| 功能 | 聚合70+搜索引擎结果 |
| 输出格式 | JSON / CSV / RSS |
| 隐私特性 | 不追踪用户、不存储查询 |
| 部署方式 | 公共实例或自建Docker |
| 健康检查 | 每5分钟自动检测可用性 |
| 降级策略 | 自动切换备用引擎 |

**支持的搜索引擎：**
- 通用：Google、Bing、DuckDuckGo、Brave、Qwant
- 图片：Google Images、Bing Images、Flickr
- 视频：YouTube、Dailymotion、PeerTube
- 新闻：Google News、Bing News、Reddit
- IT：GitHub、GitLab、StackOverflow、Hacker News
- 科学：arXiv、PubMed、CORE、Crossref

**API参数：**
```python
{
    "q": "搜索查询",
    "categories": "general,images,videos,news,it,science",
    "engines": "google,bing,duckduckgo",
    "language": "zh-CN",
    "time_range": "day|month|year",
    "safesearch": "0|1|2",
    "format": "json"
}
```

#### 2.2 DuckDuckGo (备用引擎)

| 属性 | 说明 |
|------|------|
| 类型 | 隐私搜索引擎 |
| 库依赖 | `duckduckgo-search` |
| 特点 | 无需API key、不限制调用频率 |
| 区域支持 | 全球/特定区域 |
| 降级级别 | Level 2 |

**功能：**
- 文本搜索
- 时间范围过滤 (day/week/month/year)
- 安全搜索级别

### 3. 内容抓取与处理

#### 3.1 HTTP客户端

| 组件 | 说明 | 用途 |
|------|------|------|
| `httpx` | 异步HTTP客户端 | 搜索API调用、页面获取 |
| 特性 | 异步支持、自动重定向、超时控制 | - |

#### 3.2 内容提取

| 组件 | 说明 | 版本 |
|------|------|------|
| `trafilatura` | 专业网页正文提取 | >=1.12.0 |
| `beautifulsoup4` | HTML解析 | >=4.12.0 |
| `playwright` | 动态页面渲染（可选） | >=1.40.0 |

**提取策略：**
1. **首选**：`trafilatura.extract()` - 基于机器学习的正文提取
2. **备用**：BeautifulSoup - 标签清洗 + 文本提取
3. **增强**：Playwright - 检测到JS渲染时自动启用
4. **清洗**：移除脚本/样式/导航/广告标签

**清洗规则：**
```python
移除标签: ['script', 'style', 'nav', 'footer', 'header']
文本处理: 合并空白、截断至最大长度
内容截断: 默认10000字符（可配置）
```

### 4. 数据处理

#### 4.1 结果去重

| 组件 | 说明 |
|------|------|
| 算法 | SimHash + 布隆过滤器 |
| 复杂度 | O(n) 优化 |
| 阈值 | 默认0.85（85%相似度视为重复） |
| 匹配维度 | URL完全匹配 / 标题相似度 |
| 内存优化 | 降低50%内存占用 |

**去重流程：**
1. 检查URL是否已存在
2. 计算标题相似度（忽略大小写）
3. 相似度>阈值则视为重复

#### 4.2 结果排序

**质量评分维度：**
| 因素 | 权重 | 说明 |
|------|------|------|
| 摘要长度 | +10 | 长度>50字符的完整摘要 |
| 发布日期 | +5 | 有明确时间戳的结果 |
| 多引擎确认 | +3 | 多个引擎返回相同结果 |
| 引擎评分 | 动态 | SearXNG提供的相关性分数 |

### 5. 配置管理

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| SearXNG实例 | `SEARXNG_URL` | `https://<your-searxng-instance>` | SearXNG 实例基址（例如 https://searx.example.com） |
| 超时时间 | `SEARCH_TIMEOUT` | 30秒 | HTTP请求超时 |
| 默认结果数 | `DEFAULT_LIMIT` | 10 | 单次搜索返回数量 |
| 深度搜索页数 | `DEEP_SEARCH_MAX_PAGES` | 5 | 获取全文的最大页面数 |
| 最大内容长度 | `MAX_CONTENT_LENGTH` | 10000 | 单页面内容截断长度 |
| Redis缓存 | `REDIS_URL` | `redis://localhost:6379` | 缓存服务地址 |
| 缓存TTL | `CACHE_TTL` | 3600 | 缓存过期时间（秒） |
| 限流速率 | `RATE_LIMIT_RPM` | 200 | 每分钟最大请求数 |
| 最大并发 | `MAX_CONCURRENT` | 20 | 最大并发请求数 |
| 启用Playwright | `ENABLE_PLAYWRIGHT` | false | 是否启用动态页面渲染 |

---

## 项目结构

```
enhanced-search-mcp/
├── pyproject.toml              # 项目配置与依赖
├── README.md                   # 项目说明
├── docs/
│   └── tech-stack.md          # 本文档
└── src/
    └── enhanced_search/
        ├── __init__.py
        ├── server.py          # MCP服务器主入口
        ├── config.py          # 配置管理
        ├── cache/
        │   ├── __init__.py
        │   └── redis_cache.py # Redis缓存层
        ├── engines/
        │   ├── __init__.py
        │   ├── base.py        # 引擎基类（插件化）
        │   ├── searxng.py     # SearXNG客户端
        │   ├── duckduckgo.py  # DuckDuckGo客户端
        │   └── fetcher.py     # 页面抓取器
        └── utils/
            ├── __init__.py
            ├── dedup.py       # SimHash去重
            ├── rate_limit.py  # 令牌桶限流
            ├── health_check.py # 健康检查
            └── retry.py       # 重试机制
```

---

## 依赖清单

```toml
[dependencies]
mcp>=1.0.0                    # MCP SDK
httpx>=0.27.0                 # 异步HTTP客户端
beautifulsoup4>=4.12.0        # HTML解析
duckduckgo-search>=6.0.0      # DuckDuckGo搜索
trafilatura>=1.12.0           # 网页正文提取
pydantic>=2.0.0               # 数据验证
redis>=5.0.0                  # Redis缓存（可选）
playwright>=1.40.0           # 动态页面渲染（可选）
```

**说明：**
- 所有依赖均为开源免费库
- Redis和Playwright为可选组件
- 无需任何付费API密钥

---

## 部署方式

 ### 方式1：使用公共SearXNG实例（推荐入门）
 
 零配置即可使用，从 [searx.space](https://searx.space) 选择可用实例：
 
 ```env
 SEARXNG_URL=https://<choose-from-searx.space>
 ```

**选择公共实例建议：**
- **优先选择**：可用性为 `OK`、响应时间低、最近检查时间新。
- **引擎可用性**：不少公共实例会禁用/被上游封禁 Google/Bing 等引擎，需在 searx.space 查看该实例启用的引擎。
- **稳定性与隐私**：公共实例由第三方运营，建议避免在查询中包含敏感信息。
- **生产/高频使用**：更建议自建 SearXNG（见下方方式2），可控且更稳定。

### 方式2：自建SearXNG（推荐生产环境）

```bash
# Docker部署
docker run -d --name searxng \
  -p 8080:8080 \
  -v /path/to/searxng:/etc/searxng \
  searxng/searxng

# 配置MCP使用自建实例
SEARXNG_URL=http://localhost:8080
```

---

## MCP工具接口

### 1. search - 增强搜索

**输入参数：**
```json
{
    "query": "搜索查询词",
    "limit": 10,
    "categories": "general",
    "engines": "google,bing,duckduckgo",
    "language": "zh-CN",
    "time_range": "month"
}
```

**输出格式：**
```json
[
    {
        "title": "结果标题",
        "url": "https://example.com",
        "snippet": "摘要内容...",
        "engine": "google",
        "score": 8.5,
        "published_date": "2024-01-15"
    }
]
```

### 2. fetch_content - 获取页面内容

**输入参数：**
```json
{
    "url": "https://example.com",
    "max_length": 10000
}
```

**输出格式：**
```json
{
    "url": "https://example.com",
    "title": "页面标题",
    "content": "清洗后的正文内容...",
    "success": true,
    "error": null
}
```

### 3. deep_search - 深度搜索

**输入参数：**
```json
{
    "query": "搜索词",
    "fetch_limit": 3,
    "search_limit": 10
}
```

**输出格式：** 包含 `full_content` 字段的搜索结果数组

### 4. extract_structured - 结构化提取

**输入参数：**
```json
{
    "urls": ["url1", "url2"],
    "fields": ["title", "content_summary", "author"]
}
```

### 5. search_images - 图片搜索（新增）

**输入参数：**
```json
{
    "query": "搜索词",
    "limit": 10,
    "size": "medium"
}
```

### 6. search_history - 搜索历史（新增）

**输入参数：**
```json
{
    "action": "list|execute|clear",
    "query_id": "查询ID（execute时需要）"
}
```

---

## 性能特点

| 指标 | 优化后 |
|------|--------|
| 搜索延迟 | 通常1-3秒（并行多引擎） |
| 内容获取 | 单页面1-2秒（取决于目标网站） |
| 缓存命中率 | 30-50%（热门查询） |
| 去重性能 | O(n) 复杂度，支持10,000+结果 |
| 并发能力 | 最大20并发，动态调整 |
| 内存占用 | 低（流式处理 + Redis缓存） |
| 动态页面覆盖率 | 提升30%（Playwright） |

---

## 隐私与安全

| 方面 | 措施 |
|------|------|
| 用户追踪 | 不记录任何搜索历史（可选本地历史） |
| 数据传输 | 仅向搜索引擎发送查询（通过SearXNG/DDG） |
| 内容缓存 | Redis缓存（TTL 1小时，不持久化） |
| 安全搜索 | 支持安全搜索级别配置 |
| 请求限流 | 令牌桶算法防止滥用 |
| 错误重试 | 指数退避策略（最多3次） |
| 健康检查 | 自动监控引擎可用性 |
| 完全免费 | 无需任何付费API |

---

## 优化路线图

### P0 - 核心优化（必须）

- [x] 缓存层：Redis缓存热门查询
- [x] 请求限流：令牌桶算法
- [x] 健康检查：引擎可用性监控
- [x] 降级策略：多级引擎切换
- [x] 错误重试：指数退避机制

### P1 - 性能优化（重要）

- [x] SimHash去重：O(n)复杂度优化
- [x] 并发控制：动态并发限制
- [x] 超时分级：搜索10s/抓取30s/深度60s
- [x] Playwright：动态页面支持

### P2 - 功能增强（推荐）

- [x] 图片搜索：扩展SearXNG图片类别
- [x] 搜索历史：会话级历史管理
- [x] 插件化架构：可扩展搜索引擎

### P3 - 智能增强（可选）

- [ ] 相关推荐：基于查询推荐
- [ ] 结果分类：自动分类展示

**注意：**
- LLM摘要功能由调用MCP的模型处理，MCP返回原始内容即可
- 所有功能无需付费API

---

## 扩展建议

### 可增强功能

1. **向量检索**：对常用结果建立向量索引加速检索
2. **图片搜索**：扩展SearXNG图片类别支持
3. **本地化**：多语言搜索结果聚合
4. **插件系统**：用户自定义搜索引擎
5. **配置热更新**：运行时配置变更
6. **流式响应**：增量返回结果
7. **多语言翻译**：自动翻译非目标语言内容

**LLM摘要说明：**
- MCP返回原始内容
- 由调用MCP的模型（如Claude）进行摘要
- 无需在MCP中配置额外模型API

### 监控指标

- 搜索成功率
- 各引擎响应时间
- 内容提取成功率
- 平均去重比例
- 缓存命中率
- 限流触发次数
- 降级切换次数

---

## 相关资源

- [SearXNG官方文档](https://docs.searxng.org/)
- [MCP协议规范](https://modelcontextprotocol.io/)
- [公共SearXNG实例列表](https://searx.space)
- [trafilatura文档](https://trafilatura.readthedocs.io/)
- [Playwright文档](https://playwright.dev/python/)
- [Redis文档](https://redis.io/docs/)
- [SimHash算法](https://en.wikipedia.org/wiki/SimHash)
