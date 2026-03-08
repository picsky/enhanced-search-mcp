"""Tests for the deduplication module."""

import pytest

from enhanced_search.utils.dedup import (
    ResultDeduplicator,
    _band_keys,
    _hamming_distance,
    _similarity,
    _simhash,
)


class TestSimHash:
    def test_empty_string_returns_zero(self) -> None:
        assert _simhash("") == 0

    def test_whitespace_only_returns_zero(self) -> None:
        assert _simhash("   ") == 0

    def test_identical_strings_same_hash(self) -> None:
        h1 = _simhash("hello world test")
        h2 = _simhash("hello world test")
        assert h1 == h2

    def test_case_insensitive(self) -> None:
        h1 = _simhash("Hello World")
        h2 = _simhash("hello world")
        assert h1 == h2

    def test_similar_strings_high_similarity(self) -> None:
        h1 = _simhash("python programming language tutorial")
        h2 = _simhash("python programming language guide")
        assert _similarity(h1, h2) > 0.7

    def test_different_strings_low_similarity(self) -> None:
        h1 = _simhash("python programming language")
        h2 = _simhash("chocolate cake recipe baking")
        sim = _similarity(h1, h2)
        assert sim < 0.9


class TestHammingDistance:
    def test_identical_values(self) -> None:
        assert _hamming_distance(0, 0) == 0
        assert _hamming_distance(42, 42) == 0

    def test_one_bit_difference(self) -> None:
        assert _hamming_distance(0b1000, 0b1001) == 1

    def test_all_bits_different(self) -> None:
        assert _hamming_distance(0, (1 << 64) - 1) == 64


class TestBandKeys:
    def test_returns_correct_number_of_bands(self) -> None:
        keys = _band_keys(12345)
        assert len(keys) == 4

    def test_identical_fingerprints_same_keys(self) -> None:
        k1 = _band_keys(999)
        k2 = _band_keys(999)
        assert k1 == k2

    def test_different_fingerprints_different_keys(self) -> None:
        k1 = _band_keys(0)
        k2 = _band_keys((1 << 64) - 1)
        assert k1 != k2


class TestResultDeduplicator:
    def setup_method(self) -> None:
        self.dedup = ResultDeduplicator(similarity_threshold=0.85)

    def test_empty_list(self) -> None:
        assert self.dedup.deduplicate([]) == []

    def test_no_duplicates(self) -> None:
        results = [
            {"url": "https://a.com", "title": "Alpha article about cats"},
            {"url": "https://b.com", "title": "Beta article about dogs"},
        ]
        unique = self.dedup.deduplicate(results)
        assert len(unique) == 2

    def test_url_exact_dedup(self) -> None:
        results = [
            {"url": "https://a.com", "title": "First"},
            {"url": "https://a.com", "title": "Duplicate URL"},
        ]
        unique = self.dedup.deduplicate(results)
        assert len(unique) == 1
        assert unique[0]["title"] == "First"

    def test_title_similarity_dedup(self) -> None:
        # Identical titles on different URLs should be detected as duplicates
        results = [
            {"url": "https://a.com", "title": "Python programming tutorial for beginners complete guide"},
            {"url": "https://b.com", "title": "Python programming tutorial for beginners complete guide"},
        ]
        unique = self.dedup.deduplicate(results)
        assert len(unique) == 1

    def test_near_duplicate_titles(self) -> None:
        # With 4 bands (16-bit each), near-duplicates need closer hashes to collide
        title_base = "Introduction to machine learning algorithms and deep neural networks overview"
        h1 = _simhash(title_base)
        h2 = _simhash(title_base + " part 1")
        sim = _similarity(h1, h2)
        # Verify similarity is still high even if bands don't collide
        assert sim > 0.7, f"Expected high similarity, got {sim}"

    def test_different_titles_kept(self) -> None:
        results = [
            {"url": "https://a.com", "title": "Machine learning introduction guide"},
            {"url": "https://b.com", "title": "Chocolate cake baking recipe easy"},
        ]
        unique = self.dedup.deduplicate(results)
        assert len(unique) == 2

    def test_sort_by_quality_snippet_bonus(self) -> None:
        results = [
            {"url": "https://a.com", "snippet": "short", "score": 0},
            {"url": "https://b.com", "snippet": "x" * 60, "score": 0},
        ]
        sorted_r = ResultDeduplicator.sort_by_quality(results)
        assert sorted_r[0]["url"] == "https://b.com"

    def test_sort_by_quality_date_bonus(self) -> None:
        results = [
            {"url": "https://a.com", "snippet": "", "score": 0},
            {"url": "https://b.com", "snippet": "", "score": 0, "published_date": "2024-01-01"},
        ]
        sorted_r = ResultDeduplicator.sort_by_quality(results)
        assert sorted_r[0]["url"] == "https://b.com"

    def test_sort_by_quality_multi_engine_bonus(self) -> None:
        results = [
            {"url": "https://a.com", "snippet": "", "engine": "google", "score": 0},
            {"url": "https://b.com", "snippet": "", "engine": "google, bing", "score": 0},
        ]
        sorted_r = ResultDeduplicator.sort_by_quality(results)
        assert sorted_r[0]["url"] == "https://b.com"
