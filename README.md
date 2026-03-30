# sentitrade

**Author:** Ridhaant Ajoy Thackur  
**License:** MIT  
**Python:** 3.9+

> Real-time Indian financial news sentiment pipeline.  
> Ingests NSE/BSE market news via RSS, runs domain-tuned VADER NLP,  
> classifies into sectors (Banking, IT, Pharma, Energy…) and publishes  
> structured sentiment signals over ZMQ — ready to feed into any trading engine.

---

## Pipeline

```
┌──────────────────────────────────────────────────────────────────┐
│                       SentiPipeline                              │
│                                                                  │
│  RSS Feeds (feedparser)                                          │
│  ┌─────────────────┐  ┌──────────────────┐  ┌────────────────┐  │
│  │ Economic Times  │  │  Moneycontrol    │  │ Business Std.  │  │
│  └────────┬────────┘  └────────┬─────────┘  └───────┬────────┘  │
│           └────────────────────┴───────────────────── ┘          │
│                                │                                  │
│                   ┌────────────▼─────────────┐                   │
│                   │   _DedupeCache           │                   │
│                   │   (SHA-256 URL hash)      │                   │
│                   └────────────┬─────────────┘                   │
│                                │  new articles only              │
│                   ┌────────────▼─────────────┐                   │
│                   │   analyse_text()          │                   │
│                   │   VADER compound score    │                   │
│                   │ + Indian keyword boosters │                   │
│                   │ + High-impact amplifier   │                   │
│                   │ + Sector classifier       │                   │
│                   └────────────┬─────────────┘                   │
│                                │                                  │
│                   ┌────────────▼─────────────┐                   │
│                   │   SentimentSignal         │                   │
│                   │   {score, label,          │                   │
│                   │    sectors, impact,       │                   │
│                   │    headline, source, ts}  │                   │
│                   └────────────┬─────────────┘                   │
│                                │                                  │
│           ┌────────────────────┴─────────────────┐               │
│           │                                      │               │
│  ┌────────▼────────┐                  ┌──────────▼─────────┐     │
│  │ ZMQ PUSH socket │                  │ User callbacks     │     │
│  │ tcp://:28090    │                  │ on_signal(fn)      │     │
│  └─────────────────┘                  └────────────────────┘     │
└──────────────────────────────────────────────────────────────────┘
```

---

## Sentiment model

The analyser combines **VADER** (general English NLP) with an **Indian market keyword lexicon** (130+ terms) tuned to NSE/BSE news patterns:

| Layer | Details |
|---|---|
| **VADER base score** | Compound sentiment in `[-1, +1]` |
| **Keyword boost** | ±5% per bullish/bearish keyword hit, capped at ±0.5 |
| **High-impact amplifier** | ×1.2 if headline contains "breaking", "surge", "crash", "rally", etc. |
| **Final score** | `clip((vader + boost) × amp, -1, +1)` |

### Sector classification

Automatically tags articles with affected NSE sectors:
`Banking · IT · Pharma · Auto · Energy · Metals · FMCG · Realty · Indices · Crypto`

---

## Installation

```bash
pip install feedparser vaderSentiment pyzmq pytz
```

```bash
pip install -r requirements.txt
```

---

## Quickstart

### As a library

```python
from src.sentitrade import SentiPipeline, FeedConfig

def on_signal(s):
    print(f"[{s.label}] {s.score:+.3f} | {s.headline[:70]}")
    print(f"  sectors={s.sectors}  impact={s.impact}")

pipeline = SentiPipeline(
    feeds=[
        FeedConfig("ET Markets", "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"),
        FeedConfig("Moneycontrol", "https://www.moneycontrol.com/rss/marketsindia.xml"),
    ],
    poll_interval=60,
)
pipeline.on_signal(on_signal)
pipeline.start()

import time; time.sleep(300)
agg = pipeline.aggregate(window=20)
print(agg)
# {'score': 0.124, 'label': 'BULLISH', 'n': 20, 'top_sectors': ['Banking', 'IT', 'Indices']}
```

### As a standalone process

```bash
python src/sentitrade.py --interval 60 --port 28090
```

### Subscribing from another process

```python
import zmq, json

ctx = zmq.Context()
sock = ctx.socket(zmq.PULL)
sock.connect("tcp://127.0.0.1:28090")

while True:
    signal = sock.recv_json()
    print(signal["label"], signal["score"], signal["sectors"])
```

---

## SentimentSignal schema

```json
{
  "score":            -0.412,
  "label":            "BEARISH",
  "confidence":        0.412,
  "sectors":          ["Banking", "Indices"],
  "impact":           "HIGH",
  "headline":         "RBI holds repo rate; warns of sticky inflation",
  "source":           "Economic Times Markets",
  "url":              "https://...",
  "ts":               "2025-09-01T10:32:14+05:30",
  "article_id":       "a3f2c91d",
  "bullish_triggers": [],
  "bearish_triggers": ["rate hike", "inflation high"]
}
```

---

## Aggregate sentiment API

```python
agg = pipeline.aggregate(window=20)
# {
#   "score":       0.085,
#   "label":       "NEUTRAL",
#   "n":           20,
#   "top_sectors": ["IT", "Banking", "Pharma"]
# }
```

---

## Custom feeds

Create a `feeds.json`:

```json
[
  {"name": "NSE India", "url": "https://www.nseindia.com/feed.xml", "weight": 1.5, "max_articles": 30},
  {"name": "Zerodha Pulse", "url": "https://zerodha.com/pulse/feed/", "weight": 1.0, "max_articles": 20}
]
```

Then:

```bash
python src/sentitrade.py --feeds feeds.json
```

---

## Running tests

```bash
pytest tests/ -v
```

---

## Project context

The NLP and sector classification logic is extracted from [AlgoStack](https://github.com/ridhaant/algostack)'s `sentiment_analyzer.py` and `news_dashboard.py`. In production AlgoStack, sentiment signals feed into a 16-process trading system via the same ZMQ bus (`ipc_bus.py`) used for price distribution.

---

## License

MIT © 2025 Ridhaant Ajoy Thackur
