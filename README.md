# LLM Playground — Financial Sentiment & Signal Pipeline

An end-to-end financial analysis pipeline that collects real-time market data and news articles for US stocks, runs sentiment analysis via FinBERT (a financial-domain LLM), generates trading signals (buy/sell/hold), and produces multi-format end-of-day reports.

## Pipeline Overview

```
                         ┌──────────────────┐
                         │  Market Data API  │
                         │  (Yahoo Finance → │
                         │   Alpha Vantage → │
                         │   Finnhub)        │
                         └────────┬─────────┘
                                  │ OHLCV data
                                  ▼
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│   News API       │    │   Validator       │    │   TextCleaner    │
│  (Finnhub →      │───▶│  (prices, volume, │───▶│  (ftfy, lang     │
│   NewsAPI)       │    │   timestamps)     │    │   detection)     │
└────────┬─────────┘    └────────┬─────────┘    └────────┬─────────┘
         │                       │                       │
         └───────────┬───────────┘                       │
                     │                                   │
                     ▼                                   │
             ┌────────────────┐                          │
             │  DataFusion    │◀─────────────────────────┘
             │  Engine        │
             │  (ticker+date) │
             └────────┬───────┘
                      │ FusedRecord
                      ▼
             ┌──────────────────┐
             │  FinBERT         │
             │  Sentiment       │
             │  (ProsusAI/      │
             │   finbert)       │
             └────────┬─────────┘
                      │ sentiment score
                      ▼
             ┌──────────────────┐
             │  TradingSignal   │
             │  Generator       │
             │  (buy/sell/hold) │
             └────────┬─────────┘
                      │ signals
                      ▼
             ┌──────────────────┐
             │  ReportGenerator │
             │  (.txt/.json/    │
             │   .html)         │
             └──────────────────┘
```

## Features

- **Multi-provider fallback** — Market data tries Yahoo Finance → Alpha Vantage → Finnhub; news tries Finnhub → NewsAPI
- **Graceful degradation** — When live data fails, falls back to cached data up to 5 trading days old
- **Financial sentiment analysis** — Uses [ProsusAI/finbert](https://huggingface.co/ProsusAI/finbert), a BERT model fine-tuned on financial text
- **Trading signal generation** — Combines sentiment scores with market returns using a weighted formula, with confidence penalties for conflicting signals
- **Multi-format reports** — Generates text (terminal-friendly), JSON (machine-readable), and HTML (styled tables) output
- **Async throughout** — All data collection is async via `httpx` with retry logic and token-bucket rate limiting
- **Pluggable tokenizers** — `tiktoken`, HuggingFace `tokenizers`, and `sentencepiece` backends available (not yet wired into the pipeline)

## Quick Start

### Prerequisites

- Python 3.12
- [uv](https://docs.astral.sh/uv/) package manager

### Setup

```bash
# Clone and enter the project
git clone <repo-url> && cd llm-playground

# Create environment and install all extras
uv sync --extra all

# Copy and fill in API keys (optional — Yahoo Finance works without one)
cp .env.example .env
```

### Running the Pipeline

```bash
# Single ticker
uv run python -m src.pipeline --ticker AAPL --date 2026-05-22

# All 10 tickers + generate report
uv run python -m src.pipeline --all --report --date 2026-05-22

# Report only (from cached fused data)
uv run python -m src.generate --date 2026-05-22
```

Flags:
| Flag | Default | Description |
|------|---------|-------------|
| `--ticker` | `AAPL` | Single ticker to process |
| `--date` | today | Target date (YYYY-MM-DD) |
| `--all` | — | Run for all 10 configured tickers |
| `--report` | — | Generate report after pipeline (or standalone) |

### Code Quality

```bash
uv run ruff check .        # Lint
uv run ruff format .       # Format
uv run mypy src/           # Type check
uv run pytest              # Run tests
```

## Report Examples

Reports are generated in three formats and written to `data/processed/reports/{uuid}.{txt,json,html}`.

### Text Format (`data/processed/reports/0a79e442.txt`)

```
Report: 2026-05-22
Report ID: 0a79e442
============================================================

Ticker          Signal  Confidence   SentimentMarket Return Rationale
---------------------------------------------------------------------
AAPL              hold        0.45     +0.0075       +0.88% Sentiment positive (0.01) with confidence 0.81...
MSFT              hold        0.20     +0.1625       -0.23% Sentiment positive (0.16) with confidence 0.80...
GOOGL             hold        0.23     +0.1429       -1.13% Sentiment positive (0.14) with confidence 0.81...
AMZN              hold        0.22     +0.0479       -0.87% Sentiment positive (0.05) with confidence 0.79...
META              hold        0.21     -0.0221       +0.39% Sentiment negative (-0.02) with confidence 0.81...
TSLA              hold        0.44     +0.0135       +0.79% Sentiment positive (0.01) with confidence 0.80...
NVDA              hold        0.27     +0.2107       -2.52% Sentiment positive (0.21) with confidence 0.81...
JPM               hold        0.44     +0.1045       +0.56% Sentiment positive (0.10) with confidence 0.82...
V                 hold        0.43     -0.2624       -0.50% Sentiment negative (-0.26) with confidence 0.81...
JNJ               hold        0.43     +0.2005       +0.58% Sentiment positive (0.20) with confidence 0.80...

============================================================
```

### JSON Format (`data/processed/reports/0a79e442.json`)

```json
{
  "report_id": "0a79e442",
  "date": "2026-05-22",
  "signals": [
    {
      "ticker": "AAPL",
      "signal": "hold",
      "confidence": 0.45,
      "sentiment_score": 0.0075,
      "market_return": 0.0088,
      "rationale": "Sentiment positive (0.01) with confidence 0.81. Market return: +0.88%. Combined score: 0.05. Signal: hold."
    },
    {
      "ticker": "MSFT",
      "signal": "hold",
      "confidence": 0.20,
      "sentiment_score": 0.1625,
      "market_return": -0.0023,
      "rationale": "Sentiment positive (0.16) with confidence 0.80. Market return: -0.23%. Combined score: 0.07. Sentiment and market disagree — confidence halved. Signal: hold."
    }
  ]
}
```

### HTML Format (`data/processed/reports/0a79e442.html`)

The HTML report renders as a styled table with color-coded signals (green for buy, red for sell, gray for hold) and yellow warning banners for degraded data.

<table>
  <tr><th>Ticker</th><th>Signal</th><th>Confidence</th><th>Sentiment</th><th>Market Return</th><th>Rationale</th></tr>
  <tr><td>AAPL</td><td style="color:#888">hold</td><td>0.45</td><td>+0.0075</td><td>+0.88%</td><td>Sentiment positive (0.01) with confidence 0.81...</td></tr>
  <tr><td>MSFT</td><td style="color:#888">hold</td><td>0.20</td><td>+0.1625</td><td>-0.23%</td><td>Sentiment positive (0.16)...Sentiment and market disagree — confidence halved...</td></tr>
  <tr><td>NVDA</td><td style="color:#888">hold</td><td>0.27</td><td>+0.2107</td><td>-2.52%</td><td>Sentiment positive (0.21)...Sentiment and market disagree — confidence halved...</td></tr>
</table>

### Signal Logic

The `TradingSignalGenerator` computes a combined score:

```
combined_score = 0.5 × sentiment_score + 0.5 × market_signal
```

| Condition | Signal | Confidence |
|-----------|--------|------------|
| combined_score > 0.3 | `buy` | Full |
| combined_score < -0.3 | `sell` | Full |
| sentiment and market disagree | `hold` | Halved |
| otherwise | `hold` | Proportional |

## Project Structure

```
src/
├── pipeline.py              # Main orchestrator (end-to-end pipeline)
├── collect/                 # Data collection from external APIs
│   ├── client.py            #   Async HTTP client with retry + rate limiting
│   ├── rate_limiter.py      #   Token-bucket rate limiter
│   ├── market_data.py       #   OHLCV data collector (Yahoo → Alpha Vantage → Finnhub)
│   ├── news_collector.py    #   News article collector (Finnhub → NewsAPI)
│   ├── transformers.py      #   Market data response normalizers
│   ├── news_transformers.py #   News response normalizers
│   ├── date_utils.py        #   Weekend/holiday adjustment
│   └── exceptions.py        #   Collection-specific exceptions
├── preprocess/              # Cleaning, validation, fusion
│   ├── cleaner.py           #   Text encoding fix (ftfy), whitespace, garbled detection
│   ├── language_filter.py   #   English language detection (langdetect)
│   ├── text_preprocessor.py #   Stopword removal, sentence tokenization (NLTK)
│   ├── validator.py         #   Market data & news field validation
│   ├── fusion.py            #   Fuses market data + news into FusedRecord
│   ├── output_writer.py     #   Writes fused records to disk
│   ├── tokenizer.py         #   Abstract tokenizer + 3 implementations
│   ├── tokenizer_configs.py #   Tokenizer configuration
│   └── exceptions.py        #   Preprocessing-specific exceptions
├── model/
│   └── pretrained/
│       ├── sentiment.py     #   FinBERT sentiment analysis (ProsusAI/finbert)
│       └── signals.py       #   Trading signal generation (buy/sell/hold)
└── generate/
    ├── config.py            #   Ticker list configuration
    ├── models.py            #   ReportInput/ReportResult dataclasses
    ├── reporter.py          #   .txt/.json/.html report generator
    ├── orchestrate.py       #   Full report generation orchestrator
    └── degradation.py       #   Graceful degradation (historical fallback)

data/
├── raw/                     # Immutable raw data (never modified)
└── processed/
    ├── fused/               # Cached fused records per ticker per date
    └── reports/             # Generated reports (.txt, .json, .html)

tests/                       # 19 test files, 10 fixture files
docs/context/                # Detailed documentation
```

## Tickers

The pipeline operates on these 10 major US stocks:

| Ticker | Company |
|--------|---------|
| AAPL | Apple Inc. |
| MSFT | Microsoft Corporation |
| GOOGL | Alphabet Inc. |
| AMZN | Amazon.com Inc. |
| META | Meta Platforms Inc. |
| TSLA | Tesla Inc. |
| NVDA | NVIDIA Corporation |
| JPM | JPMorgan Chase & Co. |
| V | Visa Inc. |
| JNJ | Johnson & Johnson |

## API Keys (Optional)

The pipeline works without any API keys (Yahoo Finance is tried first and requires no key). For better reliability, set these in `.env`:

| Variable | Provider | Source |
|----------|----------|--------|
| `ALPHAVANTAGE_API_KEY` | Alpha Vantage | [alphavantage.co](https://www.alphavantage.co/support/#api-key) |
| `FINNHUB_API_KEY` | Finnhub | [finnhub.io](https://finnhub.io/register) |
| `NEWSAPI_KEY` | NewsAPI | [newsapi.org](https://newsapi.org/register) |

## Tech Stack

| Category | Libraries |
|----------|-----------|
| **HTTP & Async** | `httpx` |
| **ML/NLP** | `torch`, `transformers` (FinBERT), `accelerate` |
| **Text Processing** | `ftfy`, `regex`, `langdetect`, `nltk` |
| **Tokenization** | `tiktoken`, `tokenizers`, `sentencepiece` |
| **Visualization** | `wandb`, `tensorboard` |
| **Testing** | `pytest`, `pytest-asyncio`, `pytest-mock` |
| **Code Quality** | `ruff`, `mypy` |

## Graceful Degradation

When data collection fails (all API providers exhausted), the system automatically searches for cached fused records up to 5 trading days prior. The report includes a warning banner indicating which tickers used stale data, allowing consumers to discount those signals.

## Architecture Decisions

- **Provider fallback chain**: Each data source has multiple providers tried in sequence on failure
- **Conditional imports**: Heavy dependencies (`torch`, `transformers`) are imported lazily — the pipeline skips sentiment gracefully if they're unavailable
- **Async-first**: All I/O is async with connection pooling for efficient multi-ticker runs
- **Dataclass-heavy**: All data transfer objects use `@dataclass` for simplicity and type safety
