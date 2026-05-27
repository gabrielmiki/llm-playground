# Data Pipeline Documentation

## Overview
The data pipeline handles collection, cleaning, and tokenization of text data for LLM training and experimentation.

## Pipeline Stages

### 1. Collection (`src/collect/`)
Methods for gathering raw data from various sources.

**Sources supported:**
- HTTP APIs via `httpx` (async)
- Web scraping via `beautifulsoup4`
- PDF text extraction via `pypdf`
- Word documents via `python-docx`
- Local files (CSV, JSON, text) via `pandas`

**Design principles:**
- All collectors yield raw text (no processing)
- Rate limiting built-in for API sources
- Error handling for malformed content
- Progress tracking via `tqdm`

### 2. Preprocessing (`src/preprocess/`)
Cleaning and normalization of collected text.

**Operations:**
- Encoding fixes via `ftfy`
- Language detection via `langdetect`
- Text normalization (whitespace, special chars)
- NLP preprocessing via `nltk` (stopwords, tokenization helpers)
- Regex-based cleaning via `regex`

**Design principles:**
- Immutable: original text preserved in `data/raw/`
- All cleaning operations are reversible where possible
- Streaming support for large datasets
- Output goes to `data/processed/`

### 3. Tokenization (`src/preprocess/`)
Converting text to token sequences.

**Tokenizers:**
- `tiktoken` — OpenAI-style BPE (fast, good for GPT models)
- `tokenizers` — HuggingFace fast tokenizers
- `sentencepiece` — Subword tokenization (flexible vocab)

**Design principles:**
- Vocab files saved alongside tokenized data
- Consistent encoding across pipeline
- Support for special tokens (BOS, EOS, PAD, UNK)

## Data Flow
```
data/raw/          →  src/collect/     →  raw text
raw text           →  src/preprocess/  →  cleaned text
cleaned text       →  tokenizers       →  tokenized data
tokenized data     →  data/processed/  →  training-ready
```

## Usage Patterns

### Collection
```python
from src.collect import APICollector, WebScraper, PDFExtractor

# API source
async with APICollector("https://api.example.com") as collector:
    async for text in collector.collect(endpoint="/posts"):
        yield text

# PDF files
extractor = PDFExtractor()
for text in extractor.extract("path/to/docs/"):
    yield text
```

### Preprocessing
```python
from src.preprocess import TextCleaner, LanguageFilter

cleaner = TextCleaner()
for cleaned in cleaner.clean(raw_texts):
    yield cleaned
```

### Tokenization
```python
from src.preprocess.tokenizer import TokenizerFactory

# Fixed-encoding backend (tiktoken, no vocab_size)
tokenizer = TokenizerFactory.create("tiktoken")
tokens = tokenizer.encode("Hello, world!")

# Trainable backend accepts vocab_size
hf_tokenizer = TokenizerFactory.create("tokenizers", vocab_size=16384)
sp_tokenizer = TokenizerFactory.create("sentencepiece", vocab_size=8192)

# Tokenize fused analysis text
fused_text = TokenizerFactory.fused_record_to_text(fused_record)
tokens = tokenizer.encode(fused_text)
```

## Testing
- Unit tests for each collector and cleaner
- Integration tests for pipeline stages
- Fixtures in `tests/fixtures/` for sample data

## MVP End-to-End Test

An orchestration script (`src/pipeline.py`) wires the existing stages into a
single command:

```text
collect → preprocess (clean, validate, language-filter) → fuse → write output → sentiment
```

### Usage

```bash
uv run python -m src.pipeline --ticker AAPL --date 2026-05-22
```

Default ticker is `AAPL`, default date is today.

### Test Results (2026-05-22, AAPL)

| Stage | Result | Detail |
|-------|--------|--------|
| Collection | ✅ | Yahoo (429) → **Alpha Vantage** (OHLCV); **Finnhub** (50 articles) |
| Preprocessing | ✅ | 50/50 passed cleaning, validation, language filtering |
| Fusion | ✅ | 50/50 articles matched target date |
| Output | ✅ | `data/processed/fused/AAPL_2026-05-22.json` |
| Sentiment | ✅ | Score: +0.0075 (neutral), confidence: 0.81 |

### Platform Notes

- **Python**: Pinned to 3.12 via `.python-version` (torch lacks macOS x86_64
  wheels for >=2.4 + Python 3.14). Switch back by deleting `.python-version`.
- **torch**: 2.2.2 installed from `https://download.pytorch.org/whl/cpu` (last
  version with macOS x86_64 support).
- **transformers**: 4.47.1 (compatible with torch 2.2.2).

### Bugs Fixed During Testing

| File | Before | After |
|------|--------|-------|
| `src/collect/market_data.py:175` | `except A, B:` | `except (A, B):` |
| `src/collect/transformers.py:171,179` | `except A, B:` | `except (A, B):` |
| `tests/fixtures/resource_tracker.py:56,78` | `except A, B:` | `except (A, B):` |

### Pre-existing Test Failures

6 tests fail (unrelated to pipeline changes):
- `test_fallback_to_finnhub`, `test_transform_finnhub_valid_response` —
  `transform_finnhub()` assumes dict input but mock provides list.
- `test_old_articles_filtered` (Finnhub + NewsAPI) — test fixture dates are
  relative to `datetime.now()` and don't align with the 365-day filter.
- `test_finnhub_fallback_to_newsapi` — mock raises bare `Exception` instead of
  `NewsDataError`.
- `test_creates_and_closes_client` — `close()` not called in test.
