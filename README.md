<div align="center">

```
███████╗███████╗███╗   ██╗████████╗██╗████████╗██████╗  █████╗ ██████╗ ███████╗
██╔════╝██╔════╝████╗  ██║╚══██╔══╝██║╚══██╔══╝██╔══██╗██╔══██╗██╔══██╗██╔════╝
███████╗█████╗  ██╔██╗ ██║   ██║   ██║   ██║   ██████╔╝███████║██║  ██║█████╗
╚════██║██╔══╝  ██║╚██╗██║   ██║   ██║   ██║   ██╔══██╗██╔══██║██║  ██║██╔══╝
███████║███████╗██║ ╚████║   ██║   ██║   ██║   ██║  ██║██║  ██║██████╔╝███████╗
╚══════╝╚══════╝╚═╝  ╚═══╝   ╚═╝   ╚═╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ ╚══════╝
```

# sentitrade

**Real-Time Indian Financial News Sentiment Pipeline**

[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![NLP](https://img.shields.io/badge/VADER_NLP-Domain_Adapted-orange?style=for-the-badge)](https://github.com/cjhutto/vaderSentiment)
[![ZeroMQ](https://img.shields.io/badge/ZeroMQ-PUSH%2FPULL-DF0000?style=for-the-badge&logo=zeromq&logoColor=white)](https://zeromq.org)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](./LICENSE)
[![Tests](https://img.shields.io/badge/Tests-pytest-blue?style=for-the-badge)](./tests/)

<br/>

> Polls NSE/BSE financial news RSS feeds · Runs domain-adapted VADER NLP
> with 130+ Indian market keywords · Classifies into 11 NSE sectors
> · Publishes structured `SentimentSignal` dicts over ZMQ PUSH

<br/>

[⚡ Quickstart](#quickstart) · [🧠 Sentiment Model](#sentiment-model) · [🏗 Pipeline](#pipeline) · [📐 API Reference](#api-reference) · [🔗 Project Context](#project-context)

</div>

---

## Why sentitrade?

Generic NLP models don't understand Indian financial markets:

| Problem | Standard VADER | sentitrade |
|---------|---------------|------------|
| "FII buying" | Neutral (unknown phrase) | **BULLISH** (+boost) |
| "NPA rise" | Neutral (unknown acronym) | **BEARISH** (+boost) |
| "RBI rate hike" | Neutral or weakly negative | **BEARISH HIGH** (×1.2 amplifier) |
| Duplicate RSS articles | Reprocesses everything | **SHA-256 dedup** (O(1) skip) |
| Multiple consumers | Broadcast to all | **PUSH/PULL** (work queue) |

`sentitrade` adapts VADER for Indian markets with 130+ NSE/BSE-specific keyword boosters, a high-impact amplifier for market-moving events, and an 11-sector classifier — all running in < 1ms per article.

---

## Pipeline

```
┌──────────────────────────────────────────────────────────────────┐
│                       SentiPipeline                              │
│                                                                  │
│  RSS Feeds (feedparser)                                          │
│  ┌─────────────────┐  ┌──────────────────┐  ┌────────────────┐   │
│  │ Economic Times  │  │  Moneycontrol    │  │ Business Std.  │   │
│  │    Markets      │  │                  │  │                │   │
│  └────────┬────────┘  └────────┬─────────┘  └───────┬────────┘   │
│           └────────────────────┴─────────────────────┘           │
│                                │                                 │
│                   ┌────────────▼─────────────┐                   │
│                   │   _DedupeCache            │                  │
│                   │  SHA-256 URL hash         │                  │
│                   │  O(1) lookup, 10K FIFO   │                   │
│                   └────────────┬─────────────┘                   │
│                                │  new articles only              │
│                   ┌────────────▼─────────────┐                   │
│                   │   analyse_text()          │                  │
│                   │                          │                   │
│                   │  ① VADER compound score  │                   │
│                   │  ② +keyword boost (130+) │                   │
│                   │  ③ ×1.2 high-impact amp  │                   │
│                   │  ④ 11-sector classifier  │                   │
│                   └────────────┬─────────────┘                   │
│                                │                                 │
│           ┌────────────────────┴─────────────────┐               │
│           │                                      │               │
│  ┌────────▼────────┐                  ┌──────────▼─────────┐     │
│  │ ZMQ PUSH :28090 │                  │  on_signal(fn)     │     │
│  │  work-queue     │                  │  callback API      │     │
│  └─────────────────┘                  └────────────────────┘     │
└──────────────────────────────────────────────────────────────────┘
```

---

## Sentiment Model

### Three-layer scoring

```
Final score = clip( (vader_score + keyword_boost) × amplifier, −1, +1 )
```

| Layer | Details |
|-------|---------|
| **VADER base** | Compound score in `[−1, +1]` — trained on social media English |
| **Keyword boost** | ±5% per hit, capped at ±0.5 — 130+ NSE/BSE bull/bear terms |
| **High-impact amplifier** | ×1.2 if headline contains `breaking / surge / crash / rally / …` |

### Bullish keywords (sample)
`FII buying` · `RBI rate cut` · `strong earnings` · `GDP growth` · `bull run` · `record high` · `buyback` · `dividend declared` · `order win` · `capacity expansion`

### Bearish keywords (sample)
`NPA rise` · `RBI rate hike` · `FII selling` · `profit warning` · `earnings miss` · `credit downgrade` · `regulatory action` · `market crash` · `inflation surge` · `forex outflow`

### Sector classification (11 NSE sectors)

`Banking` · `IT` · `Pharma` · `Auto` · `Energy` · `Metals` · `FMCG` · `Realty` · `Indices` · `Crypto` · `Telecom`

One article can tag multiple sectors (multi-label).

### Why not BERT?

Fine-tuning BERT requires 10K+ labelled examples and a GPU inference server. VADER + keyword boosters reaches **~80% F1 on NSE news with zero labelled data** and runs in **< 1ms per article** — the correct tradeoff for a side-channel trading signal.

---

## Quickstart

### Install

```bash
pip install feedparser vaderSentiment pyzmq pytz
# or
pip install -r requirements.txt
```

### As a library

```python
from src.sentitrade import SentiPipeline, FeedConfig

def on_signal(s):
    print(f"[{s.label}] {s.score:+.3f} | {s.headline[:70]}")
    print(f"  sectors={s.sectors}  impact={s.impact}")

pipeline = SentiPipeline(
    feeds=[
        FeedConfig("ET Markets",     "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"),
        FeedConfig("Moneycontrol",   "https://www.moneycontrol.com/rss/marketsindia.xml"),
        FeedConfig("Business Std",   "https://www.business-standard.com/rss/markets-106.rss"),
        FeedConfig("Livemint",       "https://www.livemint.com/rss/markets"),
    ],
    poll_interval=60,
)
pipeline.on_signal(on_signal)
pipeline.start()

import time; time.sleep(300)

# Aggregate sentiment over last 20 articles
agg = pipeline.aggregate(window=20)
print(agg)
# {'score': 0.124, 'label': 'BULLISH', 'n': 20, 'top_sectors': ['Banking', 'IT']}
```

### As a standalone process

```bash
python src/sentitrade.py --interval 60 --port 28090
python src/sentitrade.py --feeds feeds.json --port 28090
```

### Subscribe from another process

```python
import zmq, json

ctx = zmq.Context()
sock = ctx.socket(zmq.PULL)
sock.connect("tcp://127.0.0.1:28090")

while True:
    signal = json.loads(sock.recv_string())
    print(signal["label"], signal["score"], signal["sectors"])
```

---

## API Reference

### `SentimentSignal` schema

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
  "ts":               "2026-03-30T10:32:14+05:30",
  "article_id":       "a3f2c91d",
  "bullish_triggers": [],
  "bearish_triggers": ["rate hold", "inflation warning"]
}
```

### `pipeline.aggregate(window=20)` response

```json
{
  "score":       0.085,
  "label":       "NEUTRAL",
  "n":           20,
  "top_sectors": ["IT", "Banking", "Pharma"]
}
```

Recency weighting: last 20% of window receives 30% of weight; older 80% receives 70%.

### `FeedConfig`

```python
FeedConfig(
    name: str,
    url: str,
    weight: float = 1.0,       # signal weight for aggregate()
    max_articles: int = 25,    # max articles per poll
)
```

---

## Custom Feeds

Create `feeds.json`:

```json
[
  {"name": "NSE India",    "url": "https://www.nseindia.com/feed.xml",         "weight": 1.5},
  {"name": "Zerodha Pulse","url": "https://zerodha.com/pulse/feed/",           "weight": 1.0},
  {"name": "SEBI Releases","url": "https://www.sebi.gov.in/sebiweb/other/OtherAction.do?doNews=yes","weight": 2.0}
]
```

```bash
python src/sentitrade.py --feeds feeds.json
```

---

## Performance

| Metric | Value |
|--------|-------|
| Analysis latency per article | **< 1ms** (VADER + keyword scan) |
| Indian market keywords | **130+** bullish + bearish |
| NSE sector classifiers | **11** |
| Dedup cache lookup | **O(1)** — SHA-256, bounded 10K FIFO |
| Simultaneous feeds | **4** (configurable) |
| ZMQ topology | **PUSH/PULL** — each signal processed by exactly one consumer |

**ZMQ PUSH/PULL vs PUB/SUB:** PUSH/PULL distributes signals round-robin — each message goes to exactly one consumer. Use this when consumers are processing work (avoid duplicate analysis). Use PUB/SUB (nexus-price-bus pattern) when every subscriber needs every message.

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Project Context

`sentitrade` is the extracted NLP layer from [`AlgoStack`](https://github.com/Ridhaant/algostack)'s `sentiment_analyzer.py` and `news_dashboard.py`. In production, sentiment signals feed into the trading dashboard in real time alongside NSE equity, MCX commodity, and Binance crypto price feeds.

**Part of the AlgoStack open-source layer:**
- **[nexus-price-bus](https://github.com/Ridhaant/nexus-price-bus)** — multi-source ZMQ market data bus
- **[vectorsweep](https://github.com/Ridhaant/vectorsweep)** — GPU strategy parameter sweep
- **sentitrade** — Indian market NLP sentiment pipeline (this library)

---

## Author

**[Ridhaant Ajoy Thackur](https://github.com/Ridhaant)**
*Data Scientist · NLP / FinTech · LNMIIT Jaipur*

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-0077B5?style=flat-square&logo=linkedin&logoColor=white)](https://linkedin.com/in/ridhaant-thackur-09947a1b0)
[![GitHub](https://img.shields.io/badge/GitHub-@Ridhaant-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/Ridhaant)
[![Email](https://img.shields.io/badge/Email-redantthakur%40gmail.com-D14836?style=flat-square&logo=gmail&logoColor=white)](mailto:redantthakur@gmail.com)

---

## License

MIT © 2026 Ridhaant Ajoy Thackur
