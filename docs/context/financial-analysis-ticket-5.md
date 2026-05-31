# Financial LLM Analysis - Implementation Tickets

Generated from PRD: Financial Markets LLM Analysis System

---

## Ticket 5: Tokenization Pipeline

**type**: story
**layer**: preprocess
**complexity**: medium
**dependencies**: [Ticket 4]

**title**: Implement tokenization for fused analysis text

**description**:
Add tokenization step to preprocessing pipeline, converting fused analysis text into token sequences for downstream model consumption. Supports three backends with different training characteristics: `tiktoken` (fixed-encoding OpenAI BPE), `tokenizers` (trainable HuggingFace fast BPE), and `sentencepiece` (trainable unigram). This fills the tokenization gap documented in `pipeline.md` Section 3.

**Fused analysis text contract**:
Tokenization operates on a fused text string constructed from a `FusedRecord` (Ticket 4). The numeric fields (`open`, `high`, `low`, `close`, `volume`, `adjusted_close`) are not tokenized — only the textual content from news articles is. The fused text for a `FusedRecord` is defined as:

```python
def fused_record_to_text(record: FusedRecord) -> str:
    """Build tokenizer input from a FusedRecord (only text fields)."""
    parts: list[str] = []
    for article in record.news_articles:
        title = article.get("title", "")
        summary = article.get("summary", "")
        text = f"{title} {summary}".strip()
        if text:
            parts.append(text)
    return "\n".join(parts)
```

If `news_articles` is empty, the fused text is an empty string `""`. This function lives in the tokenizer module (not on the FusedRecord dataclass itself) to keep the data model clean.

**implementation**:
- `src/preprocess/tokenizer.py` — `TokenizerFactory` with `.create(backend, **kwargs)` and concrete `BaseTokenizer` subclasses per backend
- `src/preprocess/exceptions.py` — Add `TokenizerError(PreprocessingError)` to existing hierarchy
- `src/preprocess/__init__.py` — Export new symbols
- `src/preprocess/tokenizer_configs.py` — Per-backend configuration dataclasses
- `tests/test_tokenizer.py` — 11 tests (parametrized across backends)
- `tests/fixtures/tokenizer_data.py` — Sample texts for encode/decode roundtrip testing
- `tests/conftest.py` — Register new fixture plugin

**dependencies_note**: Requires `tiktoken`, `tokenizers`, and `sentencepiece` packages (added to `pyproject.toml` under `[project.optional-dependencies] preprocess` group).

**description_details**:

### 1. Tokenizer Factory (`tokenizer.py`)

Factory pattern to instantiate the correct tokenizer backend. Backend type determines whether `vocab_size` is configurable:

| Backend | Type | Accepts `vocab_size`? | Default encoding |
|---------|------|----------------------|------------------|
| `"tiktoken"` | Fixed encoding | **No** (ignored if passed) | `cl100k_base` |
| `"tokenizers"` | Trainable BPE | Yes (default 8192) | N/A |
| `"sentencepiece"` | Trainable unigram | Yes (default 8192) | N/A |

```python
@dataclass
class TokenizerConfig:
    backend: str                    # "tiktoken" | "tokenizers" | "sentencepiece"
    vocab_size: int = 8192          # Only used by trainable backends
    special_tokens: dict[str, int] | None = None  # e.g., {"<|endoftext|>": 100257}

class TokenizerFactory:
    @staticmethod
    def create(backend: str, vocab_size: int = 8192, **kwargs) -> "BaseTokenizer":
        ...

    @staticmethod
    def fused_record_to_text(record: FusedRecord) -> str:
        """Extract tokenization-ready text from a fused record."""
```

### 2. Backend Class Hierarchy

All backends implement the same public interface via `BaseTokenizer`. Each backend has a concrete subclass:

```python
class BaseTokenizer(ABC):
    @abstractmethod
    def encode(self, text: str) -> list[int]:
        """Convert text to token IDs."""

    @abstractmethod
    def decode(self, tokens: list[int]) -> str:
        """Convert token IDs back to text."""

    @abstractmethod
    def vocab_size(self) -> int:
        """Return the actual vocabulary size of this tokenizer instance."""

class TikTokenTokenizer(BaseTokenizer):
    """Fixed-encoding tiktoken backend (vocab_size param ignored)."""

class HFTokenizerTokenizer(BaseTokenizer):
    """Trainable HuggingFace tokenizers backend (accepts vocab_size)."""

class SentencePieceTokenizer(BaseTokenizer):
    """Trainable SentencePiece backend (accepts vocab_size)."""
```

### 3. Backend Notes

- **tiktoken**: Uses `tiktoken.get_encoding("cl100k_base")` for GPT-4-compatible tokenization. Fastest option. Does NOT accept `vocab_size` — `vocab_size()` returns `encoding.n_vocab` (100277 in tiktoken≥0.13.0; this value is version-dependent). Passing `vocab_size` is silently ignored.
- **tiktoken special tokens**: `tiktoken.encode()` raises `ValueError` when input contains special tokens unless `allowed_special` is set. The `TikTokenTokenizer.encode()` implementation must pass `allowed_special="all"` or enumerate known special tokens (e.g., `allowed_special={"<|endoftext|>"}`) to avoid errors on special token sequences.
- **tokenizers**: Uses HuggingFace `tokenizers.Tokenizer.from_pretrained()` with BPE model. Trainable on custom vocab. Accepts `vocab_size` for initialization. Supports special tokens via `tokenizers.AddedToken`.
- **sentencepiece**: Uses `sentencepiece.SentencePieceProcessor`. Trainable from raw text. Accepts `vocab_size` for training. Supports special tokens via `control_symbols()` or `user_defined_symbols()`.

### 4. Integration with Pipeline

Tokenization is **not** part of `run_preprocessing()` — it's a separate step applied to fused text before model inference. The factory pattern allows downstream tickets (Sentiment Analysis, Signal Generation) to choose the appropriate backend.

### 5. Trainable Backend Lifecycle

`tiktoken` (fixed-encoding) requires no training — `TokenizerFactory.create("tiktoken")` returns a ready-to-use instance.

For trainable backends (`tokenizers`, `sentencepiece`), the lifecycle requires explicit training before encoding:

```python
# Create (not ready for encode yet)
tokenizer = TokenizerFactory.create("tokenizers", vocab_size=512)

# Train on sample texts
tokenizer.train([
    "Apple Inc. reported record quarterly earnings.",
    "The Federal Reserve maintained interest rates.",
    "Markets rallied on positive economic data.",
])

# Now encode is available
tokens = tokenizer.encode("Hello world")
```

The `BaseTokenizer` interface gains:
```python
class BaseTokenizer(ABC):
    @abstractmethod
    def encode(self, text: str) -> list[int]: ...

    @abstractmethod
    def decode(self, tokens: list[int]) -> str: ...

    @abstractmethod
    def vocab_size(self) -> int: ...

    def train(self, texts: list[str]) -> None:
        """Train the tokenizer on sample texts.
        No-op for tiktoken (fixed encoding — no training needed).
        Required before encode() for tokenizers and sentencepiece.
        """
```

**Test helper for parametrized tests**:
```python
BACKENDS = ["tiktoken", "tokenizers", "sentencepiece"]

@pytest.fixture(params=BACKENDS)
def tokenizer(request):
    t = TokenizerFactory.create(request.param)
    if request.param != "tiktoken":
        t.train(["Sample training text for initialization."])
    return t
```

**Usage**:
```python
from src.preprocess.tokenizer import TokenizerFactory

# Build text from fused record
fused_text = TokenizerFactory.fused_record_to_text(fused_record)

# Tokenize with tiktoken (fixed encoding, fast)
tokenizer = TokenizerFactory.create("tiktoken")
tokens = tokenizer.encode(fused_text)

# Tokenize with trainable backend for custom vocab
hf_tokenizer = TokenizerFactory.create("tokenizers", vocab_size=16384)

# Roundtrip
decoded = tokenizer.decode(tokens)  # equals fused_text for ASCII
```

**Output format**: Tokenized data is stored as a dictionary with keys:
```python
{
    "ticker": str,            # From FusedRecord
    "date": str,              # From FusedRecord
    "backend": str,           # "tiktoken" | "tokenizers" | "sentencepiece"
    "token_ids": list[int],   # Encoded token sequence
    "vocab_size": int,        # Actual vocab size of the tokenizer used
    "n_tokens": int,          # len(token_ids)
}
```

This can be serialized to JSON alongside the fused JSON files, or saved as `.pt` tensor files for PyTorch model consumption.

**acceptance_criteria**:

All behavioral ACs (AC-01 through AC-06) are parametrized across all three backends using `@pytest.mark.parametrize("backend", ["tiktoken", "tokenizers", "sentencepiece"])`. Each test creates a fresh tokenizer via `TokenizerFactory.create(backend)`.

- **AC-01** (encode returns integers): Given text "Hello world", When `TokenizerFactory.create(backend).encode()` is called, Then returns a `list[int]` with length > 0 for all three backends
- **AC-02** (ASCII roundtrip): Given text "Hello world", When encoded then decoded, Then the output equals the original text (roundtrip fidelity for ASCII text) for all three backends
- **AC-03** (vocab_size returns positive int): Given `TokenizerFactory.create("tiktoken")`, When `.vocab_size()` is called, Then returns 100277 (the `n_vocab` of `cl100k_base` in tiktoken≥0.13.0). Given `TokenizerFactory.create("tokenizers", vocab_size=8192)` or `create("sentencepiece", vocab_size=8192)` (after `.train()`), When `.vocab_size()` is called, Then returns 8192
- **AC-04** (unknown backend error): Given unknown backend name "invalid_backend", When `TokenizerFactory.create()` is called, Then raises `TokenizerError` with message "Unknown tokenizer backend: invalid_backend" (not bare `ValueError`)
- **AC-05** (empty string encode): Given empty string `""`, When `TokenizerFactory.create(backend).encode()` is called, Then returns empty list `[]` for all three backends
- **AC-06** (empty list decode): Given empty token list `[]`, When `BaseTokenizer.decode()` is called, Then returns empty string `""` for all three backends
- **AC-07** (special token roundtrip, per-backend): Given text containing `<|endoftext|>` and `TokenizerFactory.create("tiktoken")`, When encoded then decoded, Then the output equals the original text and `<|endoftext|>` is preserved as a single token ID 100257. Given `TokenizerFactory.create("tokenizers", special_tokens={"<|pad|>": 0, "<|bos|>": 1})` (after `.train()`), When text containing `<|pad|>` and `<|bos|>` is encoded then decoded, Then each special token is preserved as a single token ID matching its assigned value. Given `TokenizerFactory.create("sentencepiece", special_tokens={"<|pad|>": 3, "<|bos|>": 4})` (after `.train()`), When text containing the special tokens is encoded then decoded, Then each special token is preserved as a single token ID matching its assigned value. Note: sentencepiece reserves IDs 0=UNK, 1=BOS, 2=EOS as built-in immutable tokens, so user-defined special tokens must start at ID 3+
- **AC-08** (backend class verification): Given `TokenizerFactory.create("tiktoken")`, When `isinstance(tokenizer, TikTokenTokenizer)` is checked, Then returns True. Same pattern for `HFTokenizerTokenizer` and `SentencePieceTokenizer` via concrete subclasses (not raw backend-proxy instances)
- **AC-09** (tokenizers backend functional): Given `TokenizerFactory.create("tokenizers", vocab_size=512)` (after `.train()` with sample texts), When `.encode("Hello world")` is called, Then returns `list[int]` with length > 0 and all token IDs < 512
- **AC-10** (invalid vocab_size for trainable backends): Given `TokenizerFactory.create("tokenizers", vocab_size=-1)` or `create("sentencepiece", vocab_size=0)`, When called, Then raises `TokenizerError` with message containing "vocab_size must be positive"
- **AC-11** (fused_record_to_text conversion): Given a `FusedRecord` with 2 news articles (titles and summaries), When `TokenizerFactory.fused_record_to_text()` is called, Then returns a string containing both titles and summaries joined by newlines. Given a `FusedRecord` with empty `news_articles`, When called, Then returns `""`

**api_spec** (internal):
```
TokenizerFactory.create(backend: str, vocab_size: int = 8192, **kwargs) -> BaseTokenizer
  Input: backend name, vocab_size (ignored for tiktoken), optional kwargs per backend
  Output: BaseTokenizer instance
  Error: TokenizerError for unknown backend or invalid params

TokenizerFactory.fused_record_to_text(record: FusedRecord) -> str
  Input: FusedRecord from Ticket 4 fusion stage
  Output: concatenated text from news article titles and summaries

BaseTokenizer.encode(text: str) -> list[int]
  Input: fused analysis text string
  Output: list of token IDs

BaseTokenizer.decode(tokens: list[int]) -> str
  Input: list of token IDs
  Output: reconstructed text string

BaseTokenizer.vocab_size() -> int
  Output: actual vocabulary size (fixed for tiktoken, configured for trainable)
```

**exception_additions** (to `src/preprocess/exceptions.py`):
```python
class TokenizerError(PreprocessingError):
    """Raised when tokenizer initialization or operation fails."""
    pass
```

**container for tokenizer_data.py**:
```python
# Sample texts matching the FusedRecord contract
SAMPLE_FUSED_TEXT = "Apple Reports Record Earnings Apple Inc. announced strong Q4 results with revenue exceeding expectations."
SAMPLE_FUSED_TEXT_MULTI = """Apple Reports Record Earnings Apple Inc. announced strong Q4 results.
Markets Rally on Fed Decision The Federal Reserve maintained interest rates."""
SAMPLE_SPECIAL_TOKENS = "<|endoftext|>Hello<|endoftext|>"
SAMPLE_EMPTY = ""
SAMPLE_TICKER = "AAPL"
SAMPLE_DATE = "2024-01-15"
```
