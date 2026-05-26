# Financial LLM Analysis - Implementation Tickets

Generated from PRD: Financial Markets LLM Analysis System

---

## Ticket 6: Sentiment Analysis with Pretrained Model

**type**: story  
**layer**: model  
**complexity**: medium  
**dependencies**: [Ticket 4]

**title**: Implement financial sentiment analysis using FinBERT

**description**:
Use `ProsusAI/finbert` for financial sentiment classification. Accept `FusedRecord` (from Ticket 4 fusion pipeline), tokenize internally with FinBERT's own `BertTokenizer` (WordPiece), and return per-article and aggregated sentiment scores. The pipeline does NOT consume Ticket 5's tokenized output — FinBERT requires its own tokenizer incompatible with the Ticket 5 BPE backends.

**acceptance_criteria**:

- AC-01: Given `FinBertSentiment(model_name="ProsusAI/finbert")`, When constructed, Then model loads in eval mode with gradient computation disabled and no exception is raised
- AC-02: Given a FusedRecord with 1 positive news article, When `analyze(record)` is called, Then returns `SentimentResult` where `sentiment_score` is a float in [-1.0, 1.0], `confidence` is a float in [0.0, 1.0], `sentiment_score == P(positive) - P(negative)` from the model's softmax output, and `len(breakdown) == 1`
- AC-03: Given a FusedRecord with 3 mixed-sentiment news articles, When `analyze(record)` is called, Then aggregated `sentiment_score` is the confidence-weighted average of per-article scores, aggregated `confidence` is the mean of per-article confidences, `len(breakdown) == 3`, and each `breakdown[i]` contains `article_title`, `score`, `confidence`, and `label`
- AC-04: Given a FusedRecord with empty `news_articles=[]`, When `analyze(record)` is called, Then returns `SentimentResult(sentiment_score=0.0, confidence=0.0, breakdown=[])`
- AC-05: Given offline network (FinBERT not cached locally), When `FinBertSentiment(model_name="ProsusAI/finbert")` is constructed, Then raises `ModelLoadError` with message containing "Failed to load model from HuggingFace"
- AC-06: Given an article with text exceeding model's `max_length` (default 512 tokens), When `analyze(record)` is called, Then text is silently truncated to `max_length` tokens and analysis proceeds without error
- AC-07: Given a FusedRecord where one article has empty title and whitespace-only summary, When `analyze(record)` is called, Then that article is skipped in `breakdown` and does not contribute to aggregation
- AC-08: Given GPU is unavailable (`torch.cuda.is_available()` returns `False`), When `FinBertSentiment(model_name="ProsusAI/finbert")` is constructed, Then `self.device == "cpu"`
- AC-09: Given a FusedRecord with `market_data` only and `news_articles=[]`, When `analyze(record)` is called, Then returns neutral result identical to AC-04
- AC-10: Given `None` passed as `fused_record`, When `analyze(None)` is called, Then raises `TypeError` with message "fused_record must be a FusedRecord"
- AC-11: Given a FusedRecord where a news article dict is missing the "title" key, When `analyze(record)` is called, Then the article is processed using only the summary field (no `KeyError` raised)

**api_spec** (internal):
```python
# Dataclasses
@dataclass
class ArticleSentiment:
    article_title: str
    score: float           # [-1.0, 1.0], P(pos) - P(neg)
    confidence: float      # [0.0, 1.0], max(P(pos), P(neg), P(neu))
    label: str             # "positive" | "negative" | "neutral"

@dataclass
class SentimentResult:
    sentiment_score: float # aggregated score, confidence-weighted
    confidence: float      # mean of per-article confidences
    breakdown: list[ArticleSentiment]

# Constructor
FinBertSentiment(
    model_name: str = "ProsusAI/finbert",
    device: str | None = None,        # default: cuda if available else cpu
    max_length: int = 512,
    batch_size: int = 32,
)

# Main method
FinBertSentiment.analyze(record: FusedRecord) -> SentimentResult
```

**implementation_files**:
- `src/model/__init__.py` — Package declaration
- `src/model/exceptions.py` — `ModelLoadError` exception
- `src/model/pretrained/__init__.py` — Subpackage declaration
- `src/model/pretrained/sentiment.py` — `FinBertSentiment`, `SentimentResult`, `ArticleSentiment`

**test_files**:
- `tests/test_sentiment.py` — Sentiment analysis tests
- `tests/fixtures/sentiment_data.py` — FusedRecord fixtures for sentiment testing

**modified_files**:
- `tests/conftest.py` — Add `"tests.fixtures.sentiment_data"` to `pytest_plugins`

**notes**:
- FinBERT uses `BertTokenizer` (WordPiece, vocab ~30522) internally — NOT the Ticket 5 tokenizer backends
- Score formula: `sentiment_score = P(positive) - P(negative)` from 3-class softmax {pos, neg, neu}
- Aggregation: weighted by confidence: `Σ(score_i × confidence_i) / Σ(confidence_i)`
- Model label mapping (ProsusAI/finbert): `id2label = {0: "positive", 1: "negative", 2: "neutral"}`
