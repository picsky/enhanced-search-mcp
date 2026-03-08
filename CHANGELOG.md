# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-03-07

### Architecture

- **Refactored server.py into handler modules** — Extracted 7 tool handlers from the monolithic 878-line `server.py` into dedicated modules under `handlers/` (`search.py`, `fetch.py`, `extract.py`, `history.py`). `server.py` is now a thin orchestration layer (~400 lines).
- **Introduced Pydantic models** — Created `models.py` with typed data models (`SearchResultModel`, `FetchResult`, `DeepSearchSource`, `DeepSearchResult`, `ExtractedItem`, `HistoryEntry`) replacing raw `Dict[str, Any]` passing.

### Configuration

- **Replaced manual `os.getenv` Config with Pydantic `BaseSettings`** — All configuration fields now have type validation, range constraints (`ge`, `le`), and descriptive metadata. Invalid env values (e.g. `SEARCH_TIMEOUT=abc`) are caught at startup instead of crashing at runtime.
- **Added `pydantic-settings>=2.0.0`** as a new dependency.

### Bug Fixes

- **Fixed resource leak in `main()`** — The previous implementation called `asyncio.run(mcp.cleanup())` after `asyncio.run(mcp.run())`, creating a second event loop which could not properly close resources from the first. Cleanup is now performed via `try/finally` within a single `asyncio.run()` call.

### Performance

- **Optimized SimHash dedup from O(n²) to amortised O(n)** — Replaced pairwise hash comparison with band-based bucket partitioning (8 bands × 8 bits). Only candidate hashes sharing at least one band key are compared, dramatically reducing comparisons for large result sets (10,000+).

### Testing

- **Added comprehensive test suite** — 40+ tests covering core modules:
  - `test_dedup.py` — SimHash, hamming distance, band keys, URL dedup, title similarity dedup, quality sorting
  - `test_text_analysis.py` — Key paragraph extraction, relevance scoring, recency scoring, conflict detection, follow-up query generation
  - `test_cache.py` — Cache key generation, LRU memory cache (get/set/TTL/eviction), SearchCache integration
  - `test_retry.py` — Retry success/failure, exponential backoff, non-retryable HTTP status codes, argument passing
  - `test_rate_limit.py` — Token bucket acquire, refill, max tokens, initial state
- **Added `pytest>=8.0.0` and `pytest-asyncio>=0.23.0`** as dev dependencies.

### Internationalization

- **Unified message language to English** — Replaced Chinese UI strings (e.g. `"搜索历史已清除"`) with English equivalents (`"Search history cleared"`). Chinese strings in stopwords and regex patterns for bilingual content extraction are preserved as functional.

### Project Structure (after refactoring)

```
src/enhanced_search/
├── server.py              # Thin MCP server orchestration (~400 lines)
├── config.py              # Pydantic BaseSettings config with validation
├── models.py              # Pydantic data models (NEW)
├── handlers/              # Tool handler modules (NEW)
│   ├── __init__.py
│   ├── search.py          # search, deep_search, agent_search, search_images
│   ├── fetch.py           # fetch_content
│   ├── extract.py         # extract_structured
│   └── history.py         # search_history + SearchHistory class
├── engines/               # Search engine clients (unchanged)
├── cache/                 # Redis + LRU cache (unchanged)
└── utils/                 # Dedup, rate limit, health check, retry, text analysis
tests/
├── conftest.py
├── test_dedup.py
├── test_text_analysis.py
├── test_cache.py
├── test_retry.py
└── test_rate_limit.py
```

## [1.0.1] - Initial tracked version

- Multi-engine aggregation (SearXNG + DuckDuckGo)
- SimHash deduplication
- Content fetching (trafilatura + BeautifulSoup)
- Deep search with TF-IDF paragraph extraction
- Agent search with multi-round follow-up
- Redis cache with in-memory LRU fallback
- Token bucket rate limiting
- Engine health check and automatic failover
