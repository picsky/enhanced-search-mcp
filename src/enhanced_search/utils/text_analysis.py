"""Text analysis utilities: paragraph extraction, relevance scoring, recency, conflict detection, follow-up suggestions."""

import math
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import jieba

# Suppress jieba initialization logs
jieba.setLogLevel(jieba.logging.WARNING)

_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]")


def _has_chinese(text: str) -> bool:
    """Check if text contains CJK characters."""
    return bool(_CJK_RE.search(text))


# ---------------------------------------------------------------------------
# Tokenization helpers
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> List[str]:
    """Chinese-aware tokenizer: uses jieba for CJK text, regex for others."""
    text = text.lower().strip()
    if not text:
        return []
    if _has_chinese(text):
        # jieba cut for Chinese segments, regex for non-Chinese segments
        tokens: List[str] = []
        for word in jieba.cut(text):
            word = word.strip()
            if not word:
                continue
            if _CJK_RE.search(word):
                if len(word) >= 2:
                    tokens.append(word)
            else:
                sub = re.findall(r"\w+", word)
                tokens.extend(sub)
        return tokens
    return re.findall(r"\w+", text)


def _ngrams(tokens: List[str], n: int = 2) -> List[str]:
    """Generate n-grams from token list."""
    return [" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]


# ---------------------------------------------------------------------------
# TF-IDF based paragraph extraction (P1-1)
# ---------------------------------------------------------------------------

def _idf(term: str, documents: List[List[str]]) -> float:
    """Inverse document frequency for a term across documents."""
    doc_count = sum(1 for doc in documents if term in doc)
    if doc_count == 0:
        return 0.0
    return math.log(len(documents) / doc_count) + 1.0


def extract_key_paragraphs(
    content: str,
    query: str,
    top_k: int = 3,
    min_paragraph_length: int = 40,
) -> List[str]:
    """Extract the top-k most query-relevant paragraphs from content using TF-IDF."""
    if not content or not query:
        return []

    paragraphs = [p.strip() for p in re.split(r"\n{2,}|\n(?=[A-Z\u4e00-\u9fff])", content) if p.strip()]
    # Also split very long paragraphs by single newline
    expanded: List[str] = []
    for p in paragraphs:
        if len(p) > 500:
            sub = [s.strip() for s in p.split("\n") if s.strip()]
            expanded.extend(sub)
        else:
            expanded.append(p)

    paragraphs = [p for p in expanded if len(p) >= min_paragraph_length]
    if not paragraphs:
        # fallback: return truncated content
        return [content[:500] + "..."] if len(content) > 500 else [content]

    query_tokens = set(_tokenize(query))
    query_bigrams = set(_ngrams(_tokenize(query)))

    # Tokenize all paragraphs as "documents" for IDF
    para_token_lists = [_tokenize(p) for p in paragraphs]

    scores: List[Tuple[float, int]] = []
    for idx, (para, tokens) in enumerate(zip(paragraphs, para_token_lists)):
        if not tokens:
            scores.append((0.0, idx))
            continue

        tf = Counter(tokens)
        total = len(tokens)

        # Unigram TF-IDF overlap with query
        score = 0.0
        for qt in query_tokens:
            term_tf = tf.get(qt, 0) / total
            term_idf = _idf(qt, para_token_lists)
            score += term_tf * term_idf

        # Bigram bonus
        para_bigrams = set(_ngrams(tokens))
        bigram_overlap = len(query_bigrams & para_bigrams)
        score += bigram_overlap * 2.0

        # Length penalty: prefer medium-length paragraphs
        if len(para) > 1000:
            score *= 0.8

        scores.append((score, idx))

    scores.sort(key=lambda x: x[0], reverse=True)
    selected = [paragraphs[idx] for _, idx in scores[:top_k] if _ > 0]

    if not selected:
        return [content[:500] + "..."] if len(content) > 500 else [content]

    return selected


# ---------------------------------------------------------------------------
# Relevance scoring (P1-2)
# ---------------------------------------------------------------------------

def compute_relevance_score(
    query: str,
    title: str,
    snippet: str,
    engine: str,
) -> float:
    """
    Compute relevance score for a search result.
    - Title similarity: 40%
    - Snippet match: 40%
    - Multi-source confirmation: 20%
    Returns: 0.0 - 1.0
    """
    query_tokens = set(_tokenize(query))
    if not query_tokens:
        return 0.0

    # Title similarity (40%)
    title_tokens = set(_tokenize(title))
    title_overlap = len(query_tokens & title_tokens) / len(query_tokens) if query_tokens else 0.0
    title_score = min(title_overlap, 1.0) * 0.4

    # Snippet match (40%)
    snippet_tokens = set(_tokenize(snippet))
    snippet_overlap = len(query_tokens & snippet_tokens) / len(query_tokens) if query_tokens else 0.0
    snippet_score = min(snippet_overlap, 1.0) * 0.4

    # Multi-source confirmation (20%)
    engine_count = len(engine.split(",")) if engine else 1
    multi_source_score = min(engine_count / 3.0, 1.0) * 0.2

    return round(title_score + snippet_score + multi_source_score, 3)


# ---------------------------------------------------------------------------
# Recency scoring (P1-4)
# ---------------------------------------------------------------------------

_DATE_PATTERNS = [
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",
    r"\d{4}-\d{2}-\d{2}",
    r"\d{4}/\d{2}/\d{2}",
    r"\w+ \d{1,2}, \d{4}",
]


def compute_recency_score(published_date: Optional[str], max_age_days: int = 730) -> float:
    """
    Compute recency score: 0.0 (old/unknown) - 1.0 (today).
    max_age_days: dates older than this get score 0.
    """
    if not published_date:
        return 0.0

    parsed = _parse_date(published_date)
    if not parsed:
        return 0.0

    now = datetime.now(timezone.utc)
    age_days = (now - parsed).days
    if age_days < 0:
        return 1.0
    if age_days > max_age_days:
        return 0.0

    return round(1.0 - (age_days / max_age_days), 3)


def _parse_date(date_str: str) -> Optional[datetime]:
    """Try multiple date formats."""
    formats = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%B %d, %Y",
        "%b %d, %Y",
    ]
    # Strip timezone info like +00:00 for naive parsing
    clean = re.sub(r"\.\d+", "", date_str.strip())
    for fmt in formats:
        try:
            dt = datetime.strptime(clean, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Follow-up suggestions (P1-3)
# ---------------------------------------------------------------------------

_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "above", "below", "between", "out", "off", "over",
    "under", "again", "further", "then", "once", "and", "but", "or",
    "nor", "not", "so", "if", "this", "that", "these", "those", "it",
    "its", "he", "she", "they", "we", "you", "what", "which", "who",
    "when", "where", "why", "how", "all", "each", "every", "both",
    "few", "more", "most", "other", "some", "such", "no", "only",
    "same", "than", "too", "very", "just", "about", "also", "de", "en",
    "new", "use", "used", "using", "based", "like", "make", "way",
    "get", "one", "two", "first", "best", "top", "know", "learn",
    "guide", "free", "full", "read", "here", "need", "many", "much",
    "well", "even", "still", "help", "work", "find", "good", "great",
    "的", "了", "是", "在", "有", "和", "与", "为", "这", "那", "个",
    "中", "上", "下", "不", "也", "就", "都", "而", "及", "或", "等",
    "到", "被", "从", "对", "于", "将", "要", "把", "能", "可以",
}


def generate_follow_up_queries(
    query: str,
    results: List[Dict[str, Any]],
    count: int = 3,
) -> List[str]:
    """Generate follow-up query suggestions based on original query and results."""
    if not results:
        return []

    query_tokens = set(_tokenize(query))
    chinese = _has_chinese(query)

    # Min token length: 2 for Chinese (jieba words), 4 for English
    min_token_len = 2 if chinese else 4

    # Collect tokens and bigrams from result titles and snippets
    all_tokens: List[str] = []
    all_bigrams: List[str] = []
    for r in results:
        title_toks = _tokenize(r.get("title", ""))
        snippet_toks = _tokenize(r.get("snippet", ""))
        all_tokens.extend(title_toks)
        all_tokens.extend(snippet_toks)
        all_bigrams.extend(_ngrams(title_toks))

    # Filter tokens: not in query, not stopword, not purely numeric
    filtered = [
        t for t in all_tokens
        if t not in query_tokens
        and t not in _STOPWORDS
        and len(t) >= min_token_len
        and not t.isdigit()
    ]
    freq = Counter(filtered)
    top_terms = [term for term, _ in freq.most_common(20)]

    # Filter bigrams: at least one non-stopword, not all query tokens
    bigram_freq = Counter(all_bigrams)
    top_bigrams = []
    for bg, _ in bigram_freq.most_common(10):
        bg_tokens = set(bg.split())
        if bg_tokens <= query_tokens:
            continue
        if bg_tokens <= _STOPWORDS:
            continue
        top_bigrams.append(bg)

    suggestions: List[str] = []

    # Strategy 1: query + top relevant bigram (higher quality than single term)
    if top_bigrams:
        suggestions.append(f"{query} {top_bigrams[0]}")
    elif top_terms:
        suggestions.append(f"{query} {top_terms[0]}")

    # Strategy 2: Explore a related entity (use bigram if available, else term)
    entity = top_bigrams[1] if len(top_bigrams) >= 2 else (top_terms[1] if len(top_terms) >= 2 else None)
    if entity:
        if chinese:
            suggestions.append(f"{entity} 详细介绍")
        else:
            suggestions.append(f"{entity} explained")

    # Strategy 3: query + "latest" / "最新" (only if we have meaningful tokens)
    if top_terms or top_bigrams:
        if chinese:
            suggestions.append(f"{query} 最新进展")
        else:
            suggestions.append(f"{query} latest developments")

    return suggestions[:count]


# ---------------------------------------------------------------------------
# Conflict detection (P2-2)
# ---------------------------------------------------------------------------

_CLAIM_PATTERN = re.compile(
    r"(?:"
    r"(?:about|approximately|around|roughly|estimated|worth|revenue|price|cost|"
    r"market cap|valuation|funding|raised|profit|loss|growth|decline|population|"
    r"total|number|size|rate|salary|income|budget|debt|GDP|"
    r"is|was|are|were|has|have|reached|hit|exceed|over|under|"
    r"价格|收入|营收|市值|融资|利润|增长|下降|约|大约|人口|总计|数量|规模)"
    r"\s*[:：]?\s*)?"
    r"[¥$€£]?\s*(\d[\d,]*\.?\d*)\s*"
    r"(%|USD|EUR|RMB|元|美元|亿|万|billion|million|trillion|bn|m\b|thousand|hundred|百|千)",
    re.IGNORECASE,
)


def detect_conflicts(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Detect potential conflicts across sources.
    Only flags numbers that appear in a meaningful claim context with explicit units.
    Filters out noise: years, bare numbers, and very small values.
    """
    conflicts: List[Dict[str, Any]] = []

    # Extract number claims from each source (only with explicit unit + context keyword)
    all_claims: List[Tuple[float, str, int]] = []  # (value, unit, source_id)
    for idx, src in enumerate(sources):
        excerpts = src.get("key_excerpts", [])
        text = " ".join(excerpts) if excerpts else ""
        for match in _CLAIM_PATTERN.finditer(text):
            n_str, unit = match.group(1), match.group(2)
            try:
                val = float(n_str.replace(",", ""))
            except ValueError:
                continue
            # Filter out year-like numbers and very small numbers
            if 1900 <= val <= 2099:
                continue
            if val < 1:
                continue
            all_claims.append((val, unit.lower(), idx))

    # Group by unit and compare
    by_unit: Dict[str, List[Tuple[float, int]]] = {}
    for val, unit, sid in all_claims:
        by_unit.setdefault(unit, []).append((val, sid))

    for unit, vals in by_unit.items():
        # Need claims from at least 2 different sources
        source_ids = set(s for _, s in vals)
        if len(source_ids) < 2:
            continue
        values = [v for v, _ in vals]
        if max(values) > 0 and min(values) > 0:
            ratio = max(values) / min(values)
            if ratio >= 1.5:
                conflicts.append({
                    "type": "number_discrepancy",
                    "unit": unit,
                    "values": [{"source_id": s, "value": v} for v, s in vals],
                    "source_ids": list(source_ids),
                    "description": f"Sources disagree on {unit} values: {[v for v, _ in vals]}",
                })

    return conflicts
