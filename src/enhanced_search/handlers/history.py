"""Search history handler logic."""

import json
import logging
import time
from typing import Any, Dict, List, Optional

from mcp.types import TextContent

logger = logging.getLogger("enhanced-search")


class SearchHistory:
    """Simple in-memory search history for the current session."""

    def __init__(self, max_size: int = 100):
        self._history: List[Dict[str, Any]] = []
        self._max_size = max_size
        self._counter = 0

    def add(self, query: str, tool: str, result_count: int) -> None:
        self._counter += 1
        entry = {
            "id": self._counter,
            "query": query,
            "tool": tool,
            "result_count": result_count,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        self._history.append(entry)
        if len(self._history) > self._max_size:
            self._history = self._history[-self._max_size:]

    def list_all(self) -> List[Dict[str, Any]]:
        return list(reversed(self._history))

    def get(self, query_id: int) -> Optional[Dict[str, Any]]:
        for h in self._history:
            if h["id"] == query_id:
                return h
        return None

    def clear(self) -> None:
        self._history.clear()
        self._counter = 0


class HistoryHandler:
    """Handles search_history tool."""

    def __init__(self, history: SearchHistory) -> None:
        self.history = history

    async def handle_history(
        self,
        args: Dict[str, Any],
        search_callback: Any,
    ) -> list[TextContent]:
        action = args["action"]

        if action == "list":
            data = self.history.list_all()
            return [TextContent(type="text", text=json.dumps(data, ensure_ascii=False, indent=2))]

        elif action == "clear":
            self.history.clear()
            return [TextContent(type="text", text=json.dumps({"message": "Search history cleared"}))]

        elif action == "execute":
            query_id = args.get("query_id")
            if query_id is None:
                return [TextContent(type="text", text=json.dumps({"error": "query_id is required for execute"}))]
            entry = self.history.get(int(query_id))
            if not entry:
                return [TextContent(type="text", text=json.dumps({"error": f"History entry {query_id} not found"}))]
            # Dispatch to the original tool type if callback is a dict
            tool = entry.get("tool", "search")
            if isinstance(search_callback, dict):
                handler = search_callback.get(tool, search_callback.get("search"))
            else:
                handler = search_callback
            if handler is None:
                return [TextContent(type="text", text=json.dumps({"error": f"Cannot re-execute tool: {tool}"}))]
            return await handler({"query": entry["query"]})

        return [TextContent(type="text", text=json.dumps({"error": f"Unknown action: {action}"}))]
