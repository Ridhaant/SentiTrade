"""
sentitrade.py
=============
Author  : Ridhaant Ajoy Thackur
Project : sentitrade
License : MIT

Real-time Indian financial news sentiment pipeline.

Pipeline:
  RSS feeds → Article ingestion → VADER + keyword NLP → Sector tagging
  → ZMQ PUSH signal → Downstream consumers (dashboards, strategy engines)

Designed to slot directly into a trading system as a sentiment signal
provider: subscribe to "sentiment" topic on the ZMQ bus and receive
structured, sector-tagged sentiment events for each new news article.

Usage (run as standalone process):
    python sentitrade.py --feeds feeds.json --port 28090

Usage (import):
    from sentitrade import SentiPipeline, FeedConfig, SentimentSignal

    pipeline = SentiPipeline(
        feeds=[
            FeedConfig("Economic Times", "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"),
            FeedConfig("Moneycontrol", "https://www.moneycontrol.com/rss/marketsindia.xml"),
        ],
        zmq_push_addr="tcp://127.0.0.1:28090",
        poll_interval=60,
    )
    pipeline.start()
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Set

import pytz

log = logging.getLogger("sentitrade")
IST = pytz.timezone("Asia/Kolkata")

# ── Dependency detection ───────────────────────────────────────────────────────
try:
    import feedparser
    _FEED_OK = True
except ImportError:
    feedparser = None  # type: ignore
    _FEED_OK = False
    log.warning("feedparser not installed (pip install feedparser) — feed ingestion disabled.")

try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    _vader = SentimentIntensityAnalyzer()
    _VADER_OK = True
except ImportError:
    _vader = None
    _VADER_OK = False
    log.warning("vaderSentiment not installed — using keyword-only scoring.")

try:
    import zmq
    _ZMQ_OK = True
except ImportError:
    zmq = None  # type: ignore
    _ZMQ_OK = False


# ══════════════════════════════════════════════════════════════════════════════
# DOMAIN TYPES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class FeedConfig:
    name: str
    url: str
    weight: float = 1.0          # relative weight in aggregate scores
    max_articles: int = 20       # articles to process per poll


@dataclass
class SentimentSignal:
    """
    Structured sentiment event published on the ZMQ bus.

    score       : float [-1, +1]  — composite sentiment
    label       : "BULLISH" | "BEARISH" | "NEUTRAL"
    confidence  : float [0, 1]
    sectors     : List[str]       — affected NSE sectors
    impact      : "HIGH" | "MEDIUM" | "LOW"
    headline    : str             — article title
    source      : str             — feed name
    url         : str
    ts          : str             — ISO-8601 timestamp (IST)
    article_id  : str             — SHA-256 hex of URL (dedup key)
    """
    score: float
    label: str
    confidence: float
    sectors: List[str]
    impact: str
    headline: str
    source: str
    url: str
    ts: str
    article_id: str
    bullish_triggers: List[str] = field(default_factory=list)
    bearish_triggers: List[str] = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════════════════
# SENTIMENT ANALYSER  (Indian market domain — mirrors AlgoStack's analyzer)
# ══════════════════════════════════════════════════════════════════════════════

# Bullish / Bearish keyword lexicons tuned for NSE/BSE news
_BULLISH = frozenset({
    "buyback", "dividend", "bonus share", "results beat", "strong quarter",
    "all-time high", "record profit", "fii buying", "dii buying",
    "rate cut", "stimulus", "capex boost", "pli scheme", "infrastructure push",
    "order win", "new contract", "expansion", "acquisition", "merger approved",
    "rbi support", "government boost", "tax cut", "ease regulations",
    "monsoon normal", "gst collection high", "exports rise", "rupee stable",
    "upgrade", "outperform", "buy rating", "target price raised",
    "strong guidance", "beat estimates", "revenue growth", "margin expansion",
    "debt reduction", "credit upgrade", "overweight", "strong buy",
})

_BEARISH = frozenset({
    "profit warning", "downgrade", "fii selling", "margin pressure",
    "rate hike", "inflation high", "npa rise", "bank stress", "bad loans",
    "slowdown", "recession fears", "global selloff", "circuit breaker",
    "sebi probe", "ed raid", "cbi investigation", "promoter pledge",
    "debt default", "ncd default", "credit downgrade", "rating cut",
    "monsoon deficit", "gst miss", "trade deficit", "rupee fall",
    "sanctions", "tariff hike", "supply chain disruption",
    "miss estimates", "weak guidance", "below expectations",
    "losses widened", "revenue decline", "cash crunch", "insolvency",
    "underweight", "sell rating", "target price cut", "reduce",
})

_HIGH_IMPACT = frozenset({
    "breaking", "urgent", "alert", "crash", "rally", "surge",
    "plunge", "soar", "collapse", "record", "historic",
})

# Sector classification
_SECTORS: Dict[str, List[str]] = {
    "Banking":  ["bank", "nbfc", "rbi", "repo rate", "credit", "npa", "hdfc", "sbi", "icici"],
    "IT":       ["it sector", "software", "infosys", "tcs", "wipro", "hcl", "us gdp", "cloud"],
    "Pharma":   ["pharma", "drug", "usfda", "cipla", "sunpharma", "drreddy", "biocon"],
    "Auto":     ["auto", "ev", "electric vehicle", "tatamotors", "maruti", "bajaj", "hero"],
    "Energy":   ["crude oil", "bpcl", "reliance", "ongc", "opec", "energy", "petroleum"],
    "Metals":   ["steel", "metals", "vedanta", "tata steel", "jsw", "coal", "iron ore"],
    "FMCG":     ["fmcg", "hul", "itc", "britannia", "rural demand", "dabur", "nestle"],
    "Realty":   ["real estate", "realty", "dlf", "housing", "home loan", "cement"],
    "Indices":  ["nifty", "sensex", "banknifty", "market breadth", "fii flows", "dii flows"],
    "Crypto":   ["bitcoin", "ethereum", "crypto", "defi", "web3", "blockchain", "binance"],
}


def analyse_text(text: str) -> dict:
    """
    Score a news headline or body text for Indian market sentiment.

    Returns
    -------
    dict with keys: score, label, confidence, sectors, impact,
                    bullish_triggers, bearish_triggers
    """
    if not text:
        return {"score": 0.0, "label": "NEUTRAL", "confidence": 0.0,
                "sectors": [], "impact": "LOW",
                "bullish_triggers": [], "bearish_triggers": []}

    lower = text.lower()

    # Base VADER score
    vader_score = _vader.polarity_scores(text)["compound"] if _VADER_OK else 0.0

    # Keyword boost (±5% per hit, capped ±0.5)
    b_hits = [k for k in _BULLISH if k in lower]
    bear_hits = [k for k in _BEARISH if k in lower]
    boost = max(-0.5, min(0.5, (len(b_hits) - len(bear_hits)) * 0.05))

    # High-impact amplifier
    amp = 1.2 if any(w in lower for w in _HIGH_IMPACT) else 1.0

    score = max(-1.0, min(1.0, (vader_score + boost) * amp))

    # Sector detection
    sectors = [s for s, kws in _SECTORS.items() if any(k in lower for k in kws)]

    # Impact level
    if any(w in lower for w in _HIGH_IMPACT) or abs(score) > 0.5:
        impact = "HIGH"
    elif abs(score) > 0.2 or (len(b_hits) + len(bear_hits)) >= 2:
        impact = "MEDIUM"
    else:
        impact = "LOW"

    return {
        "score": round(score, 3),
        "label": "BULLISH" if score > 0.1 else "BEARISH" if score < -0.1 else "NEUTRAL",
        "confidence": round(abs(score), 3),
        "sectors": sectors,
        "impact": impact,
        "bullish_triggers": b_hits[:5],
        "bearish_triggers": bear_hits[:5],
    }


# ══════════════════════════════════════════════════════════════════════════════
# DEDUPLICATION CACHE
# ══════════════════════════════════════════════════════════════════════════════

class _DedupeCache:
    """
    In-memory set of seen article IDs (SHA-256 of URL).
    Bounded to max_size to avoid unbounded memory growth during long runs.
    """

    def __init__(self, max_size: int = 10_000) -> None:
        self._seen: Set[str] = set()
        self._order: List[str] = []
        self._max = max_size

    def seen(self, article_id: str) -> bool:
        return article_id in self._seen

    def mark(self, article_id: str) -> None:
        if article_id in self._seen:
            return
        self._seen.add(article_id)
        self._order.append(article_id)
        # Evict oldest if over limit
        while len(self._order) > self._max:
            evict = self._order.pop(0)
            self._seen.discard(evict)


def _article_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


# ══════════════════════════════════════════════════════════════════════════════
# ZMQ PUSH PUBLISHER
# ══════════════════════════════════════════════════════════════════════════════

class _SignalPublisher:
    """Pushes SentimentSignal dicts over ZMQ PUSH socket."""

    def __init__(self, addr: str) -> None:
        self._addr = addr
        self._sock = None
        self._ctx = None
        self._lock = threading.Lock()

    def _ensure(self) -> bool:
        if self._sock is not None:
            return True
        if not _ZMQ_OK:
            return False
        try:
            self._ctx = zmq.Context.instance()
            self._sock = self._ctx.socket(zmq.PUSH)
            self._sock.setsockopt(zmq.SNDHWM, 500)
            self._sock.setsockopt(zmq.LINGER, 0)
            self._sock.bind(self._addr)
            log.info("SentimentSignal PUSH socket on %s", self._addr)
            return True
        except zmq.ZMQError as e:
            log.warning("ZMQ PUSH bind failed: %s", e)
            return False

    def push(self, signal: SentimentSignal) -> None:
        with self._lock:
            if not self._ensure():
                return
            try:
                self._sock.send_json(asdict(signal), flags=zmq.NOBLOCK)
            except zmq.ZMQError:
                pass

    def close(self) -> None:
        with self._lock:
            if self._sock:
                self._sock.close(linger=0)
                self._sock = None


# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

class SentiPipeline:
    """
    Full sentiment ingestion pipeline.

    Polls all configured RSS feeds every `poll_interval` seconds.
    For each new article:
      1. Deduplicates by URL hash
      2. Runs VADER + keyword analysis
      3. Emits a SentimentSignal via ZMQ PUSH (+ optional callbacks)

    Example
    -------
    >>> from sentitrade import SentiPipeline, FeedConfig

    >>> def on_signal(s):
    ...     if s.impact == "HIGH":
    ...         print(f"[{s.label}] {s.headline} | sectors={s.sectors}")

    >>> pipeline = SentiPipeline(
    ...     feeds=[FeedConfig("ET Markets", "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms")],
    ...     poll_interval=60,
    ... )
    >>> pipeline.on_signal(on_signal)
    >>> pipeline.start()
    """

    def __init__(
        self,
        feeds: List[FeedConfig],
        zmq_push_addr: str = "tcp://127.0.0.1:28090",
        poll_interval: float = 60.0,
        max_history: int = 500,
    ) -> None:
        self._feeds = feeds
        self._pub = _SignalPublisher(zmq_push_addr)
        self._interval = poll_interval
        self._dedupe = _DedupeCache()
        self._history: List[SentimentSignal] = []
        self._max_history = max_history
        self._callbacks: List[Callable[[SentimentSignal], None]] = []
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    # ── Callback registration ──────────────────────────────────────────────────
    def on_signal(self, callback: Callable[[SentimentSignal], None]) -> None:
        self._callbacks.append(callback)

    # ── Lifecycle ──────────────────────────────────────────────────────────────
    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._loop, name="SentiPipeline", daemon=True
        )
        self._thread.start()
        log.info(
            "SentiPipeline started | %d feeds | poll=%.0fs", len(self._feeds), self._interval
        )

    def stop(self) -> None:
        self._stop.set()
        self._pub.close()

    def get_history(self, n: Optional[int] = None) -> List[SentimentSignal]:
        """Return most recent signals (most recent first)."""
        h = list(reversed(self._history))
        return h[:n] if n else h

    def aggregate(self, window: int = 20) -> dict:
        """
        Compute aggregate sentiment across the last `window` articles.

        Returns avg score, dominant label, top sectors.
        """
        recent = self._history[-window:]
        if not recent:
            return {"score": 0.0, "label": "NEUTRAL", "n": 0, "top_sectors": []}
        scores = [s.score for s in recent]
        avg = sum(scores) / len(scores)
        from collections import Counter
        all_sectors = [sec for s in recent for sec in s.sectors]
        top = [s for s, _ in Counter(all_sectors).most_common(5)]
        return {
            "score": round(avg, 3),
            "label": "BULLISH" if avg > 0.1 else "BEARISH" if avg < -0.1 else "NEUTRAL",
            "n": len(recent),
            "top_sectors": top,
        }

    # ── Internal ───────────────────────────────────────────────────────────────
    def _loop(self) -> None:
        while not self._stop.is_set():
            self._poll_all()
            self._stop.wait(self._interval)

    def _poll_all(self) -> None:
        for feed_cfg in self._feeds:
            try:
                self._poll_feed(feed_cfg)
            except Exception as exc:
                log.warning("[%s] poll error: %s", feed_cfg.name, exc)

    def _poll_feed(self, feed_cfg: FeedConfig) -> None:
        if not _FEED_OK:
            log.warning("feedparser unavailable — skipping %s", feed_cfg.name)
            return

        parsed = feedparser.parse(feed_cfg.url)
        entries = parsed.get("entries", [])[:feed_cfg.max_articles]

        for entry in entries:
            url = entry.get("link", "")
            if not url:
                continue
            aid = _article_id(url)
            if self._dedupe.seen(aid):
                continue
            self._dedupe.mark(aid)

            title   = entry.get("title", "")
            summary = entry.get("summary", "")
            text    = f"{title}. {summary}"

            result = analyse_text(text)

            signal = SentimentSignal(
                score=result["score"],
                label=result["label"],
                confidence=result["confidence"],
                sectors=result["sectors"],
                impact=result["impact"],
                headline=title[:200],
                source=feed_cfg.name,
                url=url[:500],
                ts=datetime.now(IST).isoformat(),
                article_id=aid,
                bullish_triggers=result["bullish_triggers"],
                bearish_triggers=result["bearish_triggers"],
            )

            # Append to history (bounded)
            self._history.append(signal)
            if len(self._history) > self._max_history:
                self._history.pop(0)

            # Publish
            self._pub.push(signal)

            # Fire callbacks
            for cb in self._callbacks:
                try:
                    cb(signal)
                except Exception as exc:
                    log.warning("Callback error: %s", exc)

            log.debug(
                "[%s] %s | %s (%.3f) | sectors=%s",
                feed_cfg.name, result["label"], title[:60], result["score"], result["sectors"],
            )


# ══════════════════════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

_DEFAULT_FEEDS = [
    FeedConfig("Economic Times Markets",
               "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"),
    FeedConfig("Moneycontrol Markets",
               "https://www.moneycontrol.com/rss/marketsindia.xml"),
    FeedConfig("Business Standard Markets",
               "https://www.business-standard.com/rss/markets-106.rss"),
    FeedConfig("Livemint Markets",
               "https://www.livemint.com/rss/markets"),
]


def main() -> None:
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    )

    parser = argparse.ArgumentParser(description="sentitrade — Indian market sentiment pipeline")
    parser.add_argument("--port", type=int, default=28090, help="ZMQ PUSH port")
    parser.add_argument("--interval", type=float, default=60.0, help="Poll interval (s)")
    parser.add_argument("--feeds", type=str, default=None, help="Path to JSON feed list")
    args = parser.parse_args()

    feeds = _DEFAULT_FEEDS
    if args.feeds and os.path.exists(args.feeds):
        with open(args.feeds) as fh:
            raw = json.load(fh)
        feeds = [FeedConfig(**f) for f in raw]

    def on_signal(s: SentimentSignal) -> None:
        icon = "🟢" if s.label == "BULLISH" else "🔴" if s.label == "BEARISH" else "⚪"
        print(
            f"{icon} [{s.source}] {s.label:<8} {s.score:+.3f} | {s.headline[:70]}"
            f"\n   sectors={s.sectors} | triggers_bull={s.bullish_triggers}"
        )

    pipeline = SentiPipeline(
        feeds=feeds,
        zmq_push_addr=f"tcp://127.0.0.1:{args.port}",
        poll_interval=args.interval,
    )
    pipeline.on_signal(on_signal)
    pipeline.start()

    print(f"sentitrade running | {len(feeds)} feeds | poll={args.interval}s | ZMQ port={args.port}")
    print("Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(30)
            agg = pipeline.aggregate(window=20)
            print(f"\n[Aggregate] score={agg['score']:+.3f}  label={agg['label']}  "
                  f"n={agg['n']}  top_sectors={agg['top_sectors']}\n")
    except KeyboardInterrupt:
        pipeline.stop()
        print("\nStopped.")


if __name__ == "__main__":
    main()
