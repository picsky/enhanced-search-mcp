"""Result deduplication using SimHash + URL exact match with O(n) bucket optimization."""

import hashlib
import re
from collections import defaultdict
from typing import Any, Dict, List, Set

import jieba

jieba.setLogLevel(jieba.logging.WARNING)

_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]")

# Number of bands for SimHash bucket partitioning
# Fewer bands = fewer false positives; 4 bands × 16 bits is more selective
_NUM_BANDS = 4
_BAND_SIZE = 64 // _NUM_BANDS  # 16 bits per band


def _tokenize_for_hash(text: str) -> List[str]:
    """Tokenize text for SimHash: Chinese-aware with jieba."""
    text = text.lower().strip()
    if not text:
        return []
    if _CJK_RE.search(text):
        tokens: List[str] = []
        for word in jieba.cut(text):
            word = word.strip()
            if not word:
                continue
            if _CJK_RE.search(word) and len(word) >= 2:
                tokens.append(word)
            elif re.match(r"\w+", word):
                tokens.append(word)
        return tokens
    return re.findall(r"\w+", text)


def _simhash(text: str) -> int:
    """Compute a 64-bit SimHash for a given text string."""
    tokens = _tokenize_for_hash(text)
    if not tokens:
        return 0

    v = [0] * 64
    for token in tokens:
        h = int(hashlib.md5(token.encode()).hexdigest(), 16)
        for i in range(64):
            if h & (1 << i):
                v[i] += 1
            else:
                v[i] -= 1

    fingerprint = 0
    for i in range(64):
        if v[i] > 0:
            fingerprint |= 1 << i
    return fingerprint


def _hamming_distance(a: int, b: int) -> int:
    """Hamming distance between two 64-bit integers."""
    x = a ^ b
    count = 0
    while x:
        count += 1
        x &= x - 1
    return count


def _similarity(a: int, b: int) -> float:
    """Similarity based on SimHash hamming distance (0.0 - 1.0)."""
    dist = _hamming_distance(a, b)
    return 1.0 - dist / 64.0


def _band_keys(fingerprint: int) -> List[int]:
    """Split a 64-bit fingerprint into band keys for bucket hashing.

    Each band covers _BAND_SIZE bits. Two fingerprints sharing any band key
    are candidate near-duplicates, reducing pairwise comparisons to ~O(n).
    """
    keys: List[int] = []
    mask = (1 << _BAND_SIZE) - 1
    for band_idx in range(_NUM_BANDS):
        band_val = (fingerprint >> (band_idx * _BAND_SIZE)) & mask
        keys.append((band_idx << _BAND_SIZE) | band_val)
    return keys


class ResultDeduplicator:
    """Deduplicate search results using URL exact match + SimHash title similarity.

    Uses band-based bucket partitioning to achieve amortised O(n) dedup
    instead of O(n^2) pairwise comparison.
    """

    def __init__(self, similarity_threshold: float = 0.85):
        self.threshold = similarity_threshold

    def deduplicate(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen_urls: Set[str] = set()
        # Band buckets: band_key -> set of fingerprints in that bucket
        buckets: Dict[int, Set[int]] = defaultdict(set)
        seen_hashes: Set[int] = set()
        unique: List[Dict[str, Any]] = []

        for r in results:
            url = r.get("url", "")

            # URL exact match
            if url in seen_urls:
                continue

            # SimHash title similarity with bucket optimization
            title = r.get("title", "")
            h = _simhash(title)
            is_dup = False

            if title and h != 0:
                # Only compare against candidate hashes from matching buckets
                bands = _band_keys(h)
                candidates: Set[int] = set()
                for bk in bands:
                    candidates.update(buckets.get(bk, set()))

                for existing_h in candidates:
                    if _similarity(h, existing_h) > self.threshold:
                        is_dup = True
                        break

                if not is_dup:
                    # Register this hash in all its band buckets
                    for bk in bands:
                        buckets[bk].add(h)
                    seen_hashes.add(h)

            if not is_dup:
                seen_urls.add(url)
                unique.append(r)

        return unique

    @staticmethod
    def sort_by_quality(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sort results by quality score with gradient snippet scoring."""

        def _score(r: Dict[str, Any]) -> float:
            s = 0.0
            snippet = r.get("snippet", "")
            # Gradient snippet score: 0-20 chars=0, 20-50=5, 50-100=8, 100+=10
            slen = len(snippet) if snippet else 0
            if slen > 100:
                s += 10
            elif slen > 50:
                s += 8
            elif slen > 20:
                s += 5
            if r.get("published_date"):
                s += 5
            engine = r.get("engine", "")
            if "," in engine:
                s += 3
            s += r.get("score", 0.0)
            return s

        return sorted(results, key=_score, reverse=True)
