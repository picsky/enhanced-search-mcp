"""Local SearXNG config verification test."""
import httpx
import time
import json

BASE = "http://localhost:8888"

def test_search(label: str, params: dict, timeout: int = 20) -> None:
    start = time.time()
    try:
        r = httpx.get(f"{BASE}/search", params=params, timeout=timeout)
        d = r.json()
        results = d.get("results", [])
        unresp = d.get("unresponsive_engines", [])
        elapsed = time.time() - start

        engines_used = set()
        for item in results:
            for e in item.get("engines", []):
                engines_used.add(e)

        has_img = all(item.get("img_src") for item in results) if results else False
        img_note = f", img_src={'yes' if has_img else 'no'}" if "images" in str(params) else ""

        status = "OK" if results else "EMPTY"
        print(f"  [{status}] {label} ({elapsed:.1f}s) {len(results)} results{img_note}")
        print(f"        engines: {engines_used or 'none'}")
        if unresp:
            print(f"        unresponsive: {unresp}")
    except Exception as e:
        elapsed = time.time() - start
        print(f"  [ERR] {label} ({elapsed:.1f}s) {e}")

def main() -> None:
    # Health check
    try:
        r = httpx.get(BASE, timeout=5)
        print(f"SearXNG status: {r.status_code}\n")
    except Exception as e:
        print(f"SearXNG unreachable: {e}")
        return

    print("=== General Search ===")
    test_search("English (default engines)", {"q": "Python programming", "format": "json", "engines": "bing,baidu,sogou,360search,mojeek,presearch"})
    test_search("Chinese query", {"q": "人工智能最新发展", "format": "json", "engines": "bing,baidu,sogou"})
    test_search("No engines specified", {"q": "test", "format": "json"})

    print("\n=== Image Search ===")
    test_search("Image (engines only)", {"q": "sunset", "format": "json", "engines": "sogou images,unsplash,pexels,mojeek images,presearch images"})
    test_search("Image (category)", {"q": "cat", "format": "json", "categories": "images"})

    print("\n=== News ===")
    test_search("News", {"q": "technology", "format": "json", "categories": "news"})

    print("\n=== Code & Academic ===")
    test_search("Code", {"q": "FastAPI", "format": "json", "engines": "github,stackoverflow,pypi"})
    test_search("Academic", {"q": "machine learning", "format": "json", "engines": "arxiv,semantic scholar"})

    print("\n=== Individual Engine Check ===")
    for engine in ["bing", "baidu", "sogou", "360search", "mojeek", "presearch"]:
        test_search(engine, {"q": "test", "format": "json", "engines": engine}, timeout=20)

if __name__ == "__main__":
    main()
