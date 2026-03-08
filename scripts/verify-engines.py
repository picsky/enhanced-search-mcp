#!/usr/bin/env python3
"""
SearXNG Engine Verification Tool

Tests which search engines are actually reachable from the current server.
Outputs a recommended SEARXNG_DEFAULT_ENGINES and SEARXNG_IMAGE_ENGINES config.

Usage:
    python3 scripts/verify-engines.py [--url http://localhost:8888] [--timeout 15]
"""

import argparse
import json
import sys
import time
from typing import Dict, List, Tuple

try:
    import httpx
except ImportError:
    print("ERROR: httpx not installed. Run: pip install httpx")
    sys.exit(1)


GENERAL_ENGINES = [
    "bing", "baidu", "sogou", "google", "duckduckgo",
    "brave", "startpage", "mojeek", "yandex", "naver",
    "quark", "360search", "presearch", "wikipedia",
]

IMAGE_ENGINES = [
    "bing images", "baidu images", "sogou images", "google images",
    "unsplash", "pexels", "pixabay images", "mojeek images",
    "presearch images", "deviantart", "openverse",
]

CODE_ENGINES = [
    "github", "gitlab", "stackoverflow", "mdn", "arxiv", "pypi", "npm",
]


def test_engine(base_url: str, engine: str, timeout: int) -> Tuple[str, bool, str]:
    """Test a single engine. Returns (name, success, detail)."""
    try:
        start = time.time()
        resp = httpx.get(
            f"{base_url}/search",
            params={"q": "test", "format": "json", "engines": engine},
            timeout=timeout,
        )
        elapsed = time.time() - start
        data = resp.json()
        results = data.get("results", [])
        unresp = data.get("unresponsive_engines", [])

        if results:
            return (engine, True, f"{len(results)} results in {elapsed:.1f}s")
        elif unresp:
            reason = unresp[0][1] if unresp else "unknown"
            return (engine, False, reason)
        else:
            return (engine, False, f"0 results in {elapsed:.1f}s")
    except httpx.TimeoutException:
        return (engine, False, "client timeout")
    except Exception as e:
        return (engine, False, str(e)[:60])


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify SearXNG engine availability")
    parser.add_argument("--url", default="http://localhost:8888", help="SearXNG base URL")
    parser.add_argument("--timeout", type=int, default=15, help="Per-engine timeout in seconds")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    base_url = args.url.rstrip("/")

    # Check SearXNG is reachable
    try:
        resp = httpx.get(f"{base_url}/", timeout=5)
        if resp.status_code != 200:
            print(f"ERROR: SearXNG returned {resp.status_code} at {base_url}")
            sys.exit(1)
    except Exception as e:
        print(f"ERROR: Cannot reach SearXNG at {base_url}: {e}")
        sys.exit(1)

    categories: Dict[str, List[str]] = {
        "General Search": GENERAL_ENGINES,
        "Image Search": IMAGE_ENGINES,
        "Code & Academic": CODE_ENGINES,
    }

    working: Dict[str, List[str]] = {}
    all_results: List[Dict[str, str]] = []

    for cat_name, engines in categories.items():
        if not args.json:
            print(f"\n--- {cat_name} ---")
        working[cat_name] = []

        for engine in engines:
            name, ok, detail = test_engine(base_url, engine, args.timeout)
            status = "OK" if ok else "FAIL"
            all_results.append({"engine": name, "category": cat_name, "status": status, "detail": detail})

            if not args.json:
                icon = "✅" if ok else "❌"
                print(f"  {icon} {name:20s} {detail}")

            if ok:
                working[cat_name].append(name)

    # Generate recommended config
    general = ",".join(working.get("General Search", []))
    images = ",".join(working.get("Image Search", []))

    if args.json:
        output = {
            "results": all_results,
            "recommended": {
                "SEARXNG_DEFAULT_ENGINES": general,
                "SEARXNG_IMAGE_ENGINES": images,
            },
            "working_engines": working,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print("\n" + "=" * 60)
        print("Recommended .env configuration:")
        print("=" * 60)
        print(f'SEARXNG_DEFAULT_ENGINES={general}')
        print(f'SEARXNG_IMAGE_ENGINES={images}')
        total = sum(len(v) for v in working.values())
        print(f"\nTotal working engines: {total}/{sum(len(v) for v in categories.values())}")


if __name__ == "__main__":
    main()
