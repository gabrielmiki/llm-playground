# Financial LLM Analysis - Implementation Tickets

Generated from PRD: Financial Markets LLM Analysis System

---

## Ticket 4: Data Quality & Fusion

**type**: story  
**layer**: preprocess  
**complexity**: medium  
**dependencies**: [Ticket 2, Ticket 3]  
**status**: ✅ COMPLETE

**title**: Build preprocessing pipeline for data quality and fusion

**description**:  
Implement text cleaning for financial news articles, language detection/filtering, market data validation, and fusion of both data sources into unified analysis-ready records. Builds on the MarketData (Ticket 2) and NewsArticle (Ticket 3) dataclasses.

**implementation**:
- `src/preprocess/__init__.py` — Package exports (exposes all public classes)
- `src/preprocess/exceptions.py` — `PreprocessingError`, `LanguageFilterError`, `FusionError` hierarchy
- `src/preprocess/cleaner.py` — `TextCleaner` (ftfy encoding fixes, regex normalization, whitespace)
- `src/preprocess/language_filter.py` — `LanguageFilter` (langdetect-based English filtering)
- `src/preprocess/text_preprocessor.py` — `StopwordRemover` (nltk stopwords), `SentenceTokenizer` (nltk sentence/word tokenization)
- `src/preprocess/validator.py` — `MarketDataValidator`, `NewsValidator` (field-level checks)
- `src/preprocess/fusion.py` — `DataFusionEngine` (correlate market data + news by date), generator/batch methods
- `src/preprocess/output_writer.py` — `FusedRecordWriter` (persist fused records to `data/processed/`)
- `tests/conftest.py` — Register `"tests.fixtures.preprocess_data"` in `pytest_plugins`
- `tests/test_cleaner.py` — 10 tests
- `tests/test_text_preprocessor.py` — 6 tests (stopword removal, sentence tokenization)
- `tests/test_language_filter.py` — 6 tests
- `tests/test_validator.py` — 12 tests
- `tests/test_fusion.py` — 8 tests
- `tests/test_output_writer.py` — 4 tests
- `tests/fixtures/preprocess_data.py` — 12 fixtures (clean/dirty text, mixed language, valid/invalid market data, valid/invalid news, texts for stopword/nltk)

**description_details**:

### 1. Text Cleaning (`cleaner.py`)

Clean financial news article text before analysis. Uses the `regex` third-party library (Unicode-aware, supports `\p{L}` property escapes) for all pattern matching. Operations in order:

1. **Encoding fix** — `ftfy.fix_text()` to repair mojibake, Latin-1 vs UTF-8 mismatches
2. **Whitespace normalization** — Collapse multiple spaces/newlines, strip leading/trailing whitespace (via `regex.sub(r"\s+", " ")`)
3. **Special character handling** — Remove/replace control characters, zero-width spaces, non-printable chars (via `regex.sub(r"\p{C}", "")`)
4. **Garbled text detection** — Flag text with excessive non-alphabetic ratio (>50% non-alpha chars after cleaning, counting via `regex.sub(r"\p{L}", "", text)`)

Cleaning is **always applied** (no skip). Garbled text is flagged but not removed — the LanguageFilter stage decides exclusion.

```python
@dataclass
class CleaningResult:
    cleaned_text: str
    original_text: str
    was_fixed: bool              # True if any fix was applied
    encoding_fixed: bool
    whitespace_fixed: bool
    special_chars_removed: int
    is_garbled: bool             # True if >50% non-alpha chars after cleaning
```

### 2. Language Detection & Filtering (`language_filter.py`)

Filter non-English news articles before sentiment analysis.

**Algorithm:**
1. Run `langdetect.detect_langs(text)` on cleaned article text
2. If `langdetect.lang_detect_exception.Error` (text too short), treat as `unknown` and emit WARNING
3. Accept article if: primary language is `"en"` AND confidence >= `0.90`
4. Non-English or low-confidence articles are excluded and logged at INFO level

**Edge cases:**
- Empty text after cleaning → excluded (logged WARNING)
- Text under 10 characters → `LanguageDetectionError` caught, excluded (logged WARNING)
- Mixed language articles → evaluated on primary detected language only
- Ticker mentions/symbols are **not** a signal of English — pure language detection

```python
@dataclass
class LanguageFilterResult:
    article_index: int              # Index in original list
    detected_languages: list[tuple[str, float]]  # [(lang, confidence), ...]
    is_english: bool
    confidence: float
    excluded: bool
    reason: str | None              # e.g., "low_confidence", "not_english", "too_short"
```

### 3. Data Validation (`validator.py`)

Validate market data and news articles before fusion.

**MarketData validation rules:**
| Field | Rule |
|-------|------|
| `open` | > 0, not NaN, not None |
| `high` | > 0, >= open, >= close |
| `low` | > 0, <= open, <= close |
| `close` | > 0, not NaN, not None |
| `volume` | >= 0, int |
| `timestamp` | Valid ISO8601 date string, <= today |
| `adjusted_close` | > 0 or None |

**NewsArticle validation rules:**
| Field | Rule |
|-------|------|
| `title` | Non-empty string, length >= 5 chars |
| `source` | Non-empty string |
| `published_at` | Valid ISO8601 datetime string |
| `url` | Non-empty string, valid URL format (starts with http/https) |
| `summary` | Non-empty string (may be truncated source content) |

All validation failures produce a `ValidationWarning` and the record is **excluded** from fusion. Invalid fields are logged at WARNING level with field name and value snippet.

```python
@dataclass
class ValidationWarning:
    category: str        # e.g., "invalid_price", "missing_field", "date_out_of_range"
    field: str
    message: str
    value: str | None    # Truncated value for context

@dataclass
class ValidationResult:
    is_valid: bool
    warnings: list[ValidationWarning]

# Exceptions (in src/preprocess/exceptions.py)
class PreprocessingError(Exception):                          # Base
class LanguageFilterError(PreprocessingError):                 # Language detection failure
class FusionError(PreprocessingError):                         # Fusion correlation failure
```

### 4. Data Fusion (`fusion.py`)

Correlate validated market data with filtered news for the same ticker + date.

**Input:** `MarketData` for a ticker, `list[dict]` of NewsArticles for same ticker (already cleaned, filtered, validated)

**Fusion logic:**
1. Group news articles by `published_at` date (same calendar date as market data)
2. Attach articles as a list to the market data record
3. If no articles for that date, produce record with empty list (not a warning)
4. Non-matching articles (different dates) are dropped silently (logged at DEBUG level)
5. If market data is missing but news exists, fusion produces a partial record with `market_data=None` and a `ValidationWarning` with category "missing_market_data"

**Streaming/batch support:**
- `DataFusionEngine.fuse_many(records: Iterable[tuple[str, str, MarketData | None, list[dict]]])` → `Generator[FusedRecord]` for batch processing
- Accepts any iterable of (ticker, date, market_data, news_articles) tuples
- Yields `FusedRecord` one at a time to support large datasets without loading all into memory

```python
@dataclass
class FusedRecord:
    ticker: str
    date: str                            # ISO8601 date
    market_data: MarketData | None       # None if unavailable
    news_articles: list[dict]            # Already cleaned + filtered + validated
    warnings: list[ValidationWarning]    # All warnings from validation + fusion

@dataclass
class FusionResult:
    records: list[FusedRecord]
    fusion_warnings: list[ValidationWarning]  # Cross-record warnings (e.g., missing data)
```

### 5. NLP Preprocessing (`text_preprocessor.py`)

Apply NLTK-based NLP operations to cleaned article text before sentiment analysis.

**Operations in order:**

1. **Stopword removal** — Remove English stopwords via `nltk.corpus.stopwords.words("english")`
   - Case-insensitive matching
   - Punctuation-tokenized: split on non-alpha boundaries before matching
   - Output preserves original case of non-stopword tokens, rejoined with space

2. **Sentence tokenization** — Split article into sentences via `nltk.tokenize.sent_tokenize`
   - Return as list of strings
   - Empty/malformed text returns empty list (not an error)
   - Primarily for downstream analysis (not consumed by fusion — available as utility)

```python
@dataclass
class StopwordRemovalResult:
    original_text: str
    cleaned_text: str         # After stopword removal
    removed_stopwords: list[str]  # List of removed words (lowercased)
    stopword_count: int

@dataclass
class SentenceTokenizeResult:
    original_text: str
    sentences: list[str]      # Empty list if text too short or empty
    sentence_count: int

class StopwordRemover:
    def remove(self, text: str, language: str = "english") -> StopwordRemovalResult:
        # Load nltk stopwords for language
        # Tokenize by non-alpha boundaries
        # Filter out stopwords (case-insensitive)
        # Return result with removed_stopwords list

class SentenceTokenizer:
    def tokenize(self, text: str) -> SentenceTokenizeResult:
        # Use nltk.tokenize.sent_tokenize
        # Return empty list for text < 20 chars
        # Handle edge case: text with no sentence-ending punctuation
```

### 6. Output Writer (`output_writer.py`)

Persist fused analysis records to `data/processed/` in JSON lines format.

**File naming:** `data/processed/fused/{ticker}_{date}.json`

**Format per line:** Single JSON object with FusedRecord fields

```python
@dataclass
class FusedRecordWriter:
    output_dir: str = "data/processed/fused"

    def write_record(self, record: FusedRecord) -> str:
        # Serialize FusedRecord to JSON
        # Write to {output_dir}/{ticker}_{date}.json
        # Create output_dir if not exists
        # Return file path

    def write_many(self, records: Iterable[FusedRecord]) -> list[str]:
        # Batch write, returns list of file paths
```

**Design note:** This writer handles the output persistence requirement from the pipeline spec. Cleaning operations are not reversed after writing — reversibility is documented as a future enhancement.

**acceptance_criteria**:

**Cleaner (AC-01 to AC-05):**
- Given text with mojibake sequence `"â€"` (should be em-dash U+2014) and `"â€™"` (should be right single quote U+2019), When `TextCleaner.clean()` is called, Then `cleaned_text` contains `"—"` (U+2014) and `"'"` (U+2019), and `encoding_fixed` is True
- Given text with excessive whitespace (3+ spaces between words and trailing newlines), When `TextCleaner.clean()` is called, Then `cleaned_text` has single-space separators and no leading/trailing whitespace
- Given text with >50% non-alphabetic characters (e.g., `"!!! 123 $$$ %% 456"`), When `TextCleaner.clean()` is called, Then `is_garbled` is True
- Given text with zero-width spaces (U+200B) and control characters (U+0000-U+001F), When `TextCleaner.clean()` is called, Then `special_chars_removed` > 0 and those characters are absent from `cleaned_text`
- Given clean text with no issues, When `TextCleaner.clean()` is called, Then `was_fixed` is False and `cleaned_text == original_text`

**Language Filter (AC-06 to AC-09):**
- Given English text, When `LanguageFilter.filter()` is called with `langdetect.detect_langs` mocked to return `[("en", 0.95)]`, Then `is_english` is True and `excluded` is False
- Given Portuguese text, When `LanguageFilter.filter()` is called with `langdetect.detect_langs` mocked to return `[("pt", 0.95)]`, Then `is_english` is False and `excluded` is True with reason `"not_english"`
- Given text that after `TextCleaner.clean()` results in fewer than 10 characters, When `LanguageFilter.filter()` is called, Then `excluded` is True with reason `"too_short"` and WARNING is logged
- Given empty text `""`, When `LanguageFilter.filter()` is called, Then `excluded` is True with reason `"too_short"`

**Market Data Validator (AC-10 to AC-17):**
- Given `MarketData` with `open=0.0`, When `MarketDataValidator.validate()` is called, Then returns `ValidationResult(is_valid=False)` with `ValidationWarning` category `"invalid_price"`
- Given `MarketData` with `high=100.0, low=90.0, close=95.0` (all valid), When validated, Then `is_valid` is True with empty warnings list
- Given `MarketData` with `high=90.0, low=100.0` (high < low inverted), When validated, Then `is_valid` is False with `ValidationWarning` category `"invalid_price_range"`
- Given `MarketData` with `volume=-500`, When validated, Then `is_valid` is False with `ValidationWarning` category `"invalid_volume"`
- Given `MarketData` with `adjusted_close=-1.0`, When validated, Then `is_valid` is False with `ValidationWarning` category `"invalid_adjusted_close"`
- Given `MarketData` with `adjusted_close=None`, When validated, Then `is_valid` is True (None is allowed for adjusted_close)
- Given `MarketData` with `adjusted_close=0.0`, When validated, Then `is_valid` is False with `ValidationWarning` category `"invalid_adjusted_close"` (must be > 0)
- Given `MarketData` with `timestamp="2099-01-01"` (future date), When validated, Then `is_valid` is False with `ValidationWarning` category `"future_timestamp"`

**News Validator (AC-18 to AC-22):**
- Given NewsArticle with empty title `""`, When `NewsValidator.validate()` is called, Then `is_valid` is False with `ValidationWarning` category `"missing_field"`
- Given NewsArticle with title `"AB"` (shorter than 5 chars), When validated, Then `is_valid` is False with `ValidationWarning` category `"title_too_short"`
- Given NewsArticle with all valid fields, When validated, Then `is_valid` is True
- Given NewsArticle with URL `"not-a-url"` (not http/https), When validated, Then `is_valid` is False with `ValidationWarning` category `"invalid_url"`
- Given NewsArticle with `published_at="not-a-date"`, When validated, Then `is_valid` is False with `ValidationWarning` category `"invalid_date"`

**Fusion (AC-23 to AC-27):**
- Given MarketData and 2 news articles for same ticker + date, When `DataFusionEngine.fuse()` is called, Then `FusedRecord` has matching ticker, date, market_data, and 2 news_articles
- Given 4 news articles with 3 matching and 1 different date than market data, When fused, Then only the 3 matching articles are included and non-matching are dropped silently
- Given only news articles (no market data) for a ticker, When fused, Then record has `market_data=None` and a `ValidationWarning` with category `"missing_market_data"`
- Given MarketData passes but NewsArticle fails validation, When full pipeline runs, Then fused record has market_data, empty news_articles, and `ValidationWarning` about excluded article
- Given empty articles list and valid market data, When fused, Then record has market_data and empty news_articles (not an error)

**NLP Preprocessing (AC-28 to AC-31):**
- Given text `"The quick brown fox jumps over the lazy dog"`, When `StopwordRemover.remove()` is called, Then `removed_stopwords` contains `["the", "over", "the"]` and `stopword_count` is 3
- Given text with no stopwords `"quick brown fox jumps lazy dog"`, When `StopwordRemover.remove()` is called, Then `stopword_count` is 0 and `cleaned_text` equals `original_text`
- Given text `"Hello world. This is a test."`, When `SentenceTokenizer.tokenize()` is called, Then `sentences` is `["Hello world.", "This is a test."]` and `sentence_count` is 2
- Given text `"Hi"` (shorter than 20 characters), When `SentenceTokenizer.tokenize()` is called, Then `sentence_count` is 0 and `sentences` is empty list

**Output Writer (AC-32 to AC-33):**
- Given a valid `FusedRecord`, When `FusedRecordWriter.write_record()` is called, Then a JSON file is created at `data/processed/fused/{ticker}_{date}.json` with matching content
- Given 3 `FusedRecord` objects, When `FusedRecordWriter.write_many()` is called, Then 3 JSON files are created and returned paths match expected pattern

**Streaming (AC-34):**
- Given 5 (ticker, date, market_data, news_articles) tuples, When `DataFusionEngine.fuse_many()` is iterated over, Then it yields 5 `FusedRecord` objects without loading all into memory (verified via custom iterable that tracks `__next__` calls)

**api_spec** (internal):
```
Imports (from src.collect):
  from src.collect.market_data import MarketData
  from src.collect.exceptions import MarketDataError
  # NewsArticle is typed as dict[str, str] with fields:
  #   { title: str, source: str, published_at: str, url: str, summary: str }

Tier 1 — Individual Cleaners/Validators:

TextCleaner:
  .clean(text: str) -> CleaningResult
    Input: raw text string
    Output: { cleaned_text, original_text, was_fixed, encoding_fixed, 
              whitespace_fixed, special_chars_removed, is_garbled }
  .clean_many(texts: Iterable[str]) -> Generator[CleaningResult]
    Input: iterable of raw text strings
    Output: yields CleaningResult for each input
    Note: lazy evaluation, supports streaming

StopwordRemover:
  .remove(text: str, language: str = "english") -> StopwordRemovalResult
    Input: cleaned text string, language code
    Output: { original_text, cleaned_text, removed_stopwords: list[str],
              stopword_count: int }

SentenceTokenizer:
  .tokenize(text: str) -> SentenceTokenizeResult
    Input: cleaned text string
    Output: { original_text, sentences: list[str], sentence_count: int }

LanguageFilter:
  .filter(article_index: int, text: str) -> LanguageFilterResult
    Input: article index, cleaned text
    Output: { article_index, detected_languages, is_english, confidence, excluded, reason }
  .filter_many(items: Iterable[tuple[int, str]]) -> Generator[LanguageFilterResult]
    Input: iterable of (article_index, cleaned_text) tuples
    Output: yields LanguageFilterResult for each input

MarketDataValidator:
  .validate(data: MarketData) -> ValidationResult
    Input: MarketData dataclass
    Output: { is_valid, warnings: [{ category, field, message, value }] }

NewsValidator:
  .validate(article: dict) -> ValidationResult
    Input: NewsArticle dict (title, source, published_at, url, summary)
    Output: { is_valid, warnings: [{ category, field, message, value }] }

Tier 2 — Fusion:

DataFusionEngine:
  .fuse(ticker, date, market_data, news_articles) -> FusedRecord
    Input: ticker: str, date: str, market_data: MarketData | None, 
           news_articles: list[dict] (already cleaned+filtered+validated)
    Output: { ticker, date, market_data, news_articles, warnings }
  .fuse_many(records: Iterable[tuple[str, str, MarketData | None, list[dict]]])
      -> Generator[FusedRecord]
    Input: iterable of (ticker, date, market_data, news_articles) tuples
    Output: yields FusedRecord for each input

Tier 3 — Output Writer:

FusedRecordWriter:
  .write_record(record: FusedRecord) -> str
    Input: FusedRecord
    Output: file path string (creates data/processed/fused/{ticker}_{date}.json)
  .write_many(records: Iterable[FusedRecord]) -> list[str]
    Input: iterable of FusedRecord
    Output: list of file path strings

Tier 4 — Orchestrated Pipeline:

run_preprocessing(ticker, date, market_data, raw_news_articles) -> FusedRecord
  Input: ticker, date, market_data (from Ticket 2), raw_news_articles (from Ticket 3)
  Output: FusedRecord (all cleaning+filtering+validation+fused+persisted in one call)
  
  Internal flow:
    1. Clean each news article via TextCleaner.clean()
    2. Remove stopwords via StopwordRemover.remove() on each cleaned text
    3. Filter non-English via LanguageFilter.filter()
    4. Validate cleaned+filtered+stopped articles via NewsValidator.validate()
    5. Validate market_data via MarketDataValidator.validate()
    6. Fuse via DataFusionEngine.fuse()
    7. Persist via FusedRecordWriter.write_record()
    8. Return FusedRecord with all warnings accumulated

run_preprocessing_batch(records: Iterable[tuple]) -> Generator[FusedRecord]
  Input: iterable of (ticker, date, market_data, raw_news_articles) tuples
  Output: yields FusedRecord for each input using generator pipeline
  Internal: chains clean_many -> filter_many -> fuse_many -> write_many
```
