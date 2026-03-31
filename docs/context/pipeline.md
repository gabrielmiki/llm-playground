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

tokenizer = TokenizerFactory.create("tiktoken", vocab_size=8192)
tokens = tokenizer.encode("Hello, world!")
```

## Testing
- Unit tests for each collector and cleaner
- Integration tests for pipeline stages
- Fixtures in `tests/fixtures/` for sample data
