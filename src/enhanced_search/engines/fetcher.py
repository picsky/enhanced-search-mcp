"""Web page content fetcher with trafilatura + BeautifulSoup fallback."""

import logging
import re
from typing import Any, Dict, Optional

import httpx
import trafilatura
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


class ContentFetcher:
    """Fetches and extracts clean text content from web pages."""

    def __init__(self, timeout: int = 30, max_length: int = 10000):
        self.timeout = timeout
        self.max_length = max_length
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                headers={"User-Agent": _USER_AGENT},
            )
        return self._client

    async def fetch(self, url: str, max_length: Optional[int] = None, output_format: str = "text") -> Dict[str, Any]:
        """Fetch a page, extract and clean its main content.

        Args:
            url: The URL to fetch.
            max_length: Maximum content length.
            output_format: 'text' for plain text, 'markdown' for structured markdown.
        """
        limit = max_length or self.max_length
        try:
            resp = await self.client.get(url)
            resp.raise_for_status()
            html = resp.text

            if output_format == "markdown":
                content = self._extract_markdown(html)
            else:
                content = self._extract_content(html)
            title = self._extract_title(html)

            if content:
                content = self._clean(content)[:limit]

            return {
                "url": url,
                "title": title,
                "content": content or "",
                "format": output_format,
                "success": bool(content),
                "error": None if content else "Failed to extract content",
            }
        except Exception as e:
            logger.error("Fetch error for %s: %s", url, e)
            return {
                "url": url,
                "title": None,
                "content": None,
                "success": False,
                "error": str(e),
            }

    # ------------------------------------------------------------------
    # Extraction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_content(html: str) -> Optional[str]:
        """Try trafilatura first, fall back to BeautifulSoup."""
        content = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            deduplicate=True,
        )
        if content:
            return content

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True) or None

    @staticmethod
    def _extract_markdown(html: str) -> Optional[str]:
        """Extract content as markdown using trafilatura, with BS4 fallback."""
        content = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            include_links=True,
            deduplicate=True,
            output_format="markdown",
        )
        if content:
            return content

        # Fallback: manual HTML → markdown conversion
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        parts: list = []
        for el in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "pre", "code", "blockquote"]):
            tag_name = el.name
            text = el.get_text(strip=True)
            if not text:
                continue
            if tag_name == "h1":
                parts.append(f"# {text}")
            elif tag_name == "h2":
                parts.append(f"## {text}")
            elif tag_name == "h3":
                parts.append(f"### {text}")
            elif tag_name in ("h4", "h5", "h6"):
                parts.append(f"#### {text}")
            elif tag_name == "li":
                parts.append(f"- {text}")
            elif tag_name == "blockquote":
                parts.append(f"> {text}")
            elif tag_name in ("pre", "code"):
                parts.append(f"```\n{text}\n```")
            else:
                parts.append(text)

        return "\n\n".join(parts) if parts else None

    @staticmethod
    def _extract_title(html: str) -> Optional[str]:
        soup = BeautifulSoup(html, "html.parser")
        tag = soup.find("title")
        return tag.get_text(strip=True) if tag else None

    @staticmethod
    def _clean(text: str) -> str:
        text = re.sub(r"\n\s*\n", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        return text.strip()

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
