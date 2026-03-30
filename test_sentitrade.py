"""
tests/test_sentitrade.py
Author : Ridhaant Ajoy Thackur
"""

import pytest
from src.sentitrade import (
    analyse_text,
    _DedupeCache,
    _article_id,
    FeedConfig,
    SentiPipeline,
    SentimentSignal,
)


class TestAnalyseText:
    def test_empty_returns_neutral(self):
        result = analyse_text("")
        assert result["label"] == "NEUTRAL"
        assert result["score"] == 0.0

    def test_bullish_keywords(self):
        result = analyse_text("RBI announces rate cut, strong guidance for banking sector")
        assert result["label"] == "BULLISH"
        assert result["score"] > 0

    def test_bearish_keywords(self):
        result = analyse_text("Company reports losses widened, revenue decline, credit downgrade")
        assert result["label"] == "BEARISH"
        assert result["score"] < 0

    def test_sector_detection_banking(self):
        result = analyse_text("RBI cuts repo rate, SBI shares surge")
        assert "Banking" in result["sectors"]

    def test_sector_detection_it(self):
        result = analyse_text("Infosys beats estimates with strong US dollar revenue growth")
        assert "IT" in result["sectors"]

    def test_high_impact_amplification(self):
        text_normal = "Markets decline slightly"
        text_high   = "BREAKING: Markets crash amid global selloff"
        r_normal = analyse_text(text_normal)
        r_high   = analyse_text(text_high)
        assert abs(r_high["score"]) >= abs(r_normal["score"])
        assert r_high["impact"] in ("HIGH", "MEDIUM")

    def test_score_bounds(self):
        for text in [
            "best ever record breaking all-time high dividend buyback strong buy",
            "crash plunge collapse insolvency credit downgrade sebi probe ed raid losses widened",
            "market opened today",
        ]:
            r = analyse_text(text)
            assert -1.0 <= r["score"] <= 1.0

    def test_confidence_equals_abs_score(self):
        result = analyse_text("Dividend announced, FII buying increases")
        assert abs(round(result["score"], 3)) == result["confidence"]


class TestDedupeCache:
    def test_new_article_not_seen(self):
        cache = _DedupeCache()
        assert not cache.seen("abc123")

    def test_seen_after_mark(self):
        cache = _DedupeCache()
        cache.mark("abc123")
        assert cache.seen("abc123")

    def test_eviction_when_over_limit(self):
        cache = _DedupeCache(max_size=3)
        for i in range(5):
            cache.mark(f"id_{i}")
        # First two should have been evicted
        assert not cache.seen("id_0")
        assert not cache.seen("id_1")
        assert cache.seen("id_4")


class TestArticleId:
    def test_deterministic(self):
        assert _article_id("https://example.com") == _article_id("https://example.com")

    def test_different_urls_different_ids(self):
        assert _article_id("https://a.com") != _article_id("https://b.com")

    def test_length_16(self):
        assert len(_article_id("https://test.com/article/123")) == 16


class TestSentiPipeline:
    def test_aggregate_empty(self):
        pipeline = SentiPipeline(feeds=[], poll_interval=999)
        agg = pipeline.aggregate()
        assert agg["label"] == "NEUTRAL"
        assert agg["n"] == 0

    def test_callback_registration(self):
        pipeline = SentiPipeline(feeds=[], poll_interval=999)
        received = []
        pipeline.on_signal(received.append)
        assert len(pipeline._callbacks) == 1

    def test_get_history_empty(self):
        pipeline = SentiPipeline(feeds=[], poll_interval=999)
        assert pipeline.get_history() == []
