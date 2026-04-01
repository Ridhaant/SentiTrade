<div align="center">

<img src="https://readme-typing-svg.demolab.com?font=Fira+Code&size=24&duration=2500&pause=800&color=00FF41&center=true&vCenter=true&width=800&lines=SentiTrade;Real-Time+Indian+Market+Sentiment+%7C+Production+NLP;VADER+%2B+130+Domain+Boosters+%7C+11-Sector+Classifier;SHA-256+Dedup+%7C+ZMQ+Signal+Bus+%7C+GenAI-Ready" alt="sentitrade" />

<br/>

![NLP](https://img.shields.io/badge/NLP-VADER%20%2B%20Boosters-00FF41?style=for-the-badge)
![Sectors](https://img.shields.io/badge/Sectors-11%20Classified-00D4FF?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)

<br/>

<img src="https://skillicons.dev/icons?i=python,linux,docker,git&theme=dark" />

<br/><br/>

![VADER](https://img.shields.io/badge/VADER_NLP-3fb950?style=flat-square)
![ZeroMQ](https://img.shields.io/badge/ZeroMQ_PUSH-DF0000?style=flat-square&logo=zeromq&logoColor=white)
![SHA-256](https://img.shields.io/badge/SHA--256_Dedup-000000?style=flat-square)
![feedparser](https://img.shields.io/badge/feedparser_RSS-FF6B35?style=flat-square)
![Anthropic](https://img.shields.io/badge/Claude_Optional-191919?style=flat-square&logo=anthropic&logoColor=white)
![OpenAI](https://img.shields.io/badge/GPT--4o_Optional-412991?style=flat-square&logo=openai&logoColor=white)
![Gemini](https://img.shields.io/badge/Gemini_Optional-4285F4?style=flat-square&logo=google&logoColor=white)

*Sole-authored by **[Ridhaant Ajoy Thackur](https://github.com/Ridhaant)** · Extracted from [AlgoStack](https://github.com/Ridhaant/AlgoStack)*

</div>

---

## ⚡ What Is SentiTrade?

A production-tested NLP sentiment pipeline purpose-built for **Indian financial markets** — ingests 4 simultaneous RSS feeds, applies domain-adapted VADER with **130+ NSE/BSE keyword boosters**, classifies across **11 sectors**, and distributes structured signals over ZMQ PUSH/PULL. Optional GenAI enrichment via Anthropic Claude / OpenAI / Gemini (env-only keys — never hardcoded).

---

## 🏗️ Pipeline Architecture

```mermaid
graph LR
    subgraph "📡 Ingestion"
        RSS["4 Indian Market RSS Feeds<br/>MoneyControl · ET Markets<br/>LiveMint · Business Standard"]
    end
    subgraph "🧠 NLP Pipeline"
        DEDUP["SHA-256 URL Dedup<br/>O(1) · 10K FIFO"]
        VADER["VADER Compound Score"]
        BOOST["130+ Keyword Boosters<br/>±5% per hit · ±0.5 cap<br/>×1.2 high-impact amplifier"]
        SECTOR["11-Sector Classifier<br/>Banking · IT · Pharma · Auto<br/>Energy · Metals · FMCG · Realty<br/>Indices · Crypto · Telecom"]
    end
    subgraph "📊 Output"
        SIGNAL["SentimentSignal<br/>score · label · confidence<br/>sectors · triggers"]
        ZMQ["ZMQ PUSH/PULL<br/>Exactly-once delivery"]
    end
    RSS --> DEDUP --> VADER --> BOOST --> SECTOR --> SIGNAL --> ZMQ

    style DEDUP fill:#0d1117,stroke:#FF6B35,stroke-width:2px,color:#FF6B35
    style BOOST fill:#0d1117,stroke:#00FF41,stroke-width:2px,color:#00FF41
```

### Why SHA-256 Dedup?

Fixed 16-char hex keys prevent URL-based injection attacks. O(1) lookup with predictable memory (bounded 10K FIFO). Avoids regex-based URL parsing vulnerabilities.

### Why Domain-Adaptive Boosters?

Standard VADER is calibrated for social media — Indian financial news uses domain-specific terminology ("FII buying", "NPA", "Nifty breakout"). 130+ keyword boosters bridge this gap with measurable impact: ±5% compound shift per keyword hit, capped at ±0.5 to prevent keyword stuffing.

---

## 🔗 Proven in Production

Extracted from [AlgoStack](https://github.com/Ridhaant/AlgoStack)'s live NLP layer — processing real Indian market news in real-time across 16 concurrent processes.

---

## 📦 Related

[![AlgoStack](https://img.shields.io/badge/AlgoStack-Parent%20Platform-00D4FF?style=for-the-badge)](https://github.com/Ridhaant/AlgoStack)
[![nexus-price-bus](https://img.shields.io/badge/nexus--price--bus-Price%20Bus-DF0000?style=for-the-badge)](https://github.com/Ridhaant/Nexus-Price-Bus)
[![vectorsweep](https://img.shields.io/badge/vectorsweep-GPU%20Sweeps-76B900?style=for-the-badge)](https://github.com/Ridhaant/VectorSweep)
[![SentinelVault](https://img.shields.io/badge/SentinelVault-Security-FF6B35?style=for-the-badge)](https://github.com/Ridhaant/SentinelVault)

---

<div align="center">

© 2026 Ridhaant Ajoy Thackur · MIT License

</div>
