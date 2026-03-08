"""Extract structured information handler logic."""

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional

from mcp.types import TextContent

from ..engines.fetcher import ContentFetcher
from ..utils.rate_limit import TokenBucketRateLimiter

logger = logging.getLogger("enhanced-search")


class ExtractHandler:
    """Handles extract_structured tool."""

    def __init__(
        self,
        fetcher: ContentFetcher,
        rate_limiter: TokenBucketRateLimiter,
        semaphore: asyncio.Semaphore,
    ) -> None:
        self.fetcher = fetcher
        self.rate_limiter = rate_limiter
        self.semaphore = semaphore

    async def handle_extract(self, args: Dict[str, Any]) -> list[TextContent]:
        urls: List[str] = args["urls"]
        fields: List[str] = args.get("fields", ["title", "content_summary"])
        schema: Optional[Dict[str, str]] = args.get("schema")

        async def _fetch_one(url: str) -> Dict[str, Any]:
            async with self.semaphore:
                await self.rate_limiter.acquire()
                return await self.fetcher.fetch(url)

        tasks = [_fetch_one(u) for u in urls]
        try:
            contents = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=30 * len(urls),
            )
        except asyncio.TimeoutError:
            contents = [TimeoutError("Extract batch timed out")] * len(urls)

        extracted: List[Dict[str, Any]] = []
        for url, content in zip(urls, contents):
            if isinstance(content, dict) and content.get("success"):
                item: Dict[str, Any] = {"url": url}
                text = content.get("content", "")

                for field in fields:
                    if field == "title":
                        item[field] = content.get("title")
                    elif field == "content_summary":
                        item[field] = (text[:500] + "...") if len(text) > 500 else text
                    elif field == "date":
                        item[field] = _extract_date_from_text(text)
                    elif field == "author":
                        item[field] = _extract_author_from_text(text)
                    elif field == "links":
                        item[field] = _extract_links_from_text(text)
                    else:
                        item[field] = None

                if schema:
                    custom = _extract_by_schema(text, schema)
                    item["extracted"] = custom

                extracted.append(item)
            else:
                err = str(content) if isinstance(content, Exception) else "Failed to fetch"
                extracted.append({"url": url, "error": err})

        return [TextContent(type="text", text=json.dumps(extracted, ensure_ascii=False, indent=2))]


def _extract_date_from_text(text: str) -> Optional[str]:
    """Try to find a date in the text."""
    patterns = [
        r"\d{4}-\d{2}-\d{2}",
        r"\d{4}/\d{2}/\d{2}",
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2},?\s+\d{4}",
        r"\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{4}",
    ]
    for pat in patterns:
        m = re.search(pat, text[:2000])
        if m:
            return m.group(0)
    return None


def _extract_author_from_text(text: str) -> Optional[str]:
    """Try to find an author in the text."""
    patterns = [
        r"(?:by|作者|author)[:\s]+([^\n,]{2,40})",
        r"(?:written by|posted by)[:\s]+([^\n,]{2,40})",
    ]
    for pat in patterns:
        m = re.search(pat, text[:2000], re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def _extract_links_from_text(text: str) -> List[str]:
    """Extract URLs from text content."""
    urls = re.findall(r"https?://[^\s<>\"')\]]+", text)
    return list(dict.fromkeys(urls))[:20]


def _extract_by_schema(text: str, schema: Dict[str, str]) -> Dict[str, Any]:
    """
    Extract fields from text based on a user-defined schema.
    Schema format: {"field_name": "type"} where type is "string", "number", "list".
    """
    result: Dict[str, Any] = {}

    for field_name, field_type in schema.items():
        name_variants = [field_name, field_name.replace("_", " "), field_name.replace("_", "-")]
        value: Any = None

        for variant in name_variants:
            if field_type == "number":
                pat = rf"(?:{re.escape(variant)})[:\s]*[¥$€£]?\s*([\d,]+\.?\d*)"
                m = re.search(pat, text, re.IGNORECASE)
                if m:
                    try:
                        value = float(m.group(1).replace(",", ""))
                        if value == int(value):
                            value = int(value)
                    except ValueError:
                        pass
                    break
            elif field_type == "list":
                pat = rf"(?:{re.escape(variant)})[:\s]*(.+?)(?:\n|$)"
                m = re.search(pat, text, re.IGNORECASE)
                if m:
                    raw = m.group(1)
                    value = [s.strip() for s in re.split(r"[,;、|]", raw) if s.strip()]
                    break
            else:  # string
                pat = rf"(?:{re.escape(variant)})[:\s]*(.+?)(?:\n|$)"
                m = re.search(pat, text, re.IGNORECASE)
                if m:
                    value = m.group(1).strip()
                    break

        result[field_name] = value

    return result
