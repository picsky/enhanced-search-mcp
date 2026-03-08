"""Tests for the text analysis module."""

import pytest

from enhanced_search.utils.text_analysis import (
    compute_recency_score,
    compute_relevance_score,
    detect_conflicts,
    extract_key_paragraphs,
    generate_follow_up_queries,
)


class TestExtractKeyParagraphs:
    def test_empty_content(self) -> None:
        assert extract_key_paragraphs("", "query") == []

    def test_empty_query(self) -> None:
        assert extract_key_paragraphs("some content here", "") == []

    def test_returns_relevant_paragraphs(self) -> None:
        content = (
            "Python is a great programming language.\n\n"
            "Java is used in enterprise applications.\n\n"
            "Python has excellent machine learning libraries like TensorFlow and PyTorch."
        )
        results = extract_key_paragraphs(content, "Python machine learning", top_k=2)
        assert len(results) <= 2
        assert any("Python" in p for p in results)

    def test_short_content_fallback(self) -> None:
        content = "Short"
        results = extract_key_paragraphs(content, "test", min_paragraph_length=40)
        assert len(results) == 1
        assert results[0] == "Short"

    def test_long_content_truncated_fallback(self) -> None:
        content = "x" * 1000
        results = extract_key_paragraphs(content, "unrelated query", min_paragraph_length=2000)
        assert len(results) == 1
        assert results[0].endswith("...")

    def test_top_k_limit(self) -> None:
        content = "\n\n".join([f"Paragraph {i} about Python programming" for i in range(10)])
        results = extract_key_paragraphs(content, "Python", top_k=3, min_paragraph_length=10)
        assert len(results) <= 3


class TestComputeRelevanceScore:
    def test_perfect_title_match(self) -> None:
        score = compute_relevance_score(
            query="python tutorial",
            title="python tutorial",
            snippet="Learn python basics",
            engine="google",
        )
        assert score > 0.5

    def test_no_match(self) -> None:
        score = compute_relevance_score(
            query="python tutorial",
            title="chocolate cake recipe",
            snippet="baking instructions for cakes",
            engine="google",
        )
        assert score < 0.3

    def test_multi_engine_bonus(self) -> None:
        score_single = compute_relevance_score(
            query="test",
            title="test page",
            snippet="test snippet",
            engine="google",
        )
        score_multi = compute_relevance_score(
            query="test",
            title="test page",
            snippet="test snippet",
            engine="google, bing, duckduckgo",
        )
        assert score_multi > score_single

    def test_empty_query_returns_zero(self) -> None:
        score = compute_relevance_score(query="", title="test", snippet="test", engine="google")
        assert score == 0.0

    def test_score_range(self) -> None:
        score = compute_relevance_score(
            query="python",
            title="python",
            snippet="python",
            engine="google, bing, duckduckgo",
        )
        assert 0.0 <= score <= 1.0


class TestComputeRecencyScore:
    def test_none_date(self) -> None:
        assert compute_recency_score(None) == 0.0

    def test_empty_date(self) -> None:
        assert compute_recency_score("") == 0.0

    def test_invalid_date(self) -> None:
        assert compute_recency_score("not-a-date") == 0.0

    def test_recent_date_high_score(self) -> None:
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        score = compute_recency_score(today)
        assert score > 0.9

    def test_old_date_low_score(self) -> None:
        score = compute_recency_score("2020-01-01")
        assert score == 0.0  # >730 days old

    def test_iso_format_with_time(self) -> None:
        from datetime import datetime, timedelta, timezone
        recent = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S")
        score = compute_recency_score(recent)
        assert score > 0.5


class TestDetectConflicts:
    def test_no_conflicts_empty(self) -> None:
        assert detect_conflicts([]) == []

    def test_no_conflicts_single_source(self) -> None:
        sources = [{"key_excerpts": ["Revenue: $100 million"]}]
        assert detect_conflicts(sources) == []

    def test_detects_number_discrepancy(self) -> None:
        sources = [
            {"key_excerpts": ["revenue: $100 million"]},
            {"key_excerpts": ["revenue: $500 million"]},
        ]
        conflicts = detect_conflicts(sources)
        assert len(conflicts) >= 1
        assert conflicts[0]["type"] == "number_discrepancy"

    def test_ignores_year_like_numbers(self) -> None:
        sources = [
            {"key_excerpts": ["Founded in 2020 USD"]},
            {"key_excerpts": ["Started in 2021 USD"]},
        ]
        conflicts = detect_conflicts(sources)
        assert len(conflicts) == 0

    def test_same_values_no_conflict(self) -> None:
        sources = [
            {"key_excerpts": ["revenue: $100 million"]},
            {"key_excerpts": ["revenue: $100 million"]},
        ]
        conflicts = detect_conflicts(sources)
        assert len(conflicts) == 0


class TestGenerateFollowUpQueries:
    def test_empty_results(self) -> None:
        suggestions = generate_follow_up_queries("python", [], count=3)
        assert len(suggestions) <= 3

    def test_returns_requested_count(self) -> None:
        results = [
            {"title": "Python programming tutorial advanced topics", "snippet": "Learn advanced Python features"},
            {"title": "Python machine learning with TensorFlow", "snippet": "Deep learning frameworks"},
        ]
        suggestions = generate_follow_up_queries("python", results, count=2)
        assert len(suggestions) <= 2

    def test_suggestions_contain_query(self) -> None:
        results = [
            {"title": "React hooks tutorial complete guide", "snippet": "Learn React hooks patterns"},
        ]
        suggestions = generate_follow_up_queries("React", results, count=3)
        assert any("React" in s or "react" in s.lower() for s in suggestions)
